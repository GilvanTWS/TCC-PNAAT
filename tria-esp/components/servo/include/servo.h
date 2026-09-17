#pragma once

#include "esp_err.h"

/**
 * @brief Inicializa o PWM usado para controlar o servo.
 *
 * @param gpio GPIO conectado ao fio de sinal do servo.
 * Reserva timer/canal LEDC 0 a 50 Hz. Chamar uma vez antes de set_angle;
 * não envia pulsos até o primeiro ângulo. Propaga erros do driver.
 */
esp_err_t servo_init(int gpio);

/**
 * @brief Move o servo para um angulo entre 0 e 180 graus.
 * Converte para 500..2500 us; validar o curso mecânico antes de usar extremos.
 * Retorna ESP_OK após atualizar PWM, sem aguardar nem medir a posição física.
 */
esp_err_t servo_set_angle(int angle);
