/*
 * TRIA - Triagem Visual Integrada de Componentes
 * Firmware ESP32 (Heltec WiFi LoRa 32 V3) - Nó de Atuação
 *
 * Responsabilidades:
 *  - Assinar tópico tria/triagem (decisões do Raspberry Pi)
 *  - Mover servo para posição A, B ou C
 *  - Exibir classe/destino/estado no OLED
 *  - Publicar confirmação em tria/atuador
 *  - Publicar estado em tria/status/esp32
 *  - Watchdog de comunicação (reconectar se perder conexão)
 *
 * Pinagem (Heltec WiFi LoRa 32 V3):
 *  - Servo: GPIO 13 (PWM)
 *  - OLED:  I2C (SoftwareWire pinos)
 *
 * Compilar: pio run -e heltec_wifi_lora32_v3
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <ArduinoJson.h>

/* ============ Configuração da Rede ============ */
// TODO: preencher com os dados da rede do ensaio
const char* WIFI_SSID     = "SUA_REDE_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA";

// TODO: IP do Mosquitto (pode ser localhost no Pi ou IP na rede)
const char* MQTT_SERVER   = "192.168.0.100";
const int   MQTT_PORT     = 1883;

// ID fixo do nó (usado no Last Will e tópicos de status)
const char* ESP32_ID      = "esp32-tria-01";

/* ============ Tópicos MQTT ============ */
const char* TOPICO_TRIAGEM      = "tria/triagem";
const char* TOPICO_STATUS_ESP32 = "tria/status/esp32";
const char* TOPICO_ATUADOR      = "tria/atuador";

/* ============ Servo ============ */
// Pin do servo (configurar conforme montagem)
#define SERVO_PIN 13

// Ângulos calibrados do desviador (ajustar na montagem)
const int ANGULO_A = 45;   // Saída A - Quadrado
const int ANGULO_B = 90;   // Saída B - Triângulo
const int ANGULO_C = 135;  // Saída C - Descarte

// Tempo máximo para o servo estabilizar (ms)
const int TEMPO_MOVIMENTO_SERVO_MS = 500;

/* ============ Watchdog de comunicação ============ */
// Se não receber mensagem em X segundos, indicar indisponibilidade
const unsigned long WATCHDOG_TIMEOUT_MS = 15000;  // 15s (RNF04)

/* ============ Variáveis globais ============ */
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, /* reset=*/ U8G2_PIN_NONE);

ESP32Servo servoMotor;

unsigned long ultimaMensagemRecebidaMs = 0;
String ultimaClasseRecebida = "";
String ultimoDestinoRecebido = "";
String ultimoIDRecebido = "";
bool comunicacaoDisponivel = true;

/* ============ Protótipos ============ */
void conectarMqtt();
void publicarStatus();
void publicarConfirmacao(const char* id_evento, const char* classe, const char* destino);
void moverServoPara(const char* destino);
void mostrarOled(const char* linha1, const char* linha2, const char* linha3);
void callbackMqtt(char* topic, byte* payload, unsigned int length);

/* ============ Callback MQTT ============ */
/* Recebe decisão da rede: tria/triagem */
void callbackMqtt(char* topic, byte* payload, unsigned int length) {
  String topico = String(topic);

  // Ignorar payloads vazios
  if (length == 0) return;

  // Converter payload para String
  String payloadStr;
  payloadStr.reserve(length);
  for (unsigned int i = 0; i < length; i++) {
    payloadStr += (char)payload[i];
  }

  Serial.print("MQTT recebido em: ");
  Serial.println(topico);
  Serial.print("Payload: ");
  Serial.println(payloadStr);

  if (topico == String(TOPICO_TRIAGEM)) {
    // Analisar JSON
    StaticJsonDocument<512> doc;
    DeserializationError erro = deserializeJson(doc, payloadStr);

    if (erro) {
      Serial.print("Falha ao analisar JSON: ");
      Serial.println(erro.c_str());
      return;
    }

    const char* id_evento = doc["id_evento"] | "";
    const char* classe    = doc["classe"] | "";
    const char* destino   = doc["destino"] | "";

    // Validar campos obrigatórios
    if (strlen(id_evento) == 0 || strlen(destino) == 0) {
      Serial.println("Payload inválido: falta id_evento ou destino");
      return;
    }

    Serial.print("Decisão recebida: destino=");
    Serial.println(destino);

    // Atualizar watchdog (RNF04)
    ultimaMensagemRecebidaMs = millis();

    // Guardar dados recebidos
    ultimoIDRecebido = String(id_evento);
    ultimaClasseRecebida = String(classe);
    ultimoDestinoRecebido = String(destino);

    // Mover servo para a posição calibrada
    moverServoPara(destino);

    // Publicar confirmação em tria/atuador (RF05)
    publicarConfirmacao(id_evento, classe, destino);

    // Atualizar OLED
    mostrarOled(ultimaClasseRecebida.c_str(), destino, "");
  }
  else if (topico == String(TOPICO_STATUS_ESP32)) {
    // (opcional) tratar comando de status
  }
}

/* ============ Mover Servo ============ */
/* Leva o servo à posição calibrada A, B ou C */
void moverServoPara(const char* destino) {
  int angulo;

  if (strcmp(destino, "A") == 0) {
    angulo = ANGULO_A;
  } else if (strcmp(destino, "B") == 0) {
    angulo = ANGULO_B;
  } else if (strcmp(destino, "C") == 0) {
    angulo = ANGULO_C;
  } else {
    Serial.print("Destino desconhecido: ");
    Serial.println(destino);
    return;
  }

  Serial.print("Movendo servo para posição ");
  Serial.print(destino);
  Serial.print(" (ângulo ");
  Serial.print(angulo);
  Serial.println("°)");

  servoMotor.write(angulo);
  delay(TEMPO_MOVIMENTO_SERVO_MS);
  Serial.println("Servo estabilizado.");
}

/* ============ Publicar confirmação ============ */
/* Confirmação vinculada ao id_evento e posição comandada (RF05) */
void publicarConfirmacao(const char* id_evento, const char* classe, const char* destino) {
  StaticJsonDocument<256> doc;

  doc["id_evento"] = id_evento;
  doc["horario"] = millis();  // timestamp de uptime (ajustar com RTC se necessário)
  doc["classe"] = classe;
  doc["destino"] = destino;
  doc["posicao_comandada"] = destino;
  doc["estado_servo"] = "estabilizado";

  char buffer[256];
  serializeJson(doc, buffer, sizeof(buffer));

  mqttClient.publish(TOPICO_ATUADOR, buffer);
  Serial.print("Confirmação publicada em ");
  Serial.print(TOPICO_ATUADOR);
  Serial.print(": ");
  Serial.println(buffer);
}

/* ============ Publicar status ============ */
/* Status do nó de atuação (RNF04 - indique disponibilidade) */
void publicarStatus() {
  StaticJsonDocument<256> doc;

  doc["id_evento"] = ESP32_ID;
  doc["horario"] = millis();
  doc["conectado"] = mqttClient.connected();
  doc["ultima_classe"] = ultimaClasseRecebida;
  doc["ultimo_destino"] = ultimoDestinoRecebido;
  doc["estado_oled"] = "ativo";

  char buffer[256];
  serializeJson(doc, buffer, sizeof(buffer));

  mqttClient.publish(TOPICO_STATUS_ESP32, buffer, true);  // retain
  Serial.println("Status publicado.");
}

/* ============ Conectar MQTT ============ */
/* Conecta ao broker com retentativa automática */
void conectarMqtt() {
  Serial.print("Conectando ao MQTT em ");
  Serial.print(MQTT_SERVER);
  Serial.print(":");

  while (!mqttClient.connected()) {
    Serial.print("Tentando conectar...");
    String clientId = String(ESP32_ID) + "-" + String(millis() % 1000);

    // Definir Last Will (RNF04 - detectar desconexão)
    bool conectado = mqttClient.connect(
      clientId.c_str(),
      NULL, NULL,
      TOPICO_STATUS_ESP32, 0, true,
      "{\"conectado\":false}"
    );

    if (conectado) {
      Serial.println(" Conectado!");
      mqttClient.subscribe(TOPICO_TRIAGEM);
      Serial.print("Assinando tópico: ");
      Serial.println(TOPICO_TRIAGEM);

      comunicacaoDisponivel = true;
      publicarStatus();
      mostrarOled("TRIA ATIVO", "Aguardando", "decisao");
    } else {
      Serial.print("Falha, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" tentando em 5s...");
      delay(5000);
    }
  }
}

/* ============ Display OLED ============ */
/* Exibe 3 linhas: classe, destino e estado da conexão */
void mostrarOled(const char* linha1, const char* linha2, const char* linha3) {
  oled.clearBuffer();
  oled.setFont(u8g2_font_ncenB08_tr);
  oled.drawStr(0, 12, linha1);
  oled.drawStr(0, 30, linha2);
  oled.drawStr(0, 48, linha3);
  oled.sendBuffer();
}

/* ============ Setup ============ */
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n===== TRIA - Nó de Atuação ESP32 =====");
  Serial.println("Inicializando...");

  // Inicializar OLED
  oled.begin();
  oled.clearBuffer();
  oled.setFont(u8g2_font_ncenB08_tr);
  oled.drawStr(0, 12, "TRIA - ESP32");
  oled.drawStr(0, 30, "Iniciando...");
  oled.sendBuffer();

  // Inicializar servo
  servoMotor.attach(SERVO_PIN, 500, 2500);  // 500us-2500us (ajustar)
  servoMotor.write(ANGULO_B);  // posição neutra
  Serial.print("Servo no GPIO ");
  Serial.println(SERVO_PIN);

  // Conectar Wi-Fi
  Serial.println("Conectando ao Wi-Fi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Wi-Fi conectado. IP: ");
  Serial.println(WiFi.localIP());

  // Configurar MQTT
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(callbackMqtt);
  mqttClient.setKeepAlive(30);

  // Conectar MQTT
  conectarMqtt();

  ultimaMensagemRecebidaMs = millis();
  Serial.println("ESP32 pronto. Aguardando decisões...");
}

/* ============ Loop principal ============ */
void loop() {
  // Manter conexão MQTT
  if (!mqttClient.connected()) {
    conectarMqtt();
    comunicacaoDisponivel = false;
  }
  mqttClient.loop();

  // Watchdog de comunicação (RNF04)
  unsigned long agora = millis();
  unsigned long diff = agora - ultimaMensagemRecebidaMs;

  if (diff > WATCHDOG_TIMEOUT_MS) {
    if (comunicacaoDisponivel) {
      Serial.println("Timeout de comunicação - indicando indisponibilidade no OLED");
      comunicacaoDisponivel = false;

      mostrarOled("S/ COMUNICACAO", "Verificando...", "reconexao");

      // Publicar status de indisponibilidade
      StaticJsonDocument<128> doc;
      doc["id_evento"] = ESP32_ID;
      doc["horario"] = agora;
      doc["conectado"] = false;
      doc["estado_oled"] = "timeout";

      char buffer[128];
      serializeJson(doc, buffer, sizeof(buffer));
      mqttClient.publish(TOPICO_STATUS_ESP32, buffer, true);
    }
  } else if (!comunicacaoDisponivel) {
    // Recuperou a comunicação
    comunicacaoDisponivel = true;
    mostrarOled("TRIA ATIVO", ultimaClasseRecebida.c_str(), ultimoDestinoRecebido.c_str());
  }

  // Publicar status periodicamente (a cada 30s, opcional)
  static unsigned long ultimoStatus = 0;
  if (millis() - ultimoStatus > 30000) {
    ultimoStatus = millis();
    if (mqttClient.connected()) {
      publicarStatus();
    }
  }

  delay(10);
}