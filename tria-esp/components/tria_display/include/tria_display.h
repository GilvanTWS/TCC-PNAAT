#pragma once

#include "esp_err.h"

esp_err_t tria_display_init(int sda_gpio, int scl_gpio,
                            int reset_gpio, int power_gpio);
void tria_display_show(const char *line_1, const char *line_2, const char *line_3);
