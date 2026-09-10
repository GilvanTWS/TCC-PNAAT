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

# Parâmetros de classificação
LIMIAR_CONFIANCA = 0.7
LIMIAR_AREA_MINIMA = 500
LIMIAR_CIRCULARIDADE = 0.7
MAX_TENTATIVAS = 3

# Parâmetros de reanálise
PARAMETROS_REANALISE = [
    {"binarizacao": 127, "epsilon_ratio": 0.04},
    {"binarizacao": 100, "epsilon_ratio": 0.04},
    {"binarizacao": 150, "epsilon_ratio": 0.06},
]

# Câmera
RESOLUCAO = (640, 480)
FRAMERATE = 30

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
