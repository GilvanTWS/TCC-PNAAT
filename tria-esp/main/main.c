#include "esp_check.h"
#include "esp_log.h"

#include "conveyor.h"
#include "tria_actuator.h"
#include "tria_display.h"
#include "tria_network.h"
#include "vibration.h"

static const char *TAG = "tria_esp";

/* Executado na tarefa MQTT: os textos de decisao valem apenas nesta chamada.
 * O retorno confirma comando + espera, sem sensor de posição do SG90. */
static esp_err_t processar_decisao(const tria_decision_t *decisao, void *context)
{
    ESP_RETURN_ON_ERROR(tria_actuator_move(decisao->destino),
                        TAG, "Falha ao posicionar atuador");
    tria_display_show(decisao->classe, decisao->destino, "OK");
    return ESP_OK;
}

static void atualizar_estado_rede(tria_network_state_t estado, void *context)
{
    switch (estado) {
    case TRIA_NETWORK_CONNECTED:
        tria_display_show("TRIA ATIVO", "Aguardando", "decisao");
        break;
    case TRIA_NETWORK_TIMEOUT:
        tria_display_show("S/ COMUNICACAO", "Verificando", "rede...");
        break;
    case TRIA_NETWORK_DISCONNECTED:
        tria_display_show("S/ COMUNICACAO", "Reconectando", "MQTT...");
        break;
    }
}

void app_main(void)
{
    const tria_actuator_config_t actuator_config = {
        .servo_gpio = CONFIG_TRIA_SERVO_GPIO,
        .angle_a = CONFIG_TRIA_ANGULO_A,
        .angle_b = CONFIG_TRIA_ANGULO_B,
        .angle_c = CONFIG_TRIA_ANGULO_C,
        .settling_time_ms = CONFIG_TRIA_TEMPO_SERVO_MS,
    };
    const vibration_config_t vibration_config = {
        .button_gpio = CONFIG_TRIA_BUTTON_GPIO,
        .motor_gpio = CONFIG_TRIA_VIBRATION_GPIO,
        .debounce_ms = CONFIG_TRIA_BUTTON_DEBOUNCE_MS,
    };
    const conveyor_config_t conveyor_config = {
        .gpio = CONFIG_TRIA_CONVEYOR_GPIO,
        .speed_percent = CONFIG_TRIA_CONVEYOR_SPEED_PERCENT,
    };
    const tria_network_config_t network_config = {
        .wifi_ssid = CONFIG_TRIA_WIFI_SSID,
        .wifi_password = CONFIG_TRIA_WIFI_PASSWORD,
        .mqtt_broker_uri = CONFIG_TRIA_MQTT_BROKER_URI,
        .client_id = CONFIG_TRIA_ESP32_ID,
        .watchdog_timeout_ms = CONFIG_TRIA_WATCHDOG_TIMEOUT_S * 1000,
        .status_interval_ms = CONFIG_TRIA_STATUS_INTERVAL_S * 1000,
        .decision_handler = processar_decisao,
        .state_handler = atualizar_estado_rede,
    };

    ESP_LOGI(TAG, "TRIA - No de atuacao iniciando...");
    ESP_ERROR_CHECK(tria_display_init(CONFIG_TRIA_OLED_SDA_GPIO,
                                      CONFIG_TRIA_OLED_SCL_GPIO,
                                      CONFIG_TRIA_OLED_RESET_GPIO,
                                      CONFIG_TRIA_OLED_POWER_GPIO));
    tria_display_show("TRIA - ESP32", "Iniciando...", "");

    /* Inicializa saídas antes da rede. A esteira começa no duty configurado;
     * fan começa desligada. Perder MQTT não para automaticamente os motores. */
    ESP_ERROR_CHECK(tria_actuator_start(&actuator_config));
    ESP_ERROR_CHECK(vibration_start(&vibration_config));
    ESP_ERROR_CHECK(conveyor_start(&conveyor_config));

    tria_display_show("TRIA - ESP32", "Conectando", "MQTT...");
    ESP_ERROR_CHECK(tria_network_start(&network_config));
}
