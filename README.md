# TRIA - Triagem Visual Integrada de Componentes

Projeto de Conclusão de Curso do programa **PNAAT 2026** (Programa Nacional de Aprendizagem Acelerada em Tecnologia).

## Visão Geral

O **TRIA** é um protótipo de **visão computacional + IoT** para triagem automática de componentes em uma esteira de produção industrial. Uma câmera captura peças impressas em 3D, um classificador OpenCV as reconhece pela forma geométrica e o resultado é publicado via **MQTT** para um painel web que simula a esteira em tempo real.

O sistema classifica as peças em **5 destinos**:

| Código | Destino | Descrição |
|--------|---------|-----------|
| **A** | Circular | Peça reconhecida como círculo |
| **B** | Quadrada | Peça reconhecida como quadrado |
| **C** | Triangular | Peça reconhecida como triângulo |
| **R** | Revisão | Peça ambígua na 1ª passagem → reanálise |
| **D** | Descarte | Peça ainda ambígua após reanálise / não conforme |

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
                                    │ Daemon MQTT      │
                                    │ broker.hivemq.com│
                                    └────────┬─────────┘
                                             ▼
                                    ┌──────────────────┐
                                    │  Esteira Virtual │
                                    │   (React/MQTT.js)│
                                    └──────────────────┘
```

### Fluxo MQTT

- **Tópico:** `esteira/separacao`
- **QoS:** `1`
- **Retain:** `false`
- **Publicador:** Raspberry Pi (classificador)
- **Assinante:** Painel web (esteira virtual)

O Raspberry Pi publica um JSON com `id_evento` e `destino`:

```json
{"id_evento": "pi-1234567890ab", "destino": "A", "timestamp": "2026-01-01T12:00:00"}
```

O painel web usa o `id_evento` para deduplicar mensagens e animar o destino (A/B/C/R/D).

## Estrutura do Repositório

```
TCC-PNAAT/
│
├── docs/                     Documentação acadêmica
│   ├── Levantamento_de_Requisitos.pdf
│   ├── Cenários.pdf
│   └── Apostila ... PNAAT 2026.pdf
│
├── pi/                       Código Python (visão computacional)
│   ├── classifier.py         OpenCV: contornos, vértices, circularidade, revisão
│   ├── mqtt_publisher.py     Publica destino no tópico esteira/separacao
│   ├── config.py             Tópicos, classes, thresholds, constantes
│   ├── requirements.txt      Dependências Python
│   └── tests/
│       └── test_classifier.py  Testes locais (sem hardware)
│
├── demo-esteira/             Painel web React (esteira virtual)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx           Lógica e animação da esteira
│       ├── App.css           Visual do chão de fábrica
│       └── index.css         Estilos globais
│
├── .gitignore
├── README.md
└── LICENSE
```

## Classificador

A pasta `pi/` contém o classificador que decide o destino de cada peça a partir de uma imagem:

1. **Pré-processamento** — escala de cinza + binarização.
2. **Detecção de contornos** — filtra contornos com área mínima relevante.
3. **Análise de forma** — conta vértices e calcula a circularidade.
4. **Reanálise automática** — se a confiança fica abaixo do limiar, tenta parâmetros alternativos de binarização.
5. **Decisão final**:
   - Confiante → `A`, `B` ou `C`
   - Ambígua na 1ª passagem → `R` (vai para a revisão)
   - Ambígua ao retornar da revisão → `D` (descarte)

### Rodar os testes

```bash
cd pi
source venv/bin/activate   # ou criar um ambiente com as dependências
python tests/test_classifier.py
```

## Esteira Virtual

A pasta `demo-esteira/` é o painel web que simula a esteira industrial em tempo real, consumindo as mensagens MQTT publicadas pelo classificador.

- **Stack:** React + Vite, MQTT.js (WebSocket)
- **Broker:** `broker.hivemq.com` (WebSocket seguro: `wss://...`)

### Executar

```bash
cd demo-esteira
npm install
npm run dev
```

> O site e o aplicativo do classificador usam o **mesmo tópico** (`esteira/separacao`) e o **mesmo formato de payload** para funcionarem em conjunto.

## Requisitos de Aceite

### Funcionais
| ID | Descrição | Meta |
|----|-----------|------|
| RF01 | Precisão de classificação por classe | ≥ 90% (27/30) |
| RF02 | Classificação correta das 3 formas | Circular, quadrada, triangular |
| RF03 | Revisão automática de classificações incertas | 1ª passagem → `R`, reanálise → `D` |
| RF04 | Comunicação MQTT funcionando | Pi → Painel web |
| RF05 | Deduplicação de eventos no site | Sem duplicatas |
| RF06 | Rota de descarte para peças não conformes | Funcional |
| RF07 | Histórico de classificações | Visualização + exportação CSV |

### Não-funcionais
| ID | Descrição | Meta |
|----|-----------|------|
| RNF01 | Tempo de resposta da animação | < 2 segundos |
| RNF02 | Operação offline contínua | ≥ 10 minutos, reconexão < 30s |

## Tecnologias

| Categoria | Tecnologia | Uso |
|-----------|------------|-----|
| Computador single-board | Raspberry Pi 5 (8 GB) | Captura e processamento |
| Câmera | CSI Camera V1.3 (5 MP) | Captura silhuetas das peças |
| Visão computacional | OpenCV (Python) | Detecção de contornos, análise de forma |
| Captura de imagem | Picamera2 (Python) | Interface com câmera CSI |
| Messaging | MQTT (HiveMQ público) | Comunicação Pi ↔ Painel web |
| Frontend web | React + Vite, MQTT.js | Esteira virtual, animações, contadores |

## Escopo

### Incluído
- Classificação de peças por silhueta (3 formas)
- Comunicação MQTT entre o classificador e o painel web
- Esteira virtual com fluxo contínuo, revisão e descarte
- Reanálise automática de classificações incertas

### Fora de Escopo
- Esteira motorizada real (simulada virtualmente)
- Separação física por servos/motores (simulada no site)
- Controle de impressora 3D
- Etapa de desacoplamento inicial das peças (normalmente resolvida por esteira vibratória)

## Licença

[MIT License](LICENSE) - Copyright 2026 GilvanTWS and Claylton-Muniz
