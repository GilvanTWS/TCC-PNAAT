idf_component_register(SRCS "main.c"
                    INCLUDE_DIRS "."
                    REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_driver_gpio servo cjson esp_timer esp_http_client esp_https_ota mqtt_client)