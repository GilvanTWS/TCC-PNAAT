# Entrega 4 — Esboço da Documentação (README.md)

Este documento contém o **esboço** do manual do projeto (README.md) a ser
adotado no repositório. Diagrama de blocos, lista de dependências e requisitos
representam **a mesma solução** (a PoC física TRIA).

---

## Proposta de conteúdo para o README.md do repositório

# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso do programa **PNAAT 2026** (Programa Nacional de
Aprendizagem Acelerada em Tecnologia). Equipe **Os guri do pinati**.

PoC física que valida a cadeia: **pré-separação física → esteira → captura →
classificação → MQTT → atuação do servo → três destinos físicos → registro e
visualização na stack MING**. A solução ataca o **Cenário 2** dos Cenários:
triagem de componentes misturados em uma linha de manufatura, em posições
variadas, em contato ou parcialmente sobrepostas.

## Diagrama de blocos preliminar da arquitetura

Solucão integrada (IoT + visão computacional). O diagrama identifica os
elementos de sensoriamento, processamento, conectividade e software, e o fluxo
entre eles.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          SENSORIAMENTO (entrada)                          │
│                                                                            │
│   [Pré-separador vibratório]  [Esteira]  [Câmera CSI V1.3 fixa]          │
│   (reduz contato/sobreposição)   (transporte)   (captura, fundo fosco)    │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │ quadro (640x480 @ 30 fps)
┌───────────────────────────────────▼────────────────────────────────────────┐
│                     PROCESSAMENTO — Visão computacional                    │
│                     Raspberry Pi 5 (8 GB) · Python 3                       │
│   Picamera2 (captura) → OpenCV (segmentação → contornos → approxPolyDP     │
│   → Hough para marca X) → decisão: classe, destino, defeito,               │
│   instante de atuação                                                      │
└───────────────────────────────────┬────────────────────────────────────────┘
                                    │ MQTT publish: tria/triagem, tria/status/pi
┌───────────────────────────────────▼────────────────────────────────────────┐
│                      CONECTIVIDADE — Broker Mosquitto                      │
└──────────────┬────────────────────────────┬────────────────────────────────┘
               │ subscribe tria/triagem     │ subscribe tria/triagem
┌──────────────▼──────────────────┐  ┌──────▼───────────────────────────────┐
│ ATUAÇÃO — IoT (hardware)        │  │ INTEGRAÇÃO E DADOS — software        │
│ Heltec WiFi LoRa 32 V3 (ESP32-S3)│  │ Stack MING (Docker Compose)          │
│  Firmware ESP-IDF               │  │  Node-RED (validação + deduplicação) │
│  Servo → posições A/B/C         │  │   → InfluxDB (série temporal)         │
│  → saídas A (quadrado), B       │  │   → Grafana (dashboard)               │
│  (triângulo), C (descarte)      │  │                                       │
│  OLED + watchdog MQTT           │  │  Publicação: tria/atuador,            │
└─────────────────────────────────┘  │  tria/status/esp32                     │
                                     └───────────────────────────────────────┘
```

Fluxo físico: entrada → pré-separador → esteira → câmera → desviador (servo) →
saídas A/B/C.
Fluxo de dados: Pi → Mosquitto → ESP32 (atuação) + Node-RED → InfluxDB → Grafana.

### Situação visual e destino

| Visual | Decisão | Destino físico |
|--------|---------|----------------|
| QUADRADO | Peça normal | Saída A - Quadrado |
| TRIÂNGULO | Peça normal | Saída B - Triângulo |
| QUADRADO COM X | Peça defeituosa | Saída C - Descarte |

## Dependências do projeto

### Hardware (Kit Maker + bancada)

| Recurso | Função |
|---------|--------|
| Raspberry Pi 5, 8 GB | Captura e processamento; decide e publica MQTT |
| Câmera CSI V1.3 (5 MP) + cabo adaptador | Captura da região de inspeção |
| Heltec WiFi LoRa 32 V3 (ESP32-S3) + OLED | Nó de atuação: servo, OLED, MQTT |
| Esteira (laboratório) | Transporte da câmera ao desviador |
| Micro servo (SG90 ou similar, 5 V, ≥1 A) | Aleta desviadora de 3 posições |
| Motor vibratório (pré-separação) | Reduz contato/sobreposição antes da esteira |
| Desviador + 3 calhas | Encaminhamento às saídas A/B/C |
| Peças de ensaio (quadrado, triângulo, quadrado com X) | Amostras reproduzíveis |
| Fonte 5 V externa, microSD 128 GB, suporte e iluminação/fundo fosco | Apoio de bancada |

### Software e bibliotecas (Pi — `pi/`)

| Dependência | Uso |
|-------------|-----|
| Python 3 | Linguagem do pipeline |
| opencv-python ≥ 4.8 | Segmentação, contornos, approxPolyDP, Canny, Hough |
| numpy ≥ 1.24 | Cálculos geométricos e vetoriais |
| paho-mqtt ≥ 2.0 | Cliente MQTT (publicação de eventos) |
| picamera2 ≥ 0.3.12 | Interface com a câmera CSI |

### Firmware (ESP32 — `tria-esp/`)

| Dependência | Uso |
|-------------|-----|
| ESP-IDF (esp32s3) | Framework do firmware |
| esp-mqtt (componente) | Cliente MQTT no ESP32 |
| u8g2 (componente) | Driver do OLED SSD1306 |
| cJSON | Parse do payload MQTT |
| Componente `servo/` | Controle PWM do servomotor |

### Stack MING (integração e dados — `ming/`)

| Dependência | Uso |
|-------------|-----|
| Docker + Docker Compose | Orquestração reprodutível da stack |
| eclipse-mosquitto 2.0 | Broker MQTT local (1883/9001) |
| nodered/node-red | Validação, transformação e deduplicação |
| influxdb 2.7 | Banco de série temporal (bucket `tria_events`) |
| grafana/grafana + data source InfluxDB | Dashboard (totais, classes, defeitos, histórico) |

### Plataformas e ferramentas

| Recurso | Uso |
|---------|-----|
| Raspberry Pi OS 64 bits | Sistema do Pi |
| Git + GitHub | Versionamento e repositório |
| OBS Studio | Gravação do vídeo pitch (Entrega 3) |
| VS Code + Dev Container `tria-esp/.devcontainer` | Desenvolvimento do firmware |
| Terminal `mosquitto_sub` | Inspeção dos tópicos em tempo real |

## Requisitos e critérios de aceite (mesma solução)

### Funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RF01 | Detectar passagem e capturar | ≥ 19/20 ciclos válidos, 1 evento por peça |
| RF02 | Classificar quadrado e triângulo | ≥ 18/20 para cada classe |
| RF03 | Identificar quadrado com X | ≥ 18/20 como defeito |
| RF04 | Comunicar via MQTT | ≥ 29/30 eventos consistentes |
| RF05 | Posicionar servo corretamente | ≥ 27/30 comandos |
| RF06 | Encaminhar fisicamente | ≥ 27/30 peças na saída correta |
| RF07 | Pré-separação por vibração | ≥ 8/10 chegadas separadas |
| RF08 | Registrar no InfluxDB | 30/30 registros sem perda |
| RF09 | Apresentar no Grafana | Painéis conferem com InfluxDB |
| RF10 | Fluxo completo | ≥ 13/15 ciclos completos |

### Não-funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RNF01 | Preparar atuação no prazo | Servo estabiliza com ≥ 0,3 s de margem |
| RNF02 | Consistência da comunicação | ≥ 29/30 entregas válidas |
| RNF03 | Operar continuamente | 15 min ou 30 peças sem reinício |
| RNF04 | Recuperar comunicação | Reconectar em ≤ 30 s, sem comando antigo |
| RNF05 | Não duplicar contagens | 30 IDs únicos, sem duplicatas |
| RNF06 | Funcionar localmente | 15 min sem Internet |

## Tópicos MQTT

| Tópico | Publica | Assina | Conteúdo |
|--------|---------|--------|----------|
| `tria/triagem` | Raspberry Pi | ESP32, Node-RED | Resultado da inspeção e destino |
| `tria/status/pi` | Raspberry Pi | Node-RED | Disponibilidade do processo de visão |
| `tria/status/esp32` | ESP32 | Node-RED, Pi (opcional) | Conexão do nó de atuação |
| `tria/atuador` | ESP32 | Pi, Node-RED | Confirmação vinculada ao id_evento |

## Como rodar

```bash
# 1. Classificador (Pi)
cd pi && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python tests/test_classifier.py      # testes locais
python main.py                       # captura ao vivo
python main.py --imagem teste.jpg    # simulação sem câmera

# 2. Stack MING
cd ming && docker compose up -d      # Grafana :3000 · Node-RED :1880 · MQTT :1883

# 3. Firmware ESP32
cd tria-esp
idf.py set-target esp32s3
idf.py menuconfig                    # Wi-Fi, broker, ângulos A/B/C, pinos
idf.py build && idf.py -p /dev/ttyUSB0 flash monitor
```

## Estrutura do repositório

```
TCC-PNAAT/
├── docs/           (documentação acadêmica e entregas)
├── pi/             (visão computacional - Raspberry Pi)
│   ├── main.py     pipeline: Picamera2, ROI, detecção de passagem, MQTT
│   ├── classifier.py  OpenCV: contornos, vértices, Hough (marca X)
│   ├── mqtt_publisher.py  tópicos tria/* 
│   ├── config.py   configurações centralizadas
│   ├── requirements.txt
│   └── tests/      testes locais (sem hardware)
├── tria-esp/       (firmware ESP32 - nó de atuação)
│   ├── main/main.c MQTT, servo A/B/C, OLED, watchdog
│   ├── components/servo/  controle PWM do servo
│   └── LIGACAO_MICRO_SERVO.md
├── ming/           (stack MING - Docker Compose)
│   ├── docker-compose.yml
│   ├── mosquitto/mosquitto.conf
│   ├── nodered/flows.json
│   └── grafana/datasources/influxdb.yml
├── README.md
└── LICENSE
```

---

## Checklist de conformidade da Entrega 4

- [ ] Repositório GitHub criado e versionado (repositório atual `TCC-PNAAT`)
- [ ] README.md contém o diagrama de blocos preliminar (sensoriamento,
      processamento, conectividade, software; entrada/processamento/resultado
      da visão; relação IoT + visão computacional)
- [ ] README.md contém a lista de dependências (bibliotecas, plataformas,
      ferramentas, recursos)
- [ ] Diagrama, dependências e requisitos descrevem a mesma solução (TRIA)
- [ ] Link do diagrama e das entregas consistentes com os documentos em `docs/`
