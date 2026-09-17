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
 * @param config GPIO e duty em porcentagem de 0 a 100, não velocidade em m/s.
 * Os valores são copiados; timer/canal LEDC 1 ficam reservados à esteira.
 * @return ESP_OK ou erro de configuração/driver. Uma segunda partida é rejeitada.
 */
esp_err_t conveyor_start(const conveyor_config_t *config);

/**
 * @brief Liga ou desliga a esteira.
 *
 * Ao ligar, restaura a velocidade informada em conveyor_start().
 * Requer start bem-sucedido. Não é chamado automaticamente em falhas de rede.
 */
esp_err_t conveyor_set_enabled(bool enabled);
