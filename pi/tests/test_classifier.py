"""
Teste do classificador com reanálise automática
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from classifier import classify_with_confidence, annotate_image


IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")

ESPERADO = {
    "c1": "A", "c2": "A", "c3": "A",
    "q1": "B", "q2": "B", "q3": "B",
    "t1": "C", "t2": "C", "t3": "C",
}


def testar_classificador():
    """Testa todas as imagens com reanálise."""
    print("=" * 70)
    print("TESTE DO CLASSIFICADOR COM REANÁLISE - TRIA")
    print("=" * 70)

    acertos = 0
    total = 0
    descartados = 0

    for filename in sorted(os.listdir(IMAGES_DIR)):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        if filename.startswith("anotada_"):
            continue

        name = os.path.splitext(filename)[0]
        path = os.path.join(IMAGES_DIR, filename)

        resultado = classify_with_confidence(path)
        esperado = ESPERADO.get(name, "?")

        total += 1
        classe = resultado.get("classe", "N/A")
        status = resultado.get("status", "N/A")
        tentativas = len(resultado.get("historico", []))

        if status == "discard":
            descartados += 1
            status_icon = "DESCARTADO"
        elif classe == esperado:
            acertos += 1
            status_icon = "OK"
        else:
            status_icon = "FALHOU"

        print(f"\n{filename}:")
        print(f"  Esperado: {esperado}")
        print(f"  Resultado: {classe}")
        print(f"  Circularidade: {resultado.get('circularidade', 'N/A')}")
        print(f"  Vértices: {resultado.get('vertices', 'N/A')}")
        print(f"  Tentativas: {tentativas}")
        print(f"  Status: {status_icon}")

        # Salva imagem anotada
        output_path = os.path.join(IMAGES_DIR, f"anotada_{filename}")
        annotate_image(path, output_path)

    print("\n" + "=" * 70)
    print(f"RESULTADO FINAL: {acertos}/{total} acertos")
    print(f"Descartados: {descartados}")
    print("=" * 70)


if __name__ == "__main__":
    testar_classificador()
