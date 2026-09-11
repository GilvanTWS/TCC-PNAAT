#pragma once

#include <stdint.h>

#include "esp_err.h"

typedef struct {
    const char *id_evento;
    const char *classe;
    const char *destino;
} tria_decision_t;

typedef enum {
    TRIA_NETWORK_CONNECTED,
    TRIA_NETWORK_DISCONNECTED,
    TRIA_NETWORK_TIMEOUT,
} tria_network_state_t;

typedef esp_err_t (*tria_decision_handler_t)(const tria_decision_t *decision,
                                            void *context);
typedef void (*tria_network_state_handler_t)(tria_network_state_t state,
                                             void *context);

typedef struct {
    const char *wifi_ssid;
    const char *wifi_password;
    const char *mqtt_broker_uri;
    const char *client_id;
    uint32_t watchdog_timeout_ms;
    uint32_t status_interval_ms;
    tria_decision_handler_t decision_handler;
    tria_network_state_handler_t state_handler;
    void *callback_context;
} tria_network_config_t;

esp_err_t tria_network_start(const tria_network_config_t *config);
