# Guia do código

Este guia complementa a instalação e o protocolo do [README](../README.md). Os comentários próximos às regras explicam unidades, decisões e limitações; as interfaces C documentam inicialização, retorno e tempo de vida dos dados.

## Mapa para manutenção

| Módulo | Responsabilidade e ponto de alteração |
|---|---|
| `pi/config.py` | HSV, ROI indireta, limiares e rede. Valores de distância/velocidade são iniciais, não medições |
| `pi/image_io.py` | Abre caminhos com Unicode pelo Python e decodifica BGR no OpenCV |
| `pi/classifier.py` | Localiza MDF → retifica perspectiva → reconhece símbolo; retorna `classe` ou `erro`, com diagnóstico |
| `pi/main.py` | Confirma presença/ausência, acumula amostras, fecha passagem, publica e apresenta imagens |
| `pi/mqtt_publisher.py` | Monta payload/ID e publica; confirmação do broker não comprova atuação |
| `pi/evaluate_videos.py` | Compara sequências por gabarito, separando troca, perda e extra |
| `tria-esp/main/main.c` | Compõe os módulos e liga callbacks de rede, atuador e OLED |
| `conveyor` / `vibration` | Esteira em PWM contínuo / fan digital alternada por botão com debounce |
| `servo` / `tria_actuator` | Conversão ângulo→pulso / mapa A/B/C e espera de estabilização |
| `tria_network` / `tria_display` | Wi-Fi/MQTT e supervisão / exibição protegida por mutex |
| `ming/nodered/flows.json` | Validação → cache de IDs → line protocol → escrita HTTP no InfluxDB |

## Visão: contratos e escolhas

As entradas de imagem usam BGR. A placa é localizada por HSV e geometria, com rejeição de candidatas que tocam a borda. A maior candidata é retificada para 400 × 400 pixels; isso pressupõe uma placa por vez. O contorno/box retornado usa a escala original, enquanto a máscara de localização usa a escala reduzida.

Para fotos, black-hat realça a marca escura e a classificação considera vértices e solidez. Para vídeo/câmera, a mediana de ocupação central ajuda a reconhecer X, e o melhor contorno da passagem distingue os polígonos. Os kernels e limiares são heurísticos, sujeitos à iluminação, desfoque e tamanho das gravações. **`confianca = 0.95` é um escore fixo, não uma probabilidade calibrada nem a acurácia medida.**

Presença confirmada abre uma passagem; ausência confirmada encerra a coleta e dispara uma classificação. A sequência deve ter intervalo livre entre placas. `total_eventos` conta entradas, incluindo passagens não classificadas. Uma falha de classificação não publica descarte automático. No vídeo, o fim do arquivo também encerra uma passagem aberta; não representa uma observação física de saída.

O servidor web transmite o quadro JPEG mais recente por conexões independentes, com sincronização por condição. Ele não fornece autenticação e destina-se à rede de ensaio. A lista de amostras cresce até a peça sair; não há limite de permanência para uma placa parada na ROI.

## Atuação e concorrência

| Recurso | Uso |
|---|---|
| LEDC timer/canal 0 | Servo, 50 Hz, 14 bits; sem pulso até o primeiro destino |
| LEDC timer/canal 1 | Esteira, 20 kHz, 10 bits; 65% → duty inteiro 664 de 1023 |
| Tarefa `vibration` | Leitura a cada 10 ms, confirmação estável por 30 ms, alternância somente ao pressionar |
| Callback MQTT | Parser → `processar_decisao` → PWM → espera de 500 ms → confirmação |
| Supervisor | Verifica inatividade de decisões e atualiza status/display |
| Mutex do display | Protege limpar/desenhar/enviar de chamadas concorrentes |

Os textos da decisão pertencem ao cJSON e são liberados ao fim do callback. Um futuro consumidor assíncrono deve copiá-los. A configuração de rede copia ponteiros: strings e contexto precisam continuar válidos; no aplicativo atual vêm de constantes do SDK.

A espera do servo usa `vTaskDelay`: outras tarefas podem executar, mas o callback MQTT continua ocupado. Não existe agendamento por `instante_atuacao`, realimentação de posição, fila de peças ou parada de motores por perda de rede. O timeout também ocorre em uma linha ociosa, pois mede tempo sem decisões.

## Registro e confiabilidade

O Pi publica QoS 1; reentregas são possíveis. O retorno da função contém o payload mesmo após timeout. O ESP32 não guarda IDs para deduplicar; o Node-RED guarda os últimos 100 em memória, perdidos no reinício. Esse cache é atualizado antes do HTTP, portanto um erro de escrita pode deixar um evento sem registro e com nova tentativa bloqueada pelo cache.

A escrita é confirmada por HTTP 204; ver o evento no Debug não comprova persistência. Eventos de mesma série no mesmo milissegundo podem colidir. O flow valida valores individuais, sem conferir integralmente a combinação classe/destino/defeito. Essas condições constam no README para orientar os ensaios e futuras mudanças.

## Validar uma alteração

1. Execute os testes e os vídeos como descrito em [VALIDACAO.md](VALIDACAO.md). Preserve gabaritos; não altere expectativas para ocultar regressões.
2. Para GPIO, duty ou ângulos, atualize `Kconfig.projbuild`, `sdkconfig.defaults`, esquema e ficha; confira um `sdkconfig` antigo antes de gravar.
3. Para firmware, compile com ESP-IDF 5.5.5 e teste fisicamente as saídas. Comentários e validação estática não substituem compilação.
4. Para protocolo/flow, envie um evento válido, inválido e duplicado no ambiente MING; confira ID, confirmação e registro. Documente o que foi efetivamente executado.
