#include "conveyor.h"

#include <stdbool.h>
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_check.h"
#include "esp_log.h"

#define CONVEYOR_PWM_FREQUENCY_HZ    20000
#define CONVEYOR_DUTY_RESOLUTION     LEDC_TIMER_10_BIT
#define CONVEYOR_MAX_DUTY            ((1U << 10) - 1U)

static const char *TAG = "conveyor";
static const ledc_mode_t conveyor_speed_mode = LEDC_LOW_SPEED_MODE;
static const ledc_timer_t conveyor_timer = LEDC_TIMER_1;
static const ledc_channel_t conveyor_channel = LEDC_CHANNEL_1;
static uint32_t configured_duty;
static int configured_speed_percent;
static bool started;

static esp_err_t conveyor_apply_duty(uint32_t duty)
{
    ESP_RETURN_ON_ERROR(ledc_set_duty(conveyor_speed_mode, conveyor_channel, duty),
                        TAG, "Falha ao definir duty cycle");
    return ledc_update_duty(conveyor_speed_mode, conveyor_channel);
}

esp_err_t conveyor_start(const conveyor_config_t *config)
{
    ESP_RETURN_ON_FALSE(config != NULL, ESP_ERR_INVALID_ARG, TAG,
                        "Configuracao ausente");
    ESP_RETURN_ON_FALSE(!started, ESP_ERR_INVALID_STATE, TAG,
                        "Componente ja iniciado");
    ESP_RETURN_ON_FALSE(GPIO_IS_VALID_OUTPUT_GPIO(config->gpio),
                        ESP_ERR_INVALID_ARG, TAG, "GPIO invalido");
    ESP_RETURN_ON_FALSE(config->speed_percent >= 0 && config->speed_percent <= 100,
                        ESP_ERR_INVALID_ARG, TAG, "Velocidade invalida");

    const ledc_timer_config_t timer_config = {
        .speed_mode = conveyor_speed_mode,
        .duty_resolution = CONVEYOR_DUTY_RESOLUTION,
        .timer_num = conveyor_timer,
        .freq_hz = CONVEYOR_PWM_FREQUENCY_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_RETURN_ON_ERROR(ledc_timer_config(&timer_config), TAG,
                        "Falha ao configurar timer PWM");

    configured_duty = (CONVEYOR_MAX_DUTY * config->speed_percent) / 100U;
    const ledc_channel_config_t channel_config = {
        .gpio_num = config->gpio,
        .speed_mode = conveyor_speed_mode,
        .channel = conveyor_channel,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = conveyor_timer,
        .duty = configured_duty,
        .hpoint = 0,
    };
    ESP_RETURN_ON_ERROR(ledc_channel_config(&channel_config), TAG,
                        "Falha ao configurar canal PWM");

    configured_speed_percent = config->speed_percent;
    started = true;
    ESP_LOGI(TAG, "Esteira no GPIO %d: PWM de %d%% a %d Hz",
             config->gpio, configured_speed_percent, CONVEYOR_PWM_FREQUENCY_HZ);
    return ESP_OK;
}

esp_err_t conveyor_set_enabled(bool enabled)
{
    ESP_RETURN_ON_FALSE(started, ESP_ERR_INVALID_STATE, TAG,
                        "Componente nao iniciado");
    ESP_RETURN_ON_ERROR(conveyor_apply_duty(enabled ? configured_duty : 0), TAG,
                        "Falha ao alterar estado da esteira");

    ESP_LOGI(TAG, "Esteira %s (%d%%)", enabled ? "ligada" : "desligada",
             enabled ? configured_speed_percent : 0);
    return ESP_OK;
}
