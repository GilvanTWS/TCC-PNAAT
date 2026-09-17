#include "tria_network.h"

#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_check.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"

#include "cJSON.h"
#include "mqtt_client.h"

#define TOPIC_DECISION "tria/triagem"
#define TOPIC_STATUS   "tria/status/esp32"
#define TOPIC_ACTUATOR "tria/atuador"

#define SUPERVISOR_INTERVAL_MS 100
#define SUPERVISOR_STACK_SIZE  3072
#define SUPERVISOR_PRIORITY    4

static const char *TAG = "tria_network";
static tria_network_config_t network_config;
static esp_mqtt_client_handle_t mqtt_client;
static char last_class[32];
static char last_destination[16];
static volatile TickType_t last_message;
static volatile bool communication_ok;
static bool initialized;

static void notify_state(tria_network_state_t state)
{
    if (network_config.state_handler != NULL) {
        network_config.state_handler(state, network_config.callback_context);
    }
}

static void publish_status(bool connected)
{
    char payload[192];
    snprintf(payload, sizeof(payload),
             "{\"id_evento\":\"%s\",\"conectado\":%s,"
             "\"ultima_classe\":\"%s\",\"ultimo_destino\":\"%s\"}",
             network_config.client_id, connected ? "true" : "false",
             last_class, last_destination);

    esp_mqtt_client_publish(mqtt_client, TOPIC_STATUS, payload, 0, 1, 1);
    ESP_LOGI(TAG, "Status publicado: %s", payload);
}

static void publish_confirmation(const tria_decision_t *decision)
{
    /* Preserva o ID para correlação. "estabilizado" significa espera cumprida,
     * não realimentação física: o servo não possui sensor externo de posição. */
    char payload[192];
    snprintf(payload, sizeof(payload),
             "{\"id_evento\":\"%s\",\"classe\":\"%s\",\"destino\":\"%s\","
             "\"posicao_comandada\":\"%s\",\"estado_servo\":\"estabilizado\"}",
             decision->id_evento, decision->classe,
             decision->destino, decision->destino);

    esp_mqtt_client_publish(mqtt_client, TOPIC_ACTUATOR, payload, 0, 1, 0);
    ESP_LOGI(TAG, "Confirmacao publicada: %s", payload);
}

static bool topic_matches(const char *topic, int topic_length, const char *expected)
{
    /* Buffers recebidos do ESP-MQTT não precisam terminar em NUL. */
    return topic_length == strlen(expected) &&
           memcmp(topic, expected, topic_length) == 0;
}

static bool parse_decision(const cJSON *document, tria_decision_t *decision)
{
    const cJSON *event_id = cJSON_GetObjectItemCaseSensitive(document, "id_evento");
    const cJSON *class = cJSON_GetObjectItemCaseSensitive(document, "classe");
    const cJSON *destination = cJSON_GetObjectItemCaseSensitive(document, "destino");

    if (!cJSON_IsString(event_id) ||
        !cJSON_IsString(class) ||
        !cJSON_IsString(destination)) {
        return false;
    }

    /* Ponteiros emprestados do cJSON: válidos até cJSON_Delete(document).
     * Um consumidor assíncrono teria de copiar os textos antes de retornar. */
    decision->id_evento = event_id->valuestring;
    decision->classe = class->valuestring;
    decision->destino = destination->valuestring;
    return true;
}

static void handle_decision(const char *topic, int topic_length,
                            const char *data, int data_length)
{
    if (!topic_matches(topic, topic_length, TOPIC_DECISION)) {
        return;
    }

    char *payload = strndup(data, data_length);
    if (payload == NULL) {
        ESP_LOGE(TAG, "Falha ao alocar payload");
        return;
    }

    cJSON *document = cJSON_Parse(payload);
    tria_decision_t decision;

    if (document == NULL || !parse_decision(document, &decision)) {
        ESP_LOGW(TAG, "Decisao MQTT invalida: %.*s", data_length, data);
    } else if (network_config.decision_handler(&decision,
                                               network_config.callback_context) == ESP_OK) {
        snprintf(last_class, sizeof(last_class), "%s", decision.classe);
        snprintf(last_destination, sizeof(last_destination), "%s", decision.destino);
        last_message = xTaskGetTickCount();
        communication_ok = true;
        publish_confirmation(&decision);
    }

    cJSON_Delete(document);
    free(payload);
}

static void mqtt_event_handler(void *args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    esp_mqtt_event_handle_t event = event_data;

    switch ((esp_mqtt_event_id_t)event_id) {
    case MQTT_EVENT_CONNECTED:
        ESP_LOGI(TAG, "Conectado ao broker %s", network_config.mqtt_broker_uri);
        esp_mqtt_client_subscribe(event->client, TOPIC_DECISION, 1);
        last_message = xTaskGetTickCount();
        communication_ok = true;
        publish_status(true);
        notify_state(TRIA_NETWORK_CONNECTED);
        break;

    case MQTT_EVENT_DISCONNECTED:
        ESP_LOGW(TAG, "Desconectado do broker");
        communication_ok = false;
        notify_state(TRIA_NETWORK_DISCONNECTED);
        break;

    case MQTT_EVENT_DATA:
        /* Contrato atual: decisão curta em um evento. Não há remontagem de
         * payload fragmentado nem deduplicação de IDs reenviados por QoS 1. */
        handle_decision(event->topic, event->topic_len,
                        event->data, event->data_len);
        break;

    case MQTT_EVENT_ERROR:
        ESP_LOGE(TAG, "Erro MQTT");
        break;

    default:
        break;
    }
}

static esp_err_t storage_start(void)
{
    esp_err_t error = nvs_flash_init();
    if (error == ESP_ERR_NVS_NO_FREE_PAGES ||
        error == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_RETURN_ON_ERROR(nvs_flash_erase(), TAG, "Falha ao limpar NVS");
        error = nvs_flash_init();
    }
    return error;
}

static void wifi_event_handler(void *args, esp_event_base_t base,
                               int32_t event_id, void *event_data)
{
    if (base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "Wi-Fi desconectado; tentando novamente");
        esp_wifi_connect();
    }
}

static esp_err_t wifi_start(void)
{
    ESP_RETURN_ON_ERROR(storage_start(), TAG, "Falha ao iniciar NVS");
    ESP_RETURN_ON_ERROR(esp_netif_init(), TAG, "Falha ao iniciar rede");
    ESP_RETURN_ON_ERROR(esp_event_loop_create_default(), TAG,
                        "Falha ao criar loop de eventos");
    ESP_RETURN_ON_FALSE(esp_netif_create_default_wifi_sta() != NULL,
                        ESP_FAIL, TAG, "Falha ao criar interface Wi-Fi");

    const wifi_init_config_t init_config = WIFI_INIT_CONFIG_DEFAULT();
    wifi_config_t wifi_config = {
        .sta = {
            .threshold.authmode = WIFI_AUTH_WPA2_PSK,
        },
    };
    snprintf((char *)wifi_config.sta.ssid, sizeof(wifi_config.sta.ssid),
             "%s", network_config.wifi_ssid);
    snprintf((char *)wifi_config.sta.password, sizeof(wifi_config.sta.password),
             "%s", network_config.wifi_password);

    ESP_RETURN_ON_ERROR(esp_wifi_init(&init_config), TAG, "Falha ao iniciar Wi-Fi");
    ESP_RETURN_ON_ERROR(
        esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED,
                                   wifi_event_handler, NULL),
        TAG, "Falha ao registrar reconexao Wi-Fi");
    ESP_RETURN_ON_ERROR(esp_wifi_set_storage(WIFI_STORAGE_RAM), TAG,
                        "Falha ao definir armazenamento Wi-Fi");
    ESP_RETURN_ON_ERROR(esp_wifi_set_mode(WIFI_MODE_STA), TAG,
                        "Falha ao definir modo Wi-Fi");
    ESP_RETURN_ON_ERROR(esp_wifi_set_config(WIFI_IF_STA, &wifi_config), TAG,
                        "Falha ao configurar Wi-Fi");
    ESP_RETURN_ON_ERROR(esp_wifi_start(), TAG, "Falha ao iniciar Wi-Fi");
    return esp_wifi_connect();
}

static esp_err_t mqtt_start(void)
{
    const esp_mqtt_client_config_t config = {
        .broker.address.uri = network_config.mqtt_broker_uri,
        .credentials.client_id = network_config.client_id,
        .session.keepalive = 30,
        .network.reconnect_timeout_ms = 5000,
        .session.last_will.topic = TOPIC_STATUS,
        .session.last_will.msg = "{\"conectado\":false}",
        .session.last_will.msg_len = 19,
        .session.last_will.qos = 1,
        .session.last_will.retain = true,
    };

    mqtt_client = esp_mqtt_client_init(&config);
    ESP_RETURN_ON_FALSE(mqtt_client != NULL, ESP_ERR_NO_MEM, TAG,
                        "Falha ao criar cliente MQTT");
    ESP_RETURN_ON_ERROR(
        esp_mqtt_client_register_event(mqtt_client, ESP_EVENT_ANY_ID,
                                       mqtt_event_handler, NULL),
        TAG, "Falha ao registrar eventos MQTT");
    return esp_mqtt_client_start(mqtt_client);
}

static void supervisor_task(void *args)
{
    TickType_t last_status = xTaskGetTickCount();
    const TickType_t watchdog_timeout =
        pdMS_TO_TICKS(network_config.watchdog_timeout_ms);
    const TickType_t status_interval =
        pdMS_TO_TICKS(network_config.status_interval_ms);

    while (true) {
        vTaskDelay(pdMS_TO_TICKS(SUPERVISOR_INTERVAL_MS));
        const TickType_t now = xTaskGetTickCount();

        /* Supervisiona decisões aceitas, não um heartbeat do Pi. Uma linha
         * sem peças também vence o timeout, mesmo com Wi-Fi/MQTT conectados. */
        if (communication_ok && now - last_message > watchdog_timeout) {
            communication_ok = false;
            ESP_LOGW(TAG, "Tempo limite sem mensagem MQTT");
            publish_status(false);
            notify_state(TRIA_NETWORK_TIMEOUT);
        }

        if (communication_ok && now - last_status > status_interval) {
            last_status = now;
            publish_status(true);
        }
    }
}

static bool valid_config(const tria_network_config_t *config)
{
    return config != NULL &&
           config->wifi_ssid != NULL &&
           config->wifi_password != NULL &&
           config->mqtt_broker_uri != NULL &&
           config->client_id != NULL &&
           config->watchdog_timeout_ms > 0 &&
           config->status_interval_ms > 0 &&
           config->decision_handler != NULL;
}

esp_err_t tria_network_start(const tria_network_config_t *config)
{
    ESP_RETURN_ON_FALSE(valid_config(config), ESP_ERR_INVALID_ARG, TAG,
                        "Configuracao invalida");
    ESP_RETURN_ON_FALSE(!initialized, ESP_ERR_INVALID_STATE, TAG,
                        "Componente ja iniciado");

    /* Copia a estrutura, não as strings/contexto: devem durar toda a execução. */
    network_config = *config;
    ESP_RETURN_ON_ERROR(wifi_start(), TAG, "Falha ao iniciar Wi-Fi");
    ESP_RETURN_ON_ERROR(mqtt_start(), TAG, "Falha ao iniciar MQTT");
    ESP_RETURN_ON_FALSE(
        xTaskCreate(supervisor_task, "tria_network", SUPERVISOR_STACK_SIZE,
                    NULL, SUPERVISOR_PRIORITY, NULL) == pdPASS,
        ESP_ERR_NO_MEM, TAG, "Falha ao criar supervisor");

    last_message = xTaskGetTickCount();
    initialized = true;
    ESP_LOGI(TAG, "Wi-Fi STA iniciado: %s", network_config.wifi_ssid);
    return ESP_OK;
}
