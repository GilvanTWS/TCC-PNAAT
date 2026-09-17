"""Leitura e escrita de imagens com caminhos Unicode, inclusive no Windows.

O Python abre o arquivo; o OpenCV recebe os bytes, sem interpretar o caminho.
As imagens seguem a convenção BGR usada pelo restante do pipeline.
"""

from pathlib import Path

import cv2
import numpy as np


def ler_imagem(path):
    """Retorna uma imagem BGR ou None para arquivo ausente, vazio ou inválido."""
    try:
        dados = Path(path).read_bytes()
    except OSError:
        return None
    if not dados:
        return None
    try:
        return cv2.imdecode(np.frombuffer(dados, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        return None


def salvar_imagem(path, image):
    """Codifica pela extensão e salva; falhas de escrita são propagadas."""
    output = Path(path)
    sucesso, dados = cv2.imencode(output.suffix, image)
    if not sucesso:
        raise ValueError(f"Não foi possível codificar a imagem: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(dados.tobytes())
