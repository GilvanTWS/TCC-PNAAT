"""
TRIA - Triagem Visual Integrada de Componentes
Classificador de formas via OpenCV
"""

import cv2
import numpy as np


# Thresholds
LIMIAR_CIRCULARIDADE = 0.7
LIMIAR_AREA_MINIMA = 500
LIMIAR_CONFIANCA = 0.7
MAX_TENTATIVAS = 3

# Parâmetros de reanálise
PARAMETROS_REANALISE = [
    {"binarizacao": 127, "epsilon_ratio": 0.04},   # Padrão
    {"binarizacao": 100, "epsilon_ratio": 0.04},   # Binarização mais sensível
    {"binarizacao": 150, "epsilon_ratio": 0.06},   # Binarização mais rígida + epsilon maior
]


def preprocess_image(image, limiar_binarizacao=127):
    """Pré-processamento: escala de cinza + binarização."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, limiar_binarizacao, 255, cv2.THRESH_BINARY_INV)
    return thresh


def detect_contours(thresh):
    """Detecta contornos e retorna apenas os válidos."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return [c for c in contours if cv2.contourArea(c) > LIMIAR_AREA_MINIMA]


def calculate_circularity(contour):
    """Calcula circularidade: 4π × área / perímetro²"""
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return 0
    return (4 * np.pi * area) / (perimeter ** 2)


def count_vertices(contour, epsilon_ratio=0.04):
    """Conta vértices usando approxPolyDP."""
    perimeter = cv2.arcLength(contour, True)
    epsilon = epsilon_ratio * perimeter
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return len(approx)


def classify_contour(contour, epsilon_ratio=0.04):
    """
    Classifica um contorno individual.

    Retorna: (classe, confiança, vértices)
    """
    vertices = count_vertices(contour, epsilon_ratio)
    circularity = calculate_circularity(contour)

    # Triângulo: 3 vértices → alta confiança se detectou 3 claramente
    if vertices == 3:
        # Confiança alta: detectou 3 vértices = é triângulo
        confianca = 0.9
        return 'C', confianca, vertices

    # Quadrado: 4 vértices → alta confiança se detectou 4 claramente
    if vertices == 4:
        confianca = 0.85
        return 'B', confianca, vertices

    # Círculo: alta circularidade e mais de 4 vértices
    if circularity > LIMIAR_CIRCULARIDADE:
        return 'A', circularity, vertices

    # Caso ambíguo
    if circularity > 0.8:
        return 'A', circularity, vertices
    elif vertices <= 5:
        return 'B', 0.6, vertices
    else:
        return 'A', circularity, vertices


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
    classe, circularity, vertices = classify_contour(main_contour, epsilon_ratio)
    area = cv2.contourArea(main_contour)

    return {
        "classe": classe,
        "circularidade": round(circularity, 3),
        "vertices": vertices,
        "area": round(area, 1),
        "confianca": round(circularity, 2)
    }


def classify_with_confidence(image_path):
    """
    Classifica com reanálise automática.

    Fluxo:
    1. Tenta classificar com parâmetros padrão
    2. Se confiança < limiar, reanálise com parâmetros alternativos
    3. Após MAX_TENTATIVAS sem confiança, retorna 'discard'

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

        # Se tem erro, pula pra próxima tentativa
        if "erro" in resultado:
            continue

        # Se confiança é alta o suficiente, aceita
        if resultado["confianca"] >= LIMIAR_CONFIANCA:
            resultado["status"] = "aceito"
            resultado["historico"] = historico
            return resultado

    # Todas as tentativas falharam
    ultimo = historico[-1] if historico else {}
    ultimo["status"] = "discard"
    ultimo["motivo"] = f"Confiança abaixo do limiar ({LIMIAR_CONFIANCA}) após {len(PARAMETROS_REANALISE)} tentativas"
    ultimo["historico"] = historico
    return ultimo


def annotate_image(image_path, output_path=None):
    """Desenha anotações na imagem para visualização."""
    image = cv2.imread(image_path)
    if image is None:
        return None

    resultado = classify_with_confidence(image_path)

    # Reconstrói imagem para anotação
    image = cv2.imread(image_path)
    thresh = preprocess_image(image)
    contours = detect_contours(thresh)

    if not contours:
        return image

    main_contour = max(contours, key=cv2.contourArea)
    classe = resultado.get("classe", "?")
    vertices = resultado.get("vertices", "?")
    circularity = resultado.get("circularidade", 0)
    status = resultado.get("status", "?")

    # Cor baseada no status
    if status == "aceito":
        cor = (0, 255, 0)  # Verde
    else:
        cor = (0, 0, 255)  # Vermelho

    cv2.drawContours(image, [main_contour], -1, cor, 2)

    label = f"{classe} | V:{vertices} | C:{circularity:.2f} | {status}"
    cv2.putText(image, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, cor, 2)

    if output_path:
        cv2.imwrite(output_path, image)

    return image
