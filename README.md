# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso — Capacitação **PNAAT 2026** (Programa Nacional de Aprendizagem Acelerada em Tecnologia).
**Equipe:** Os guri do pinati.

## Sumário

- [1. Visão Geral](#1-visão-geral)
- [2. Arquitetura da PoC](#2-arquitetura-da-poc)
- [3. Situação visual e destino](#3-situação-visual-e-destino)
- [4. Estrutura do Repositório](#4-estrutura-do-repositório)
- [5. Componentes](#5-componentes)
- [6. Tópicos MQTT](#6-tópicos-mqtt)
- [7. Payload MQTT](#7-payload-mqtt)
- [8. Requisitos e Critérios de Aceite](#8-requisitos-e-critérios-de-aceite)
- [9. Dependências](#9-dependências)
- [10. Como Rodar](#10-como-rodar)
- [11. Escopo](#11-escopo)
- [12. Licença](#12-licença)
- [13. Checklist de Conformidade](#13-checklist-de-conformidade)

## 1. Visão Geral

O **TRIA** é uma Prova de Conceito (PoC) física que valida experimentalmente a cadeia:

**pré-separação física → esteira → captura → classificação → MQTT → atuação do servo → três destinos físicos → registro e visualização no MING**

A solução ataca o **Cenário 2** do documento de Cenários: triagem de diferentes componentes misturados em uma linha de manufatura, com peças em posições variadas, em contato ou parcialmente sobrepostas.

O sistema integra **Visão Computacional** na borda (Raspberry Pi 5) e **Atuação Física via IoT** (ESP32-S3), orquestrados por uma arquitetura MQTT e monitorados pela **Stack MING** (Mosquitto, Node-RED, InfluxDB e Grafana).

As **3 situações visuais** das peças de ensaio (MDF):
- **QUADRADO** — peça normal (Saída A);
- **TRIÂNGULO** — peça normal (Saída B);
- **QUADRADO COM X** — peça defeituosa, com marca X contrastante no centro (Saída C, descarte).

## 2. Arquitetura da PoC

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUXO FÍSICO                                 │
│                                                                     │
│  [Entrada] → [Pré-separador Vibratório] → [Esteira] → [Câmera]    │
│       ↓                                                           │
│  [Raspberry Pi 5 - Classificação da peça/marca X]                  │
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

### Elementos de hardware e software e fluxo entre eles

| Nó | Tipo | Papel na solução |
|----|------|------------------|
| Pré-separador vibratório + esteira | Hardware (sensoriamento) | Reduz contato/sobreposição e transporta a peça |
| Câmera CSI V1.3 | Hardware (sensoriamento) | Captura a região de inspeção (entrada da visão) |
| Raspberry Pi 5 + Picamera2/OpenCV | Hardware + software (processamento) | Segmenta o contorno e classifica a peça/marca X |
| Mosquitto / MQTT | Software (conectividade) | Distribui a decisão entre Pi, ESP32 e Node-RED |
| ESP32-S3 + servo + OLED | Hardware + software (atuação IoT) | Posiciona o desviador A/B/C, confirma e exibe estado |
| Node-RED, InfluxDB, Grafana | Software (integração e dados) | Valida, registra a série temporal e apresenta o dashboard |

Fluxo físico: entrada → pré-separador → esteira → câmera → desviador (servo) → saídas A/B/C.
Fluxo de dados: Pi → Mosquitto → ESP32 (atuação) + Node-RED → InfluxDB → Grafana (monitoramento, sem participar da decisão).

## 3. Situação visual e destino

| Situação visual | Decisão | Destino físico |
|-----------------|---------|----------------|
| QUADRADO | Peça normal | Saída A - Quadrado |
| TRIÂNGULO | Peça normal | Saída B - Triângulo |
| QUADRADO COM X | Peça defeituosa | Saída C - Descarte |

## 4. Estrutura do Repositório

```
TCC-PNAAT/
├── docs/                          Documentação acadêmica e entregas
│   ├── TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf
│   ├── Entrega_3_Esboco_Video_Pitch.md
│   ├── Cenários.pdf
│   └── Apostila ... PNAAT 2026.pdf
│
├── pi/                            Código Python (visão computacional - Raspberry Pi)
│   ├── main.py                    Pipeline: Picamera2, ROI, detecção de passagem, MQTT
│   ├── classifier.py              OpenCV: contorno + vértices (quadrado/triângulo) + marca X
│   ├── mqtt_publisher.py          Publica decisões e status nos tópicos MQTT
│   ├── config.py                  Configurações centralizadas (classes, destinos, calibração)
│   ├── requirements.txt           Dependências Python
│   └── tests/
│       └── test_classifier.py     Testes locais (sem hardware)
│
├── tria-esp/                      Firmware ESP32 do nó de atuação (ESP-IDF)
│   ├── components/servo/          Componente do servo (base: PoC do Claylton)
│   ├── main/
│   │   ├── main.c                 MQTT, servo (A/B/C), OLED, watchdog
│   │   ├── Kconfig.projbuild      Configuração via menuconfig
│   │   └── idf_component.yml      Dependências (esp-mqtt, u8g2)
│   ├── LIGACAO_MICRO_SERVO.md     Guia de ligação do micro servo ao ESP32
│   └── .devcontainer/             Ambiente de desenvolvimento
│
├── ming/                          Stack MING (Docker Compose)
│   ├── docker-compose.yml         Mosquitto, Node-RED, InfluxDB, Grafana
│   ├── mosquitto/
│   │   └── mosquitto.conf         Configuração do broker MQTT
│   ├── nodered/
│   │   ├── flows.json             Fluxo de validação e deduplicação
│   │   └── data/                  Dados de runtime do Node-RED (.gitkeep)
│   └── grafana/
│       ├── datasources/
│       │   └── influxdb.yml       DataSource InfluxDB (auto-provisioning)
│       └── dashboards/            Painéis provisionados
│
├── .gitignore
├── README.md
└── LICENSE
```

## 5. Componentes

### Raspberry Pi (visão computacional)

- **main.py** - Pipeline principal (seção 2.1 do levantamento):
  - Captura ao vivo com **Picamera2** (câmera CSI fixa)
  - Detecta quando uma nova peça entra na **ROI**, sem sensor de presença
  - Classifica cada peça **uma única vez** antes de liberar a próxima (RNF04)
  - Publica a decisão no MQTT e calcula o instante de atuação (RNF01)
  - Modo `--imagem` para simulação/teste sem câmera
- **classifier.py** - Classifica as 3 situações visuais usando OpenCV:
  - Segmenta o contorno externo e conta vértices com `approxPolyDP`
  - **Triângulo** (peça normal): 3 vértices
  - **Quadrado** (peça normal): 4 vértices
  - **X (defeito)**: Hough Line Transform com linhas diagonais (~45° e ~135°) na região central do quadrado
  - Reanálise automática com parâmetros alternativos
- **mqtt_publisher.py** - Publica nos tópicos MQTT:
  - `tria/triagem` - resultado da inspeção (payload mínimo: id_evento, horario, classe, destino, defeito)
  - `tria/status/pi` - disponibilidade do processo de visão
- **config.py** - Configurações de tópicos, classes, destinos, calibração

### ESP32 (nó de atuação - Heltec WiFi LoRa 32 V3) — `tria-esp/`

Firmware ESP-IDF construído sobre a **PoC do servo do Claylton** (`components/servo`), expandido para:

- Assina `tria/triagem` e move o servo para a posição calibrada (A/B/C)
- Exibe classe, destino e estado no OLED integrado
- Publica confirmação em `tria/atuador` (RF05) e estado em `tria/status/esp32`
- **Watchdog de comunicação** (RNF03): Last Will + OLED indicam indisponibilidade se sem mensagem por >15s
- Configurável via `idf.py menuconfig` (Wi-Fi, broker, ângulos A/B/C, pinos)

**Guia de ligação:** [`tria-esp/LIGACAO_MICRO_SERVO.md`](tria-esp/LIGACAO_MICRO_SERVO.md) — onde conectar cada fio do micro servo (GND, VCC e sinal PWM no `GPIO 47`).

> Os guias de ligação dos componentes serão mantidos em cada pasta do projeto e referenciados neste README.

### Stack MING (Docker)

- **Mosquitto** - Broker MQTT local (portas 1883/9001 WebSocket)
- **Node-RED** - Valida campos, evita reprocessamento de IDs conhecidos, grava no InfluxDB
- **InfluxDB** - Armazena cada evento de triagem como registro temporal
- **Grafana** - Dashboard: totais, classes, defeitos, destinos, histórico, estado de comunicação

## 6. Tópicos MQTT

| Tópico | Publica | Assina | Conteúdo |
|--------|---------|--------|----------|
| `tria/triagem` | Raspberry Pi | ESP32, Node-RED | Resultado da inspeção e destino |
| `tria/status/pi` | Raspberry Pi | Node-RED | Disponibilidade do processo de visão |
| `tria/status/esp32` | ESP32 | Node-RED, Pi | Conexão do nó de atuação |
| `tria/atuador` | ESP32 | Raspberry Pi, Node-RED | Confirmação vinculada ao id_evento |

## 7. Payload MQTT (tria/triagem)

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

`classe` pode ser `QUADRADO`, `TRIÂNGULO` ou `QUADRADO_COM_X`; quando `QUADRADO_COM_X`, `defeito` é `true` e `destino` é `C`.

## 8. Requisitos e Critérios de Aceite

### Funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RF01 | Detectar passagem e capturar | 19/20 ciclos válidos |
| RF02 | Classificar quadrado e triângulo | >= 18/20 para cada classe |
| RF03 | Identificar a marca X (defeito) | >= 18/20 como defeito |
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
| RNF04 | Não duplicar contagens | 30 IDs únicos, sem duplicatas |
| RNF05 | Recuperar comunicação | Reconectar em <= 30s, sem executar comando antigo |
| RNF06 | Funcionar localmente | 15 minutos sem Internet |

## 9. Dependências

### Hardware (Kit Maker + bancada)

| Recurso | Função |
|---------|--------|
| Raspberry Pi 5, 8 GB | Captura e processamento; decide e publica MQTT |
| Câmera CSI V1.3 (5 MP) + cabo adaptador | Captura da região de inspeção |
| Heltec WiFi LoRa 32 V3 (ESP32-S3) + OLED | Nó de atuação: servo, OLED, MQTT |
| Esteira (laboratório) | Transporte da câmera ao desviador |
| Micro servo (5 V, >= 1 A) | Aleta desviadora de 3 posições |
| Motor vibratório (pré-separação) | Reduz contato/sobreposição antes da esteira |
| Desviador + 3 calhas | Encaminhamento às saídas A/B/C |
| Peças de ensaio (MDF quadrado/triângulo/X) | Amostras reproduzíveis |
| Fonte 5 V, microSD 128 GB, suporte, iluminação/fundo fosco | Apoio de bancada |

### Software e bibliotecas (Pi — `pi/`)

| Dependência | Versão mínima | Uso |
|-------------|---------------|-----|
| Python | >= 3.10 | Linguagem do pipeline |
| opencv-python | >= 4.8 | Segmentação, contornos, approxPolyDP, Canny, Hough |
| numpy | >= 1.24 | Cálculos geométricos e vetoriais |
| paho-mqtt | >= 2.0 | Cliente MQTT (publicação de eventos) |
| picamera2 | >= 0.3.12 | Interface com a câmera CSI |

### Firmware (ESP32 — `tria-esp/`)

| Dependência | Uso |
|-------------|-----|
| ESP-IDF v5.x (target esp32s3) | Framework do firmware |
| Componente esp-mqtt | Cliente MQTT no ESP32 |
| Componente u8g2 | Driver do OLED SSD1306 |
| Componente cJSON | Parse do payload MQTT |
| Componente driver/mcpwm | Controle PWM do servomotor |
| Componente `servo/` | Controle de posição do servomotor |

### Stack MING (integração e dados — `ming/`)

| Serviço | Imagem | Porta | Uso |
|---------|--------|-------|-----|
| Mosquitto | eclipse-mosquitto:2.0 | 1883 / 9001 | Broker MQTT local (MQTT + WebSocket) |
| Node-RED | nodered/node-red:latest | 1880 | Validação, transformação e deduplicação |
| InfluxDB | influxdb:2.7 | 8086 | Banco de série temporal (bucket `tria_events`) |
| Grafana | grafana/grafana:latest | 3000 | Dashboard (totais, classes, defeitos, histórico) |

## 10. Como Rodar

### Pré-requisitos
- Git (>= 2.34)
- Docker + Docker Compose (stack MING)
- Python 3.10+ no Pi/máquina
- ESP-IDF v5.x (compilação do ESP32)

### 1. Classificador (Raspberry Pi)

```bash
sudo apt install libcap-dev          # headers da libcap (build do python-prctl, dependência do picamera2)
cd pi
python3 -m venv --system-site-packges venv
source venv/bin/activate
pip install -r requirements.txt
python tests/test_classifier.py        # testes locais
python main.py                         # captura ao vivo (Picamera2)
python main.py --imagem teste.jpg      # simulação sem câmera
```

### 2. Stack MING

```bash
cd ming
docker compose up -d
```

Interfaces disponíveis:
- **Grafana:** http://localhost:3000 (login `admin` / `admin123456`)
- **Node-RED:** http://localhost:1880
- **InfluxDB:** http://localhost:8086
- **Broker MQTT:** localhost:1883

O dashboard **TRIA - Monitoramento da Triagem** é provisionado
automaticamente a partir de `ming/grafana/dashboards/tria-dashboard.json`.
Ele contém totais, taxa de defeitos, distribuições por classe e destino,
produção por minuto, tempo de processamento e as últimas inspeções.

Após atualizar os arquivos de provisionamento, recrie o Grafana:

```bash
cd ming
docker compose up -d --force-recreate grafana
```

Alterações feitas pela interface ficam no volume do Grafana, mas não atualizam
o JSON versionado. Para manter uma edição na branch, exporte o dashboard como
JSON clássico e substitua o arquivo em `ming/grafana/dashboards/`.

### 3. Firmware ESP32 (tria-esp)

```bash
cd tria-esp
idf.py set-target esp32s3
idf.py menuconfig    # TRIA: Wi-Fi, broker MQTT, ângulos A/B/C, pinos
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## 11. Escopo

### Incluído
- Pré-separação vibratória (mecânica a definir)
- Classificação das 3 situações visuais (quadrado, triângulo e quadrado com X) com OpenCV
- Detecção da marca X contrastante (defeito)
- Comunicação MQTT local entre Pi, ESP32 e Node-RED
- Atuação com servo de 3 posições
- Dashboard com totais, classes, defeitos e histórico
- Registro temporal de todos os eventos

### Fora de escopo
- Certificação industrial / normas de segurança
- Integração com CLP, MES, ERP ou nuvem
- Reconhecimento de peças arbitrárias ou Deep Learning
- Sensor óptico, encoder ou sensor de presença dedicado

## 12. Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS and Claylton-Muniz

## 13. Checklist de Conformidade

- [x] Repositório Git configurado e organizado.
- [x] Diagrama de blocos integrando IoT, Visão Computacional e Software.
- [x] Lista completa de dependências por componente.
- [x] Mapeamento de requisitos funcionais e não-funcionais alinhados com o diagrama.
- [x] Nomes de arquivos e caminhos relativos mapeados na estrutura do repositório.
- [x] Instruções passo a passo para preparação e execução do ambiente em ambiente limpo.
