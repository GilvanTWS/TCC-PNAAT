"""
TRIA - Triagem Visual Integrada de Componentes
Publicador MQTT - Raspberry Pi
"""

import json
from datetime import datetime


# Tópicos MQTT (simplificados)
TOPICO_CLASSIFICACAO = "tria/classificacao"
TOPICO_COMANDO = "tria/comando"


def publish_classification(classification, confidence):
    """
    Publica o resultado da classificação nos tópicos MQTT.

    Args:
        classification: 'A', 'B', 'C', 'review', 'discard'
        confidence: nível de confiança (0.0 a 1.0)
    """
    payload = {
        "tipo": classification,
        "confianca": confidence,
        "timestamp": datetime.now().isoformat()
    }

    # TODO: Implementar publicação MQTT
    print(f"Publicando: {json.dumps(payload)}")
