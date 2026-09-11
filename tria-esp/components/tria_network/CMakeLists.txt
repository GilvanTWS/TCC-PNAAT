idf_component_register(
    SRCS "tria_network.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_event esp_netif esp_wifi json mqtt nvs_flash
)
