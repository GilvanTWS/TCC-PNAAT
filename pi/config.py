"""
TRIA - Configurações do Classificador
"""

# MQTT
MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_PORT = 1883
TOPICO_SEPARACAO = "esteira/separacao"

# Classificação
CLASSES = {
    "A": "circular",
    "B": "quadrada",
    "C": "triangular",
    "R": "revisão",
    "D": "descarte"
}

# Thresholds de confiança
LIMIAR_CONFIANCA = 0.7
MAX_TENTATIVAS_REVISAO = 3

# Câmera
RESOLUCAO = (640, 480)
