#pragma once

#include <stdbool.h>

#include "esp_err.h"

typedef struct {
    int gpio;
} conveyor_config_t;

/**
 * @brief Configura a esteira como saida digital e a inicia ligada.
 *
 * @param config GPIO usado para controlar a esteira.
 */
esp_err_t conveyor_start(const conveyor_config_t *config);

/**
 * @brief Liga ou desliga a esteira usando nivel alto ou baixo.
 */
esp_err_t conveyor_set_enabled(bool enabled);
