"""
Teste do classificador com as 3 classes da PoC Física
QUADRADO, TRIÂNGULO e QUADRADO COM X
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import classifier
from classifier import classify_with_confidence, annotate_image, get_destino, detect_mark_x


IMAGES_DIR = os.path.join(os.path.dirname(__file__), "images")


def testar_classificador():
    """Testa todas as imagens disponíveis."""
    print("=" * 70)
    print("TESTE DO CLASSIFICADOR - TRIA (PoC Física)")
    print("Classes: QUADRADO, TRIÂNGULO, QUADRADO COM X")
    print("=" * 70)

    total = 0

    for filename in sorted(os.listdir(IMAGES_DIR)):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        if filename.startswith("anotada_"):
            continue

        path = os.path.join(IMAGES_DIR, filename)

        resultado = classify_with_confidence(path)

        total += 1
        classe = resultado.get("classe", "N/A")
        destino = get_destino(classe)
        confianca = resultado.get("confianca", 0)
        status = resultado.get("status", "N/A")

        print(f"\n{filename}:")
        print(f"  Classe: {classe}")
        print(f"  Destino: {destino}")
        print(f"  Confiança: {confianca}")
        print(f"  Vértices: {resultado.get('vertices', 'N/A')}")
        print(f"  Status: {status}")

        # Gerar imagem anotada
        output_path = os.path.join(IMAGES_DIR, f"anotada_{filename}")
        annotate_image(path, output_path)

    print("\n" + "=" * 70)
    print(f"TOTAL CLASSIFICADO: {total} imagens")
    print("""
Validação com peças reais (RF02/RF03):
- 20 apresentações de QUADRADO -> meta >= 18 acertos
- 20 apresentações de TRIÂNGULO -> meta >= 18 acertos
- 20 apresentações de QUADRADO COM X -> meta >= 18 reconhecimentos
    """)
    print("=" * 70)


def testar_fluxos():
    """Testa as funções auxiliares: get_destino e detecção de X."""
    print("=" * 70)
    print("TESTE DE FLUXOS - TRIA")
    print("=" * 70)

    # Teste de destinos
    ok_destinos = {
        "QUADRADO": "A",
        "TRIÂNGULO": "B",
        "QUADRADO_COM_X": "C",
    }
    for classe, destino_esperado in ok_destinos.items():
        destino = get_destino(classe)
        ok = destino == destino_esperado
        print(f"  get_destino({classe}) = {destino} {'OK' if ok else 'FALHOU'}")
        if not ok:
            return False

    print("  Destinos: OK")

    # Verificar payload mqtt usa defeito corretamente
    import config
    assert config.TOPICO_TRIAGEM == "tria/triagem"
    assert config.TOPICO_STATUS_PI == "tria/status/pi"
    assert config.TOPICO_STATUS_ESP32 == "tria/status/esp32"
    assert config.TOPICO_ATUADOR == "tria/atuador"
    print("  Tópicos MQTT: OK")

    return True


if __name__ == "__main__":
    testar_classificador()
    testar_fluxos()