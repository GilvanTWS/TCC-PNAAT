"""
TRIA - Triagem Visual Integrada de Componentes
Classificador de formas via OpenCV
"""

import cv2
import numpy as np


# Thresholds
LIMIAR_CIRCULARIDADE = 0.7
LIMIAR_AREA_MINIMA = 500


def preprocess_image(image):
    """Pré-processamento: escala de cinza + binarização."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    return thresh


def detect_contours(thresh):
    """Detecta contornos e retorna apenas os válidos."""
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Filtra contornos muito pequenos (ruído)
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


def classify_contour(contour):
    """
    Classifica um contorno individual.

    Retorna: 'A' (circular), 'B' (quadrada), 'C' (triangular)
    """
    vertices = count_vertices(contour)
    circularity = calculate_circularity(contour)

    # Triângulo: 3 vértices
    if vertices == 3:
        return 'C', circularity, vertices

    # Quadrado: 4 vértices
    if vertices == 4:
        return 'B', circularity, vertices

    # Círculo: alta circularidade e mais de 4 vértices
    if circularity > LIMIAR_CIRCULARIDADE:
        return 'A', circularity, vertices

    # Caso ambíguo: usa circularidade como desempate
    if circularity > 0.8:
        return 'A', circularity, vertices
    elif vertices <= 5:
        return 'B', circularity, vertices
    else:
        return 'A', circularity, vertices


def classify_image(image_path):
    """
    Classifica a imagem inteira.

    Retorna: dict com resultado da classificação
    """
    image = cv2.imread(image_path)
    if image is None:
        return {"erro": f"Não foi possível carregar: {image_path}"}

    thresh = preprocess_image(image)
    contours = detect_contours(thresh)

    if not contours:
        return {"erro": "Nenhum contorno detectado"}

    # Pega o maior contorno (peça principal)
    main_contour = max(contours, key=cv2.contourArea)

    classe, circularity, vertices = classify_contour(main_contour)
    area = cv2.contourArea(main_contour)

    return {
        "classe": classe,
        "circularidade": round(circularity, 3),
        "vertices": vertices,
        "area": round(area, 1),
        "confianca": round(circularity, 2)
    }


def annotate_image(image_path, output_path=None):
    """Desenha anotações na imagem para visualização."""
    image = cv2.imread(image_path)
    if image is None:
        return None

    thresh = preprocess_image(image)
    contours = detect_contours(thresh)

    if not contours:
        return image

    main_contour = max(contours, key=cv2.contourArea)
    classe, circularity, vertices = classify_contour(main_contour)

    # Desenha contorno
    cv2.drawContours(image, [main_contour], -1, (0, 255, 0), 2)

    # Texto com classificação
    label = f"Classe: {classe} | Vertices: {vertices} | Circ: {circularity:.2f}"
    cv2.putText(image, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if output_path:
        cv2.imwrite(output_path, image)

    return image
