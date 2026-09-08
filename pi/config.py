"""
TRIA - Configurações do Classificador
"""

MQTT_BROKER = "broker.mqttdashboard.com"
MQTT_PORT = 1883
TOPICO_SEPARACAO = "esteira/separacao"

CLASSES = {
    "A": "circular",
    "B": "quadrada",
    "C": "triangular",
    "R": "revisão",
    "D": "descarte"
}

LIMIAR_CONFIANCA = 0.7
MAX_TENTATIVAS_REVISAO = 3

RESOLUCAO = (640, 480)
