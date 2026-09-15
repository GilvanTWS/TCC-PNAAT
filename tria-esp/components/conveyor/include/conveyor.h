#pragma once

#include <stdbool.h>

#include "esp_err.h"

typedef struct {
    int gpio;
    int speed_percent;
} conveyor_config_t;

/**
 * @brief Configura o PWM da esteira e aplica a velocidade inicial.
 *
 * @param config GPIO e velocidade, em porcentagem de 0 a 100.
 */
esp_err_t conveyor_start(const conveyor_config_t *config);

/**
 * @brief Liga ou desliga a esteira.
 *
 * Ao ligar, restaura a velocidade informada em conveyor_start().
 */
esp_err_t conveyor_set_enabled(bool enabled);
