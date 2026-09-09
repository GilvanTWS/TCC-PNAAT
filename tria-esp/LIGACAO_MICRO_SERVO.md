# Ligação do micro servo ao ESP32

Este guia descreve como conectar um micro servo de três fios, como o SG90, ao ESP32 usado neste projeto.

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
- Prefira uma fonte externa regulada de `5 V`, capaz de fornecer pelo menos `1 A` para um micro servo.
- Não aplique `5 V` ao `GPIO 47`; somente o fio de sinal do servo deve ser conectado a ele.
- Para reduzir ruídos e quedas de tensão, pode ser usado um capacitor eletrolítico de `470 µF` a `1000 µF` entre `5 V` e `GND`, próximo ao servo, respeitando a polaridade.
- Antes de prender o braço do servo ao mecanismo, teste o movimento sem carga para evitar colisões nos limites de rotação.

## Relação com o firmware

O pino de sinal está definido em [`main/main.c`](main/main.c):

```c
#define SERVO_GPIO 47
```

Se o fio de sinal for conectado a outro GPIO, altere esse valor no código antes de compilar e gravar o firmware. Futuramente colocarei isso no menuconfig, então se não tiver essa linha verifique o menuconfig.
