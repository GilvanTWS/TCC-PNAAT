"""
TRIA - Triagem Visual Integrada de Componentes
Pipeline principal do Raspberry Pi

Fluxo (seção 2.1 do Levantamento):
  1. Capture os quadros com Picamera2 (câmera CSI fixa).
  2. Detecte quando uma nova peça entra na região de interesse (ROI),
     sem sensor de presença.
  3. Colete amostras até confirmar a saída; classifique a passagem UMA vez.
  4. Publique por MQTT somente uma classificação válida e libere a próxima peça.
     O campo instante_atuacao é informativo: o ESP32 atua ao receber a decisão.

Uso:
  python main.py                    # câmera ao vivo + janela de visualização
  python main.py --web              # visualização no navegador
  python main.py --sem-mqtt         # testa a câmera sem broker MQTT
  python main.py --imagem x.png     # classifica a imagem inteira
  python main.py --video teste.mp4  # reproduz um ensaio gravado
  python main.py --sem-janela       # execução sem interface gráfica

Requisitos relacionados: RF01 (captura), RF04 (MQTT) e RNF05 (contagem).
O aceite físico de RF05/RNF01 exige medir a chegada ao servo na bancada.
"""

import argparse
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2

from image_io import ler_imagem

from classifier import (
    classificar_sequencia_normalizada,
    classify_image,
    get_destino,
    localizar_peca_mdf,
)
from config import (
    FRAMES_CONFIRMAR_AUSENCIA,
    FRAMES_CONFIRMAR_PRESENCA,
    FRAMERATE,
    RESOLUCAO,
)
from mqtt_publisher import create_client, publicar_classificacao, publicar_status_pi

# Picamera2 é opcional (Raspberry Pi). Fora dele, a captura ao vivo fica indisponível.
try:
    from picamera2 import Picamera2
    PICAMERA_DISPONIVEL = True
except ImportError:
    PICAMERA_DISPONIVEL = False


class MaquinaDeEstados:
    """Controla uma passagem; pressupõe intervalo livre entre peças.

    total_eventos conta entradas confirmadas, inclusive as que depois falham
    na classificação. Não é a quantidade de publicações confirmadas pelo broker.
    """

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
    Retorna True somente se houver uma placa de MDF plausível.
    """
    x, y, w, h = roi
    recorte = frame[y:y + h, x:x + w]
    if recorte.size == 0:
        return False

    return localizar_peca_mdf(recorte) is not None


def capturar_quadro(camera):
    """Captura um quadro da Picamera2."""
    frame = camera.capture_array("main")
    if frame.ndim == 3 and frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def processar_peca(frame, roi=None):
    """
    Classifica a peça que está na ROI.
    Retorna dict com classe, destino, defeito e tempo de processamento.
    """
    t0 = time.perf_counter()

    if roi is None:
        recorte = frame
    else:
        x, y, w, h = roi
        recorte = frame[y:y + h, x:x + w]

    resultado = classify_image(recorte)
    tempo_processamento_ms = round((time.perf_counter() - t0) * 1000, 1)

    if "erro" in resultado:
        return {
            "tempo_processamento_ms": tempo_processamento_ms,
            "erro": resultado["erro"],
            "status": resultado.get("status", "erro"),
        }

    classe = resultado["classe"]
    destino = get_destino(classe)
    defeito = classe == "QUADRADO_COM_X"

    return {
        "classe": classe,
        "destino": destino,
        "defeito": defeito,
        "confianca": resultado["confianca"],
        "box": resultado.get("box"),
        "tempo_processamento_ms": tempo_processamento_ms,
    }


def processar_amostras_peca(amostras_normalizadas):
    """Classifica uma passagem usando as melhores informações de vários frames."""
    t0 = time.perf_counter()
    resultado = classificar_sequencia_normalizada(amostras_normalizadas)
    tempo_processamento_ms = round((time.perf_counter() - t0) * 1000, 1)

    if "erro" in resultado:
        return {
            "tempo_processamento_ms": tempo_processamento_ms,
            "erro": resultado["erro"],
            "status": resultado.get("status", "erro"),
        }

    classe = resultado["classe"]
    return {
        "classe": classe,
        "destino": get_destino(classe),
        "defeito": classe == "QUADRADO_COM_X",
        "confianca": resultado["confianca"],
        "tempo_processamento_ms": tempo_processamento_ms,
    }


def _janela_disponivel(solicitada):
    """Abre a janela somente quando há uma sessão gráfica disponível."""
    if not solicitada:
        return False
    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        print("Aviso: ambiente sem tela gráfica; usando o navegador.")
        return False
    try:
        cv2.namedWindow("TRIA - Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("TRIA - Camera", 960, 720)
        return True
    except cv2.error as exc:
        print(f"Aviso: não foi possível abrir a janela: {exc}")
        return False


class VisualizadorWeb:
    """Publica o último quadro como MJPEG, sem depender do HighGUI."""

    PAGINA = b"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TRIA - Camera</title>
  <style>
    html, body { height: 100%; }
    body { margin: 0; background: #111; color: #eee; font-family: sans-serif;
           display: grid; place-items: center; }
    main { width: min(96vw, 960px); text-align: center; }
    h1 { font-size: 1.15rem; font-weight: 500; }
    img { display: block; width: 100%; height: auto; background: #222;
          border: 1px solid #444; border-radius: 8px; }
    p { color: #aaa; font-size: .9rem; }
  </style>
</head>
<body><main>
  <h1>TRIA - Camera ao vivo</h1>
  <img id="camera" src="/stream.mjpg" alt="Imagem ao vivo da camera">
  <p>Para encerrar a captura, pressione Ctrl+C no terminal.</p>
</main>
<script>
  const camera = document.getElementById('camera');
  camera.onerror = () => setTimeout(() => {
    camera.src = '/stream.mjpg?' + Date.now();
  }, 1000);
</script></body></html>"""

    def __init__(self, porta=8081, host="0.0.0.0"):
        self.host = host
        self.porta = porta
        self._jpeg = None
        self._versao = 0
        self._encerrado = False
        self._condicao = threading.Condition()
        self._servidor = None
        self._thread = None

    def iniciar(self):
        visualizador = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                caminho = self.path.split("?", 1)[0]
                if caminho == "/":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(visualizador.PAGINA)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(visualizador.PAGINA)
                elif caminho == "/stream.mjpg":
                    self._enviar_stream()
                elif caminho == "/snapshot.jpg":
                    self._enviar_snapshot()
                else:
                    self.send_error(404)

            def _enviar_snapshot(self):
                with visualizador._condicao:
                    jpeg = visualizador._jpeg
                if jpeg is None:
                    self.send_error(503, "Camera ainda sem imagem")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpeg)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(jpeg)

            def _enviar_stream(self):
                self.send_response(200)
                self.send_header(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                versao_enviada = -1
                try:
                    while True:
                        with visualizador._condicao:
                            visualizador._condicao.wait_for(
                                lambda: (
                                    visualizador._encerrado
                                    or visualizador._versao != versao_enviada
                                ),
                                timeout=5,
                            )
                            if visualizador._encerrado:
                                return
                            jpeg = visualizador._jpeg
                            versao_enviada = visualizador._versao
                        if jpeg is None:
                            continue
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                            + jpeg
                            + b"\r\n"
                        )
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, _format, *_args):
                # Evita uma linha no terminal para cada acesso do navegador.
                pass

        class Servidor(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self._servidor = Servidor((self.host, self.porta), Handler)
        self.porta = self._servidor.server_address[1]
        self._thread = threading.Thread(
            target=self._servidor.serve_forever,
            name="tria-visualizador-web",
            daemon=True,
        )
        self._thread.start()

    def atualizar(self, frame):
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ok:
            return False
        with self._condicao:
            self._jpeg = buffer.tobytes()
            self._versao += 1
            self._condicao.notify_all()
        return True

    def urls(self):
        urls = [f"http://127.0.0.1:{self.porta}"]
        try:
            conexao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                conexao.connect(("8.8.8.8", 80))
                ip_rede = conexao.getsockname()[0]
            finally:
                conexao.close()
            if ip_rede and not ip_rede.startswith("127."):
                urls.append(f"http://{ip_rede}:{self.porta}")
        except OSError:
            pass
        return urls

    def fechar(self):
        if self._servidor is None:
            return
        with self._condicao:
            self._encerrado = True
            self._condicao.notify_all()
        self._servidor.shutdown()
        self._servidor.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._servidor = None


def _desenhar_interface(
    frame, roi, localizacao, estado, ultima_mensagem,
    instrucao_saida="Q ou ESC: sair",
):
    """Desenha ROI, contorno da peça e estado do classificador."""
    exibicao = frame.copy()
    x, y, w, h = roi
    cor_roi = (0, 255, 0) if localizacao is not None else (0, 200, 255)
    cv2.rectangle(exibicao, (x, y), (x + w, y + h), cor_roi, 2)

    if localizacao is not None:
        box = localizacao["box"].copy()
        box[:, 0] += x
        box[:, 1] += y
        cv2.polylines(exibicao, [box], True, (0, 255, 0), 3)

    estado_tela = estado.replace("_", " ").upper()
    mensagem_tela = ultima_mensagem.replace("TRIÂNGULO", "TRIANGULO")
    cv2.rectangle(exibicao, (0, 0), (exibicao.shape[1], 76), (25, 25, 25), -1)
    cv2.putText(
        exibicao, f"Estado: {estado_tela}", (12, 27),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
    )
    cv2.putText(
        exibicao, mensagem_tela, (12, 55),
        cv2.FONT_HERSHEY_SIMPLEX, 0.62, cor_roi, 2,
    )
    cv2.putText(
        exibicao, instrucao_saida,
        (max(10, exibicao.shape[1] - 155), exibicao.shape[0] - 12),
        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
    )
    return exibicao


def main_loop(
    camera, mqtt_client, roi, intervalo_s=0.03, exibir=True,
    somente_web=False, porta_web=8081,
):
    """
    Loop principal: detecta passagem, classifica e publica via MQTT.
    Cada passagem confirmada gera no máximo um evento local (RNF05); QoS 1
    ainda pode reenviá-lo na rede. Três quadros ausentes encerram a passagem.
    As amostras permanecem em memória até a saída; uma peça parada por tempo
    indefinido na ROI exige intervenção do operador.
    """
    maquina = MaquinaDeEstados()
    frame_atual = capturar_quadro(camera)
    janela_ativa = _janela_disponivel(exibir and not somente_web)
    visualizador_web = None
    if exibir and (somente_web or not janela_ativa):
        try:
            visualizador_web = VisualizadorWeb(porta=porta_web)
            visualizador_web.iniciar()
            print("Visualização da câmera disponível no navegador:")
            for url in visualizador_web.urls():
                print(f"  {url}")
        except OSError as exc:
            visualizador_web = None
            print(f"Aviso: não foi possível iniciar a visualização web: {exc}")
    frames_presente = 0
    frames_ausente = 0
    numero_frame = 0
    historico_presenca = []
    amostras_peca = []
    ultima_mensagem = "Aguardando peca entrar completamente na ROI"

    print("TRIA - iniciando pipeline de captura. Ctrl+C para encerrar.")
    print(f"ROI: {roi}")
    if janela_ativa:
        print("Janela da câmera aberta. Pressione Q ou ESC para encerrar.")
    elif visualizador_web is not None:
        print("Abra um dos endereços acima; Ctrl+C encerra o programa.")

    try:
        while True:
            time.sleep(intervalo_s)
            frame_atual = capturar_quadro(camera)
            numero_frame += 1

            x, y, w, h = roi
            recorte = frame_atual[y:y + h, x:x + w]
            localizacao = localizar_peca_mdf(recorte)
            presente = localizacao is not None
            nova_peca = False

            if presente:
                frames_presente += 1
                frames_ausente = 0
                normalizada_atual = localizacao["normalizada"].copy()
                if maquina.estado == "livre":
                    historico_presenca.append(normalizada_atual)
                    historico_presenca = historico_presenca[
                        -FRAMES_CONFIRMAR_PRESENCA:
                    ]
            else:
                frames_ausente += 1
                frames_presente = 0
                if maquina.estado == "livre":
                    historico_presenca.clear()

            if (
                frames_presente >= FRAMES_CONFIRMAR_PRESENCA
                and maquina.ao_detectar_peca()
            ):
                nova_peca = True
                # Preserva os quadros usados na confirmação de entrada, sem
                # acrescentar novamente o quadro atual ao iniciar a passagem.
                amostras_peca = list(historico_presenca)
                historico_presenca.clear()
                print(f"\n[{time.strftime('%H:%M:%S')}] Peça {maquina.peca_atual} "
                      f"detectada na ROI - coletando amostras...")
                ultima_mensagem = "Peca detectada - coletando amostras"

            if (
                maquina.estado == "ocupado_aguardando"
                and presente
                and not nova_peca
            ):
                amostras_peca.append(normalizada_atual)

            if (
                frames_ausente >= FRAMES_CONFIRMAR_AUSENCIA
                and maquina.ocupada
            ):
                resultado = processar_amostras_peca(amostras_peca)
                if "erro" in resultado:
                    ultima_mensagem = resultado["erro"]
                    print(f"  Não foi possível classificar: {resultado['erro']}")
                else:
                    maquina.marcar_classificada()
                    ultima_mensagem = (
                        f"{resultado['classe']} -> Saida {resultado['destino']} "
                        f"({resultado['confianca']:.0%})"
                    )
                    print(
                        f"  classe={resultado['classe']} | "
                        f"destino={resultado['destino']} | "
                        f"defeito={resultado['defeito']} | "
                        f"confiança={resultado['confianca']:.0%} | "
                        f"{resultado['tempo_processamento_ms']} ms"
                    )
                    evento = publicar_classificacao(
                        mqtt_client,
                        classe=resultado["classe"],
                        destino=resultado["destino"],
                        defeito=resultado["defeito"],
                        tempo_processamento_ms=resultado["tempo_processamento_ms"],
                    )
                    print(f"  Evento: {evento['id_evento']}")
                maquina.ao_sair_peca()
                amostras_peca.clear()
                print(f"[{time.strftime('%H:%M:%S')}] Peça saiu da ROI - "
                      f"aguardando próximo ciclo.")
                if "erro" not in resultado:
                    ultima_mensagem = "Aguardando proxima peca"

            if janela_ativa or visualizador_web is not None:
                exibicao = _desenhar_interface(
                    frame_atual, roi, localizacao, maquina.estado, ultima_mensagem,
                    "Q ou ESC: sair" if janela_ativa else "Ctrl+C: sair",
                )

            if visualizador_web is not None:
                visualizador_web.atualizar(exibicao)

            if janela_ativa:
                try:
                    cv2.imshow("TRIA - Camera", exibicao)
                    tecla = cv2.waitKey(1) & 0xFF
                    if tecla in (ord("q"), ord("Q"), 27):
                        break
                    if cv2.getWindowProperty("TRIA - Camera", cv2.WND_PROP_VISIBLE) < 1:
                        break
                except cv2.error as exc:
                    print(f"Aviso: janela da câmera desativada: {exc}")
                    janela_ativa = False

    except KeyboardInterrupt:
        print("\nEncerrado pelo operador.")
    finally:
        publicar_status_pi(mqtt_client, ciclo_atual=maquina.total_eventos)
        if janela_ativa:
            cv2.destroyAllWindows()
        if visualizador_web is not None:
            visualizador_web.fechar()


def modo_simulacao(imagem_path, roi=None):
    """Modo de teste sem câmera: classifica uma imagem já salva."""
    frame = ler_imagem(imagem_path)
    if frame is None:
        print(f"Erro: não foi possível carregar {imagem_path}")
        sys.exit(1)

    print(f"Modo simulação - processando {imagem_path}")
    resultado = processar_peca(frame, roi)

    if "erro" in resultado:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps({
        "classe": resultado["classe"],
        "destino": resultado["destino"],
        "defeito": resultado["defeito"],
        "confianca": resultado["confianca"],
        "tempo_processamento_ms": resultado["tempo_processamento_ms"],
    }, ensure_ascii=False, indent=2))
    return 0


def processar_video(
    video_path, roi=None, exibir=False, somente_web=False, porta_web=8081,
    tempo_real=False,
):
    """
    Executa o mesmo detector de passagem sobre um vídeo gravado.

    Não publica MQTT, para que um ensaio nunca mova o atuador. Retorna os
    eventos na ordem em que foram detectados, permitindo comparar o resultado
    com o gabarito do vídeo.
    """
    captura = cv2.VideoCapture(str(video_path))
    if not captura.isOpened():
        return {"erro": f"Não foi possível abrir o vídeo: {video_path}"}

    fps = captura.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = float(FRAMERATE)

    ok, frame = captura.read()
    if not ok or frame is None:
        captura.release()
        return {"erro": f"O vídeo não possui quadros legíveis: {video_path}"}

    try:
        roi_video = validar_roi(roi, frame.shape) if roi else definir_roi(frame.shape)
    except ValueError as exc:
        captura.release()
        return {"erro": str(exc)}

    janela_ativa = _janela_disponivel(exibir and not somente_web)
    visualizador_web = None
    if exibir and (somente_web or not janela_ativa):
        try:
            visualizador_web = VisualizadorWeb(porta=porta_web)
            visualizador_web.iniciar()
            print("Reprodução do vídeo disponível no navegador:")
            for url in visualizador_web.urls():
                print(f"  {url}")
        except OSError as exc:
            print(f"Aviso: não foi possível iniciar a visualização web: {exc}")

    maquina = MaquinaDeEstados()
    frames_presente = 0
    frames_ausente = 0
    numero_frame = 0
    historico_presenca = []
    amostras_peca = []
    ultimo_frame_peca = 0
    eventos = []
    ultima_mensagem = "Aguardando peca entrar completamente na ROI"
    interrompido = False

    def finalizar_peca_video():
        """Fecha a passagem atual, inclusive quando o vídeo acaba com a peça na ROI."""
        nonlocal ultima_mensagem, ultimo_frame_peca
        resultado = processar_amostras_peca(amostras_peca)
        if "erro" in resultado:
            ultima_mensagem = resultado["erro"]
        else:
            maquina.marcar_classificada()
            ultima_mensagem = (
                f"{resultado['classe']} -> Saida {resultado['destino']} "
                f"({resultado['confianca']:.0%})"
            )
            evento = {
                "ordem": len(eventos) + 1,
                "frame": ultimo_frame_peca,
                "tempo_video_s": round((ultimo_frame_peca - 1) / fps, 3),
                "classe": resultado["classe"],
                "destino": resultado["destino"],
                "confianca": resultado["confianca"],
                "tempo_processamento_ms": resultado["tempo_processamento_ms"],
            }
            eventos.append(evento)
            print(
                f"  [{evento['tempo_video_s']:7.2f}s] "
                f"{evento['classe']} -> {evento['destino']} "
                f"({evento['tempo_processamento_ms']} ms)"
            )
        maquina.ao_sair_peca()
        amostras_peca.clear()
        ultimo_frame_peca = 0
        if "erro" not in resultado:
            ultima_mensagem = "Aguardando proxima peca"

    try:
        while ok and frame is not None:
            inicio_frame = time.perf_counter()
            numero_frame += 1

            x, y, w, h = roi_video
            recorte = frame[y:y + h, x:x + w]
            localizacao = localizar_peca_mdf(recorte)
            presente = localizacao is not None
            nova_peca = False

            if presente:
                frames_presente += 1
                frames_ausente = 0
                normalizada_atual = localizacao["normalizada"].copy()
                if maquina.estado == "livre":
                    historico_presenca.append(normalizada_atual)
                    historico_presenca = historico_presenca[
                        -FRAMES_CONFIRMAR_PRESENCA:
                    ]
            else:
                frames_ausente += 1
                frames_presente = 0
                if maquina.estado == "livre":
                    historico_presenca.clear()

            if (
                frames_presente >= FRAMES_CONFIRMAR_PRESENCA
                and maquina.ao_detectar_peca()
            ):
                nova_peca = True
                amostras_peca = list(historico_presenca)
                historico_presenca.clear()
                ultimo_frame_peca = numero_frame
                ultima_mensagem = "Peca detectada - coletando amostras"

            if (
                maquina.estado == "ocupado_aguardando"
                and presente
                and not nova_peca
            ):
                amostras_peca.append(normalizada_atual)
                ultimo_frame_peca = numero_frame

            if (
                frames_ausente >= FRAMES_CONFIRMAR_AUSENCIA
                and maquina.ocupada
            ):
                finalizar_peca_video()

            if janela_ativa or visualizador_web is not None:
                exibicao = _desenhar_interface(
                    frame, roi_video, localizacao, maquina.estado,
                    ultima_mensagem,
                    "Q ou ESC: sair" if janela_ativa else "Ctrl+C: sair",
                )
                cv2.putText(
                    exibicao,
                    f"Video: {numero_frame / fps:.1f}s | Eventos: {len(eventos)}",
                    (12, exibicao.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1,
                )
                if visualizador_web is not None:
                    visualizador_web.atualizar(exibicao)

            espera_ms = 1
            if tempo_real:
                gasto_ms = (time.perf_counter() - inicio_frame) * 1000
                espera_ms = max(1, round(1000 / fps - gasto_ms))

            if janela_ativa:
                tecla = cv2.waitKey(espera_ms) & 0xFF
                if tecla in (ord("q"), ord("Q"), 27):
                    interrompido = True
                    break
            elif tempo_real:
                time.sleep(espera_ms / 1000)

            ok, frame = captura.read()

        if not interrompido and maquina.ocupada:
            finalizar_peca_video()
    except KeyboardInterrupt:
        interrompido = True
    finally:
        captura.release()
        if janela_ativa:
            cv2.destroyWindow("TRIA - Camera")
        if visualizador_web is not None:
            visualizador_web.fechar()

    return {
        "video": str(video_path),
        "fps": round(fps, 3),
        "frames_processados": numero_frame,
        "duracao_processada_s": round(numero_frame / fps, 3),
        "roi": roi_video,
        "eventos": eventos,
        "interrompido": interrompido,
    }


def modo_video(
    video_path, roi=None, exibir=True, somente_web=False, porta_web=8081,
):
    """Reproduz um ensaio gravado e mostra as classificações encontradas."""
    print(f"Modo vídeo - processando {video_path}")
    resultado = processar_video(
        video_path,
        roi=roi,
        exibir=exibir,
        somente_web=somente_web,
        porta_web=porta_web,
        tempo_real=exibir,
    )
    if "erro" in resultado:
        print(f"Erro: {resultado['erro']}")
        return 2

    print("\nSequência detectada:")
    if resultado["eventos"]:
        for evento in resultado["eventos"]:
            print(f"  {evento['ordem']:02d}. {evento['classe']}")
    else:
        print("  Nenhuma peça classificada.")
    print(
        f"Resumo: {len(resultado['eventos'])} evento(s), "
        f"{resultado['frames_processados']} frames, "
        f"{resultado['duracao_processada_s']:.2f}s de vídeo."
    )
    return 0


def definir_roi(frame_shape):
    """ROI central por padrão (50% da largura central, altura útil)."""
    altura, largura = frame_shape[:2]
    w = int(largura * 0.5)
    h = int(altura * 0.8)
    x = (largura - w) // 2
    y = (altura - h) // 2
    return (x, y, w, h)


def validar_roi(roi, frame_shape):
    """Valida a ROI para evitar recortes vazios ou fora do quadro."""
    altura, largura = frame_shape[:2]
    x, y, w, h = roi
    if x < 0 or y < 0 or w <= 0 or h <= 0:
        raise ValueError("a ROI deve usar X/Y >= 0 e largura/altura > 0")
    if x + w > largura or y + h > altura:
        raise ValueError(
            f"a ROI {roi} ultrapassa o quadro de {largura}x{altura}"
        )
    return roi


def main():
    parser = argparse.ArgumentParser(
        description="TRIA - pipeline principal do Pi", allow_abbrev=False
    )
    fonte = parser.add_mutually_exclusive_group()
    fonte.add_argument(
        "--imagem", "--image", dest="imagem",
        help="modo simulação: classifica uma imagem estática",
    )
    fonte.add_argument(
        "--video", dest="video",
        help="reproduz um vídeo gravado pelo pipeline da ROI",
    )
    parser.add_argument("--roi", nargs=4, type=int, metavar=("X", "Y", "W", "H"),
                        help="região de interesse (default: central)")
    parser.add_argument(
        "--sem-mqtt", action="store_true",
        help="executa a visão mesmo sem broker MQTT",
    )
    parser.add_argument(
        "--sem-janela", action="store_true",
        help="não abre a visualização ao vivo da câmera",
    )
    parser.add_argument(
        "--web", "--navegador", action="store_true",
        help="usa o navegador em vez da janela do OpenCV",
    )
    parser.add_argument(
        "--porta-web", type=int, default=8081, metavar="PORTA",
        help="porta da visualização web (default: 8081)",
    )
    args = parser.parse_args()

    if not 1 <= args.porta_web <= 65535:
        parser.error("--porta-web deve estar entre 1 e 65535")

    roi_configurada = tuple(args.roi) if args.roi else None

    if args.imagem:
        frame = ler_imagem(args.imagem)
        if frame is None:
            print(f"Erro: não foi possível carregar {args.imagem}")
            return 1
        try:
            roi = validar_roi(roi_configurada, frame.shape) if roi_configurada else None
        except ValueError as exc:
            print(f"Erro: {exc}")
            return 1
        return modo_simulacao(args.imagem, roi)

    if args.video:
        roi = roi_configurada
        return modo_video(
            args.video,
            roi=roi,
            exibir=not args.sem_janela,
            somente_web=args.web,
            porta_web=args.porta_web,
        )

    if not PICAMERA_DISPONIVEL:
        print("Picamera2 não disponível neste ambiente (necessário Raspberry Pi).")
        return 1

    camera = None
    try:
        camera = Picamera2()
        config = camera.create_video_configuration(
            main={"size": RESOLUCAO, "format": "RGB888"},
            controls={"FrameRate": FRAMERATE},
        )
        camera.configure(config)
        camera.start()
        time.sleep(0.5)
    except Exception as exc:
        print(f"Falha ao abrir a câmera: {exc}")
        if camera is not None:
            camera.close()
        return 1

    try:
        frame_inicial = capturar_quadro(camera)
        roi = validar_roi(
            roi_configurada or definir_roi(frame_inicial.shape),
            frame_inicial.shape,
        )
    except Exception as exc:
        print(f"Falha ao inicializar câmera: {exc}")
        camera.stop()
        return 1

    mqtt_client = None
    if not args.sem_mqtt:
        try:
            mqtt_client = create_client()
        except (ConnectionError, OSError, RuntimeError) as exc:
            print(f"Aviso: MQTT indisponível ({exc}). Continuando sem MQTT.")

    try:
        main_loop(
            camera, mqtt_client, roi,
            exibir=not args.sem_janela,
            somente_web=args.web,
            porta_web=args.porta_web,
        )
    finally:
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        camera.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
