"""
TRIA - Triagem Visual Integrada de Componentes
Publicador MQTT - Raspberry Pi
PoC Física - Levantamento de Requisitos
"""

import json
from datetime import datetime
from uuid import uuid4

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from config import (
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_KEEPALIVE,
    TOPICO_TRIAGEM,
    TOPICO_STATUS_PI,
    VELOCIDADE_ESTEIRA_M_S,
    DISTANCIA_CAMERA_DESVIADOR_M,
    MARGEM_SEGURANCA_S,
)


def calcular_instante_atuacao():
    """
    Calcula o tempo estimado para a peça chegar ao desviador.
    Baseado em distância e velocidade da esteira + margem de segurança.
    
    Retorna duração em segundos, não timestamp. Este campo é informativo:
    o ESP32 atua imediatamente e não usa esta estimativa para agendamento.
    """
    tempo_percurso = DISTANCIA_CAMERA_DESVIADOR_M / VELOCIDADE_ESTEIRA_M_S
    return round(tempo_percurso + MARGEM_SEGURANCA_S, 2)


def publicar_classificacao(client, classe, destino, defeito=False, tempo_processamento_ms=None):
    """
    Publica a decisão da classificação no tópico tria/triagem.
    
    Payload mínimo conforme levantamento:
    id_evento, horario, classe, destino, defeito

    Retorna o payload mesmo em timeout: retorno não comprova entrega. QoS 1
    admite reentrega; PUBACK confirma o broker, não movimento nem escrita no
    InfluxDB. O horário usa o relógio local; sincronize os nós antes do ensaio.
    
    Args:
        client: cliente paho.mqtt já conectado
        classe: 'QUADRADO', 'TRIÂNGULO' ou 'QUADRADO_COM_X'
        destino: 'A', 'B' ou 'C'
        defeito: True se a peça tem a marca X
        tempo_processamento_ms: tempo de processamento (opcional)
    """
    payload = {
        "id_evento": f"pi-{uuid4().hex[:12]}",
        "horario": datetime.now().isoformat(),
        "classe": classe,
        "destino": destino,
        "defeito": defeito,
        "instante_atuacao": calcular_instante_atuacao(),
    }

    if tempo_processamento_ms is not None:
        payload["tempo_processamento_ms"] = tempo_processamento_ms

    if client is None:
        print(f"[MQTT desativado] Evento local: {json.dumps(payload, ensure_ascii=False)}")
        return payload

    result = client.publish(TOPICO_TRIAGEM, json.dumps(payload), qos=1)
    try:
        result.wait_for_publish(timeout=2.0)
    except (RuntimeError, ValueError) as exc:
        print(f"Aviso: evento não confirmado pelo MQTT: {exc}")
    else:
        if result.is_published():
            print(f"[{datetime.now().isoformat()}] Publicado em {TOPICO_TRIAGEM}: {json.dumps(payload, ensure_ascii=False)}")
        else:
            print("Aviso: tempo esgotado aguardando confirmação do MQTT.")
    return payload


def publicar_status_pi(client, versao_calibracao="1.0", ciclo_atual=0):
    """
    Publica status de disponibilidade do processo de visão.
    Tópico: tria/status/pi

    Mantido como diagnóstico legado: disponivel é fixo e não existe heartbeat
    ou Last Will neste cliente. Não usar isoladamente como indicador de saúde.
    
    Args:
        client: cliente paho.mqtt já conectado
        versao_calibracao: versão da calibração atual
        ciclo_atual: número do último ciclo processado
    """
    payload = {
        "id_evento": f"pi-status-{uuid4().hex[:8]}",
        "horario": datetime.now().isoformat(),
        "disponivel": True,
        "ultimo_ciclo": ciclo_atual,
        "versao_calibracao": versao_calibracao,
        "ultima_classificacao": "",
        "ultimo_destino": "",
    }

    if client is None:
        return payload

    result = client.publish(TOPICO_STATUS_PI, json.dumps(payload), qos=1, retain=True)
    try:
        result.wait_for_publish(timeout=2.0)
    except (RuntimeError, ValueError) as exc:
        print(f"Aviso: status não confirmado pelo MQTT: {exc}")
        return payload
    if result.is_published():
        print(f"Status do Pi publicado em {TOPICO_STATUS_PI}: {json.dumps(payload)}")
    else:
        print("Aviso: tempo esgotado aguardando status do MQTT.")
    return payload


def create_client():
    """Cria e conecta o cliente MQTT ao broker local (Mosquitto)."""
    if mqtt is None:
        raise RuntimeError("pacote paho-mqtt não instalado")
    client = mqtt.Client(
        client_id=f"tria-pi-{uuid4().hex[:8]}",
        protocol=mqtt.MQTTv311,
    )
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
    client.loop_start()
    return client


def publicar_imagem_evidencia(client, image_path, classe, destino, defeito):
    """
    Registra uma evidência de classificação (imagem ou log).
    Gera um novo ID e envia apenas o caminho, sem transferir a imagem.
    Não é chamada pelo laço de captura. Como usa tria/triagem, também comanda
    o atuador; não chamar após publicar_classificacao para a mesma passagem.
    
    Args:
        client: cliente paho.mqtt já conectado
        image_path: caminho da imagem
        classe: classe detectada
        destino: destino físico
        defeito: booleano
    """
    payload = {
        "id_evento": f"pi-ev-{uuid4().hex[:12]}",
        "horario": datetime.now().isoformat(),
        "classe": classe,
        "destino": destino,
        "defeito": defeito,
        "imagem": image_path,
        "versao_calibracao": "1.0",
        "qualidade_segmentacao": 0.0,  # placeholder; não é uma medição calculada
    }

    if client is None:
        print(f"[MQTT desativado] Evidência local: {json.dumps(payload)}")
        return payload

    result = client.publish(TOPICO_TRIAGEM, json.dumps(payload), qos=1)
    result.wait_for_publish(timeout=2.0)
    if result.is_published():
        print(f"Evidência publicada: {json.dumps(payload)}")
    else:
        print("Aviso: tempo esgotado aguardando evidência do MQTT.")
    return payload


if __name__ == "__main__":
    client = create_client()
    try:
        print("Publicador TRIA pronto (broker local Mosquitto). Ctrl+C para encerrar.")
        while True:
            print("\nClasses disponíveis:")
            print("  1. QUADRADO")
            print("  2. TRIÂNGULO")
            print("  3. QUADRADO COM X (defeito)")
            print("  0. Publicar status do Pi")
            print("  Entrar vazio para sair")
            opcao = input("Opção: ").strip()

            if opcao == "":
                break
            elif opcao == "1":
                publicar_classificacao(client, "QUADRADO", "A", defeito=False)
            elif opcao == "2":
                publicar_classificacao(client, "TRIÂNGULO", "B", defeito=False)
            elif opcao == "3":
                publicar_classificacao(client, "QUADRADO_COM_X", "C", defeito=True)
            elif opcao == "0":
                publicar_status_pi(client)
            else:
                print("Opção inválida.")
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
