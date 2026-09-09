#pragma once

#include "esp_err.h"

/**
 * @brief Inicializa o PWM usado para controlar o servo.
 *
 * @param gpio GPIO conectado ao fio de sinal do servo.
 */
esp_err_t servo_init(int gpio);

/**
 * @brief Move o servo para um angulo entre 0 e 180 graus.
 */
esp_err_t servo_set_angle(int angle);
