# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso — Capacitação **PNAAT 2026** (Programa Nacional de Aprendizagem Acelerada em Tecnologia).
**Equipe:** Os guri do pinati.

## Sumário

- [TRIA - Triagem Visual Integrada de Componentes](#tria---triagem-visual-integrada-de-componentes)
  - [Sumário](#sumário)
  - [1. Visão Geral](#1-visão-geral)
  - [2. Situação visual e destino](#2-situação-visual-e-destino)
  - [3. Estrutura do Repositório](#3-estrutura-do-repositório)
  - [4. Componentes](#4-componentes)
  - [5. Tópicos MQTT](#5-tópicos-mqtt)
  - [6. Payload MQTT (tria/triagem)](#6-payload-mqtt-triatriagem)
  - [7. Requisitos e Critérios de Aceite](#7-requisitos-e-critérios-de-aceite)
    - [Funcionais](#funcionais)
    - [Não-funcionais](#não-funcionais)
  - [8. Dependências](#8-dependências)
    - [Hardware](#hardware)
    - [Software, bibliotecas e ferramentas](#software-bibliotecas-e-ferramentas)
  - [9. Como Rodar](#9-como-rodar)
    - [1. Classificador (Raspberry Pi)](#1-classificador-raspberry-pi)
      - [Reproduzir e avaliar os vídeos de ensaio](#reproduzir-e-avaliar-os-vídeos-de-ensaio)
    - [2. Stack MING](#2-stack-ming)
    - [3. Firmware ESP32 (tria-esp)](#3-firmware-esp32-tria-esp)
    - [Verificação inicial](#verificação-inicial)
  - [10. Escopo](#10-escopo)
  - [11. Licença](#11-licença)

## 1. Visão Geral

O **TRIA** é uma PoC física de triagem integrada com **visão computacional e IoT**, voltada ao [Cenário 2](docs/Cen%C3%A1rios.pdf): componentes misturados, em contato ou sobrepostos em uma linha de manufatura. A proposta busca separar, identificar e encaminhar peças, registrando o processo para acompanhamento.

Na bancada atual, um **motor sob uma plataforma de papelão** movimenta as peças enquanto o operador mantém o botão do ESP32 pressionado. Elas caem na esteira, onde a câmera do Raspberry Pi captura as placas de MDF. O software reconhece o **símbolo central**, decide A/B/C e publica via MQTT para atuação do servo e geração de gráficos no Grafana.


## 2. Situação visual e destino

| Símbolo na placa de MDF | Classe MQTT | Destino |
|------------------------|-------------|---------|
| Quadrado | `QUADRADO` | A — peça normal |
| Triângulo | `TRIÂNGULO` | B — peça normal |
| X | `QUADRADO_COM_X` | C — descarte / defeito |

As classes preservam os nomes do levantamento inicial. O código atual reconhece o **símbolo central**, usando contornos e geometria. Uma marca desconhecida não gera classificação válida; o pipeline tenta novamente enquanto a peça permanece na área de inspeção (ROI).

## 3. Estrutura do Repositório

```text
TCC-PNAAT/
├── docs/                         Requisitos, apostila, cenário e roteiro do pitch
├── pi/
│   ├── main.py                   Captura, ROI, MQTT e visualização
│   ├── classifier.py             Localização do MDF e reconhecimento do símbolo
│   ├── mqtt_publisher.py         Publicação de decisões e status
│   ├── config.py                 Broker e parâmetros de calibração
│   ├── requirements.txt          Bibliotecas Python
│   └── tests/
│       ├── test_classifier.py    Testes locais com pytest
│       └── images/               18 imagens de referência
├── tria-esp/
│   ├── main/                     main.c, Kconfig.projbuild e idf_component.yml
│   ├── components/               servo, tria_actuator, tria_display,
│   │                             tria_network, vibration e conveyor
│   ├── CMakeLists.txt            Compilação ESP-IDF
│   ├── dependencies.lock        Versões resolvidas
│   ├── LIGACAO_MICRO_SERVO.md    Guia de montagem do servo
│   └── .devcontainer/            Ambiente de desenvolvimento opcional
├── ming/
│   ├── docker-compose.yml       Serviços e volumes da stack
│   ├── mosquitto/mosquitto.conf  Configuração do broker
│   ├── nodered/flows.json        Validação, deduplicação e escrita
│   └── grafana/
│       ├── datasources/influxdb.yml
│       ├── provisioning/dashboards.yml
│       └── dashboards/tria-dashboard.json
├── .gitignore
├── README.md
└── LICENSE
```

Documentos: [levantamento de requisitos](docs/TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf), [apostila](docs/Apostila%20Trabalho%20de%20Conclus%C3%A3o%20da%20Capacita%C3%A7%C3%A3o%20-%20PNAAT%202026.pdf) e [roteiro do pitch](docs/RoteiroVideoPitch.pdf).

## 4. Componentes

| Componente / requisitos relacionados | Implementação |
|-------------------------------------|---------------|
| **Visão — RF01–RF04** | [`pi/main.py`](pi/main.py) captura e controla a ocupação da ROI; [`classifier.py`](pi/classifier.py) reconhece os símbolos; [`mqtt_publisher.py`](pi/mqtt_publisher.py) publica o resultado. |
| **Atuação — RF05–RF06** | [`tria_actuator/`](tria-esp/components/tria_actuator/) converte A/B/C em ângulos; [`servo/`](tria-esp/components/servo/) gera PWM por LEDC a 50 Hz. |
| **Alimentação — RF07** | [`vibration/`](tria-esp/components/vibration/) aciona o motor enquanto o botão está pressionado; [`conveyor/`](tria-esp/components/conveyor/) disponibiliza o comando digital da esteira. |
| **Rede e diagnóstico — RF04, RNF04** | [`tria_network/`](tria-esp/components/tria_network/) gerencia Wi-Fi, MQTT, confirmações e reconexão; [`tria_display/`](tria-esp/components/tria_display/) atualiza o OLED. |
| **Dados — RF08–RF09, RNF05** | [`flows.json`](ming/nodered/flows.json) valida, deduplica os últimos 100 IDs em memória e grava via HTTP no InfluxDB. O [dashboard](ming/grafana/dashboards/tria-dashboard.json) apresenta totais, classes, destinos, defeitos, produção, tempo de processamento e histórico. |
| **Integração — RF10, RNF03, RNF06** | [`main.c`](tria-esp/main/main.c), [`pi/main.py`](pi/main.py) e [`docker-compose.yml`](ming/docker-compose.yml) organizam os nós da bancada e os serviços locais. |

O firmware foi desenvolvido a partir da PoC do servo do Claylton. A configuração está em [`Kconfig.projbuild`](tria-esp/main/Kconfig.projbuild), acessível por `idf.py menuconfig`:

| Elemento | Padrão |
|----------|--------|
| Botão PRG / comando do vibrador / comando da esteira | GPIO 0 / 7 / 6; debounce do botão: 30 ms |
| Servo | GPIO 47; A/B/C: 45°/90°/135°; estabilização: 500 ms |
| OLED SDA / SCL / reset / Vext | GPIO 17 / 18 / 21 / 36 |

Montagem: [guia do micro servo](tria-esp/LIGACAO_MICRO_SERVO.md). O pino é configurado atualmente no `menuconfig`; o trecho de código desse guia é anterior à modularização. Os GPIOs dos motores são sinais para os circuitos de acionamento, cujo esquema ainda deve ser documentado.

## 5. Tópicos MQTT

| Tópico | Publica | Consome atualmente |
|--------|---------|--------------------|
| `tria/triagem` | Pi: classe, destino e evento | ESP32 e Node-RED |
| `tria/status/pi` | Pi: disponibilidade | Debug do Node-RED |
| `tria/status/esp32` | ESP32: estado e última decisão | Integração ao Pi/Node-RED prevista |
| `tria/atuador` | ESP32: confirmação com `id_evento` | Integração ao Pi/Node-RED prevista |

MQTT usa **QoS 1**; status são retidos e o ESP32 configura Last Will. Seu timeout de 15 s considera ausência de decisões válidas, inclusive durante pausas na alimentação de peças. O broker atual permite acesso anônimo na rede de bancada.

## 6. Payload MQTT (tria/triagem)

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

`id_evento` vincula inspeção e confirmação. A classe `QUADRADO_COM_X` usa `defeito: true` e destino `C`; o tempo de processamento é incluído quando medido. **O ESP32 atua ao receber a decisão**: ainda não usa `instante_atuacao` para agendamento. A confirmação é de software, após a espera configurada, sem sensor de posição do servo.

## 7. Requisitos e Critérios de Aceite

Resumo do [levantamento, seção 4](docs/TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf). São **metas a validar na bancada**, não resultados já comprovados. RF02/RF03 usam os símbolos nas placas de MDF; RF07 usa a plataforma vibratória com botão.

### Funcionais

| ID | Requisito | Meta |
|----|-----------|------|
| RF01 | Detectar passagem e capturar | ≥ 19/20 ciclos; um evento por peça e imagem ou log associado |
| RF02 / RF03 | Reconhecer quadrado, triângulo e X | ≥ 18/20 acertos por classe |
| RF04 | Comunicar via MQTT | ≥ 29/30 eventos consistentes |
| RF05 / RF06 | Posicionar servo e encaminhar | ≥ 27/30 comandos e ≥ 27/30 peças na saída correta |
| RF07 | Pré-separar por vibração | ≥ 8/10 ensaios com peças chegando separadas |
| RF08 / RF09 | Registrar e visualizar | 30/30 eventos sem perda ou extras; painéis conferem com a base |
| RF10 | Executar fluxo completo | ≥ 13/15 ciclos com saída correta e evento no dashboard |

### Não-funcionais

| ID | Requisito | Meta |
|----|-----------|------|
| RNF01 | Atuar no prazo | ≥ 18/20 ciclos com servo estabilizado ≥ 0,3 s antes da peça |
| RNF02 | Comunicação consistente | ≥ 29/30 entregas válidas |
| RNF03 | Operação contínua | 15 min ou 30 peças, o que ocorrer por último, sem reinício |
| RNF04 | Recuperar comunicação | Após interrupção de 15 s, reconectar em ≤ 30 s, sem comando antigo |
| RNF05 | Evitar duplicação | 30 IDs + 10 reenvios devem manter exatamente 30 eventos |
| RNF06 | Operar localmente | 15 min sem Internet, mantendo a rede local |

## 8. Dependências

### Hardware

- Raspberry Pi 5 (8 GB), câmera CSI V1.3 (5 MP), cabo adaptador e microSD.
- Heltec WiFi LoRa 32 V3 (ESP32-S3), com OLED e botão PRG integrados.
- Plataforma de papelão, motor vibratório, esteira, circuitos de acionamento e alimentação compatíveis com os motores.
- Micro servo de 5 V, fonte externa adequada, aleta desviadora e três saídas.
- Placas de MDF com símbolos, suporte da câmera, iluminação/fundo controlados, rede Wi-Fi e cabo USB de dados.

### Software, bibliotecas e ferramentas

| Camada | Dependências | Configuração |
|--------|--------------|--------------|
| Pi | Raspberry Pi OS 64 bits, libcamera, Python ≥ 3.10; OpenCV ≥ 4.8, NumPy ≥ 1.24, paho-mqtt ≥ 2.0, Picamera2 ≥ 0.3.12 | [`requirements.txt`](pi/requirements.txt), [`config.py`](pi/config.py) |
| Preparação e testes | Git, navegador, python3-venv, python3-pip, libcap-dev e pytest | Comandos da seção 10; [testes](pi/tests/test_classifier.py) |
| ESP32 | ESP-IDF 5.5.5 (`esp32s3`), u8g2 0.1.4; MQTT, cJSON, FreeRTOS, Wi-Fi, GPIO, LEDC e I2C do ambiente IDF; CMake/Ninja e toolchain | [Manifesto](tria-esp/main/idf_component.yml), [versões resolvidas](tria-esp/dependencies.lock) |
| MING | Docker Engine/Desktop + Compose v2 e as imagens abaixo | [`docker-compose.yml`](ming/docker-compose.yml) |

| Serviço | Imagem | Porta |
|---------|--------|-------|
| Mosquitto | `eclipse-mosquitto:2.0` | 1883 / 9001 (WebSocket) |
| Node-RED | `nodered/node-red:latest` | 1880 |
| InfluxDB | `influxdb:2.7` | 8086 |
| Grafana | `grafana/grafana:latest` | 3000 |

O flow usa nós nativos do Node-RED. O visualizador web usa a biblioteca padrão do Python. Tags `latest` e versões mínimas podem variar; registrar as versões utilizadas nos ensaios.

## 9. Como Rodar

Com as ferramentas da seção 9 instaladas, clone o [repositório](https://github.com/GilvanTWS/TCC-PNAAT):

```bash
git clone https://github.com/GilvanTWS/TCC-PNAAT.git
cd TCC-PNAAT
```

Se já estiver clonado, use a pasta existente. Cada etapa abaixo parte da raiz do projeto, em um novo terminal. **Inicie o MING (etapa 2) e prepare o ESP32 (etapa 3) antes da captura integrada no Pi.**

### 1. Classificador (Raspberry Pi)

```bash
sudo apt update
sudo apt install python3-venv python3-pip python3-picamera2 libcap-dev
cd pi
python3 -m venv --system-site-packages venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest tests/test_classifier.py -q
python main.py --imagem tests/images/q1.jpeg
```

Em `pi/config.py`, ajuste `MQTT_BROKER`: use `localhost` se o MING estiver no Pi ou o IP do computador que hospeda a stack. Ajuste também a faixa HSV e os parâmetros de câmera conforme a bancada. Picamera2 é instalado pelo sistema para acesso ao libcamera; a imagem estática permite testar sem câmera ou MQTT.

Depois, no mesmo ambiente virtual, execute:

```bash
python main.py --web
```

Acesse `http://IP_DO_PI:8081`. Alternativas: sem `--web` para janela local, `--sem-janela` para captura sem interface ou `--sem-mqtt` para teste isolado. A ROI pode ser ajustada com `--roi X Y W H`; a placa deve caber completamente nela.

#### Reproduzir e avaliar os vídeos de ensaio

O modo de vídeo usa a mesma ROI e a mesma máquina de estados da câmera ao
vivo, mas nunca publica MQTT. Para observar um ensaio gravado:

```bash
cd pi
python main.py --video tests/videos/misturado01.mp4
```

Em uma instalação sem monitor, use o visualizador web:

```bash
python main.py --video tests/videos/misturado01.mp4 --web
```

Os arquivos `misturado*.txt` contêm uma classe esperada por linha. O avaliador
processa todos os MP4, alinha as sequências e informa classificações corretas,
incorretas, perdidas e extras:

```bash
python evaluate_videos.py tests/videos
```

Para os vídeos de classe única, informe quantas peças foram apresentadas em
cada arquivo. O prefixo do nome define a classe esperada:

```bash
python evaluate_videos.py tests/videos --total-classe 10
```

Para guardar o resumo em uma planilha CSV:

```bash
python evaluate_videos.py tests/videos --total-classe 10 \
  --csv tests/videos/resultado.csv
```

Se a captura usou uma ROI manual, repita os mesmos valores durante a avaliação
com `--roi X Y W H`.

### 2. Stack MING

```bash
cd ming
docker compose config --quiet
docker compose up -d
docker compose ps
```

O flow, a fonte InfluxDB e o dashboard **TRIA - Monitoramento da Triagem** são provisionados automaticamente. Acesse Grafana em `http://IP_DO_HOST:3000`, Node-RED em `:1880` e InfluxDB em `:8086`.

Grafana e InfluxDB usam inicialmente `admin` / `admin123456`. A configuração de bancada usa organização `tria`, bucket `tria_events` e token `tria-token-2026`, mantidos coerentes entre Compose, flow e fonte do Grafana. Edições pela interface devem ser exportadas para atualizar os arquivos versionados.

### 3. Firmware ESP32 (tria-esp)

No terminal com o [ESP-IDF 5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/get-started/index.html) ativado:

```bash
cd tria-esp
idf.py set-target esp32s3
idf.py menuconfig
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

`set-target` prepara a primeira compilação. No `menuconfig`, configure SSID, senha, broker `mqtt://IP_DO_HOST_MING:1883`, pinos e ângulos da seção 5. Use a porta serial real do equipamento, como `/dev/ttyACM0` ou `COM3`. Não versione credenciais pessoais do `sdkconfig`.

### Verificação inicial

Pressione o botão para alimentar a esteira e apresente uma peça de cada símbolo. Confira classe/destino no Pi, confirmação e movimento do servo, saída física e atualização do Grafana. A partir de `ming/`, acompanhe os eventos:

```bash
docker compose exec mosquitto mosquitto_sub -h localhost -t 'tria/#' -v
```

Use os IDs para comparar inspeção e confirmação. Registre os ensaios da seção 8; testes com imagens não comprovam desempenho físico ou operação contínua.

## 10. Escopo

**Incluído:** alimentação vibratória por botão, transporte, reconhecimento dos três símbolos, decisão MQTT, servo A/B/C, OLED, registro temporal e dashboard local.

**Fora de escopo:** certificação industrial, integração com CLP/MES/ERP/nuvem, peças arbitrárias, Deep Learning e sensores dedicados de presença ou posição.

**A consolidar:** esquema dos circuitos dos motores, calibração de percurso/servo, evidências de desempenho e recuperação de rede. O consumo das confirmações pelo Pi/Node-RED, a persistência de estados e o painel de comunicação continuam previstos no levantamento.

## 11. Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS and Claylton-Muniz

