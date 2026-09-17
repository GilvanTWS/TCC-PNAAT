"""
Classificador visual das peças do TRIA.

O processamento acontece em duas etapas independentes:
  1. localizar a placa de MDF pela cor e geometria;
  2. corrigir a perspectiva da placa e classificar apenas sua marca central.

Esse fluxo evita que a esteira, as barras da estrutura ou qualquer contorno do
fundo sejam aceitos como QUADRADO.
"""

from pathlib import Path

import cv2
import numpy as np

from image_io import ler_imagem, salvar_imagem

from config import (
    AREA_MARCA_NORMALIZADA_MIN,
    AREA_PECA_FRAME_MAX,
    AREA_PECA_FRAME_MIN,
    ASPECTO_PECA_MAX,
    HSV_MDF_MAX,
    HSV_MDF_MIN,
    LIMIAR_AREA_MINIMA,
    MARGEM_MARCA,
    PREENCHIMENTO_PECA_MIN,
    TAMANHO_MAX_PROCESSAMENTO,
    TAMANHO_PECA_NORMALIZADA,
)


def redimensionar_para_padrao(image):
    """Reduz imagens grandes sem alterar sua proporção."""
    altura, largura = image.shape[:2]
    maior_lado = max(altura, largura)
    if maior_lado <= TAMANHO_MAX_PROCESSAMENTO:
        return image

    escala = TAMANHO_MAX_PROCESSAMENTO / maior_lado
    return cv2.resize(
        image,
        (max(1, round(largura * escala)), max(1, round(altura * escala))),
        interpolation=cv2.INTER_AREA,
    )


def preprocess_image(image, limiar_binarizacao=0):
    """Mantém a API antiga para diagnóstico de contornos."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if limiar_binarizacao == 0:
        _, thresh = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
    else:
        _, thresh = cv2.threshold(
            gray, limiar_binarizacao, 255, cv2.THRESH_BINARY_INV
        )
    return thresh


def detect_contours(thresh):
    """Retorna contornos externos maiores que o limiar legado."""
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    return [c for c in contours if cv2.contourArea(c) > LIMIAR_AREA_MINIMA]


def count_vertices(contour, epsilon_ratio=0.03):
    """Aproxima um contorno e conta seus vértices."""
    perimetro = cv2.arcLength(contour, True)
    if perimetro <= 0:
        return 0
    return len(cv2.approxPolyDP(contour, epsilon_ratio * perimetro, True))


def _ordenar_cantos(pontos):
    """Ordena cantos: superior esquerdo/direito, inferior direito/esquerdo.

    A mesma ordem na origem e no destino evita espelhar a placa na retificação.
    """
    pontos = np.asarray(pontos, dtype=np.float32)
    soma = pontos.sum(axis=1)
    diferenca = np.diff(pontos, axis=1).ravel()
    return np.array(
        [
            pontos[np.argmin(soma)],
            pontos[np.argmin(diferenca)],
            pontos[np.argmax(soma)],
            pontos[np.argmax(diferenca)],
        ],
        dtype=np.float32,
    )


def _mascara_mdf(image):
    """Cria uma máscara para a faixa de cor marrom/bege do MDF."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mascara = cv2.inRange(
        hsv,
        np.array(HSV_MDF_MIN, dtype=np.uint8),
        np.array(HSV_MDF_MAX, dtype=np.uint8),
    )

    # Fechamento proporcional ao quadro une a superfície do MDF; o kernel
    # ímpar preserva um centro. A abertura seguinte remove pontos isolados.
    lado_kernel = max(3, int(round(min(image.shape[:2]) * 0.012)) | 1)
    kernel = np.ones((lado_kernel, lado_kernel), np.uint8)
    mascara = cv2.morphologyEx(
        mascara, cv2.MORPH_CLOSE, kernel, iterations=2
    )
    return cv2.morphologyEx(
        mascara, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)
    )


def localizar_peca_mdf(image):
    """
    Localiza uma placa de MDF totalmente visível no quadro.

    Retorna um dicionário com o contorno, os quatro cantos no tamanho original
    e a placa BGR retificada no tamanho de config.py (400x400 por padrão).
    A máscara mantém a escala reduzida; box/contour usam pixels da entrada.
    Retorna None quando não há candidata. Pressupõe uma peça por vez na ROI.
    """
    if image is None or image.size == 0:
        return None

    altura_original, largura_original = image.shape[:2]
    reduzida = redimensionar_para_padrao(image)
    altura, largura = reduzida.shape[:2]
    escala_x = largura_original / largura
    escala_y = altura_original / altura

    mascara = _mascara_mdf(reduzida)
    contours, _ = cv2.findContours(
        mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    candidatos = []
    area_frame = float(altura * largura)
    margem_borda = 3

    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, w, h = cv2.boundingRect(contour)
        rect = cv2.minAreaRect(contour)
        rect_w, rect_h = rect[1]

        if min(rect_w, rect_h) <= 0:
            continue

        # Só classifica quando a peça entrou completamente na ROI. Isso também
        # elimina parede/estrutura que encoste nas bordas do quadro.
        toca_borda = (
            x < margem_borda
            or y < margem_borda
            or x + w > largura - margem_borda
            or y + h > altura - margem_borda
        )
        if toca_borda:
            continue

        area_retangulo = rect_w * rect_h
        aspecto = max(rect_w, rect_h) / min(rect_w, rect_h)
        preenchimento = area / max(1.0, area_retangulo)
        fracao_frame = area / area_frame

        if not (AREA_PECA_FRAME_MIN <= fracao_frame <= AREA_PECA_FRAME_MAX):
            continue
        if aspecto > ASPECTO_PECA_MAX:
            continue
        if preenchimento < PREENCHIMENTO_PECA_MIN:
            continue

        candidatos.append((area, contour, rect))

    if not candidatos:
        return None

    # Seleciona a maior candidata; isto não separa duas placas sobrepostas.
    area, contour, rect = max(candidatos, key=lambda item: item[0])
    cantos_reduzidos = _ordenar_cantos(cv2.boxPoints(rect))

    lado = TAMANHO_PECA_NORMALIZADA
    destino = np.float32(
        [[0, 0], [lado - 1, 0], [lado - 1, lado - 1], [0, lado - 1]]
    )
    matriz = cv2.getPerspectiveTransform(cantos_reduzidos, destino)
    normalizada = cv2.warpPerspective(reduzida, matriz, (lado, lado))

    cantos_originais = cantos_reduzidos.copy()
    cantos_originais[:, 0] *= escala_x
    cantos_originais[:, 1] *= escala_y

    contour_original = contour.astype(np.float32)
    contour_original[:, 0, 0] *= escala_x
    contour_original[:, 0, 1] *= escala_y

    return {
        "area": round(area * escala_x * escala_y, 1),
        "box": np.rint(cantos_originais).astype(np.int32),
        "contour": np.rint(contour_original).astype(np.int32),
        "normalizada": normalizada,
        "mascara": mascara,
    }


def _segmentar_marca(peca_normalizada):
    """Realça a gravação escura e devolve seu maior contorno plausível."""
    lado = peca_normalizada.shape[0]
    margem = round(lado * MARGEM_MARCA)
    centro = peca_normalizada[margem:lado - margem, margem:lado - margem]
    if centro.size == 0:
        return None, None, margem

    gray = cv2.cvtColor(centro, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    _, binaria = cv2.threshold(
        blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    binaria = cv2.morphologyEx(
        binaria, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
    )

    contours, _ = cv2.findContours(
        binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    area_minima = AREA_MARCA_NORMALIZADA_MIN * gray.size
    plausiveis = [c for c in contours if cv2.contourArea(c) >= area_minima]
    if not plausiveis:
        return None, binaria, margem
    return max(plausiveis, key=cv2.contourArea), binaria, margem


def _classificar_marca(contour):
    """Aplica regras geométricas; 0.95 é um escore fixo, não probabilidade.

    A precisão real deve ser medida contra gabaritos, nunca inferida do escore.
    Solidez = área / área do casco convexo: concavidades reduzem esse valor.
    """
    area = cv2.contourArea(contour)
    perimetro = cv2.arcLength(contour, True)
    if area <= 0 or perimetro <= 0:
        return None

    vertices = count_vertices(contour, 0.03)
    casco = cv2.convexHull(contour)
    solidez = area / max(1.0, cv2.contourArea(casco))

    # O contorno do X apresenta concavidades e mais vértices que os polígonos.
    if vertices >= 6 and solidez < 0.75:
        return "QUADRADO_COM_X", 0.95, vertices, solidez
    if vertices == 3 and solidez >= 0.80:
        return "TRIÂNGULO", 0.95, vertices, solidez
    if vertices == 4 and solidez >= 0.80:
        return "QUADRADO", 0.95, vertices, solidez
    return None


def classificar_sequencia_normalizada(pecas_normalizadas):
    """
    Classifica uma peça usando todos os quadros em que ela cruzou a ROI.

    Vídeo comprimido e desfoque de movimento podem apagar temporariamente um
    lado da marca. Em vez de decidir pelo primeiro quadro legível, esta função
    usa a mediana da região central para reconhecer o X e escolhe, entre todos
    os quadros, o contorno fechado de melhor qualidade para quadrado/triângulo.
    """
    if not pecas_normalizadas:
        return {
            "erro": "Nenhuma amostra da peça foi recebida",
            "status": "sem_amostras",
        }

    preenchimentos_centro = []
    melhor_contorno = None
    melhor_pontuacao = -1.0
    melhor_mascara = None
    melhor_normalizada = None

    for normalizada in pecas_normalizadas:
        if normalizada is None or normalizada.size == 0:
            continue

        lado = normalizada.shape[0]
        margem = round(lado * MARGEM_MARCA)
        centro = normalizada[margem:lado - margem, margem:lado - margem]
        if centro.size == 0:
            continue

        gray = cv2.cvtColor(centro, cv2.COLOR_BGR2GRAY)
        # O limiar adaptativo recupera sulcos fracos mesmo quando a iluminação
        # muda ao longo da esteira. O fechamento une pequenos trechos apagados
        # pela compressão/desfoque sem preencher o interior das figuras.
        binaria = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            2,
        )

        altura, largura = binaria.shape
        y0, y1 = round(altura * 0.42), round(altura * 0.58)
        x0, x1 = round(largura * 0.42), round(largura * 0.58)
        miolo = binaria[y0:y1, x0:x1]
        preenchimentos_centro.append(float(np.count_nonzero(miolo)) / miolo.size)

        fechada = cv2.morphologyEx(
            binaria,
            cv2.MORPH_CLOSE,
            np.ones((15, 15), np.uint8),
        )
        contours, _ = cv2.findContours(
            fechada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        area_imagem = float(gray.size)
        lado_marca = min(gray.shape[:2])

        for contour in contours:
            area = cv2.contourArea(contour)
            _, _, w, h = cv2.boundingRect(contour)
            if area < 0.005 * area_imagem:
                continue
            if w < 0.15 * lado_marca or h < 0.15 * lado_marca:
                continue

            area_casco = cv2.contourArea(cv2.convexHull(contour))
            solidez = area / max(1.0, area_casco)
            pontuacao = area * solidez
            if pontuacao > melhor_pontuacao:
                melhor_pontuacao = pontuacao
                melhor_contorno = contour
                melhor_mascara = fechada
                melhor_normalizada = normalizada

    if not preenchimentos_centro:
        return {
            "erro": "As amostras da peça não possuem imagem válida",
            "status": "sem_amostras",
        }

    preenchimento_centro = float(np.median(preenchimentos_centro))

    def resultado_x():
        return {
            "classe": "QUADRADO_COM_X",
            "confianca": 0.95,
            "status": "aceito",
            "preenchimento_centro": round(preenchimento_centro, 3),
            "peca_normalizada": (
                melhor_normalizada
                if melhor_normalizada is not None
                else pecas_normalizadas[-1]
            ),
            "mascara_marca": melhor_mascara,
        }

    # Nos símbolos de referência, o cruzamento do X ocupa o centro. Os limiares
    # são heurísticos: uma mancha/sombra central também pode acionar esta regra.
    if preenchimento_centro > 0.20:
        return resultado_x()

    if melhor_contorno is None:
        if preenchimento_centro > 0.05:
            return resultado_x()
        return {
            "erro": "Peça detectada, mas a marca central não foi encontrada",
            "status": "marca_nao_detectada",
        }

    perimetro = cv2.arcLength(melhor_contorno, True)
    vertices = len(cv2.approxPolyDP(melhor_contorno, 0.035 * perimetro, True))
    area = cv2.contourArea(melhor_contorno)
    area_casco = cv2.contourArea(cv2.convexHull(melhor_contorno))
    solidez = area / max(1.0, area_casco)

    # Dê prioridade a polígonos convexos bem formados. Isso evita chamar de X
    # um triângulo cuja ponta passa pelo pequeno recorte central.
    if vertices == 3 and solidez >= 0.75:
        classe = "TRIÂNGULO"
    elif vertices == 4 and solidez >= 0.75:
        classe = "QUADRADO"
    elif preenchimento_centro > 0.05 or (vertices >= 5 and solidez < 0.75):
        return resultado_x()
    else:
        return {
            "erro": "Marca encontrada, mas o formato não é reconhecido",
            "status": "marca_desconhecida",
            "vertices": vertices,
            "peca_normalizada": melhor_normalizada,
            "mascara_marca": melhor_mascara,
        }

    return {
        "classe": classe,
        "confianca": 0.95,
        "vertices": vertices,
        "solidez": round(solidez, 3),
        "preenchimento_centro": round(preenchimento_centro, 3),
        "status": "aceito",
        "peca_normalizada": melhor_normalizada,
        "mascara_marca": melhor_mascara,
    }


def classify_image(image):
    """Classifica um frame BGR; retorna classe ou erro, sempre com status.

    Arrays de diagnóstico não são serializáveis em JSON. O main seleciona os
    campos escalares para o evento MQTT; a sequência de vídeo tem fluxo próprio.
    """
    peca = localizar_peca_mdf(image)
    if peca is None:
        return {"erro": "Nenhuma peça de MDF detectada", "status": "sem_peca"}

    marca, mascara_marca, margem = _segmentar_marca(peca["normalizada"])
    if marca is None:
        return {
            "erro": "Peça detectada, mas a marca central não foi encontrada",
            "status": "marca_nao_detectada",
            "box": peca["box"],
            "peca_normalizada": peca["normalizada"],
        }

    classificacao = _classificar_marca(marca)
    if classificacao is None:
        return {
            "erro": "Marca encontrada, mas o formato não é reconhecido",
            "status": "marca_desconhecida",
            "box": peca["box"],
            "peca_normalizada": peca["normalizada"],
            "mascara_marca": mascara_marca,
        }

    classe, confianca, vertices, solidez = classificacao
    marca_global = marca.copy()
    marca_global[:, 0, 0] += margem
    marca_global[:, 0, 1] += margem

    return {
        "classe": classe,
        "confianca": confianca,
        "vertices": vertices,
        "solidez": round(solidez, 3),
        "area": peca["area"],
        "status": "aceito",
        "box": peca["box"],
        "marca_contour": marca_global,
        "peca_normalizada": peca["normalizada"],
        "mascara_marca": mascara_marca,
    }


def classify_single(image_path, limiar_binarizacao=0, epsilon_ratio=0.03):
    """Carrega uma imagem e a classifica; argumentos antigos são compatíveis."""
    del limiar_binarizacao, epsilon_ratio
    image = ler_imagem(image_path)
    if image is None:
        return {"erro": f"Não foi possível carregar: {image_path}", "status": "erro"}
    return classify_image(image)


def classify_with_confidence(image_path):
    """API pública mantida para os chamadores existentes."""
    return classify_single(image_path)


def detect_mark_x(image, contour=None):
    """Compatibilidade: informa se a imagem contém a marca X."""
    del contour
    resultado = classify_image(image)
    tem_x = resultado.get("classe") == "QUADRADO_COM_X"
    return tem_x, resultado.get("confianca", 0.0) if tem_x else 0.0


def get_destino(classe):
    """Retorna o destino físico da classe; desconhecidos vão para descarte."""
    return {
        "QUADRADO": "A",
        "TRIÂNGULO": "B",
        "QUADRADO_COM_X": "C",
    }.get(classe, "C")


def annotate_image(image_path, output_path=None):
    """Desenha a placa detectada e o resultado sobre a imagem original."""
    image = ler_imagem(image_path)
    if image is None:
        return None

    resultado = classify_image(image)
    box = resultado.get("box")
    if box is not None:
        cor = (0, 0, 255) if resultado.get("classe") == "QUADRADO_COM_X" else (0, 255, 0)
        cv2.polylines(image, [box], True, cor, 3)
    else:
        cor = (0, 165, 255)

    if "erro" in resultado:
        label = resultado["erro"]
    else:
        label = (
            f"{resultado['classe']} | Destino:{get_destino(resultado['classe'])} | "
            f"C:{resultado['confianca']:.2f}"
        )
    cv2.putText(
        image, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, cor, 2
    )

    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        salvar_imagem(output, image)
    return image
