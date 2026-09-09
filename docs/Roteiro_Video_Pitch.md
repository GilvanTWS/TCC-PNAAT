# Entrega 3 — Esboço do Vídeo Pitch

**Tema:** TRIA — Triagem Visual Integrada de Componentes
**Duração limite:** ~4 minutos (formato resumido)
**Formato:** vídeo de pitch com demonstração prática

---

## Estrutura e tempos

| Parte | Tema | Tempo |
|-------|------|-------|
| 1 | Introdução — problema | 0:00 – 1:00 |
| 2 | Solução — tecnologia escolhida | 1:00 – 2:00 |
| 3 | Demonstração — funcionamento | 2:00 – 3:30 |
| 4 | Conclusão — resultado esperado | 3:30 – 4:00 |

---

## 1. Introdução — problema (1 min)

**Fala sugerida:**
> Nas linhas de manufatura, componentes misturados precisam ser separados e
> encaminhados corretamente. Quando a triagem é manual, ela é lenta, cansativa e
> difícil de rastrear. Neste cenário, peças como quadrados e triângulos chegam
> juntas, em contato ou sobrepostas, e ainda podem apresentar defeitos que
> precisam ser detectados antes da próxima etapa.

**Visuais:** imagens das peças misturadas; silhueta de quadrado com a marca X de defeito.

---

## 2. Solução — tecnologia escolhida (1 min)

**Fala sugerida:**
> O TRIA é um sistema de triagem visual integrada de componentes. Uma câmera
> captura cada peça na esteira; um software de visão computacional em um
> Raspberry Pi identifica a forma e detecta a marca de defeito; e a decisão é
> enviada por MQTT para um servo que direciona a peça para a saída correta.
> Todo o processo é registrado em um dashboard, provando que a triagem é
> repetível e rastreável.

**Visuais:** diagrama da arquitetura (câmera → Raspberry Pi → MQTT → ESP32/servo → saídas A/B/C; Node-RED/InfluxDB/Grafana).

---

## 3. Demonstração — funcionamento (1 min 30 s)

**Fala sugerida:**
> Vamos ver o sistema em funcionamento. Uma peça entra na área de inspeção.
> O Raspberry Pi detecta a passagem, segmenta o contorno e reconhece a
> geometria. Aqui vemos o quadrado normal, o triângulo e o quadrado com a marca
> X. O software publica a decisão, o servo se posiciona e a peça segue para a
> saída correspondente: A, B ou descarte. Em paralelo, os eventos aparecem no
> dashboard com contagens, destinos e histórico.

**Visuais (gravação):**
- Entrada: imagem/peça na região de interesse
- Processamento: `pi/main.py` — contorno destacado e classe detectada
- Resultado: publicação MQTT (`tria/triagem`) e painel do Grafana atualizando

---

## 4. Conclusão — resultado esperado (30 s)

**Fala sugerida:**
> O TRIA valida que é possível automatizar a triagem de componentes com visão
> computacional e IoT a baixo custo. O resultado esperado é uma linha que
> classifica e encaminha cada peça de forma confiável, gera evidências de cada
> evento e permite acompanhar o processo em tempo real — a base para uma
> triagem industrial repetível e rastreável.

**Visuais:** logo TRIA e endereço do repositório do projeto.

---

## Observações de gravação

- Gravar a tela com OBS Studio ou similar; o roteiro em tela pode ser o editor de texto.
- Se a bancada física ainda não estiver montada, a demonstração usa o modo `--imagem` do `pi/main.py` (entrada = imagem, processamento = OpenCV, resultado = MQTT/dashboard).
- Manter a fala entre 130–150 palavras por minuto para caber nos 4 minutos.