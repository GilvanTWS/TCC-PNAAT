"""
TRIA - Configurações do Sistema
PoC Física - Levantamento de Requisitos
"""

# MQTT - Broker Local (Mosquitto)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# Tópicos MQTT (definidos no levantamento)
TOPICO_TRIAGEM = "tria/triagem"
TOPICO_STATUS_PI = "tria/status/pi"
TOPICO_STATUS_ESP32 = "tria/status/esp32"
TOPICO_ATUADOR = "tria/atuador"

# Classes de peças (3 situações visuais)
CLASSES = {
    "QUADRADO": {"destino": "A", "descricao": "Peça normal - Saída A"},
    "TRIÂNGULO": {"destino": "B", "descricao": "Peça normal - Saída B"},
    "QUADRADO_COM_X": {"destino": "C", "descricao": "Peça defeituosa - Saída C (Descarte)"},
}

# Destinos físicos
DESTINOS = {
    "A": "Saída A - Quadrado",
    "B": "Saída B - Triângulo",
    "C": "Saída C - Descarte",
}

# Compatibilidade com a função auxiliar detect_contours
LIMIAR_AREA_MINIMA = 500

# Segmentação da placa de MDF. A placa é localizada pela sua faixa de cor
# (marrom/bege), corrigida por perspectiva e só depois a marca é analisada.
# O MDF e a esteira podem ter valores (brilho) muito parecidos quando a câmera
# ajusta automaticamente a exposição. A saturação e o matiz são bem mais
# estáveis: o MDF fica amarelo/ocre, enquanto a esteira permanece quase neutra.
# Não limite S/V no topo (255), pois isso fazia placas bem iluminadas sumirem.
HSV_MDF_MIN = (5, 80, 30)
HSV_MDF_MAX = (28, 255, 255)
AREA_PECA_FRAME_MIN = 0.008       # 0,8% da ROI
AREA_PECA_FRAME_MAX = 0.85        # aceita peça próxima sem selecionar o fundo
ASPECTO_PECA_MAX = 2.4
PREENCHIMENTO_PECA_MIN = 0.45
TAMANHO_PECA_NORMALIZADA = 400
TAMANHO_MAX_PROCESSAMENTO = 900
MARGEM_MARCA = 0.15               # ignora 15% das bordas da placa
AREA_MARCA_NORMALIZADA_MIN = 0.015

# Câmera
RESOLUCAO = (640, 480)
FRAMERATE = 30
FRAMES_CONFIRMAR_PRESENCA = 3
FRAMES_CONFIRMAR_AUSENCIA = 3

# Calibração do desviador (ângulos em graus - ajustar na montagem)
ANGULOS_DESVIADOR = {
    "A": 45,   # Posição calibrada para Saída A
    "B": 90,   # Posição calibrada para Saída B
    "C": 135,  # Posição calibrada para Saída C
}

# Temporização (metros - ajustar na montagem)
DISTANCIA_CAMERA_DESVIADOR_M = 0.3  # metros
VELOCIDADE_ESTEIRA_M_S = 0.1        # m/s
MARGEM_SEGURANCA_S = 0.3            # segundos antes da peça

# ESP32
ESP32_ID = "esp32-tria-01"
