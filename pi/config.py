"""
TRIA - Configurações do Classificador
"""

# MQTT
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
TOPICO_CLASSIFICACAO = "tria/classificacao"
TOPICO_COMANDO = "tria/comando"

# Classificação
CLASSES = {
    "A": "circular",
    "B": "quadrada",
    "C": "triangular"
}

# Thresholds de confiança
LIMIAR_CONFIANCA = 0.7
MAX_TENTATIVAS_REVISAO = 3

# Câmera
RESOLUCAO = (640, 480)
