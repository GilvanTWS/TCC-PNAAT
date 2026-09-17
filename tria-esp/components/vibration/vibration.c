#include "vibration.h"

#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"

#define POLL_INTERVAL_MS 10
#define TASK_STACK_SIZE  2048
#define TASK_PRIORITY    5

static const char *TAG = "vibration";
static vibration_config_t vibration_config;
static bool started;

static void set_enabled(bool enabled)
{
    gpio_set_level(vibration_config.motor_gpio, enabled);
    ESP_LOGI(TAG, "Vibrador %s", enabled ? "ligado" : "desligado");
}

static void vibration_task(void *arg)
{
    int last_reading = gpio_get_level(vibration_config.button_gpio);
    int stable_state = last_reading;
    bool motor_enabled = false;
    TickType_t last_change = xTaskGetTickCount();
    const TickType_t debounce_ticks = pdMS_TO_TICKS(vibration_config.debounce_ms);

    while (true) {
        const int reading = gpio_get_level(vibration_config.button_gpio);
        const TickType_t now = xTaskGetTickCount();

        /* Reinicia a janela a cada oscilação do contato. Só uma transição
         * estável para zero alterna a fan; segurar PRG não repete a ação. */
        if (reading != last_reading) {
            last_reading = reading;
            last_change = now;
        } else if (reading != stable_state && now - last_change >= debounce_ticks) {
            stable_state = reading;

            /* O botao usa pull-up: nivel baixo representa um novo pressionamento. */
            if (stable_state == 0) {
                motor_enabled = !motor_enabled;
                set_enabled(motor_enabled);
            }
        }

        /* Libera CPU para rede/display durante a espera entre leituras. */
        vTaskDelay(pdMS_TO_TICKS(POLL_INTERVAL_MS));
    }
}

esp_err_t vibration_start(const vibration_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "Configuracao ausente");
    ESP_RETURN_ON_FALSE(!started, ESP_ERR_INVALID_STATE, TAG,
                        "Componente ja iniciado");
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_GPIO(config->button_gpio) &&
                        GPIO_IS_VALID_OUTPUT_GPIO(config->motor_gpio) &&
                        config->button_gpio != config->motor_gpio &&
                        config->debounce_ms > 0,
                        ESP_ERR_INVALID_ARG, TAG, "Configuracao invalida");

    const gpio_config_t button_config = {
        .pin_bit_mask = 1ULL << config->button_gpio,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    const gpio_config_t motor_config = {
        .pin_bit_mask = 1ULL << config->motor_gpio,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };

    ESP_RETURN_ON_ERROR(gpio_config(&button_config), TAG,
                        "Falha ao configurar botao");
    ESP_RETURN_ON_ERROR(gpio_config(&motor_config), TAG,
                        "Falha ao configurar motor");
    ESP_RETURN_ON_ERROR(gpio_set_level(config->motor_gpio, 0), TAG,
                        "Falha ao desligar motor");

    vibration_config = *config;
    ESP_RETURN_ON_FALSE(
        xTaskCreate(vibration_task, "vibration", TASK_STACK_SIZE,
                    NULL, TASK_PRIORITY, NULL) == pdPASS,
        ESP_ERR_NO_MEM, TAG, "Falha ao criar tarefa");

    started = true;
    ESP_LOGI(TAG, "Botao no GPIO %d; motor no GPIO %d",
             config->button_gpio, config->motor_gpio);
    return ESP_OK;
}
