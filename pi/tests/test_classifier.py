"""Testes reais do classificador e do fluxo usado pelo main.py."""

from pathlib import Path
import sys

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = Path(__file__).resolve().parent / "images"
sys.path.insert(0, str(PROJECT_ROOT))

from classifier import classify_image, classify_with_confidence, get_destino
from main import MaquinaDeEstados, processar_peca


def _classe_esperada(filename):
    if filename.startswith("q"):
        return "QUADRADO"
    if filename.startswith("t"):
        return "TRIÂNGULO"
    if filename.startswith("x"):
        return "QUADRADO_COM_X"
    raise ValueError(f"imagem de teste sem classe no nome: {filename}")


def test_classifica_as_18_imagens_de_referencia():
    imagens = sorted(
        path for path in IMAGES_DIR.glob("*.jpeg")
        if not path.name.startswith("anotada_")
    )
    assert len(imagens) == 18

    erros = []
    for path in imagens:
        obtida = classify_with_confidence(path).get("classe")
        esperada = _classe_esperada(path.name)
        if obtida != esperada:
            erros.append(f"{path.name}: esperado={esperada}, obtido={obtida}")
    assert not erros, "\n".join(erros)


def test_fluxo_do_main_classifica_as_imagens_de_referencia():
    for path in sorted(IMAGES_DIR.glob("[qtx][1-6].jpeg")):
        frame = cv2.imread(str(path))
        resultado = processar_peca(frame)
        assert resultado.get("classe") == _classe_esperada(path.name), path.name


def test_fotos_reais_adicionais_quando_presentes():
    casos = {
        "quadrado.jpeg": "QUADRADO",
        "triangulo.jpeg": "TRIÂNGULO",
        "erro.jpeg": "QUADRADO_COM_X",
    }
    for filename, esperada in casos.items():
        path = PROJECT_ROOT / filename
        if path.exists():
            assert classify_with_confidence(path).get("classe") == esperada


def test_fundo_branco_nao_vira_quadrado():
    frame_sem_peca = np.full((480, 640, 3), 255, dtype=np.uint8)
    resultado = classify_image(frame_sem_peca)
    assert resultado["status"] == "sem_peca"
    assert "classe" not in resultado


def test_destinos():
    assert get_destino("QUADRADO") == "A"
    assert get_destino("TRIÂNGULO") == "B"
    assert get_destino("QUADRADO_COM_X") == "C"


def test_maquina_de_estados_nao_duplica_eventos():
    maquina = MaquinaDeEstados()
    assert maquina.ao_detectar_peca() is True
    assert maquina.ao_detectar_peca() is False
    maquina.marcar_classificada()
    assert maquina.ao_detectar_peca() is False
    assert maquina.ao_sair_peca() is True
    assert maquina.ao_detectar_peca() is True
    assert maquina.total_eventos == 2
