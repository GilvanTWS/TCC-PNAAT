#pragma once

#include <stdint.h>

#include "esp_err.h"

/** Textos emprestados do parser, válidos somente durante decision_handler. */
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

/** Callback síncrono na tarefa MQTT; ESP_OK autoriza publicar a confirmação. */
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

/**
 * @brief Inicia Wi-Fi STA, MQTT e supervisor uma única vez.
 * @param config Estrutura copiada; strings e callback_context devem continuar
 * válidos por toda a execução. Tempos em ms, maiores que zero. decision_handler
 * obrigatório; state_handler opcional, chamado por tarefas MQTT/supervisor.
 * @return ESP_OK indica inicialização, não conexão já estabelecida. Erros de
 * configuração/inicialização são propagados; reinicialização é rejeitada.
 */
esp_err_t tria_network_start(const tria_network_config_t *config);
