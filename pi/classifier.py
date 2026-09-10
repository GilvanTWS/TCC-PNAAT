"""
TRIA - Triagem Visual Integrada de Componentes
Classificador de formas com detecção de defeito (marca X)
PoC Física - Levantamento de Requisitos
"""

import cv2
import numpy as np

from config import (
    LIMIAR_CIRCULARIDADE,
    LIMIAR_AREA_MINIMA,
    LIMIAR_CONFIANCA,
    MAX_TENTATIVAS,
    PARAMETROS_REANALISE,
)


def preprocess_image(image, limiar_binarizacao=127):
    """Pré-processamento: escala de cinza + binarização."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, limiar_binarizacao, 255, cv2.THRESH_BINARY_INV)
    return thresh


def detect_contours(thresh):
    """Detecta contornos e retorna apenas os válidos."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) > LIMIAR_AREA_MINIMA]


def count_vertices(contour, epsilon_ratio=0.04):
    """Conta vértices usando approxPolyDP."""
    perimeter = cv2.arcLength(contour, True)
    epsilon = epsilon_ratio * perimeter
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return len(approx)


def detect_mark_x(image, contour):
    """
    Detecta marca X contrastante dentro de um quadrado.
    
    Usa Hough Line Transform para detectar linhas diagonais
    que formam o X na região interna da peça.
    
    Retorna: (tem_x, confianca)
    """
    x, y, w, h = cv2.boundingRect(contour)
    
    # Extrair região de interesse (ROI) interna com margem
    margem = int(min(w, h) * 0.15)
    x1, y1 = x + margem, y + margem
    x2, y2 = x + w - margem, y + h - margem
    
    if x2 <= x1 or y2 <= y1:
        return False, 0.0
    
    roi = image[y1:y2, x1:x2]
    
    if roi.size == 0:
        return False, 0.0
    
    # Converter para escala de cinza
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Aplicar Canny para detecção de bordas
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Hough Line Transform
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
    
    # Analisar ângulos das linhas detectadas
    # Compatível com formatos (N, 1, 4) do OpenCV <5 e (N, 4) do OpenCV >=5
    if lines.ndim == 3:
        lines = lines.reshape(-1, 4)

    angulos = []
    for line in lines:
        x1_l, y1_l, x2_l, y2_l = line
        angulo = np.degrees(np.arctan2(y2_l - y1_l, x2_l - x1_l)) % 180
        angulos.append(angulo)
    
    angulos = np.array(angulos)
    
    # Verificar se existem linhas diagonais (~45° e ~135°)
    # que indicam a presença de um X
    limiar_diagonal = 20  # tolerância em graus
    tem_45 = np.any((angulos > 45 - limiar_diagonal) & (angulos < 45 + limiar_diagonal))
    tem_135 = np.any((angulos > 135 - limiar_diagonal) & (angulos < 135 + limiar_diagonal))
    
    if tem_45 and tem_135:
        # Calcular confiança baseada no número de linhas diagonais
        linhas_diagonais = np.sum(
            ((angulos > 45 - limiar_diagonal) & (angulos < 45 + limiar_diagonal)) |
            ((angulos > 135 - limiar_diagonal) & (angulos < 135 + limiar_diagonal))
        )
        confianca = min(0.9, 0.6 + (linhas_diagonais * 0.05))
        return True, confianca
    
    return False, 0.0


def classify_contour(contour, image=None, epsilon_ratio=0.04):
    """
    Classifica um contorno individual.
    
    Retorna: (classe, confianca, vertices)
    """
    vertices = count_vertices(contour, epsilon_ratio)
    
    # Triângulo: 3 vértices
    if vertices == 3:
        return "TRIÂNGULO", 0.9, vertices
    
    # Quadrado: 4 vértices
    if vertices == 4:
        # Verificar se tem marca X (defeito)
        if image is not None:
            tem_x, confianca_x = detect_mark_x(image, contour)
            if tem_x and confianca_x >= LIMIAR_CONFIANCA:
                return "QUADRADO_COM_X", confianca_x, vertices
        
        return "QUADRADO", 0.85, vertices
    
    # Para outros casos, usar lógica baseada em área/perímetro
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    
    if perimeter == 0:
        return "QUADRADO", 0.5, vertices
    
    circularidade = (4 * np.pi * area) / (perimeter ** 2)
    
    if circularidade > LIMIAR_CIRCULARIDADE:
        # Muito circular - provavelmente não é uma das 3 classes
        return "QUADRADO", 0.6, vertices
    
    if vertices <= 5:
        return "QUADRADO", 0.6, vertices
    else:
        return "TRIÂNGULO", 0.5, vertices


def classify_single(image_path, limiar_binarizacao=127, epsilon_ratio=0.04):
    """
    Classificação com parâmetros específicos.
    Retorna: dict com resultado
    """
    image = cv2.imread(image_path)
    if image is None:
        return {"erro": f"Não foi possível carregar: {image_path}"}

    thresh = preprocess_image(image, limiar_binarizacao)
    contours = detect_contours(thresh)

    if not contours:
        return {"erro": "Nenhum contorno detectado"}

    main_contour = max(contours, key=cv2.contourArea)
    classe, confianca, vertices = classify_contour(main_contour, image, epsilon_ratio)
    area = cv2.contourArea(main_contour)

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
    1. Tenta classificar com parâmetros padrão
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
            epsilon_ratio=params["epsilon_ratio"]
        )

        resultado["tentativa"] = tentativa
        historico.append(resultado)

        if "erro" in resultado:
            continue

        if resultado["confianca"] >= LIMIAR_CONFIANCA:
            resultado["status"] = "aceito"
            resultado["historico"] = historico
            return resultado

    # Se nenhuma tentativa atingiu a confiança, usar a última
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
    """Desenha anotações na imagem para visualização."""
    image = cv2.imread(image_path)
    if image is None:
        return None

    resultado = classify_with_confidence(image_path)

    image = cv2.imread(image_path)
    thresh = preprocess_image(image)
    contours = detect_contours(thresh)

    if not contours:
        return image

    main_contour = max(contours, key=cv2.contourArea)
    classe = resultado.get("classe", "?")
    vertices = resultado.get("vertices", "?")
    confianca = resultado.get("confianca", 0)
    status = resultado.get("status", "?")
    destino = get_destino(classe)

    # Cores: verde=normal, vermelho=defeito
    if classe == "QUADRADO_COM_X":
        cor = (0, 0, 255)  # Vermelho
    else:
        cor = (0, 255, 0)  # Verde

    cv2.drawContours(image, [main_contour], -1, cor, 2)

    label = f"{classe} | Destino:{destino} | V:{vertices} | C:{confianca:.2f}"
    cv2.putText(image, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)

    if output_path:
        cv2.imwrite(output_path, image)

    return image
