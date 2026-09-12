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
- [7. Payload MQTT](#7-payload-mqtt-triatriagem)
- [8. Requisitos e Critérios de Aceite](#8-requisitos-e-critérios-de-aceite)
- [9. Dependências](#9-dependências)
- [10. Como Rodar](#10-como-rodar)
- [11. Escopo](#11-escopo)
- [12. Licença](#12-licença)
- [13. Checklist de Conformidade](#13-checklist-de-conformidade)

## 1. Visão Geral

O **TRIA** é uma Prova de Conceito (PoC) física para validar experimentalmente a cadeia:

**pré-separação física → esteira → captura → classificação → MQTT → atuação do servo → três destinos físicos → registro e visualização no MING**

A solução aborda o **Cenário 2** do [documento de Cenários](docs/Cen%C3%A1rios.pdf): triagem de diferentes componentes misturados em uma linha de manufatura, com peças em posições variadas, em contato ou parcialmente sobrepostas. A proposta busca tornar a triagem repetível e rastreável, demonstrando o processo em escala de bancada.

O sistema integra **Visão Computacional** na borda (Raspberry Pi 5) e **Atuação Física via IoT** (ESP32-S3), orquestrados por uma arquitetura MQTT e monitorados pela **Stack MING** (Mosquitto, Node-RED, InfluxDB e Grafana).

Na montagem atual, uma **plataforma de papelão com um motor vibratório fixado embaixo** simula o pré-separador vibratório. O operador mantém o botão do ESP32 pressionado para movimentar as peças; elas avançam pela plataforma e caem na esteira. A câmera conectada ao Raspberry Pi observa as placas de MDF, e o software reconhece o **símbolo central**, decide o destino A/B/C e publica o evento. Os dados alimentam os gráficos do Grafana pela stack MING.

As **3 situações visuais** das peças de ensaio são:

- **QUADRADO** — símbolo quadrado na placa de MDF, peça normal (Saída A);
- **TRIÂNGULO** — símbolo triangular na placa de MDF, peça normal (Saída B);
- **QUADRADO COM X** — marca X na placa de MDF, representando defeito (Saída C, descarte).

O [levantamento de requisitos](docs/TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf) registra a proposta inicial. Este README documenta sua evolução: alimentação vibratória manual por botão, classificação da marca central e organização atual do código. Os critérios de desempenho da seção 8 são **metas de validação**, não resultados já comprovados.

## 2. Arquitetura da PoC

### Diagrama de blocos preliminar

**Fluxo físico das peças:**

```text
[Peças de MDF com símbolos]
             |
             v
[Plataforma de papelão + motor vibratório sob a base]
             | avanço por vibração e queda na esteira
             v
[Esteira: região de inspeção observada pela câmera CSI]
             | transporte da peça até o desviador
             v
[Aleta desviadora acionada por servo]
             |
             +----> [Saída A: QUADRADO]
             +----> [Saída B: TRIÂNGULO]
             +----> [Saída C: QUADRADO_COM_X / descarte]
```

**Sensoriamento, processamento, conectividade, atuação e software:**

```text
[Câmera CSI: imagens da região de inspeção]
             | CSI / Picamera2
             v
[Raspberry Pi 5 - Python / OpenCV - pasta pi/]
  Localizar MDF -> corrigir perspectiva -> reconhecer símbolo
             | resultado: classe, destino A/B/C, defeito, ID e horário
             | MQTT / TCP-IP pela rede local
             v
[Mosquitto - broker MQTT - stack ming/]
             |
             +--> [ESP32-S3 / ESP-IDF - pasta tria-esp/]
             |      | PWM, GPIO 47 -> [Servo / aleta A/B/C]
             |      | I2C          -> [OLED: classe, destino e estado]
             |      +-- MQTT ----> [Mosquitto: confirmação e status]
             |
             +--> [Node-RED: validar evento e deduplicar ID]
                         | HTTP / API de escrita
                         v
                    [InfluxDB: eventos de triagem]
                         | consultas Flux
                         v
                    [Grafana: gráficos e histórico]

[Botão PRG, GPIO 0] ---> [ESP32-S3: componente vibration]
                              | GPIO 7 / comando liga-desliga
                              v
                       [Circuito de acionamento do motor]
                              |
                              v
                       [Motor sob a plataforma de papelão]

[ESP32-S3: componente conveyor] -- GPIO 6 --> [Acionamento da esteira*]
```

As setas do primeiro bloco representam o percurso das peças; as do segundo representam imagens, dados ou comandos. Os blocos do ESP32 representam componentes do mesmo Heltec. O botão controla a vibração localmente, sem passar pelo MQTT. A decisão visual chega ao ESP32 por **Wi-Fi e MQTT**; o rádio LoRa da placa não é utilizado. O vídeo permanece no Pi, com visualização local ou HTTP opcional, e não é enviado pelo MQTT.

\* O componente `conveyor` já configura o GPIO 6 em nível alto na inicialização. O uso desse sinal no acionamento físico depende do circuito da esteira da bancada; o código não implementa controle de velocidade.

### Elementos de hardware e software e fluxo entre eles

| Nó | Tipo | Papel na solução |
|----|------|------------------|
| Plataforma de papelão + motor vibratório | Hardware (alimentação e atuação) | Movimenta as peças até a esteira e busca reduzir contato/sobreposição |
| Botão PRG do ESP32 | Hardware (entrada de comando) | Solicita vibração enquanto pressionado |
| Esteira + desviador e três saídas | Hardware (transporte e encaminhamento) | Conduz as peças pela inspeção até A/B/C |
| Câmera CSI V1.3 | Hardware (sensoriamento) | Captura a região de inspeção (entrada da visão) |
| Raspberry Pi 5 + Picamera2/OpenCV | Hardware + software (processamento) | Localiza a placa de MDF, corrige a perspectiva e classifica seu símbolo central |
| Rede local + Mosquitto / MQTT | Infraestrutura + software (conectividade) | Distribui a decisão entre Pi, ESP32 e Node-RED |
| ESP32-S3 + firmware ESP-IDF | Hardware + software (atuação IoT) | Lê o botão, comanda a vibração, posiciona o servo e atualiza o OLED |
| Node-RED, InfluxDB, Grafana | Software (integração e dados) | Valida, registra a série temporal e apresenta o dashboard |

Fluxo físico: entrada → pré-separador → esteira → região de inspeção → desviador (servo) → saídas A/B/C.

Fluxo de dados: Pi → Mosquitto → ESP32 (atuação) + Node-RED → InfluxDB → Grafana (monitoramento, sem participar da decisão).

O firmware comanda o servo ao receber uma decisão válida e espera o tempo configurado de estabilização. A confirmação é gerada pelo software; a bancada não possui sensor de posição do servo. A sincronização com a chegada real da peça ainda deve ser aferida conforme RNF01.

## 3. Situação visual e destino

| Símbolo reconhecido na placa de MDF | Decisão | Destino físico |
|-----------------|---------|----------------|
| QUADRADO | Peça normal | Saída A - Quadrado |
| TRIÂNGULO | Peça normal | Saída B - Triângulo |
| QUADRADO COM X | Peça defeituosa | Saída C - Descarte |

Os nomes das classes foram preservados para manter o contrato MQTT do levantamento. Na implementação atual, a localização da placa e o reconhecimento do símbolo são etapas distintas: o formato do fundo ou da esteira não determina a classe. Uma marca ausente ou desconhecida provoca nova tentativa enquanto a peça permanece na ROI; o pipeline não publica uma classificação válida nessa condição.

## 4. Estrutura do Repositório

```text
TCC-PNAAT/
├── docs/                          Documentação acadêmica e entregas
│   ├── TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf
│   ├── RoteiroVideoPitch.pdf
│   ├── Cenários.pdf
│   └── Apostila Trabalho de Conclusão da Capacitação - PNAAT 2026.pdf
│
├── pi/                            Código Python (visão computacional - Raspberry Pi)
│   ├── main.py                    Captura, ROI, estados, MQTT e visualização web/local
│   ├── classifier.py              Localização do MDF e classificação do símbolo central
│   ├── mqtt_publisher.py          Publica decisões e status nos tópicos MQTT
│   ├── config.py                  Configurações centralizadas (classes, destinos, calibração)
│   ├── requirements.txt           Dependências Python
│   ├── quadrado.jpeg              Foto adicional: símbolo quadrado
│   ├── triangulo.jpeg             Foto adicional: símbolo triangular
│   ├── erro.jpeg                  Foto adicional: marca X
│   └── tests/
│       ├── test_classifier.py     Testes com pytest (sem hardware)
│       └── images/                18 imagens de referência: q1-q6, t1-t6 e x1-x6
│
├── tria-esp/                      Firmware ESP32 do nó de atuação (ESP-IDF)
│   ├── components/
│   │   ├── servo/                PWM do micro servo por LEDC
│   │   ├── tria_actuator/        Posições A/B/C e espera de estabilização
│   │   ├── tria_display/         OLED SSD1306 via I2C
│   │   ├── tria_network/         Wi-Fi, MQTT, confirmações e supervisão
│   │   ├── vibration/            Botão PRG, debounce e comando do vibrador
│   │   └── conveyor/             Saída digital de acionamento da esteira
│   ├── main/
│   │   ├── main.c                 Inicialização e integração dos componentes
│   │   ├── Kconfig.projbuild      Configuração via menuconfig
│   │   ├── CMakeLists.txt         Dependências do componente principal
│   │   └── idf_component.yml      Requisito do ESP-IDF e biblioteca u8g2
│   ├── CMakeLists.txt             Projeto de compilação ESP-IDF
│   ├── dependencies.lock         Versões resolvidas e target esp32s3
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
│       ├── datasources/influxdb.yml        Fonte InfluxDB / Flux
│       ├── provisioning/dashboards.yml     Carregamento automático do painel
│       └── dashboards/tria-dashboard.json  Dashboard versionado
│
├── .gitignore
├── README.md
└── LICENSE
```

Atalhos para os materiais: [documentação acadêmica](docs/), [código de visão](pi/), [componentes do ESP32](tria-esp/components/), [configuração da stack](ming/docker-compose.yml) e [dashboard](ming/grafana/dashboards/tria-dashboard.json). Os componentes do firmware incluem seus arquivos `CMakeLists.txt` e cabeçalhos em `include/`.

## 5. Componentes

### Raspberry Pi (visão computacional)

- [**main.py**](pi/main.py) - Pipeline principal:
  - Captura ao vivo com **Picamera2** (câmera CSI fixa)
  - Detecta quando uma nova peça entra na **ROI**, sem sensor de presença
  - Confirma presença e ausência por quadros consecutivos, com estados `livre`, `ocupado_aguardando` e `ocupado_classificado`
  - Limita a um evento de classificação por ocupação da ROI; libera a próxima detecção após a saída da peça (apoio ao RNF05)
  - Publica a decisão no MQTT e mede o tempo de processamento
  - Visualização em janela OpenCV ou no navegador (`--web`, porta padrão `8081`); opção `--sem-janela`
  - Modos `--imagem` para teste sem câmera e `--sem-mqtt` para captura sem broker; ROI ajustável por `--roi X Y W H`
- [**classifier.py**](pi/classifier.py) - Classifica as 3 situações visuais usando OpenCV:
  - Localiza o MDF por faixa de cor HSV, área e geometria, rejeitando candidatos que tocam a borda da ROI
  - Retifica a placa para uma imagem de 400 × 400 pixels e analisa sua região central
  - Realça a marca escura com operação morfológica black-hat, limiar de Otsu e contornos
  - Reconhece **triângulo** por 3 vértices e **quadrado** por 4 vértices, com solidez mínima de 0,80
  - Reconhece **X** por contorno côncavo, pelo menos 6 vértices e solidez abaixo de 0,75
  - O algoritmo atual usa geometria do símbolo; a abordagem com linhas de Hough descrita na proposta inicial foi substituída
- [**mqtt_publisher.py**](pi/mqtt_publisher.py) - Publica nos tópicos MQTT:
  - `tria/triagem` - resultado da inspeção (payload mínimo: id_evento, horario, classe, destino, defeito)
  - `tria/status/pi` - disponibilidade do processo de visão
- [**config.py**](pi/config.py) - Broker, tópicos, classes, destinos, faixa HSV, câmera, detecção e parâmetros de percurso
- [**tests/test_classifier.py**](pi/tests/test_classifier.py) - Testes de imagens, destinos, rejeição de fundo vazio e estados de detecção

### ESP32 (nó de atuação - Heltec WiFi LoRa 32 V3) — `tria-esp/`

Firmware ESP-IDF construído sobre a **PoC do servo do Claylton** (`components/servo`), organizado em componentes:

- [`vibration`](tria-esp/components/vibration/vibration.c): liga o vibrador enquanto o botão PRG está pressionado e desliga ao soltá-lo; o motor inicia desligado. A leitura inclui debounce de 30 ms por padrão.
- [`conveyor`](tria-esp/components/conveyor/conveyor.c): coloca a saída de comando da esteira em nível alto na inicialização; disponibiliza função de ligar/desligar, sem ajuste de velocidade.
- [`tria_network`](tria-esp/components/tria_network/tria_network.c): conecta ao Wi-Fi, assina `tria/triagem`, publica confirmação em `tria/atuador` e estado em `tria/status/esp32`; inclui reconexão, Last Will e supervisão por timeout.
- [`tria_actuator`](tria-esp/components/tria_actuator/tria_actuator.c) + [`servo`](tria-esp/components/servo/servo.c): convertem A/B/C em ângulos configuráveis e geram PWM por **LEDC a 50 Hz**; a espera padrão de estabilização é de 500 ms.
- [`tria_display`](tria-esp/components/tria_display/tria_display.c): exibe classe, destino e estado no OLED integrado, com controle de alimentação Vext, reset e I2C.
- [`main/main.c`](tria-esp/main/main.c): inicializa os componentes e conecta as decisões MQTT à atuação e ao display.

O timeout padrão de 15 s considera o tempo sem **decisão válida recebida**. Assim, o OLED pode indicar ausência de comunicação durante uma pausa no fornecimento de peças, mesmo que a conexão com o broker permaneça ativa. Essa sinalização deve ser considerada nos ensaios de recuperação (RNF04).

### Pinagem e parâmetros iniciais do ESP32

Os valores abaixo são os padrões de [`main/Kconfig.projbuild`](tria-esp/main/Kconfig.projbuild), ajustáveis em `idf.py menuconfig` conforme a montagem:

| Elemento | GPIO / valor padrão | Função |
|----------|---------------------|--------|
| Botão PRG | GPIO 0, ativo em nível baixo | Entrada com pull-up; pressionar solicita vibração |
| Comando do vibrador | GPIO 7 | Saída digital para o circuito de acionamento do motor |
| Comando da esteira | GPIO 6 | Saída digital, inicia em nível alto |
| Sinal do servo | GPIO 47 | PWM a 50 Hz |
| Posições A / B / C | 45° / 90° / 135° | Valores iniciais a calibrar na montagem |
| Estabilização do servo | 500 ms | Espera antes da confirmação MQTT |
| OLED SDA / SCL | GPIO 17 / GPIO 18 | Comunicação I2C |
| OLED reset / Vext | GPIO 21 / GPIO 36 | Reset e alimentação; Vext ativo em nível baixo |

**Guia de ligação:** [`tria-esp/LIGACAO_MICRO_SERVO.md`](tria-esp/LIGACAO_MICRO_SERVO.md) — onde conectar cada fio do micro servo (GND, VCC e sinal PWM no `GPIO 47`).

O trecho de configuração do guia do servo é anterior à modularização: o pino atual é definido por `CONFIG_TRIA_SERVO_GPIO` no `menuconfig`. Para os motores, GPIO 6 e GPIO 7 são sinais de comando para um circuito de acionamento compatível com a carga. A identificação do driver e o esquema elétrico completo da bancada ainda devem ser registrados.

### Stack MING (Docker)

- **Mosquitto** - Broker MQTT local (portas 1883/9001 WebSocket)
- **Node-RED** - Valida campos, evita reprocessamento de IDs conhecidos, grava no InfluxDB
- **InfluxDB** - Armazena eventos na organização `tria`, bucket `tria_events`, measurement `triagem`
- **Grafana** - Dashboard provisionado: totais, peças normais/defeituosas, taxa de defeitos, classes, destinos, produção por minuto, tempo médio de processamento e últimas inspeções; atualização a cada 5 s

O [flow versionado](ming/nodered/flows.json) usa nós nativos do Node-RED e escreve no InfluxDB pela API HTTP, sem extensão adicional de InfluxDB. A deduplicação mantém os últimos 100 IDs em memória. O status do Pi é encaminhado ao debug; a persistência dos estados, o consumo das confirmações do ESP32 e o painel de comunicação permanecem previstos no levantamento.

## 6. Tópicos MQTT

| Tópico | Publica | Assina no código atual | Conteúdo |
|--------|---------|------------------------|----------|
| `tria/triagem` | Raspberry Pi | ESP32, Node-RED | Resultado da inspeção e destino |
| `tria/status/pi` | Raspberry Pi | Node-RED | Disponibilidade do processo de visão |
| `tria/status/esp32` | ESP32 | Consumo pelo Node-RED/Pi ainda previsto | Estado do nó, última classe e destino |
| `tria/atuador` | ESP32 | Consumo pelo Pi/Node-RED ainda previsto | Confirmação vinculada ao id_evento |

Os eventos e confirmações usam **QoS 1**, sem retenção. Os status usam QoS 1 com retenção; o ESP32 configura Last Will. O broker permite conexões anônimas na configuração atual de bancada. QoS 1 admite reentrega, por isso o controle de IDs continua necessário.

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

`id_evento` identifica a inspeção e acompanha a confirmação do atuador. `horario` é gerado no Pi; o Node-RED o converte para o timestamp do registro. `tempo_processamento_ms` é incluído quando medido pelo pipeline.

O campo `instante_atuacao` contém atualmente a estimativa, em segundos, calculada como `distância / velocidade + margem` (3,3 s com os valores padrão de `pi/config.py`). **O ESP32 ainda não utiliza esse campo para agendar o movimento**: atua assim que recebe a decisão. A temporização deverá ser calibrada e validada na bancada para comprovar RNF01.

## 8. Requisitos e Critérios de Aceite

Referência: [levantamento de requisitos, seção 4](docs/TRIA_Entrega_1_Levantamento_de_Requisitos_PoC_Fisica.pdf). Os critérios abaixo preservam os identificadores do documento e representam metas preliminares. RF02/RF03 são demonstrados, na versão atual, pelos símbolos nas placas de MDF; RF07 utiliza a plataforma de papelão com acionamento manual por botão. O operador alimenta a bancada, enquanto o Pi escolhe automaticamente classe e destino.

### Funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RF01 | Detectar passagem e capturar | >= 19/20 ciclos válidos, no máximo um evento por peça e imagem ou log associado |
| RF02 | Classificar quadrado e triângulo | >= 18/20 para cada classe |
| RF03 | Identificar a marca X (defeito) | >= 18/20 como defeito |
| RF04 | Comunicar via MQTT | >= 29/30 eventos consistentes |
| RF05 | Posicionar servo corretamente | >= 27/30 comandos; confirmar por MQTT e observação antes da chegada da peça |
| RF06 | Encaminhar fisicamente | >= 27/30 peças na saída correta |
| RF07 | Pré-separação por vibração | >= 8/10 ensaios com peças inicialmente em contato/sobrepostas chegando separadas |
| RF08 | Registrar no InfluxDB | 30/30 registros sem perda |
| RF09 | Apresentar no Grafana | Painéis conferem com InfluxDB |
| RF10 | Fluxo completo | >= 13/15 ciclos com saída correta e evento no dashboard, sem seleção manual de classe/destino |

### Não-funcionais

| ID | Requisito | Critério |
|----|-----------|----------|
| RNF01 | Preparar atuação no prazo | Em >= 18/20 ciclos, servo estabiliza com >= 0,3 s de margem antes da chegada |
| RNF02 | Consistência da comunicação | >= 29/30 entregas válidas |
| RNF03 | Operar continuamente | 15 minutos ou 30 peças, o que ocorrer por último, sem reinício manual |
| RNF04 | Recuperar comunicação | Após interrupção de 15 s, reconectar em <= 30 s e aceitar novo evento sem executar comando antigo |
| RNF05 | Não duplicar contagens | 30 IDs únicos + 10 reenvios idênticos devem manter exatamente 30 eventos |
| RNF06 | Funcionar localmente | 15 minutos sem Internet |

### Relação entre requisitos, arquitetura e arquivos

| Etapa / requisitos | Elementos da arquitetura | Código ou configuração |
|-------------------|--------------------------|------------------------|
| Captura e classificação: RF01-RF03 | Câmera CSI + Raspberry Pi | [`pi/main.py`](pi/main.py), [`pi/classifier.py`](pi/classifier.py), [`pi/config.py`](pi/config.py) |
| Decisão e comunicação: RF04, RNF02, RNF04 | Pi, Wi-Fi, Mosquitto e ESP32 | [`pi/mqtt_publisher.py`](pi/mqtt_publisher.py), [`tria_network.c`](tria-esp/components/tria_network/tria_network.c), [`mosquitto.conf`](ming/mosquitto/mosquitto.conf) |
| Atuação e encaminhamento: RF05-RF06, RNF01 | ESP32, servo e saídas A/B/C | [`tria_actuator.c`](tria-esp/components/tria_actuator/tria_actuator.c), [`servo.c`](tria-esp/components/servo/servo.c), [`Kconfig.projbuild`](tria-esp/main/Kconfig.projbuild) |
| Pré-separação: RF07 | Botão, ESP32, motor e plataforma de papelão | [`vibration.c`](tria-esp/components/vibration/vibration.c) |
| Registro e visualização: RF08-RF09, RNF05 | Node-RED, InfluxDB e Grafana | [`flows.json`](ming/nodered/flows.json), [`tria-dashboard.json`](ming/grafana/dashboards/tria-dashboard.json), [`test_classifier.py`](pi/tests/test_classifier.py) |
| Integração e operação local: RF10, RNF03, RNF06 | Bancada completa e rede local | [`main.c`](tria-esp/main/main.c), [`pi/main.py`](pi/main.py), [`docker-compose.yml`](ming/docker-compose.yml) |

Os arquivos indicam onde cada requisito é tratado ou será validado. A comprovação quantitativa exige os ensaios, logs, fotos e registros previstos no levantamento; testes com imagens estáticas não comprovam encaminhamento físico ou desempenho contínuo.

## 9. Dependências

### Hardware (Kit Maker + bancada)

| Recurso | Função |
|---------|--------|
| Raspberry Pi 5, 8 GB | Captura e processamento; decide e publica MQTT |
| Câmera CSI V1.3 (5 MP) + cabo adaptador | Captura da região de inspeção |
| Heltec WiFi LoRa 32 V3 (ESP32-S3) + OLED | Nó de atuação: servo, OLED, MQTT |
| Plataforma de papelão | Base atual do alimentador vibratório, posicionada antes da esteira |
| Esteira da bancada | Transporte da câmera ao desviador |
| Micro servo de 5 V + fonte externa de pelo menos 1 A | Aleta desviadora de 3 posições; conferir o modelo conforme o guia de ligação |
| Motor vibratório sob a plataforma | Movimenta as peças para a esteira enquanto o botão está pressionado |
| Botão PRG integrado ao ESP32 | Comando manual da vibração; não requer botão externo no padrão atual |
| Circuito de acionamento e alimentação dos motores | Interface entre GPIOs e cargas; modelo do driver, tensão e corrente a documentar conforme a montagem |
| Desviador + 3 calhas | Encaminhamento às saídas A/B/C |
| Placas de MDF com símbolos quadrado, triângulo e X | Amostras reproduzíveis para localização e reconhecimento da marca |
| Fonte 5 V, microSD 128 GB, suporte, iluminação/fundo fosco | Apoio de bancada |
| Rede local, cabo USB de dados e computador de desenvolvimento | Comunicação Pi/ESP32, gravação e monitoramento do firmware |

### Software e bibliotecas (Pi — `pi/`)

| Dependência | Versão mínima | Uso |
|-------------|---------------|-----|
| Raspberry Pi OS 64 bits + libcamera | Compatível com Pi 5 e câmera CSI | Sistema operacional e suporte à captura |
| Python | >= 3.10 | Linguagem do pipeline |
| opencv-python | >= 4.8 | Segmentação HSV, perspectiva, morfologia, Otsu, contornos e approxPolyDP |
| numpy | >= 1.24 | Cálculos geométricos e vetoriais |
| paho-mqtt | >= 2.0 | Cliente MQTT (publicação de eventos) |
| picamera2 | >= 0.3.12 | Interface com a câmera CSI |
| pytest | Ferramenta de desenvolvimento, instalada separadamente | Executa `pi/tests/test_classifier.py` |
| python3-venv, python3-pip, libcap-dev | Pacotes do Raspberry Pi OS | Ambiente virtual, instalação e suporte à dependência python-prctl |

As quatro bibliotecas de execução estão declaradas em [`pi/requirements.txt`](pi/requirements.txt). O visualizador HTTP/MJPEG usa a biblioteca padrão do Python, sem Flask ou servidor externo. A instalação de Picamera2 pelo sistema segue a [orientação oficial do projeto](https://github.com/raspberrypi/picamera2#installation), para manter compatibilidade com libcamera.

### Firmware (ESP32 — `tria-esp/`)

| Dependência | Uso |
|-------------|-----|
| ESP-IDF 5.5.5, target `esp32s3` | Versão registrada em `dependencies.lock`; manifesto exige IDF >= 5.0 |
| ESP-MQTT (`mqtt` do ESP-IDF 5.x) | Cliente MQTT no ESP32 |
| `nixy4/u8g2` 0.1.4 | Driver do OLED SSD1306; manifesto declara `^0.1.4` |
| `json` / cJSON do ESP-IDF | Leitura do payload MQTT |
| `driver` / LEDC, GPIO e I2C | PWM do servo, leitura do botão, comandos dos motores e OLED |
| FreeRTOS, esp_wifi, esp_netif, esp_event, nvs_flash | Tarefas, Wi-Fi, eventos e inicialização de armazenamento |
| CMake, Ninja, Python e toolchain ESP32-S3 | Ferramentas fornecidas/configuradas pelo ambiente ESP-IDF |
| Componentes locais em `tria-esp/components/` | Servo, atuação, display, rede, vibração e esteira |

O manifesto e as versões resolvidas estão em [`idf_component.yml`](tria-esp/main/idf_component.yml) e [`dependencies.lock`](tria-esp/dependencies.lock). O ambiente [`.devcontainer/`](tria-esp/.devcontainer/) é opcional; seu Dockerfile usa `espressif/idf:latest` por padrão, portanto não fixa a mesma versão do lock.

### Stack MING (integração e dados — `ming/`)

| Serviço | Imagem | Porta | Uso |
|---------|--------|-------|-----|
| Mosquitto | eclipse-mosquitto:2.0 | 1883 / 9001 | Broker MQTT local (MQTT + WebSocket) |
| Node-RED | nodered/node-red:latest | 1880 | Validação, transformação e deduplicação |
| InfluxDB | influxdb:2.7 | 8086 | Banco de série temporal (bucket `tria_events`) |
| Grafana | grafana/grafana:latest | 3000 | Dashboard (totais, classes, defeitos, histórico) |

São necessários **Docker Engine ou Docker Desktop, Docker Compose v2, Git e navegador**. As imagens e os volumes estão definidos em [`ming/docker-compose.yml`](ming/docker-compose.yml); Node-RED e Grafana usam a tag variável `latest`, e as bibliotecas Python usam versões mínimas. Para registrar um ensaio reproduzível, anotar as versões efetivamente utilizadas.

## 10. Como Rodar

### Pré-requisitos

- Git e acesso ao repositório [GilvanTWS/TCC-PNAAT](https://github.com/GilvanTWS/TCC-PNAAT).
- Docker + Docker Compose v2 no host da stack MING (Pi ou computador na mesma rede).
- Raspberry Pi OS 64 bits, Python 3.10+ e câmera CSI para captura ao vivo.
- [Ambiente ESP-IDF 5.5.5](https://docs.espressif.com/projects/esp-idf/en/v5.5.5/esp32s3/get-started/index.html), cabo USB de dados e acesso à porta serial para gravar o ESP32.

Preparação inicial, em um terminal:

```bash
git clone https://github.com/GilvanTWS/TCC-PNAAT.git
cd TCC-PNAAT
```

Se o repositório já estiver clonado, abra sua pasta existente. Cada bloco abaixo parte da raiz `TCC-PNAAT/`, em um novo terminal. Para a operação integrada, **inicie a stack da etapa 2 antes da captura ao vivo da etapa 1** e configure o ESP32 na etapa 3.

Defina o host do broker: em [`pi/config.py`](pi/config.py), `MQTT_BROKER = "localhost"` funciona se o MING estiver no próprio Pi. Se estiver em outro computador, use o IP desse computador. No ESP32, informe `mqtt://IP_DO_HOST_MING:1883` no `menuconfig`; no Node-RED em Docker, o endereço interno já é `mosquitto:1883`.

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

O ambiente virtual herda os pacotes de câmera instalados pelo sistema. O comando de [pytest](https://docs.pytest.org/en/stable/how-to/usage.html) executa os testes existentes; chamar o arquivo diretamente não executa suas funções de teste. O modo `--imagem` classifica uma foto local sem câmera e sem publicar eventos MQTT.

Com o broker iniciado e a câmera conectada, escolha **um** modo de execução no terminal com o ambiente virtual ativo:

```bash
python main.py                       # câmera ao vivo e janela OpenCV
python main.py --web                 # câmera ao vivo no navegador
python main.py --sem-janela          # captura e MQTT sem visualização
python main.py --web --sem-mqtt      # teste da câmera sem integração MQTT
```

Com `--web`, acesse `http://IP_DO_PI:8081`. A porta pode ser alterada com `--porta-web 8082`; também existem `/stream.mjpg` e `/snapshot.jpg`. Para ajustar a área de inspeção, utilize, por exemplo, `--roi 160 96 320 288` para quadros de 640 × 480. A placa deve caber inteiramente nessa área. Ajuste faixa HSV e demais limiares em `pi/config.py` conforme luz, fundo e amostras.

Em computador **sem Raspberry Pi**, os testes com imagens dispensam Picamera2. Com Python instalado, crie e ative um ambiente virtual, instale `opencv-python>=4.8.0`, `numpy>=1.24.0`, `paho-mqtt>=2.0.0` e `pytest`, e execute os mesmos comandos de teste a partir de `pi/`.

### 2. Stack MING

```bash
cd ming
docker compose config --quiet
docker compose up -d
docker compose ps
```

Aguarde a inicialização dos quatro serviços antes de alimentar a bancada. O flow do Node-RED, a fonte InfluxDB e o dashboard Grafana são carregados pelos arquivos versionados; não é necessário montar o painel manualmente.

Interfaces disponíveis:

- **Grafana:** http://localhost:3000 (login `admin` / `admin123456`)
- **Node-RED:** http://localhost:1880
- **InfluxDB:** http://localhost:8086
- **Broker MQTT:** localhost:1883

`localhost` se refere ao host do Docker. Ao acessar de outro equipamento, substitua pelo IP desse host. InfluxDB também inicia com `admin` / `admin123456`; organização `tria`, bucket `tria_events` e token de demonstração `tria-token-2026`, conforme o Compose e o provisionamento. Se configurar outros valores, mantenha o token e a organização/bucket coerentes no Compose, no flow do Node-RED e em `ming/grafana/datasources/influxdb.yml`. A operação local usa os valores de bancada versionados.

O dashboard **TRIA - Monitoramento da Triagem** é provisionado
automaticamente a partir de `ming/grafana/dashboards/tria-dashboard.json`.
Ele contém totais, taxa de defeitos, distribuições por classe e destino,
produção por minuto, tempo de processamento e as últimas inspeções.

Para acompanhar a integração a partir de `ming/`:

```bash
docker compose logs --tail=50 nodered
docker compose exec mosquitto mosquitto_sub -h localhost -t 'tria/#' -v
```

O segundo comando acompanha decisões, status e confirmações; encerre com `Ctrl+C`. A gravação bem-sucedida no InfluxDB recebe HTTP 204; o flow registra erros quando a escrita falha. O arquivo `nodered/flows.json` é montado somente para leitura: para persistir mudanças feitas no editor, exporte o flow e atualize sua cópia no repositório.

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
idf.py menuconfig
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Execute no terminal com o ambiente ESP-IDF ativado. `set-target` é uma preparação para a primeira compilação; em projeto já configurado, confirme o target antes de repeti-lo. `/dev/ttyUSB0` é um exemplo: use a porta identificada no seu equipamento, como `/dev/ttyACM0` no Linux ou `COM3` no Windows.

No `menuconfig`, preencha **TRIA - Rede** (SSID, senha e URI do broker) e confira **TRIA - Vibração**, **TRIA - Esteira**, **TRIA - Atuação (servo)**, **TRIA - OLED** e **TRIA - Watchdog de comunicação**. Os GPIOs devem corresponder à seção 5. A configuração local fica em `sdkconfig`; confira os arquivos antes de versionar para não incluir credenciais pessoais.

### Verificação inicial da bancada

1. Com os circuitos montados e alimentados conforme os componentes usados, confira o OLED e a conexão MQTT do ESP32.
2. Pressione e mantenha o botão PRG para acionar o motor sob a plataforma de papelão; solte para interromper a vibração.
3. Inicie o pipeline no Pi e apresente uma placa de cada símbolo completamente dentro da ROI, liberando a região entre as peças.
4. Confira classe e destino no Pi, o mesmo `id_evento` em `tria/triagem` e `tria/atuador`, a posição comandada no servo e a saída física observada.
5. Confira os eventos no Node-RED e os gráficos no Grafana, selecionando o intervalo de tempo do ensaio. Sem MQTT, o Pi pode continuar exibindo classificações locais, mas isso não valida a integração.
6. Registre os resultados dos ensaios da seção 8, incluindo falhas e parâmetros de montagem. A execução em ambiente limpo e os critérios físicos devem ser comprovados com essas evidências.

## 11. Escopo

### Incluído

- Pré-separação com plataforma de papelão e motor vibratório, acionada manualmente pelo botão do ESP32
- Transporte pela esteira e saída digital de comando disponível no firmware
- Classificação dos símbolos centrais nas placas de MDF (quadrado, triângulo e X) com OpenCV
- Detecção da marca X contrastante (defeito)
- Comunicação MQTT local entre Pi, ESP32 e Node-RED
- Atuação com servo de 3 posições
- Dashboard com totais, classes, defeitos e histórico
- Registro temporal de todos os eventos
- Visualização da câmera em janela ou navegador e testes com imagens estáticas

### Fora de escopo

- Certificação industrial / normas de segurança
- Integração com CLP, MES, ERP ou nuvem
- Reconhecimento de peças arbitrárias ou Deep Learning
- Sensor óptico, encoder ou sensor de presença dedicado

### Consolidação e validação previstas

- Documentar o circuito dos motores e validar a eficácia da pré-separação; a alimentação atual depende do operador pressionar o botão.
- Calibrar o desviador e medir o intervalo entre captura, decisão e chegada; `instante_atuacao` ainda não agenda a atuação no ESP32.
- Integrar consumo/persistência das confirmações e estados ao MING e ao Pi conforme a proposta, incluindo o painel de comunicação.
- Validar recuperação de rede, reentrega de mensagens, deduplicação e operação contínua; o cache de IDs do Node-RED é limitado e fica em memória.
- Consolidar evidências de montagem e desempenho e registrar as versões utilizadas nos ensaios.

## 12. Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS and Claylton-Muniz

## 13. Checklist de Conformidade

Este checklist trata dos artefatos da **Entrega 4 - Esboço da Documentação**, seguindo a organização e a reprodutibilidade discutidas na [apostila, Unidade 3, páginas 16-20](docs/Apostila%20Trabalho%20de%20Conclus%C3%A3o%20da%20Capacita%C3%A7%C3%A3o%20-%20PNAAT%202026.pdf).

- [x] Repositório Git existente, com README e sumário dos tópicos técnicos.
- [x] Diagrama de blocos com percurso físico, sensoriamento, processamento, conectividade, atuação e visualização (seção 2).
- [x] Hardware, bibliotecas, plataformas, ferramentas e recursos identificados por componente (seção 9).
- [x] Requisitos, diagrama e dependências relacionados à mesma solução integrada de IoT e visão computacional (seções 2, 8 e 9).
- [x] Pastas organizadas por documentação, visão, firmware e stack; caminhos permitem localizar os arquivos citados (seções 4 e 5).
- [x] Passos iniciais de preparação, instalação e configuração compatíveis com os arquivos e dependências do projeto (seção 10).
- [x] Funcionamento atual e etapas de validação previstas explicitados (seções 1, 5, 8 e 11).

A conclusão deste checklist documental não comprova os resultados dos ensaios físicos. Para entregar, a versão atualizada do README deve estar publicada no repositório cujo link será informado na atividade.
