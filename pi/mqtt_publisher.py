"""
TRIA - Triagem Visual Integrada de Componentes
Publicador MQTT - Raspberry Pi
"""

import json
from datetime import datetime
from uuid import uuid4

import paho.mqtt.client as mqtt

from config import MQTT_BROKER, MQTT_PORT, TOPICO_SEPARACAO


def publish_classification(client, destino, image_path=None):
    """
    Publica o resultado da classificação no tópico que o site escuta.

    Args:
        client: cliente paho.mqtt já conectado
        destino: 'A', 'B', 'C', 'R' ou 'D'
        image_path: caminho da imagem analisada (opcional, usado no payload)
    """
    payload = {
        "id_evento": f"pi-{uuid4().hex[:12]}",
        "destino": destino,
        "timestamp": datetime.now().isoformat(),
    }
    if image_path:
        payload["imagem"] = image_path

    result = client.publish(TOPICO_SEPARACAO, json.dumps(payload), qos=1)
    result.wait_for_publish()
    print(f"Publicado em {TOPICO_SEPARACAO}: {json.dumps(payload)}")


def create_client() -> mqtt.Client:
    """Cria e conecta o cliente MQTT ao broker."""
    client = mqtt.Client(
        client_id=f"tria-pi-{uuid4().hex[:8]}",
        protocol=mqtt.MQTTv311,
    )
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    client.loop_start()
    return client


if __name__ == "__main__":
    client = create_client()
    try:
        print("Publicador TRIA pronto. Ctrl+C para encerrar.")
        while True:
            destino = input("Destino (A/B/C/R/D): ").strip().upper()
            if destino in ("A", "B", "C", "R", "D"):
                publish_classification(client, destino)
            elif destino == "":
                break
            else:
                print("Destino inválido. Use A, B, C, R ou D.")
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()