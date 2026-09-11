#pragma once

#include "esp_err.h"

typedef struct {
    int servo_gpio;
    int angle_a;
    int angle_b;
    int angle_c;
    unsigned int settling_time_ms;
} tria_actuator_config_t;

esp_err_t tria_actuator_start(const tria_actuator_config_t *config);
esp_err_t tria_actuator_move(const char *destination);
