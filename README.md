# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso do programa **PNAAT 2026** (Programa Nacional de Aprendizagem Acelerada em Tecnologia).

## Visão Geral

O **TRIA** é uma Prova de Conceito (PoC) física que valida experimentalmente a cadeia:

**pré-separação física → esteira → captura → classificação → MQTT → atuação do servo → três destinos físicos → registro e visualização no MING**

A solução ataca o **Cenário 2** do documento de Cenários: triagem de diferentes componentes misturados em uma linha de manufatura, com peças em posições variadas, em contato ou parcialmente sobrepostas.

### Arquitetura da PoC

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUXO FÍSICO                                 │
│                                                                     │
│  [Entrada] → [Pré-separador Vibratório] → [Esteira] → [Câmera]    │
│       ↓                                                           │
│  [Raspberry Pi 5 - Classificação]                                  │
│       ↓                                                           │
│  [Servo Desviador] → [Saída A] [Saída B] [Saída C]                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        FLUXO DE DADOS (MING)                       │
│                                                                     │
│  Raspberry Pi 5  →  Mosquitto/MQTT  →  ESP32 (servo + OLED)       │
│                        ↓                                            │
│                    Node-RED (validação)                             │
│                        ↓                                            │
│                    InfluxDB (série temporal)                        │
│                        ↓                                            │
│                    Grafana (dashboard)                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Situação visual e destino

| Visual | Decisão | Destino físico |
|--------|---------|----------------|
| QUADRADO | Peça normal | Saída A - Quadrado |
| TRIÂNGULO | Peça normal | Saída B - Triângulo |
| QUADRADO COM X | Peça defeituosa | Saída C - Descarte |

## Estrutura do Repositório

```
TCC-PNAAT/
├── docs/                          Documentação acadêmica
│   ├── TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf
│   ├── Cenários.pdf
│   └── Apostila ... PNAAT 2026.pdf
│
├── pi/                            Código Python (visão computacional - Raspberry Pi)
│   ├── classifier.py              OpenCV: contornos, vértices, detecção de X
│   ├── mqtt_publisher.py          Publica decisões e status nos tópicos MQTT
│   ├── config.py                  Configurações centralizadas
│   ├── requirements.txt           Dependências Python
│   └── tests/
│       └── test_classifier.py     Testes locais (sem hardware)
│
├── esp32/                         Firmware ESP32 (nó de atuação)
│   ├── platformio.ini             Configuração PlatformIO
│   └── src/
│       └── main.cpp               Arduino: servo, OLED, MQTT, watchdog
│
├── ming/                          Stack MING (Docker Compose)
│   ├── docker-compose.yml         Mosquitto, Node-RED, InfluxDB, Grafana
│   ├── mosquitto/
│   │   └── mosquitto.conf         Configuração do broker MQTT
│   ├── nodered/
│   │   └── flows.json             Fluxo de validação e deduplicação
│   └── grafana/
│       └── datasources/
│           └── influxdb.yml       DataSource InfluxDB (auto-provisioning)
│
├── .gitignore
├── README.md
└── LICENSE
```

## Componentes

### Raspberry Pi (visão computacional)

- **classifier.py** - Classifica as 3 situações visuais usando OpenCV:
  - Detecção de contornos e vértices (approxPolyDP)
  - Hough Line Transform para detectar a marca X contrastante
  - Reanálise automática com parâmetros alternativos
- **mqtt_publisher.py** - Publica nos tópicos MQTT:
  - `tria/triagem` - resultado da inspeção (payload mínimo: id_evento, horario, classe, destino, defeito)
  - `tria/status/pi` - disponibilidade do processo de visão
- **config.py** - Configurações de tópicos, parâmetros, calibração

### ESP32 (nó de atuação - Heltec WiFi LoRa 32 V3)

- Assina `tria/triagem` e move o servo para a posição calibrada (A/B/C)
- Exibe classe, destino e estado no OLED integrado
- Publica confirmação em `tria/atuador` e estado em `tria/status/esp32`
- Watchdog de comunicação: OLED indica indisponibilidade se sem mensagem por >15s

### Stack MING (Docker)

- **Mosquitto** - Broker MQTT local (portas 1883/9001 WebSocket)
- **Node-RED** - Valida campos, evita reprocessamento de IDs conhecidos, grava no InfluxDB
- **InfluxDB** - Armazena cada evento de triagem como registro temporal
- **Grafana** - Dashboard: totais, classes, defeitos, destinos, histórico, estado de comunicação

## Tópicos MQTT

| Tópico | Publica | Assina | Conteúdo |
|--------|---------|--------|----------|
| `tria/triagem` | Raspberry Pi | ESP32, Node-RED | Resultado da inspeção e destino |
| `tria/status/pi` | Raspberry Pi | Node-RED | Disponibilidade do processo de visão |
| `tria/status/esp32` | ESP32 | Node-RED, Pi (opcional) | Conexão do nó de atuação |
| `tria/atuador` | ESP32 | Raspberry Pi, Node-RED | Confirmação vinculada ao id_evento |

## Payload MQTT (tria/triagem)

```json
{
  "id_evento": "pi-abc123def456",
  "horario": "2026-09-08T10:30:00",
  "classe": "QUADRADO",
  "destino": "A",
  "defeito": false,
  "instante_atuacao": 3.3,
  "tempo_processamento_ms": 45
}
```

## Requisitos e Critérios de Aceite

### Funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RF01 | Detectar passagem e capturar | 19/20 ciclos válidos |
| RF02 | Classificar quadrado e triângulo | >= 18/20 para cada classe |
| RF03 | Identificar quadrado com X | >= 18/20 como defeito |
| RF04 | Comunicar via MQTT | >= 29/30 eventos consistentes |
| RF05 | Posicionar servo corretamente | >= 27/30 comandos |
| RF06 | Encaminhar fisicamente | >= 27/30 peças na saída correta |
| RF07 | Pré-separação por vibração | >= 8/10 chegadas separadas |
| RF08 | Registrar no InfluxDB | 30/30 registros sem perda |
| RF09 | Apresentar no Grafana | Painéis conferem com InfluxDB |
| RF10 | Fluxo completo | >= 13/15 ciclos completos |

### Não-funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RNF01 | Preparar atuação no prazo | Servo estabiliza com >= 0,3s margem |
| RNF02 | Consistência da comunicação | >= 29/30 entregas válidas |
| RNF03 | Operar continuamente | 15 minutos ou 30 peças sem reinício |
| RNF04 | Recuperar comunicação | Reconectar em <= 30s, sem executar comando antigo |
| RNF05 | Não duplicar contagens | 30 IDs únicos, sem duplicatas |
| RNF06 | Funcionar localmente | 15 minutos sem Internet |

## Rodar

### 1. Classificador (Raspberry Pi)

```bash
cd pi
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python tests/test_classifier.py
```

### 2. Stack MING

```bash
cd ming
docker compose up -d
# Verificar: http://localhost:3000 (Grafana)
# Verificar: http://localhost:1880 (Node-RED)
```

### 3. Firmware ESP32

```bash
cd esp32
# Instalar PlatformIO CLI (https://platformio.org/install/cli)
# Editar WIFI_SSID, WIFI_PASSWORD e MQTT_SERVER em src/main.cpp
pio run -t upload
```

## Tecnologias

| Categoria | Tecnologia | Uso |
|-----------|------------|-----|
| Computador single-board | Raspberry Pi 5 (8 GB) | Captura e processamento |
| Câmera | CSI Camera V1.3 (5 MP) | Captura da região de inspeção |
| Visão computacional | OpenCV (Python) | Detecção de contornos, análise de forma, Hough |
| Captura de imagem | Picamera2 (Python) | Interface com câmera CSI |
| Nó de atuação | ESP32-S3 (Heltec WiFi LoRa 32 V3) | Servo, OLED, MQTT |
| Messaging | MQTT (Mosquitto local) | Comunicação Pi ↔ ESP32 ↔ Node-RED |
| Integração | Node-RED | Valiação, transformação, deduplicação |
| Banco temporal | InfluxDB | Série temporal de eventos |
| Dashboard | Grafana | Visualização de indicadores |
| Orquestração | Docker Compose | Stack MING reproduzível |

## Escopo

### Incluído
- Pré-separação vibratória (mecânica a definir)
- Classificação de 3 situações visuais com OpenCV
- Deteção de marca X contrastante (defeito)
- Comunicação MQTT local entre Pi, ESP32 e Node-RED
- Atuação com servo de 3 posições
- Dashboard com totais, classes, defeitos e histórico
- Registro temporal de todos os eventos

### Fora de escopo
- Certificação industrial / normas de segurança
- Integração com CLP, MES, ERP ou nuvem
- Reconhecimento de peças arbitrárias ou Deep Learning
- Sensor óptico, encoder ou sensor de presença dedicado

## Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS and Claylton-Muniz
