"""
TRIA - Triagem Visual Integrada de Componentes
Classificador por marca interna com detecção de defeito (X).

As peças de ensaio são quadrados de MDF e a diferença está na marca
desenhada ao centro: QUADRADO, TRIÂNGULO ou X (defeito).

Estratégia: varredura de todos os contornos (RETR_TREE) com prioridade:
  1. X: contorno com muitos vértices que confirma linhas diagonais (~45°/135°)
     via Hough → QUADRADO_COM_X (descarte);
  2. TRIÂNGULO: contorno estável de 3 vértices, em formato triangular
     plausível → TRIÂNGULO;
  3. Padrão seguro: QUADRADO (marca quadrada ou sem marca visível → Saída A).
"""

import cv2
import numpy as np

from config import (
    LIMIAR_AREA_MARCA,
    LIMIAR_AREA_MINIMA,
    LIMIAR_CONFIANCA,
    PARAMETROS_REANALISE,
    TAMANHO_CLASSIFICACAO,
)


def redimensionar_para_padrao(image):
    """Redimensiona fotos grandes para o padrão de classificação (640x480)."""
    h, w = image.shape[:2]
    if max(h, w) <= max(TAMANHO_CLASSIFICACAO):
        return image
    return cv2.resize(image, TAMANHO_CLASSIFICACAO)


def preprocess_image(image, limiar_binarizacao=0):
    """Pré-processamento: escala de cinza + binarização (Otsu quando limiar=0)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if limiar_binarizacao == 0:
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    else:
        _, thresh = cv2.threshold(gray, limiar_binarizacao, 255, cv2.THRESH_BINARY_INV)
    return thresh


def detect_contours(thresh):
    """Detecta contornos externos e retorna apenas os válidos."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) > LIMIAR_AREA_MINIMA]


def count_vertices(contour, epsilon_ratio=0.04):
    """Conta vértices usando approxPolyDP."""
    perimeter = cv2.arcLength(contour, True)
    epsilon = epsilon_ratio * perimeter
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return len(approx)


def _angulo_interno(p0, p1, p2):
    """Ângulo (graus) no vértice p1, formado por p0-p1-p2."""
    v1 = p0 - p1
    v2 = p2 - p1
    den = np.linalg.norm(v1) * np.linalg.norm(v2)
    if den == 0:
        return 180.0
    cos = np.dot(v1, v2) / den
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))


def _eh_triangulo_plausivel(contour):
    """
    Valida se o contorno se aproxima de um triângulo desenhado:
    3 vértices estáveis em duas escalas de epsilon, ângulos não muito agudos
    e lados não extremamente alongados.
    """
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False

    for eps_ratio in (0.04, 0.06):
        if count_vertices(contour, eps_ratio) != 3:
            return False

    pts = cv2.approxPolyDP(contour, 0.04 * perimeter, True).reshape(3, 2).astype(np.float64)

    a1 = _angulo_interno(pts[0], pts[1], pts[2])
    a2 = _angulo_interno(pts[1], pts[2], pts[0])
    a3 = _angulo_interno(pts[2], pts[0], pts[1])

    if min(a1, a2, a3) < 25.0:
        return False

    d01 = np.linalg.norm(pts[0] - pts[1])
    d12 = np.linalg.norm(pts[1] - pts[2])
    d20 = np.linalg.norm(pts[2] - pts[0])
    lados = sorted([d01, d12, d20])

    if lados[2] == 0:
        return False
    if lados[0] / lados[2] < 0.15:
        return False

    return True


def _afinar_zhang_suen(regiao):
    """Afinamento de Zhang-Suen: reduz uma região binária ao seu esqueleto."""
    img = np.pad((regiao > 0).astype(np.uint8), 1, mode="constant")
    prev = np.zeros_like(img)
    while not np.array_equal(img, prev):
        prev = img.copy()
        passos = [True]
        while passos:
            passos = []
            # Sub-iteração 1
            for r, c in np.argwhere(img == 1):
                p2, p3, p4, p5, p6, p7, p8, p9 = [
                    img[r - 1, c], img[r - 1, c + 1], img[r, c + 1],
                    img[r + 1, c + 1], img[r + 1, c], img[r + 1, c - 1],
                    img[r, c - 1], img[r - 1, c - 1],
                ]
                b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                if not (2 <= b <= 6):
                    continue
                a = sum(1 for x, y in
                        [(p2, p3), (p3, p4), (p4, p5), (p5, p6),
                         (p6, p7), (p7, p8), (p8, p9), (p9, p2)] if x == 0 and y == 1)
                if a == 1 and p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0:
                    passos.append((r, c))
            for r, c in passos:
                img[r, c] = 0
            passos = []
            # Sub-iteração 2
            for r, c in np.argwhere(img == 1):
                p2, p3, p4, p5, p6, p7, p8, p9 = [
                    img[r - 1, c], img[r - 1, c + 1], img[r, c + 1],
                    img[r + 1, c + 1], img[r + 1, c], img[r + 1, c - 1],
                    img[r, c - 1], img[r - 1, c - 1],
                ]
                b = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9
                if not (2 <= b <= 6):
                    continue
                a = sum(1 for x, y in
                        [(p2, p3), (p3, p4), (p4, p5), (p5, p6),
                         (p6, p7), (p7, p8), (p8, p9), (p9, p2)] if x == 0 and y == 1)
                if a == 1 and p2 * p4 * p8 == 0 and p2 * p6 * p8 == 0:
                    passos.append((r, c))
            for r, c in passos:
                img[r, c] = 0
    return img[1:-1, 1:-1]


def _pontas_do_esqueleto(image, contour):
    """
    Conta pontas (vértices de grau 1) no esqueleto da região do contorno.
    Usa a MÁSCARA preenchida do próprio contorno (ignora ruído de fundo),
    o que separa um X (4 pontas) de triângulo (2-3) e de anéis (0).
    """
    x, y, w, h = cv2.boundingRect(contour)
    if w <= 1 or h <= 1:
        return 0

    mascara = np.zeros((h + 2, w + 2), np.uint8)
    cv2.drawContours(mascara, [contour], -1, 1, -1, offset=(-x + 1, -y + 1))

    if mascara.sum() == 0:
        return 0

    mascara[0, :] = 0
    mascara[-1, :] = 0
    mascara[:, 0] = 0
    mascara[:, -1] = 0

    esqueleto = _afinar_zhang_suen(mascara)

    VIZ = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    pontas = 0
    for r, c in np.argwhere(esqueleto == 1):
        vizinhos = sum(
            1 for dr, dc in VIZ
            if 0 <= r + dr < esqueleto.shape[0] and 0 <= c + dc < esqueleto.shape[1]
            and esqueleto[r + dr, c + dc] == 1
        )
        if vizinhos == 1:
            pontas += 1
    return pontas


def detect_mark_x(image, contour):
    """
    Detecta marca X contrastante dentro de um contorno (Hough Line Transform).
    Retorna: (tem_x, confianca)
    """
    x, y, w, h = cv2.boundingRect(contour)

    margem = int(min(w, h) * 0.15)
    x1, y1 = x + margem, y + margem
    x2, y2 = x + w - margem, y + h - margem

    if x2 <= x1 or y2 <= y1:
        return False, 0.0

    roi = image[y1:y2, x1:x2]

    if roi.size == 0:
        return False, 0.0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=min(w, h) * 0.2,
        maxLineGap=10,
    )

    if lines is None or len(lines) < 2:
        return False, 0.0

    # Compatível com formatos (N, 1, 4) do OpenCV <5 e (N, 4) do OpenCV >=5
    if lines.ndim == 3:
        lines = lines.reshape(-1, 4)

    angulos = []
    for line in lines:
        x1_l, y1_l, x2_l, y2_l = line
        angulo = np.degrees(np.arctan2(y2_l - y1_l, x2_l - x1_l)) % 180
        angulos.append(angulo)

    angulos = np.array(angulos)

    limiar_diagonal = 20
    tem_45 = np.any((angulos > 45 - limiar_diagonal) & (angulos < 45 + limiar_diagonal))
    tem_135 = np.any((angulos > 135 - limiar_diagonal) & (angulos < 135 + limiar_diagonal))

    if tem_45 and tem_135:
        linhas_diagonais = np.sum(
            ((angulos > 45 - limiar_diagonal) & (angulos < 45 + limiar_diagonal)) |
            ((angulos > 135 - limiar_diagonal) & (angulos < 135 + limiar_diagonal))
        )
        confianca = min(0.9, 0.6 + (linhas_diagonais * 0.05))
        return True, confianca

    return False, 0.0


def classificar_por_varredura(image, thresh, epsilon_ratio=0.04):
    """
    Varre todos os contornos e classifica pela marca interna.
    Retorna: (classe, confianca, vertices, contorno_principal)
    Ordens: X > TRIÂNGULO > QUADRADO (padrão seguro).
    """
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, 0.0, 0, None
    hier = hierarchy[0] if hierarchy is not None else None

    maior = max(contours, key=cv2.contourArea)
    ref_area = cv2.contourArea(maior)

    if ref_area <= 0:
        return None, 0.0, 0, None

    # Faixa de área plausível para a marca (menor que a peça, acima de ruído)
    lo = max(LIMIAR_AREA_MARCA, 0.005 * ref_area)
    hi = 0.8 * ref_area

    melhor_x = None
    melhor_x_conf = 0.0
    melhor_tri = None
    melhor_tri_area = 0.0

    for i, contorno in enumerate(contours):
        area = cv2.contourArea(contorno)
        if not (lo <= area <= hi):
            continue

        vertices = count_vertices(contorno, epsilon_ratio)

        if vertices >= 5:
            # X: traços que se cruzam -> esqueleto com 3-4 pontas e forma
            # côncava (estrela), ao contrário de quadrado/triângulo (convexos).
            casco = cv2.convexHull(contorno)
            razao_casco = area / max(1.0, cv2.contourArea(casco))
            if razao_casco > 0.92:
                continue
            pontas = _pontas_do_esqueleto(thresh, contorno)
            if 3 <= pontas <= 4:
                melhor_x = contorno
                melhor_x_conf = 0.9

        elif vertices == 3 and _eh_triangulo_plausivel(contorno):
            if area > melhor_tri_area:
                melhor_tri = contorno
                melhor_tri_area = area

    # 1) Defeito (X) tem prioridade
    if melhor_x is not None and melhor_x_conf >= LIMIAR_CONFIANCA:
        v = count_vertices(melhor_x, epsilon_ratio)
        return "QUADRADO_COM_X", melhor_x_conf, v, melhor_x

    # 2) Triângulo
    if melhor_tri is not None:
        return "TRIÂNGULO", 0.9, 3, melhor_tri

    # 3) Padrão seguro: QUADRADO (usa o maior contorno para anotação)
    return "QUADRADO", 0.85, 4, maior


def classify_single(image_path, limiar_binarizacao=0, epsilon_ratio=0.04):
    """
    Classificação com parâmetros específicos.
    Retorna: dict com resultado
    """
    image = cv2.imread(image_path)
    if image is None:
        return {"erro": f"Não foi possível carregar: {image_path}"}

    image = redimensionar_para_padrao(image)

    thresh = preprocess_image(image, limiar_binarizacao)

    classe, confianca, vertices, principal = classificar_por_varredura(
        image, thresh, epsilon_ratio
    )

    if classe is None:
        return {"erro": "Nenhum contorno detectado"}

    area = cv2.contourArea(principal) if principal is not None else 0

    return {
        "classe": classe,
        "confianca": round(confianca, 3),
        "vertices": vertices,
        "area": round(area, 1),
    }


def classify_with_confidence(image_path):
    """
    Classifica com reanálise automática.

    Fluxo:
    1. Tenta classificar (Otsu + hierarquia de contornos)
    2. Se confiança < limiar, reanálise com parâmetros alternativos
    3. Retorna a classificação com maior confiança

    Args:
        image_path: caminho da imagem

    Retorna: dict com resultado final
    """
    historico = []

    for tentativa, params in enumerate(PARAMETROS_REANALISE, 1):
        resultado = classify_single(
            image_path,
            limiar_binarizacao=params["binarizacao"],
            epsilon_ratio=params["epsilon_ratio"],
        )

        resultado["tentativa"] = tentativa
        historico.append(resultado)

        if "erro" in resultado:
            continue

        if resultado["confianca"] >= LIMIAR_CONFIANCA:
            resultado["status"] = "aceito"
            resultado["historico"] = historico
            return resultado

    ultimo = historico[-1] if historico else {}
    ultimo["status"] = "aceito"  # aceitar com confiança disponível
    ultimo["motivo"] = (
        f"Confiança abaixo do limiar ({LIMIAR_CONFIANCA}) após "
        f"{len(PARAMETROS_REANALISE)} tentativas - usando último resultado"
    )
    ultimo["historico"] = historico
    return ultimo


def get_destino(classe):
    """Retorna o destino (A, B ou C) baseado na classe."""
    destinos = {
        "QUADRADO": "A",
        "TRIÂNGULO": "B",
        "QUADRADO_COM_X": "C",
    }
    return destinos.get(classe, "C")  # Default: descarte


def annotate_image(image_path, output_path=None):
    """Desenha anotações: contorno principal + marca detectada e rótulo."""
    image = cv2.imread(image_path)
    if image is None:
        return None

    image = redimensionar_para_padrao(image)

    resultado = classify_with_confidence(image_path)

    thresh = preprocess_image(image)
    classe, _, _, principal = classificar_por_varredura(image, thresh)

    cor = (0, 0, 255) if classe == "QUADRADO_COM_X" else (0, 255, 0)

    if principal is not None:
        cv2.drawContours(image, [principal], -1, cor, 2)

    destino = get_destino(classe or "QUADRADO")
    label = (
        f"{resultado.get('classe', '?')} | Destino:{destino} | "
        f"V:{resultado.get('vertices', '?')} | C:{resultado.get('confianca', 0):.2f}"
    )
    cv2.putText(image, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)

    if output_path:
        cv2.imwrite(output_path, image)

    return image