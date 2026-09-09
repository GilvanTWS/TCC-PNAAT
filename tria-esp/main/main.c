/*
 * TRIA - Triagem Visual Integrada de Componentes
 * Firmware ESP32 (Heltec WiFi LoRa 32 V3) - Nó de Atuação
 *
 * Baseado na PoC do servo de Claylton (components/servo) e expandido para:
 *  - Assinar tria/triagem (decisões do Raspberry Pi)
 *  - Mover o servo para a posição calibrada A, B ou C
 *  - Exibir classe, destino e estado de conexão no OLED
 *  - Publicar confirmação em tria/atuador (RF05)
 *  - Publicar estado em tria/status/esp32
 *  - Watchdog de comunicação (RNF04): indicar indisponibilidade no OLED
 *    e via MQTT (Last Will) quando sem mensagens.
 *
 * Configuração via menuconfig (idf.py menuconfig):
 *  - TRIA_WIFI_SSID / TRIA_WIFI_PASSWORD / TRIA_MQTT_BROKER_URI
 *  - TRIA_ANGULO_A / B / C e TRIA_SERVO_GPIO
 */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include "driver/gpio.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_check.h"
#include "esp_err.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "cJSON.h"
#include "mqtt_client.h"
#include "servo.h"

#include "u8g2.h"
#include "u8g2_esp32_hal.h"

/* ============ Tópicos MQTT ============ */
#define TOPICO_TRIAGEM      "tria/triagem"
#define TOPICO_STATUS_ESP32 "tria/status/esp32"
#define TOPICO_STATUS_PI    "tria/status/pi"
#define TOPICO_ATUADOR      "tria/atuador"

/* ============ Configuração via sdkconfig (menuconfig) ============ */
#define WIFI_SSID          CONFIG_TRIA_WIFI_SSID
#define WIFI_PASSWORD      CONFIG_TRIA_WIFI_PASSWORD
#define MQTT_BROKER_URI    CONFIG_TRIA_MQTT_BROKER_URI
#define ESP32_ID           CONFIG_TRIA_ESP32_ID

#define SERVO_GPIO         CONFIG_TRIA_SERVO_GPIO
#define ANGULO_A           CONFIG_TRIA_ANGULO_A
#define ANGULO_B           CONFIG_TRIA_ANGULO_B
#define ANGULO_C           CONFIG_TRIA_ANGULO_C
#define TEMPO_SERVO_MS     CONFIG_TRIA_TEMPO_SERVO_MS

#define OLED_SDA_GPIO      CONFIG_TRIA_OLED_SDA_GPIO
#define OLED_SCL_GPIO      CONFIG_TRIA_OLED_SCL_GPIO

#define GPIO_VIBRADOR       CONFIG_TRIA_GPIO_VIBRADOR
#define VIBRADOR_DURACAO_MS  300

#define WATCHDOG_TIMEOUT_MS (CONFIG_TRIA_WATCHDOG_TIMEOUT_S * 1000)
#define STATUS_INTERVAL_MS  (CONFIG_TRIA_STATUS_INTERVAL_S * 1000)

static const char *TAG = "tria_esp";

/* ============ Estado do nó ============ */
static esp_mqtt_client_handle_t mqtt_client;
static char ultima_classe[32]   = "";
static char ultimo_destino[16]  = "";
static char ultimo_id_evento[32] = "";

static unsigned long ultima_msg_ms = 0;
static bool comunicacao_ok = true;

/* ============ Configuração e funções do vibrador ============ */

static void vibrador_iniciar(void) {
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << GPIO_VIBRADOR),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(GPIO_VIBRADOR, 0);
}

static void acionar_vibrador(void) {
    gpio_set_level(GPIO_VIBRADOR, 1);
    vTaskDelay(pdMS_TO_TICKS(VIBRADOR_DURACAO_MS));
    gpio_set_level(GPIO_VIBRADOR, 0);
}

/* ============ OLED (U8g2 - Heltec WiFi LoRa 32 V3) ============ */
static U8G2 u8g2;  /* configuração SSD1306 128x64 SW_I2C */

static void oled_iniciar(void)
{
    u8g2_esp32_hal_t hal = U8G2_ESP32_HAL_DEFAULT;
    hal.sda = OLED_SDA_GPIO;
    hal.scl = OLED_SCL_GPIO;
    u8g2_esp32_hal_init(hal);

    u8g2_Setup_ssd1306_128x64_noname_f(&u8g2, U8G2_R0,
                                       /* rotation= */ U8G2_R0,
                                       /* byte_cb=   */ u8g2_esp32_hal_byte_cb,
                                       /* gpio_and_delay_cb= */ u8g2_esp32_hal_gpio_and_delay_cb);
    u8g2_InitDisplay(&u8g2);
    u8g2_SetPowerSave(&u8g2, 0);
    u8g2_ClearBuffer(&u8g2);
}

static void oled_mostrar(const char *linha1, const char *linha2, const char *linha3)
{
    u8g2_ClearBuffer(&u8g2);
    u8g2_SetFont(&u8g2, u8g2_font_8x13_tr);
    u8g2_DrawUTF8(&u8g2, 0, 12, linha1);
    u8g2_DrawUTF8(&u8g2, 0, 30, linha2);
    u8g2_DrawUTF8(&u8g2, 0, 48, linha3);
    u8g2_SendBuffer(&u8g2);
}

/* ============ Helpers de saída ============ */

static void mover_servo_para_destino(const char *destino)
{
    static const struct { const char *dest; int angulo; } mapa[] = {
        { "A", ANGULO_A },
        { "B", ANGULO_B },
        { "C", ANGULO_C },
        { NULL, 0 },
    };

    for (int i = 0; mapa[i].dest != NULL; i++) {
        if (strcmp(destino, mapa[i].dest) == 0) {
            ESP_LOGI(TAG, "Servo -> posicao %s (angulo %d)", destino, mapa[i].angulo);
            ESP_ERROR_CHECK(servo_set_angle(mapa[i].angulo));
            vTaskDelay(pdMS_TO_TICKS(TEMPO_SERVO_MS));
            return;
        }
    }
    ESP_LOGW(TAG, "Destino desconhecido: %s", destino);
}

static void publicar_status(bool conectado)
{
    char payload[192];
    snprintf(payload, sizeof(payload),
             "{\"id_evento\":\"%s\",\"conectado\":%s,"
             "\"ultima_classe\":\"%s\",\"ultimo_destino\":\"%s\"}",
             ESP32_ID, conectado ? "true" : "false",
             ultima_classe, ultimo_destino);

    esp_mqtt_client_publish(mqtt_client, TOPICO_STATUS_ESP32, payload, 0, 1, 1);
    ESP_LOGI(TAG, "Status publicado: %s", payload);
}

static void publicar_confirmacao(const char *id_evento, const char *classe,
                                 const char *destino)
{
    char payload[192];
    snprintf(payload, sizeof(payload),
             "{\"id_evento\":\"%s\",\"classe\":\"%s\",\"destino\":\"%s\","
             "\"posicao_comandada\":\"%s\",\"estado_servo\":\"estabilizado\"}",
             id_evento, classe, destino, destino);

    esp_mqtt_client_publish(mqtt_client, TOPICO_ATUADOR, payload, 0, 1, 0);
    ESP_LOGI(TAG, "Confirmacao em %s: %s", TOPICO_ATUADOR, payload);
}

/* ============ Tratamento de dados MQTT ============ */

static void tratar_decisao(const char *topic, int topic_len,
                           const char *data, int data_len)
{
    if (strlen(TOPICO_TRIAGEM) != topic_len ||
        memcmp(topic, TOPICO_TRIAGEM, topic_len) != 0) {
        return;
    }

    char *payload = strndup(data, data_len);
    if (payload == NULL) {
        ESP_LOGE(TAG, "Falha ao alocar payload");
        return;
    }

    cJSON *doc = cJSON_Parse(payload);
    if (doc == NULL) {
        ESP_LOGW(TAG, "JSON invalido ignorado: %.*s", data_len, data);
        free(payload);
        return;
    }

    const cJSON *id   = cJSON_GetObjectItem(doc, "id_evento");
    const cJSON *cls  = cJSON_GetObjectItem(doc, "classe");
    const cJSON *dest = cJSON_GetObjectItem(doc, "destino");

    if (!cJSON_IsString(id) || !cJSON_IsString(cls) || !cJSON_IsString(dest)) {
        ESP_LOGW(TAG, "Payload invalido: faltam id_evento/classe/destino");
        cJSON_Delete(doc);
        free(payload);
        return;
    }

    bool destino_valido =
        strcmp(dest->valuestring, "A") == 0 ||
        strcmp(dest->valuestring, "B") == 0 ||
        strcmp(dest->valuestring, "C") == 0;

    if (!destino_valido) {
        ESP_LOGW(TAG, "Destino invalido: %s", dest->valuestring);
        cJSON_Delete(doc);
        free(payload);
        return;
    }

    /* Atualizar watchdog (RNF04) */
    ultima_msg_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
    comunicacao_ok = true;

    snprintf(ultimo_id_evento, sizeof(ultimo_id_evento), "%s", id->valuestring);
    snprintf(ultima_classe, sizeof(ultima_classe), "%s", cls->valuestring);
    snprintf(ultimo_destino, sizeof(ultimo_destino), "%s", dest->valuestring);

    ESP_LOGI(TAG, "Decisao recebida: id=%s classe=%s destino=%s",
             id->valuestring, cls->valuestring, dest->valuestring);

    mover_servo_para_destino(dest->valuestring);

    oled_mostrar(ultima_classe, ultimo_destino, "OK");

    publicar_confirmacao(id->valuestring, cls->valuestring, dest->valuestring);

    cJSON_Delete(doc);
    free(payload);
}

/* ============ Eventos MQTT ============ */

static void mqtt_event_handler(void *handler_args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;
    esp_mqtt_client_handle_t client = event->client;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Conectado ao broker %s", MQTT_BROKER_URI);
        esp_mqtt_client_subscribe(client, TOPICO_TRIAGEM, 1);
        ESP_LOGI(TAG, "Assinado: %s", TOPICO_TRIAGEM);
        comunicacao_ok = true;
        publicar_status(true);
        oled_mostrar("TRIA ATIVO", "Aguardando", "decisao");
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Desconectado do broker");
        comunicacao_ok = false;
        break;

    case MQTT_EVENT_DATA:
        tratar_decisao(event->topic, event->topic_len,
                       event->data, event->data_len);
        break;

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "Erro MQTT");
        break;

    default:
        break;
    }
}

static void mqtt_iniciar(void)
{
    esp_mqtt_client_config_t cfg = {
        .broker.address.uri = MQTT_BROKER_URI,
        .credentials.client_id = ESP32_ID,
        .session.keepalive = 30,
        .network.reconnect_timeout_ms = 5000,
        .session.last_will.topic = TOPICO_STATUS_ESP32,
        .session.last_will.msg = "{\"conectado\":false}",
        .session.last_will.msg_len = 19,
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
    };

    mqtt_client = esp_mqtt_client_init(&cfg);
    esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID,
                                   mqtt_event_handler, NULL);
    ESP_ERROR_CHECK(esp_mqtt_client_start(mqtt_client));
}

/* ============ Wi-Fi (STA) ============ */

static esp_err_t wifi_iniciar(void)
{
    ESP_RETURN_ON_ERROR(nvs_flash_init(), TAG, "Falha no nvs_flash_init");

    esp_netif_init();
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_RETURN_ON_ERROR(esp_wifi_init(&cfg), TAG, "Falha no esp_wifi_init");
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), TAG, "Falha storage");

    wifi_config_t wifi_cfg = {
        .sta = {
            .ssid = WIFI_SSID,
            .password = WIFI_PASSWORD,
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG, "Falha no modo STA");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi_cfg), TAG, "Falha na config");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "Falha no esp_wifi_start");

    ESP_LOGI(TAG, "Wi-Fi STA iniciado: %s", WIFI_SSID);
    return ESP_OK;
}

/* ============ app_main ============ */

void app_main(void)
{
    ESP_LOGI(TAG, "TRIA - No de atuacao iniciando...");

    oled_iniciar();
    oled_mostrar("TRIA - ESP32", "Iniciando...", "");

    vibrador_iniciar();
    acionar_vibrador();

    ESP_ERROR_CHECK(servo_init(SERVO_GPIO));
    ESP_LOGI(TAG, "Servo no GPIO %d", SERVO_GPIO);

    ESP_ERROR_CHECK(wifi_iniciar());
    mqtt_iniciar();

    oled_mostrar("TRIA - ESP32", "Conectando", "MQTT...");

    ultima_msg_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

    /* Loop de supervisão: watchdog (RNF04) + status periódico */
    unsigned long ultimo_status_ms = 0;

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(100));

        unsigned long agora = xTaskGetTickCount() * portTICK_PERIOD_MS;

        if (agora - ultima_msg_ms > WATCHDOG_TIMEOUT_MS && comunicacao_ok) {
            comunicacao_ok = false;
            ESP_LOGW(TAG, "Sem comunicacao ha %lus - indicando indisponibilidade",
                     WATCHDOG_TIMEOUT_MS / 1000);
            publicar_status(false);
            oled_mostrar("S/ COMUNICACAO", "Verificando", "rede...");
        }

        if (agora - ultimo_status_ms > STATUS_INTERVAL_MS) {
            ultimo_status_ms = agora;
            if (comunicacao_ok) {
                publicar_status(true);
            }
        }
    }
}