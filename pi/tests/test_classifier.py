"""
Teste do classificador com imagens locais
"""

import os
import sys

# Adiciona o diretório pai ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify_image, annotate_image


IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

# Mapeamento esperado (nome da imagem → classe esperada)
ESPERADO = {
    "c1": "A", "c2": "A", "c3": "A",  # Círculos
    "q1": "B", "q2": "B", "q3": "B",  # Quadrados
    "t1": "C", "t2": "C", "t3": "C",  # Triângulos
}


def testar_classificador():
    """Testa todas as imagens e mostra resultados."""
    print("=" * 60)
    print("TESTE DO CLASSIFICADOR - TRIA")
    print("=" * 60)

    acertos = 0
    total = 0

    for filename in sorted(os.listdir(IMAGES_DIR)):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue

        name = os.path.splitext(filename)[0]
        path = os.path.join(IMAGES_DIR, filename)

        resultado = classify_image(path)
        esperado = ESPERADO.get(name, "?")

        total += 1
        if "erro" in resultado:
            status = "ERRO"
        elif resultado["classe"] == esperado:
            status = "OK"
            acertos += 1
        else:
            status = "FALHOU"

        print(f"\n{filename}:")
        print(f"  Esperado: {esperado}")
        print(f"  Resultado: {resultado.get('classe', 'N/A')}")
        print(f"  Circularidade: {resultado.get('circularidade', 'N/A')}")
        print(f"  Vértices: {resultado.get('vertices', 'N/A')}")
        print(f"  Status: {status}")

        # Salva imagem anotada
        output_path = os.path.join(IMAGES_DIR, f"anotada_{filename}")
        annotate_image(path, output_path)

    print("\n" + "=" * 60)
    print(f"RESULTADO FINAL: {acertos}/{total} acertos ({acertos/total*100:.0f}%)")
    print("=" * 60)


if __name__ == "__main__":
    testar_classificador()
