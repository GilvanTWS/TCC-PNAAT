#include "servo.h"

#include "driver/ledc.h"
#include "esp_check.h"

#define SERVO_FREQUENCY_HZ       50
#define SERVO_MIN_PULSE_US       500
#define SERVO_MAX_PULSE_US       2500
#define SERVO_PERIOD_US          (1000000 / SERVO_FREQUENCY_HZ)
#define SERVO_DUTY_RESOLUTION    LEDC_TIMER_14_BIT
#define SERVO_MAX_DUTY           ((1U << 14) - 1U)

static const ledc_mode_t servo_speed_mode = LEDC_LOW_SPEED_MODE;
static const ledc_timer_t servo_timer = LEDC_TIMER_0;
static const ledc_channel_t servo_channel = LEDC_CHANNEL_0;
static bool servo_initialized;

esp_err_t servo_init(int gpio)
{
    const ledc_timer_config_t timer_config = {
        .speed_mode = servo_speed_mode,
        .duty_resolution = SERVO_DUTY_RESOLUTION,
        .timer_num = servo_timer,
        .freq_hz = SERVO_FREQUENCY_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ESP_RETURN_ON_ERROR(ledc_timer_config(&timer_config), "servo", "Falha ao configurar timer");

    const ledc_channel_config_t channel_config = {
        .gpio_num = gpio,
        .speed_mode = servo_speed_mode,
        .channel = servo_channel,
        .intr_type = LEDC_INTR_DISABLE,
        .timer_sel = servo_timer,
        .duty = 0,
        .hpoint = 0,
    };
    ESP_RETURN_ON_ERROR(ledc_channel_config(&channel_config), "servo", "Falha ao configurar canal");

    servo_initialized = true;
    return ESP_OK;
}

esp_err_t servo_set_angle(int angle)
{
    ESP_RETURN_ON_FALSE(servo_initialized, ESP_ERR_INVALID_STATE, "servo", "Servo nao inicializado");
    ESP_RETURN_ON_FALSE(angle >= 0 && angle <= 180, ESP_ERR_INVALID_ARG, "servo", "Angulo invalido");

    const uint32_t pulse_us = SERVO_MIN_PULSE_US
                            + ((SERVO_MAX_PULSE_US - SERVO_MIN_PULSE_US) * angle) / 180;
    const uint32_t duty = (pulse_us * SERVO_MAX_DUTY) / SERVO_PERIOD_US;

    ESP_RETURN_ON_ERROR(ledc_set_duty(servo_speed_mode, servo_channel, duty),
                        "servo", "Falha ao definir duty cycle");
    return ledc_update_duty(servo_speed_mode, servo_channel);
}
