#include "tria_actuator.h"

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_check.h"
#include "esp_log.h"
#include "servo.h"

static const char *TAG = "tria_actuator";
static tria_actuator_config_t actuator_config;
static bool initialized;

static bool valid_angle(int angle)
{
    return angle >= 0 && angle <= 180;
}

esp_err_t tria_actuator_start(const tria_actuator_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "Configuracao ausente");
    ESP_RETURN_ON_FALSE(!initialized, ESP_ERR_INVALID_STATE, TAG,
                        "Componente ja iniciado");
    ESP_RETURN_ON_FALSE(valid_angle(config->angle_a) &&
                        valid_angle(config->angle_b) &&
                        valid_angle(config->angle_c),
                        ESP_ERR_INVALID_ARG, TAG, "Angulo invalido");

    ESP_RETURN_ON_ERROR(servo_init(config->servo_gpio), TAG,
                        "Falha ao iniciar servo");
    actuator_config = *config;
    initialized = true;
    ESP_LOGI(TAG, "Servo no GPIO %d", config->servo_gpio);
    return ESP_OK;
}

esp_err_t tria_actuator_move(const char *destination)
{
    ESP_RETURN_ON_FALSE(initialized, ESP_ERR_INVALID_STATE, TAG,
                        "Componente nao iniciado");
    ESP_RETURN_ON_FALSE(destination != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "Destino ausente");

    const struct {
        const char *destination;
        int angle;
    } positions[] = {
        {"A", actuator_config.angle_a},
        {"B", actuator_config.angle_b},
        {"C", actuator_config.angle_c},
    };

    for (size_t i = 0; i < sizeof(positions) / sizeof(positions[0]); ++i) {
        if (strcmp(destination, positions[i].destination) != 0) {
            continue;
        }

        ESP_LOGI(TAG, "Servo -> posicao %s (angulo %d)",
                 destination, positions[i].angle);
        ESP_RETURN_ON_ERROR(servo_set_angle(positions[i].angle), TAG,
                            "Falha ao mover servo");
        /* Espera de malha aberta: libera CPU, mas mantém o callback MQTT
         * ocupado. ESP_OK não comprova a posição física nem a saída da peça. */
        vTaskDelay(pdMS_TO_TICKS(actuator_config.settling_time_ms));
        return ESP_OK;
    }

    ESP_LOGW(TAG, "Destino desconhecido: %s", destination);
    return ESP_ERR_INVALID_ARG;
}
