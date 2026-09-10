# Entrega 3 — Esboço do Vídeo Pitch

**Tema:** TRIA — Triagem Visual Integrada de Componentes
**Equipe:** Os guri do pinati (PNAAT 2026)
**Duração limite:** 15 minutos
**Formato:** vídeo de pitch com demonstração prática ao vivo

---

## Estrutura e tempos

| Parte | Conteúdo | Tempo | Acumulado |
|-------|----------|-------|-----------|
| 1 | Introdução — problema | 0:00 – 2:30 | 2 min 30 s |
| 2 | Solução — tecnologia escolhida | 2:30 – 6:00 | 3 min 30 s |
| 3 | Demonstração — funcionamento | 6:00 – 11:30 | 5 min 30 s |
| 4 | Conclusão — resultado esperado | 11:30 – 13:30 | 2 min 00 s |
| 5 | Encerramento — créditos e margem | 13:30 – 15:00 | 1 min 30 s |

---

## 1. Introdução — o problema (0:00 – 2:30)

**Fala sugerida (≈ 340 palavras):**

> Olá, somos o grupo "Os guri do pinati" e apresentamos o TRIA, a Triagem Visual
> Integrada de Componentes, nosso trabalho de conclusão do programa PNAAT 2026.
>
> O problema nasce no cenário que escolhemos: linhas de manufatura onde
> componentes de formatos diferentes chegam misturados e precisam ser separados
> e encaminhados corretamente para as etapas seguintes. As peças podem entrar
> em posições variadas, em contato umas com as outras, ou até parcialmente
> sobrepostas — o que dificulta a identificação e o abastecimento correto das
> próximas etapas.
>
> Quando essa triagem é feita de forma manual, ela é lenta, cansativa e difícil
> de rastrear. Não há registro confiável do que passou, para onde cada peça foi
> e se ela estava boa ou defeituosa. Além disso, existem peças com a mesma
> silhueta — um quadrado normal e um quadrado com uma marca de defeito têm o
> mesmo contorno — e o operador precisa inspecionar uma a uma. Esse é o
> problema mais crítico: distinguir o defeito sem perder a velocidade da linha.
>
> Nossa proposta precisa, então, resolver três necessidades:
> reconhecer a geometria de cada peça e encaminhá-la fisicamente para a saída
> correta; reduzir o acúmulo de peças antes da inspeção; e comprovar o
> resultado por meio de registros, para que a triagem seja repetível e
> rastreável.

**Visuais:** título TRIA e nomes da equipe; imagens de peças misturadas
(quadrados/triângulos); silhueta de quadrado com a marca X contrastante;
tópicos das três necessidades aparecendo um a um.

---

## 2. Solução — a tecnologia escolhida (2:30 – 6:00)

**Fala sugerida (≈ 440 palavras):**

> Para atacar esse problema, desenvolvemos uma Prova de Conceito física que
> percorre a cadeia completa: pré-separação, esteira, captura, classificação,
> atuação e registro. A arquitetura segue a lógica entrada → processamento →
> saída.
>
> A entrada é o sensoriamento. As peças de ensaio são colocadas em uma base
> com um motor vibratório, que reduz contato e sobreposição antes da esteira.
> A esteira transporta as peças por uma área de inspeção, onde uma câmera CSI
> fixa, com fundo fosco e iluminação controlada, captura os quadros.
>
> O processamento acontece na visão computacional. Um Raspberry Pi 5 usa a
> biblioteca Picamera2 para capturar cada quadro e o OpenCV para segmentar a
> peça, detectar os contornos e aplicar a aproximação poligonal, que distingue
> o triângulo do quadrilátero. Em seguida, uma análise da região interna usa a
> transformada de Hough para detectar a marca X contrastante — é assim que o
> quadrado com defeito é separado do quadrado normal. Tudo isso sem sensor de
> presença: o software detecta a passagem da peça por uma região de interesse e
> garante que cada peça seja classificada uma única vez.
>
> Decidida a classe, vem a conectividade. O Raspberry Pi gera um evento com
> identificador único e publica a decisão por MQTT, no broker Mosquitto local.
> Ele também calcula o instante de atuação, baseado na distância da câmera ao
> desviador e na velocidade da esteira, para que o servo tenha tempo de se
> posicionar antes da peça chegar.
>
> A saída é o nó de atuação IoT. Um ESP32-S3, da Heltec, recebe a decisão,
> leva um único servo à posição calibrada A, B ou C e mostra no OLED integrado
> a última classe, o destino e o estado da conexão. O quadrado vai para a saída
> A, o triângulo para a B, e o quadrado com X para o descarte, na saída C.
>
> Em paralelo, os eventos também seguem para a stack MING — um conjunto de
> containers com Node-RED, InfluxDB e Grafana. O Node-RED valida e deduplica os
> eventos, o InfluxDB guarda cada registro como série temporal e o Grafana
> exibe o dashboard com contagens, destinos, defeitos e histórico. Um ponto
> importante: o dashboard apenas acompanha; a decisão crítica de atuação não
> depende dele. Se o Grafana estiver fechado, a triagem continua funcionando.

**Visuais:** diagrama da arquitetura animado (câmera → Raspberry Pi → MQTT →
ESP32/servo → saídas A/B/C; Node-RED → InfluxDB → Grafana);
logotipos das tecnologias; payload MQTT de exemplo em destaque.

---

## 3. Demonstração — funcionamento (6:00 – 11:30)

**Fala sugerida (≈ 500 palavras):**

> Vamos ver o sistema em funcionamento. Na bancada temos, da esquerda para a
> direita: a base de pré-separação vibratória, a esteira, a câmera fixa sobre a
> área de inspeção e o desviador com o servo, que conduz a peça para uma das
> três saídas. Ao lado, o monitor com o pipeline do Raspberry Pi e o dashboard.
>
> Primeiro, vou mostrar o software em ação com uma peça de cada classe.
> Coloco o triângulo na entrada. Ele desce pela esteira e, ao entrar na região
> de interesse, o sistema detecta a passagem sem sensor de presença. No
> terminal do Pi vemos o evento gerado: classe TRIÂNGULO, destino B. No
> broker, a mensagem MQTT chega no tópico tria/triagem, e o ESP32 confirma no
> tópico tria/atuador. O servo se posiciona em B e a peça é desviada para a
> saída correta. No dashboard, o contador de triângulos aumenta um.
>
> Agora o quadrado normal: mesmo caminho, classe QUADRADO, destino A. O servo
> vai para a posição A e a peça segue para a saída A.
>
> E agora o caso crítico: o quadrado com a marca X. A silhueta é idêntica à do
> quadrado normal, mas a análise interna detecta as linhas diagonais da marca.
> O sistema publica classe QUADRADO_COM_X, defeito verdadeiro, destino C — o
> descarte. No Elastic — desculpa — no Flow do Node-RED, vemos o evento
> chegando, sendo validado e gravado no InfluxDB. Consulto a base e o registro
> está lá com horário, classe, destino e defeito.
>
> Para mostrar a robustez, vou rodar uma sequência mista de dez peças, sem
> seleção manual. O sistema identifica cada uma, publica os eventos de forma
> única, e o dashboard vai atualizando os totais em tempo real. No final,
> comparo a ordem das peças com os registros no Grafana: classe prevista,
> classe detectada, destino e estado da comunicação — tudo confere.
>
> Por fim, demonstro o watchdog de comunicação: desligo a conexão MQTT do
> ESP32 por alguns segundos. O OLED passa a indicar indisponibilidade, e o
> status no tópico tria/status/esp32 muda para conectado: falso. Ao restaurar a
> rede, o ESP32 reconecta e aceita um novo evento em segundos, sem executar
> comando antigo.

**Visuais (gravação):**
- Bancada física: pré-separador → esteira → câmera → desviador → 3 saídas;
- Tela 1: `pi/main.py` rodando (ROI, contorno destacado, evento no terminal);
- Tela 2: `mosquitto_sub -t tra/#` mostrando tópicos em tempo real;
- Tela 3: Node-RED (flow), consulta no InfluxDB e Grafana atualizando;
- ESP32 com OLED mostrando classe/destino/estado.

**Pré-requisitos de gravação:** montagem montada e calibrada; sequência mista de
10 peças preparada; cronômetro do roteiro por parte; se a bancada não estiver
disponível, usar o modo `--imagem` do `pi/main.py` para a parte de software e
registrar a falha de etapa para o relatório.

---

## 4. Conclusão — resultado esperado (11:30 – 13:30)

**Fala sugerida (≈ 270 palavras):**

> Para fechar: o problema era a triagem manual, lenta e sem rastreabilidade de
> componentes misturados em uma linha de manufatura, incluindo a dificuldade de
> distinguir o defeito em peças de mesma silhueta.
>
> A nossa solução integra visão computacional e IoT em uma única cadeia:
> sensor, processamento, conectividade, atuação e registro — o Raspberry Pi
> vê e decide, o MQTT comunica, o ESP32 atua, e a stack MING documenta.
>
> O resultado esperado está traduzido em critérios de aceite que vamos medir
> experimentalmente: classificar pelo menos 18 de cada 20 apresentações de
> quadrado, triângulo e quadrado com X; encaminhar ao menos 27 de 30 peças para
> a saída correta; registrar todos os eventos sem perda nem duplicidade; e
> executar o fluxo completo, da entrada ao dashboard, em ao menos 13 de 15
> ciclos. É uma prova de conceito em escala de laboratório, com materiais de
> baixo custo, que demonstra que uma triagem repetível e rastreável é
> alcançável.
>
> Acreditamos que esse conjunto — visão computacional simples, protocolo leve
> de comunicação e registro temporal — é a base para evoluir a solução em
> direção a uma aplicação industrial: mais classes de peças, sensores
> dedicados e integração com sistemas de produção.
>
> O código está aberto no repositório do projeto, com o firmware do ESP32, o
> pipeline de visão e a stack completa em Docker, prontos para reprodução.
>
> Agradecemos a atenção. Obrigado!

**Visuais:** recapitulação problema → solução → resultado (três quadros);
tabela-resumo dos critérios de aceite; logo TRIA e endereço/QR do repositório.

---

## 5. Encerramento e margem (13:30 – 15:00)

**Fala/uso da margem:**
- 13:30 – 14:00 — créditos finais, nomes dos integrantes e agradecimentos
  ao PNAAT e ao laboratório;
- 14:00 – 15:00 — **margem de segurança**: usada apenas para recuperar atraso
  de engasgos na demonstração. Se a gravação estiver no tempo, encerrar o
  vídeo aos 14:00 e deixar a margem em silêncio/pausa para edição.

---

## Observações de gravação

- Gravar em duas fontes: câmera na bancada + captura de tela (OBS Studio),
  com picture-in-picture na edição.
- Ritmo de fala: 130–150 palavras por minuto, com pausas marcadas nos tempos
  acima.
- A demonstração é a parte mais curta do risco: ensaiar a sequência mista
  antes de gravar e ter o modo `--imagem` como plano B.
- O roteiro acima soma ≈ 1.550 palavras faladas, coerente com 15 minutos.
- Manter o checklist de evidências (RF08/RF09/RF10) para linkar a fala aos
  registros reais exibidos.