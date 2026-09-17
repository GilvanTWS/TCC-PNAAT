#include "tria_display.h"

#include <stdbool.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_check.h"
#include "esp32_hw_i2c.h"
#include "u8g2.h"

#define OLED_POWER_STABILIZATION_MS 100

static u8g2_t display;
static u8g2_esp32_i2c_ctx_t i2c_context;
static SemaphoreHandle_t display_mutex;
static bool initialized;

esp_err_t tria_display_init(int sda_gpio, int scl_gpio,
                            int reset_gpio, int power_gpio)
{
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_GPIO(sda_gpio) && GPIO_IS_VALID_GPIO(scl_gpio),
                        ESP_ERR_INVALID_ARG, "tria_display", "GPIO invalido");
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_OUTPUT_GPIO(reset_gpio) &&
                            GPIO_IS_VALID_OUTPUT_GPIO(power_gpio),
                        ESP_ERR_INVALID_ARG, "tria_display",
                        "GPIO de reset ou alimentacao invalido");
    ESP_RETURN_ON_FALSE(!initialized, ESP_ERR_INVALID_STATE,
                        "tria_display", "Componente ja iniciado");

    const gpio_config_t power_config = {
        .pin_bit_mask = 1ULL << power_gpio,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    ESP_RETURN_ON_ERROR(gpio_config(&power_config), "tria_display",
                        "Falha ao configurar alimentacao do OLED");
    /* Vext da Heltec V3 é ativo em zero; aguarda a alimentação estabilizar. */
    ESP_RETURN_ON_ERROR(gpio_set_level(power_gpio, 0), "tria_display",
                        "Falha ao ligar alimentacao do OLED");
    vTaskDelay(pdMS_TO_TICKS(OLED_POWER_STABILIZATION_MS));

    display_mutex = xSemaphoreCreateMutex();
    ESP_RETURN_ON_FALSE(display_mutex != NULL, ESP_ERR_NO_MEM,
                        "tria_display", "Falha ao criar mutex");

    u8g2_esp32_i2c_config_t config = U8G2_ESP32_I2C_CONFIG_DEFAULT();
    config.sda_pin = sda_gpio;
    config.scl_pin = scl_gpio;
    config.reset_pin = reset_gpio;
    i2c_context.cfg = config;

    ESP_RETURN_ON_ERROR(u8g2_esp32_i2c_set_default_context(&i2c_context),
                        "tria_display", "Falha ao configurar I2C");
    u8g2_Setup_ssd1306_i2c_128x64_noname_f(&display, U8G2_R0,
                                           u8x8_byte_esp32_hw_i2c,
                                           u8x8_gpio_and_delay_esp32_i2c);
    u8x8_SetI2CAddress(&display.u8x8, config.dev_addr_7bit << 1);
    u8g2_InitDisplay(&display);
    u8g2_SetPowerSave(&display, 0);
    u8g2_ClearBuffer(&display);
    initialized = true;
    return ESP_OK;
}

void tria_display_show(const char *line_1, const char *line_2, const char *line_3)
{
    /* MQTT e supervisor podem chamar simultaneamente. Protege o ciclo inteiro
     * de limpar/desenhar/enviar para não misturar duas telas no mesmo buffer. */
    if (!initialized || line_1 == NULL || line_2 == NULL || line_3 == NULL ||
        xSemaphoreTake(display_mutex, portMAX_DELAY) != pdTRUE) {
        return;
    }

    u8g2_ClearBuffer(&display);
    u8g2_SetFont(&display, u8g2_font_8x13_tr);
    u8g2_DrawUTF8(&display, 0, 12, line_1);
    u8g2_DrawUTF8(&display, 0, 30, line_2);
    u8g2_DrawUTF8(&display, 0, 48, line_3);
    u8g2_SendBuffer(&display);
    xSemaphoreGive(display_mutex);
}
