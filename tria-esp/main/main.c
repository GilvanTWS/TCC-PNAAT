#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_check.h"
#include "esp_log.h"
#include "servo.h"

#define SERVO_GPIO 47

static const char *TAG = "servo_test";

void app_main(void)
{
    ESP_ERROR_CHECK(servo_init(SERVO_GPIO));

    // Faixa conservadora para nao forcar os batentes de servos desconhecidos.
    const int angles[] = {0, 45, 90, 180};

    while (true) {
        for (int i = 0; i < 4; i++) {
            ESP_LOGI(TAG, "Movendo servo para %d graus", angles[i]);
            ESP_ERROR_CHECK(servo_set_angle(angles[i]));
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
    }
}
