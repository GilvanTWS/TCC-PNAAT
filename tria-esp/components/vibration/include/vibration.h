#pragma once

#include "esp_err.h"

typedef struct {
    int button_gpio;
    int motor_gpio;
    unsigned int debounce_ms;
} vibration_config_t;

/**
 * @brief Configura o motor vibratorio e cria a tarefa do botao ativo em nivel baixo.
 * Copia config (debounce em ms), inicia fan desligada e alterna a cada toque.
 * Saída digital, sem PWM. Retorna erro para GPIOs inválidos, repetição de start
 * ou falha do driver/alocação. PRG não deve ficar pressionado durante o boot.
 */
esp_err_t vibration_start(const vibration_config_t *config);
