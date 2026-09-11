#include "conveyor.h"

#include <stdbool.h>
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"

static const char *TAG = "conveyor";
static int conveyor_gpio;
static bool started;

esp_err_t conveyor_start(const conveyor_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "Configuracao ausente");
    ESP_RETURN_ON_FALSE(!started, ESP_ERR_INVALID_STATE, TAG,
                        "Componente ja iniciado");
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_OUTPUT_GPIO(config->gpio),
                        ESP_ERR_INVALID_ARG, TAG, "Configuracao invalida");

    const gpio_config_t output_config = {
        .pin_bit_mask = 1ULL << config->gpio,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&output_config), TAG,
                        "Falha ao configurar GPIO");
    ESP_RETURN_ON_ERROR(gpio_set_level(config->gpio, 1), TAG,
                        "Falha ao ligar esteira");

    conveyor_gpio = config->gpio;
    started = true;
    ESP_LOGI(TAG, "Esteira ligada no GPIO %d (HIGH)", config->gpio);
    return ESP_OK;
}

esp_err_t conveyor_set_enabled(bool enabled)
{
    ESP_RETURN_ON_FALSE(started, ESP_ERR_INVALID_STATE, TAG,
                        "Componente nao iniciado");
    ESP_RETURN_ON_ERROR(gpio_set_level(conveyor_gpio, enabled ? 1 : 0), TAG,
                        "Falha ao alterar estado da esteira");

    ESP_LOGI(TAG, "Esteira %s (%s)", enabled ? "ligada" : "desligada",
             enabled ? "HIGH" : "LOW");
    return ESP_OK;
}
