```
# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso — Capacitação **PNAAT 2026**  
**Equipe:** Os guri do pinati  

---

## 1. Visão Geral do Projeto
O **TRIA** é uma Prova de Conceito (PoC) física desenvolvida para resolver o problema de triagem de componentes misturados em uma linha de manufatura industrial. O sistema integra **Visão Computacional** na borda (Raspberry Pi 5) e **Atuação Física via IoT** (ESP32-S3), orquestrados por uma arquitetura MQTT e monitorados pela **Stack MING** (Mosquitto, Node-RED, InfluxDB e Grafana).

O fluxo operacional consiste em:
`Pré-separação física (vibração) → Esteira de transporte → Captura de imagem → Classificação por visão computacional → Publicação MQTT → Atuação física do servomotor (destinos A, B ou C) → Registro e exibição em dashboard`.

---

## 2. Diagrama de Blocos Preliminar da Arquitetura

```

┌────────────────────────────────────────────────────────────────────────────┐ │ SENSORIAMENTO (entrada) │ │ │ │ [Pré-separador vibratório] [Esteira] [Câmera CSI V1.3 fixa] │ │ (reduz contato/sobreposição) (transporte) (captura, fundo fosco) │ └───────────────────────────────────┬────────────────────────────────────────┘ │ quadro (640x480 @ 30 fps) ┌───────────────────────────────────▼────────────────────────────────────────┐ │ PROCESSAMENTO — Visão Computacional │ │ Raspberry Pi 5 (8 GB) · Python 3 │ │ Picamera2 (captura) → OpenCV (segmentação → contornos → approxPolyDP │ │ → Hough para marca X) → decisão: classe, destino, defeito, │ │ instante de atuação │ └───────────────────────────────────┬────────────────────────────────────────┘ │ MQTT publish: tria/triagem, tria/status/pi ┌───────────────────────────────────▼────────────────────────────────────────┐ │ CONECTIVIDADE — Broker Mosquitto │ └──────────────┬────────────────────────────┬────────────────────────────────┘ │ subscribe tria/triagem │ subscribe tria/triagem ┌──────────────▼──────────────────┐ ┌──────▼───────────────────────────────┐ │ ATUAÇÃO — IoT (hardware) │ │ INTEGRAÇÃO E DADOS — Software │ │ Heltec WiFi LoRa 32 V3 (ESP32-S3)│ │ Stack MING (Docker Compose) │ │ Firmware ESP-IDF │ │ Node-RED (validação + deduplicação) │ │ Servo → posições A/B/C │ │ → InfluxDB (série temporal) │ │ → saídas A (quadrado), B │ │ → Grafana (dashboard) │ │ (triângulo), C (descarte) │ │ │ │ OLED + watchdog MQTT │ │ Publicação: tria/atuador, │ └─────────────────────────────────┘ │ tria/status/esp32 │ └───────────────────────────────────────┘

```

---

## 3. Dependências e Tecnologias

### Hardware e Componentes Físicos
* **Nó de Visão Computacional:** Raspberry Pi 5 (8 GB) com módulo de câmera CSI V1.3.
* **Nó de Atuação (IoT):** Heltec WiFi LoRa 32 V3 (ESP32-S3), Micro servomotor (PWM), Display OLED SSD1306.
* **Infraestrutura Mecânica:** Esteira transportadora e pré-separador vibratório.

### Software e Bibliotecas (Visão — `pi/`)
| Dependência | Versão Mínima | Finalidade |
| :--- | :--- | :--- |
| **Python** | `≥ 3.10` | Linguagem base do pipeline de visão |
| **opencv-python** | `≥ 4.8` | Segmentação, contornos, `approxPolyDP`, Canny, Hough |
| **numpy** | `≥ 1.24` | Operações matriciais e cálculos geométricos |
| **paho-mqtt** | `≥ 2.0` | Cliente MQTT para publicação de eventos de triagem |
| **picamera2** | `≥ 0.3.12` | Interface oficial de captura da câmera no Raspberry Pi OS |

### Firmware (Atuador IoT — `tria-esp/`)
| Componente | Framework/Driver | Finalidade |
| :--- | :--- | :--- |
| **ESP-IDF** | `v5.x` | Framework oficial de desenvolvimento para ESP32-S3 |
| **esp-mqtt** | Componente nativo | Cliente MQTT no microcontrolador |
| **u8g2** | Componente C | Driver de controle do display OLED SSD1306 |
| **cJSON** | Componente nativo | Parse de mensagens JSON dos payloads MQTT |
| **driver/mcpwm** | Componente nativo | Controle de sinal PWM para o servomotor |

### Stack MING (Serviços e Banco — `ming/`)
| Serviço | Imagem/Recurso | Porta | Finalidade |
| :--- | :--- | :--- | :--- |
| **Broker MQTT** | `eclipse-mosquitto:2.0` | `1883 / 9001` | Roteamento de mensagens entre os nós |
| **Node-RED** | `nodered/node-red:latest` | `1880` | Validação, deduplicação e ingestão |
| **InfluxDB** | `influxdb:2.7` | `8086` | Armazenamento de dados em série temporal |
| **Grafana** | `grafana/grafana:latest` | `3000` | Painéis gerenciais em tempo real |

---

## 4. Requisitos e Critérios de Aceite

### Requisitos Funcionais (RF)
| ID | Descrição do Requisito | Critério de Aceite |
| :--- | :--- | :--- |
| **RF01** | Capturar passagem de objetos | $\ge 19/20$ ciclos válidos (1 evento/peça) |
| **RF02** | Classificar quadrado e triângulo | $\ge 18/20$ acertos por classe |
| **RF03** | Identificar defeito (marcação em X) | $\ge 18/20$ peças defeituosas encaminhadas ao descarte |
| **RF04** | Enviar payloads via MQTT | $\ge 29/30$ eventos publicados sem perda |
| **RF05** | Posicionar servomotor | $\ge 27/30$ acionamentos nas posições corretas (A, B ou C) |
| **RF06** | Triagem física completa | $\ge 27/30$ peças direcionadas às calhas físicas corretas |
| **RF07** | Ingestão no InfluxDB | $30/30$ registros armazenados com timestamp |

### Requisitos Não-Funcionais (RNF)
| ID | Descrição do Requisito | Critério de Aceite |
| :--- | :--- | :--- |
| **RNF01** | Margem de tempo para atuação | Servo posicionado com margem de segurança $\ge 0,3\text{ s}$ antes da chegada da peça |
| **RNF02** | Estabilidade de operação | Operação contínua por 15 minutos ou 30 peças sem reinício |
| **RNF03** | Resiliência de conexão | Reconexão MQTT automática em $\le 30\text{ s}$ após queda de rede |
| **RNF04** | Deduplicação de eventos | 0 registros duplicados no banco para o mesmo ID de evento |
| **RNF05** | Operação offline (Edge) | Manutenção do processamento local por 15 min sem conexão com a nuvem |

---

## 5. Arquitetura de Comunicação (MQTT)

| Tópico | Origem | Destino | Conteúdo do Payload |
| :--- | :--- | :--- | :--- |
| `tria/triagem` | Raspberry Pi | ESP32, Node-RED | `{"id_evento": "...", "classe": "quadrado", "destino": "A", "timestamp": ...}` |
| `tria/status/pi` | Raspberry Pi | Node-RED | `{"status": "online", "fps": 29.8}` |
| `tria/status/esp32` | ESP32 | Node-RED | `{"status": "online", "wifi_rssi": -58}` |
| `tria/atuador` | ESP32 | Node-RED | `{"id_evento": "...", "status_atuacao": "sucesso", "posicao": "A"}` |

---

## 6. Estrutura de Arquivos e Repositório

```

TCC-PNAAT/ ├── docs/ # Documentação técnica e esquemáticos │ └── diagramas/ # Imagens dos fluxogramas e arquitetura ├── pi/ # Pipeline de Visão Computacional (Raspberry Pi) │ ├── main.py # Loop principal de captura e integração MQTT │ ├── classifier.py # Lógica OpenCV (contornos, polígonos e marca X) │ ├── mqtt\_publisher.py # Cliente de publicação de mensagens MQTT │ ├── config.py # Parâmetros de ROI, limiares e IP do Broker │ └── requirements.txt # Lista de dependências Python ├── tria-esp/ # Firmware do Nó de Atuação (ESP32-S3) │ ├── main/main.c # Inicialização, clientes MQTT e callbacks │ ├── components/servo/ # Componente de controle PWM do servomotor │ ├── sdkconfig # Configurações do ambiente ESP-IDF │ └── LIGACAO\_MICRO\_SERVO.md # Mapeamento físico de pinagem ├── ming/ # Orquestração da Stack MING │ ├── docker-compose.yml # Configuração dos contêineres Docker │ ├── mosquitto/ # Configuração do broker MQTT │ ├── nodered/ # Fluxos salvos de transformação de dados │ └── grafana/ # Dashboards pré-configurados ├── .gitignore # Filtro de arquivos temporários e binários └── README.md # Manual do repositório

```

---

## 7. Pré-requisitos e Instruções de Setup

### Pré-requisitos
* Git instalado (`≥ 2.34`).
* Docker e Docker Compose instalados (para a Stack MING).
* Python `3.10+` configurado na máquina/Pi.
* Toolchain **ESP-IDF v5.x** instalada (para compilação do ESP32).

### Passo a Passo de Instalação e Execução

#### 1. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/TCC-PNAAT.git
cd TCC-PNAAT

```

#### 2\. Subir a Stack MING (Broker MQTT, Node-RED, InfluxDB e Grafana)

```
cd ming
docker compose up -d

```

* Interfaces disponíveis:
  * **Grafana:** `http://localhost:3000` (Login padrão: `admin` / `admin`)
  * **Node-RED:** `http://localhost:1880`
  * **Broker MQTT:** `localhost:1883`

#### 3\. Executar o Módulo de Visão Computacional (Raspberry Pi)

```
cd ../pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py

```

#### 4\. Compilar e Gravar o Firmware no ESP32-S3

```
cd ../tria-esp
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor

```

---

## 8\. Checklist de Conformidade da Entrega 4

* [x] Repositório Git configurado e organizado.
* [x] Diagrama de blocos integrando IoT, Visão Computacional e Software.
* [x] Lista completa de dependências por componente.
* [x] Mapeamento de requisitos funcionais e não-funcionais alinhados com o diagrama.
* [x] Nomes de arquivos e caminhos relativos mapeados na estrutura do repositório.
* [x] Instruções passo a passo para preparação e execução do ambiente em ambiente limpo.

```

---
```
