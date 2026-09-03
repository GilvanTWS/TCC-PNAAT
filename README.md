# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso do programa **PNAAT 2026** (Programa Nacional de Aprendizagem Acelerada em Tecnologia).

## Visão Geral

O **TRIA** é um protótipo de **visão computacional + IoT** para triagem automática de componentes em uma esteira de produção industrial. O sistema classifica peças impressas em 3D por sua forma geométrica (circular, quadrada, triangular) e as direciona para rotas de separação.

### Fluxo do Sistema

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│ Impressora  │ →  │  Esteira Pi  │ →  │ Pi Cam 5MP  │
│  (amostras) │    │  (simulação) │    │  (captura)  │
└─────────────┘    └──────────────┘    └──────┬──────┘
                                              │
                                     Classificação
                                     (OpenCV)
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │   MQTT Broker    │
                                    │   (Mosquitto)    │
                                    └────────┬─────────┘
                                     ┌───────┴────────┐
                                     ▼                ▼
                              ┌─────────────┐  ┌────────────┐
                              │   Website   │  │    ESP32   │
                              │  (smart)    │  │  (OLED)    │
                              └─────────────┘  └────────────┘
```

### Fluxo MQTT (Simplificado)

```
Raspberry Pi publica:
  → tria/classificacao   (tipo, confiança, timestamp)
  → tria/comando          (classe para ESP32 exibir)

Website lê:
  → tria/classificacao
  → tria/esp32/status

ESP32 lê:
  → tria/comando
```

## Estrutura do Repositório

```
TCC-PNAAT/
│
├── docs/                              Documentação (compartilhada)
│   ├── levantamento_requisitos.pdf
│   ├── cenarios.pdf
│   └── apostila_pnaat.pdf
│
├── pi/                                🟢 GILVAN (código Python)
│   ├── main.py                        Entry point
│   ├── classifier.py                  OpenCV (contornos, vértices, circularidade)
│   ├── mqtt_publisher.py              Publica nos tópicos MQTT
│   ├── config.py                      Tópicos, thresholds, constantes
│   ├── requirements.txt               Dependências Python
│   └── tests/                         Testes locais (sem hardware)
│       ├── test_classifier.py
│       └── mock_publisher.py          Simula payload MQTT
│
├── web/                               🟡 CLAYLTON (site smart)
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── app.js                     Lógica principal
│   │   ├── mqtt-client.js             MQTT.js WebSocket
│   │   ├── conveyor.js                Animação esteira + rotas
│   │   ├── history.js                 Histórico + deduplicação + CSV
│   │   └── status.js                  Status ESP32
│   └── assets/
│       └── imagens/
│
├── esp32/                             🔵 ANA BEATRIZ + ANTONIO RAFAEL
│   ├── firmware/
│   │   └── tria_display/
│   │       └── tria_display.ino
│   └── README.md
│
├── broker/                            🔵 MOSQUITTO (config)
│   ├── mosquitto.conf
│   └── README.md
│
├── testes/                            🔵 EVIDÊNCIAS DE ACEITE
│   ├── rf01/                          Precisão 90% (27/30)
│   ├── rf02/                          Classificação correta
│   ├── rf03/                          Revisão automática
│   ├── rf04/                          MQTT funcionando
│   ├── rf05/                          Deduplicação
│   ├── rf06/                          Descarte
│   ├── rf07/                          Histórico
│   ├── rnf01/                         Tempo < 2s
│   └── rnf02/                         10min offline
│
├── .gitignore
├── README.md
└── LICENSE
```

## Divisão de Tarefas

| Membro | Área | Responsabilidades |
|--------|------|-------------------|
| **Gilvan** | `pi/` | Classificação OpenCV, regras de decisão, reanálise automática, publicação MQTT, documentação técnica |
| **Claylton** | `web/` | Website smart (esteira virtual, 5 rotas, animações), cliente MQTT.js, deduplicação, histórico, CSV, status ESP32 |
| **Ana Beatriz** | `esp32/`, `broker/`, `testes/` | Montagem física, firmware ESP32 + OLED, broker Mosquitto, execução dos ensaios de aceite |
| **Antonio Rafael** | `esp32/`, `broker/`, `testes/` | Montagem física, preparação de amostras, configuração broker, coleta de evidências |

## Tecnologias

| Categoria | Tecnologia | Uso |
|-----------|------------|-----|
| Computador single-board | Raspberry Pi 5 (8 GB) | Captura, processamento, broker, servidor web |
| Câmera | CSI Camera V1.3 (5 MP) | Captura silhuetas das peças |
| Microcontrolador | Heltec WiFi LoRa 32 V3 (ESP32-S3) | Exibe resultado no OLED |
| Visão computacional | OpenCV (Python) | Detecção de contornos, análise de forma |
| Captura de imagem | Picamera2 (Python) | Interface com câmera CSI |
| Messaging | MQTT (Mosquitto) | Comunicação Pi ↔ Website ↔ ESP32 |
| Frontend web | HTML, CSS, JavaScript, MQTT.js | Esteira virtual, animações, contadores |
| Sistema operacional | Raspberry Pi OS 64-bit | Sistema base |

## Requisitos de Aceite

### Funcionais
| ID | Descrição | Meta |
|----|-----------|------|
| RF01 | Precisão de classificação por classe | ≥ 90% (27/30) |
| RF02 | Classificação correta das 3 formas | Circular, quadrada, triangular |
| RF03 | Revisão automática de classificações incertas | Limite de tentativas |
| RF04 | Comunicação MQTT funcionando | Pi → Website, Pi → ESP32 |
| RF05 | Deduplicação de eventos no site | Sem duplicatas |
| RF06 | Rota de descarte para peças não conformes | Funcional |
| RF07 | Histórico de classificações | Visualização + exportação CSV |

### Não-funcionais
| ID | Descrição | Meta |
|----|-----------|------|
| RNF01 | Tempo de resposta da animação | < 2 segundos |
| RNF02 | Operação offline contínua | ≥ 10 minutos, reconexão < 30s |

## Escopo

### Incluído
- Classificação de peças por silhueta (3 formas)
- Comunicação MQTT entre dispositivos
- Website com simulação virtual da esteira
- Exibição de resultado no OLED via ESP32
- Histórico e exportação CSV

### Fora de Escopo
- Esteira motorizada real (simulada virtualmente)
- Separação física por servos/motores (simulada no site)
- Controle de impressora 3D
- Etapa de desacoplamento inicial das peças (normalmente resolvida por esteira vibratória)

## Equipe - "Os guri do pinhatty"

- Claylton Demésio Muniz Silva
- Gilvan Alves Pastor Júnior
- Ana Beatriz Batista Caitano
- Antonio Rafael Oliveira da Cunha

## Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS
