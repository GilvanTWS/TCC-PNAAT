"""
Teste do classificador com reanálise automática
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import classifier
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
    revisados = 0

    for filename in sorted(os.listdir(IMAGES_DIR)):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        if filename.startswith("anotada_"):
            continue

        name = os.path.splitext(filename)[0]
        path = os.path.join(IMAGES_DIR, filename)

        resultado = classify_with_confidence(path, primeira_passagem=True)
        esperado = ESPERADO.get(name, "?")

        total += 1
        classe = resultado.get("classe", "N/A")
        destino = resultado.get("destino", "N/A")
        status = resultado.get("status", "N/A")
        tentativas = len(resultado.get("historico", []))

        if status == "discard":
            descartados += 1
            status_icon = "DESCARTADO"
        elif status == "review":
            revisados += 1
            status_icon = "REVISÃO"
        elif classe == esperado and destino == esperado:
            acertos += 1
            status_icon = "OK"
        else:
            status_icon = "FALHOU"

        print(f"\n{filename}:")
        print(f"  Esperado: {esperado}")
        print(f"  Resultado: {classe} (destino {destino})")
        print(f"  Circularidade: {resultado.get('circularidade', 'N/A')}")
        print(f"  Vértices: {resultado.get('vertices', 'N/A')}")
        print(f"  Tentativas: {tentativas}")
        print(f"  Status: {status_icon}")

        output_path = os.path.join(IMAGES_DIR, f"anotada_{filename}")
        annotate_image(path, output_path)

    print("\n" + "=" * 70)
    print(f"RESULTADO FINAL: {acertos}/{total} acertos")
    print(f"Descartados: {descartados}")
    print(f"Revisados: {revisados}")
    print("=" * 70)


def testar_revisao():
    """Força baixa confiança e verifica o fluxo R na 1ª passagem e D na reanálise."""
    print("=" * 70)
    print("TESTE DO FLUXO DE REVISÃO - TRIA")
    print("=" * 70)

    limiar_original = classifier.LIMIAR_CONFIANCA
    classifier.LIMIAR_CONFIANCA = 1.5

    path = os.path.join(IMAGES_DIR, "c1.png")
    if not os.path.exists(path):
        path = os.path.join(IMAGES_DIR, "c1.jpeg")

    try:
        resultado_primeira = classify_with_confidence(path, primeira_passagem=True)
        ok_primeira = (
            resultado_primeira.get("destino") == "R"
            and resultado_primeira.get("status") == "review"
        )
        print(f"\nPrimeira passagem (ambígua):")
        print(f"  Status: {resultado_primeira.get('status')}")
        print(f"  Destino: {resultado_primeira.get('destino')}")
        print(f"  Motivo: {resultado_primeira.get('motivo')}")
        print(f"  {'OK' if ok_primeira else 'FALHOU'}")

        resultado_reanalise = classify_with_confidence(path, primeira_passagem=False)
        ok_reanalise = (
            resultado_reanalise.get("destino") == "D"
            and resultado_reanalise.get("status") == "discard"
        )
        print(f"\nReanálise (ainda ambígua):")
        print(f"  Status: {resultado_reanalise.get('status')}")
        print(f"  Destino: {resultado_reanalise.get('destino')}")
        print(f"  Motivo: {resultado_reanalise.get('motivo')}")
        print(f"  {'OK' if ok_reanalise else 'FALHOU'}")

        sucesso = ok_primeira and ok_reanalise
        print("\n" + "=" * 70)
        print(f"FLUXO DE REVISÃO: {'OK' if sucesso else 'FALHOU'}")
        print("=" * 70)
    finally:
        classifier.LIMIAR_CONFIANCA = limiar_original


if __name__ == "__main__":
    testar_classificador()
    testar_revisao()