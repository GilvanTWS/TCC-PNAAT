"""
TRIA - Triagem Visual Integrada de Componentes
Pipeline principal do Raspberry Pi

Fluxo (seção 2.1 do Levantamento):
  1. Capture os quadros com Picamera2 (câmera CSI fixa).
  2. Detecte quando uma nova peça entra na região de interesse (ROI),
     sem sensor de presença.
  3. Classifique a peça UMA vez (deduplicação) com OpenCV.
  4. Gere evento, publique a decisão por MQTT e calcule o instante de atuação.
  5. Libere a detecção da próxima peça somente após a peça sair da ROI.

Uso:
  python main.py                  # captura ao vivo com Picamera2
  python main.py --imagem x.png   # modo simulação com imagem estática (teste)

Requisitos dos critérios atendidos aqui:
  RF01 (passagem/captura), RF04 (MQTT), RF05/RNF01 (instante de atuação),
  RNF05 (não duplicar contagens - um evento por peça na ROI).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

from classifier import classify_with_confidence, detect_contours, get_destino, preprocess_image
from config import (
    FRAMERATE,
    RESOLUCAO,
    LIMIAR_AREA_MINIMA,
)
from mqtt_publisher import create_client, publicar_classificacao, publicar_status_pi

# Picamera2 é opcional (Raspberry Pi). Fora dele, a captura ao vivo fica indisponível.
try:
    from picamera2 import Picamera2
    PICAMERA_DISPONIVEL = True
except ImportError:
    PICAMERA_DISPONIVEL = False


class MaquinaDeEstados:
    """Máquina de estados da detecção de passagem na ROI."""

    def __init__(self):
        self.estado = "livre"       # livre | ocupado_aguardando | ocupado_classificado
        self.peca_atual = 0
        self.total_eventos = 0

    def ao_detectar_peca(self):
        """Transição livre -> ocupado_aguardando: uma nova peça entrou na ROI."""
        if self.estado == "livre":
            self.estado = "ocupado_aguardando"
            self.peca_atual += 1
            self.total_eventos += 1
            return True
        return False

    def marcar_classificada(self):
        """Após gerar o evento da peça atual."""
        self.estado = "ocupado_classificado"

    def ao_sair_peca(self):
        """ocupado_* -> livre: a peça saiu, libera a próxima detecção."""
        if self.estado != "livre":
            self.estado = "livre"
            return True
        return False

    @property
    def ocupada(self):
        return self.estado != "livre"


def peca_presente_na_roi(frame, roi):
    """
    Detecta presença de peça dentro da ROI sem sensor de presença.
    Retorna True se houver contorno com área acima do limiar.
    """
    x, y, w, h = roi
    recorte = frame[y:y + h, x:x + w]
    if recorte.size == 0:
        return False

    thresh = preprocess_image(recorte)
    return len(detect_contours(thresh)) > 0


def capturar_quadro(camera):
    """Captura um quadro da Picamera2."""
    return camera.capture_array()


def processar_peca(frame, roi):
    """
    Classifica a peça que está na ROI.
    Retorna dict com classe, destino, defeito e tempo de processamento.
    """
    t0 = time.perf_counter()

    x, y, w, h = roi
    recorte = frame[y:y + h, x:x + w]

    # Salvar recorte temporário para o classificador (que lê de arquivo)
    caminho_temp = "/tmp/tria_roi.jpg"
    cv2.imwrite(caminho_temp, recorte)

    resultado = classify_with_confidence(caminho_temp)
    tempo_processamento_ms = round((time.perf_counter() - t0) * 1000, 1)

    if "erro" in resultado:
        return {
            "classe": "QUADRADO",
            "destino": "A",
            "defeito": False,
            "tempo_processamento_ms": tempo_processamento_ms,
            "erro": resultado["erro"],
        }

    classe = resultado["classe"]
    destino = get_destino(classe)
    defeito = classe == "QUADRADO_COM_X"

    return {
        "classe": classe,
        "destino": destino,
        "defeito": defeito,
        "tempo_processamento_ms": tempo_processamento_ms,
    }


def main_loop(camera, mqtt_client, roi, intervalo_s=0.05):
    """
    Loop principal: detecta passagem, classifica e publica via MQTT.
    Cada peça gera no máximo um evento (RNF05).
    """
    maquina = MaquinaDeEstados()
    frame_atual = capturar_quadro(camera)

    print("TRIA - iniciando pipeline de captura. Ctrl+C para encerrar.")
    print(f"ROI: {roi}")

    try:
        while True:
            # Captura em taxa controlada (delay role o frame)
            time.sleep(intervalo_s)
            frame_atual = capturar_quadro(camera)

            presente = peca_presente_na_roi(frame_atual, roi)

            if presente and maquina.ao_detectar_peca():
                print(f"\n[{time.strftime('%H:%M:%S')}] Peça {maquina.peca_atual} "
                      f"detectada na ROI - classificando...")

                resultado = processar_peca(frame_atual, roi)

                evento = publicar_classificacao(
                    mqtt_client,
                    classe=resultado["classe"],
                    destino=resultado["destino"],
                    defeito=resultado["defeito"],
                    tempo_processamento_ms=resultado["tempo_processamento_ms"],
                )

                maquina.marcar_classificada()

                print(f"  Evento: {evento['id_evento']} | "
                      f"classe={resultado['classe']} | "
                      f"destino={resultado['destino']} | "
                      f"defeito={resultado['defeito']} | "
                      f"{resultado['tempo_processamento_ms']} ms")

            elif not presente and maquina.ao_sair_peca():
                print(f"[{time.strftime('%H:%M:%S')}] Peça saiu da ROI - "
                      f"aguardando próximo ciclo.")

    except KeyboardInterrupt:
        print("\nEncerrado pelo operador.")
    finally:
        publicar_status_pi(mqtt_client, ciclo_atual=maquina.total_eventos)


def modo_simulacao(imagem_path, roi):
    """Modo de teste sem câmera: classifica uma imagem já salva."""
    frame = cv2.imread(imagem_path)
    if frame is None:
        print(f"Erro: não foi possível carregar {imagem_path}")
        sys.exit(1)

    print(f"Modo simulação - processando {imagem_path}")
    resultado = processar_peca(frame, roi)

    print(json.dumps({
        "classe": resultado["classe"],
        "destino": resultado["destino"],
        "defeito": resultado["defeito"],
        "tempo_processamento_ms": resultado["tempo_processamento_ms"],
    }, ensure_ascii=False, indent=2))


def definir_roi(frame_shape):
    """ROI central por padrão (50% da largura central, altura útil)."""
    altura, largura = frame_shape[:2]
    w = int(largura * 0.5)
    h = int(altura * 0.6)
    x = (largura - w) // 2
    y = (altura - h) // 2
    return (x, y, w, h)


def main():
    parser = argparse.ArgumentParser(description="TRIA - pipeline principal do Pi")
    parser.add_argument("--imagem", help="modo simulação: classifica uma imagem estática")
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                        help="região de interesse (default: central)")
    args = parser.parse_args()

    roi_configurada = tuple(args.roi) if args.roi else None

    if args.imagem:
        frame = cv2.imread(args.imagem)
        roi = roi_configurada or definir_roi(frame.shape)
        modo_simulacao(args.imagem, roi)
        return

    if not PICAMERA_DISPONIVEL:
        print("Picamera2 não disponível neste ambiente (necessário Raspberry Pi).")
        sys.exit(1)

    camera = Picamera2()
    config = camera.create_still_configuration(
        main={"size": RESOLUCAO}, controls={"FrameRate": FRAMERATE}
    )
    camera.configure(config)
    camera.start()

    try:
        frame_inicial = capturar_quadro(camera)
        roi = roi_configurada or definir_roi(frame_inicial.shape)
    except Exception as exc:
        print(f"Falha ao inicializar câmera: {exc}")
        sys.exit(1)

    mqtt_client = create_client()
    try:
        main_loop(camera, mqtt_client, roi)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        camera.stop()


if __name__ == "__main__":
    main()