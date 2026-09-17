#pragma once

#include "esp_err.h"

/** Inicia uma vez o OLED 128x64; Vext ativo em zero. Propaga falhas de GPIO/I2C. */
esp_err_t tria_display_init(int sda_gpio, int scl_gpio,
                            int reset_gpio, int power_gpio);
/** Exibe três linhas sob mutex; pode bloquear aguardando outra atualização.
 * Ignora chamadas antes de init ou com texto NULL. Textos não são retidos. */
void tria_display_show(const char *line_1, const char *line_2, const char *line_3);
