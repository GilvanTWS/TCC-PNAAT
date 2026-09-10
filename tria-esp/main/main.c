#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp_log.h"
#include "servo.h"

#define SERVO_GPIO 47
#define BUTTON_GPIO GPIO_NUM_0
#define VIBRATION_GPIO GPIO_NUM_7
#define BUTTON_DEBOUNCE_MS 30

static const char *TAG = "servo_test";

static void vibration_task(void *arg)
{
    int last_reading = gpio_get_level(BUTTON_GPIO);
    int stable_state = last_reading;
    int stable_time_ms = 0;

    while (true) {
        const int reading = gpio_get_level(BUTTON_GPIO);

        if (reading != last_reading) {
            last_reading = reading;
            stable_time_ms = 0;
        } else if (stable_time_ms < BUTTON_DEBOUNCE_MS) {
            stable_time_ms += 10;

            if (stable_time_ms >= BUTTON_DEBOUNCE_MS && reading != stable_state) {
                stable_state = reading;

                // O botao PRG e ativo em nivel baixo.
                const bool vibration_enabled = stable_state == 0;
                gpio_set_level(VIBRATION_GPIO, vibration_enabled);
                ESP_LOGI(TAG, "Vibrador %s", vibration_enabled ? "ligado" : "desligado");
            }
        }

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void app_main(void)
{
    const gpio_config_t button_config = {
        .pin_bit_mask = 1ULL << BUTTON_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&button_config));

    const gpio_config_t vibration_config = {
        .pin_bit_mask = 1ULL << VIBRATION_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_ERROR_CHECK(gpio_config(&vibration_config));
    ESP_ERROR_CHECK(gpio_set_level(VIBRATION_GPIO, 0));

    ESP_ERROR_CHECK(xTaskCreate(vibration_task, "vibration", 2048, NULL, 5, NULL) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);

    // Servo motor
    ESP_ERROR_CHECK(servo_init(SERVO_GPIO));
    const int angles[] = {0, 45, 90, 180}; // angulos para mover o servo

    while (true) {
        // loop que move o servo para os angulos definidos
        for (int i = 0; i < 4; i++) {
            ESP_LOGI(TAG, "Movendo servo para %d graus", angles[i]);
            ESP_ERROR_CHECK(servo_set_angle(angles[i]));
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
