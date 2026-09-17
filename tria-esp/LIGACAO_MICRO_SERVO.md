# Ligação do SG90 ao ESP32

O servo confirmado na bancada é o **SG90 de 9 g**. Este guia complementa o [esquema elétrico completo](../docs/hardware/esquema-eletrico.svg) e a [ficha da bancada](../docs/hardware/bancada.json).

## Conexões

| Fio do micro servo | Função | Conectar em |
|---|---|---|
| Marrom | Terra (`GND`) | `GND` do ESP32 e negativo da fonte externa |
| Vermelho | Alimentação (`VCC`) | Positivo de uma fonte externa regulada de `5 V` |
| Laranja | Sinal PWM | `GPIO 47` (`IO47`) do ESP32 |

> As cores podem variar conforme o fabricante. Confirme a identificação dos fios na documentação do seu servo antes de energizar o circuito.

## Esquema simplificado

```text
                    Micro servo
                  ┌──────────────┐
Fonte 5 V (+) ────┤ VCC      vermelho
                  │
ESP32 GPIO 47 ────┤ SINAL    laranja
                  │
GND comum ────────┤ GND      marrom
                  └──────────────┘

Fonte 5 V (-) ─────────┬── GND do micro servo
                       └── GND do ESP32
```

O negativo da fonte externa e o `GND` do ESP32 precisam estar conectados entre si. Sem esse terra comum, o sinal PWM pode não ser interpretado corretamente pelo servo.

## Cuidados importantes

- Desligue a alimentação antes de montar ou alterar as conexões.
- Não conecte o fio vermelho do servo a um pino `GPIO` nem ao pino `3V3`.
- Use uma fonte externa regulada de `5 V`, dimensionada para partida e movimento com carga. A corrente real desta bancada ainda precisa ser medida e registrada.
- Não aplique `5 V` ao `GPIO 47`; somente o fio de sinal do servo deve ser conectado a ele.
- Para reduzir ruídos e quedas de tensão, pode ser usado um capacitor eletrolítico de `470 µF` a `1000 µF` entre `5 V` e `GND`, próximo ao servo, respeitando a polaridade.
- Antes de prender o braço do servo ao mecanismo, teste o movimento sem carga para evitar colisões nos limites de rotação.

## Relação com o firmware

O pino de sinal é configurado em `idf.py menuconfig` → **TRIA - Atuação (servo)**, pelo parâmetro `CONFIG_TRIA_SERVO_GPIO`. O padrão é **47**, registrado em [Kconfig.projbuild](main/Kconfig.projbuild) e [sdkconfig.defaults](sdkconfig.defaults).

Se mudar o GPIO ou os ângulos, salve o menu, compile e grave novamente. Um `sdkconfig` existente tem precedência sobre os valores do perfil inicial.

1. Sem a aleta presa, teste B (90°), depois A (45°) e C (135°), usando o publicador manual do [README](../README.md#6-calibração-e-operação).
2. A 50 Hz, essas posições correspondem a pulsos aproximados de 1500, 1000 e 2000 µs. A faixa geral do gerador (500–2500 µs) não comprova o curso seguro de qualquer exemplar.
3. Fixe a aleta com o sistema desligado e calibre os três ângulos para as saídas físicas, evitando batentes.
4. Registre ângulos, fonte e estabilização na ficha. Os 500 ms do firmware são uma espera configurada, sem medição de posição.

Na inicialização não há pulso de posição: o primeiro destino recebido comanda o servo. A confirmação em `tria/atuador` indica comando e espera concluídos; o aceite também exige observar a posição e a saída real da peça.
