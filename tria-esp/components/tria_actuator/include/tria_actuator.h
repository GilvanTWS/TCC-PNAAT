#pragma once

#include "esp_err.h"

typedef struct {
    int servo_gpio;
    int angle_a;
    int angle_b;
    int angle_c;
    unsigned int settling_time_ms;
} tria_actuator_config_t;

/** Copia a configuração e inicializa o servo uma vez; ângulos em graus 0..180.
 * ESP_OK não movimenta o servo: o primeiro destino inicia os pulsos. */
esp_err_t tria_actuator_start(const tria_actuator_config_t *config);
/** Comanda A/B/C após start e bloqueia o chamador por settling_time_ms.
 * ESP_OK confirma apenas o comando e a espera; destino inválido não move.
 * Chamadas devem ser serializadas (a aplicação usa o callback MQTT). */
esp_err_t tria_actuator_move(const char *destination);
