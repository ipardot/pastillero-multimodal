// Pastillero multimodal - firmware ESP32 (Wokwi)
// El reloj vive en la app: este firmware solo reacciona a órdenes por MQTT
// y mide sus propios tiempos de escalamiento con millis() (tiempo real).

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ---------- Configuración ----------
const char* WIFI_SSID = "Wokwi-GUEST";   // red simulada de Wokwi
const char* WIFI_PASS = "";
const char* MQTT_HOST = "broker.hivemq.com";
const uint16_t MQTT_PORT = 1883;

// IMPORTANTE: debe coincidir con PASTILLERO_PREFIX de la app.
const char* TOPIC_CMD    = "eafit/julian/pastillero/cmd";     // app -> ESP32
const char* TOPIC_ESTADO = "eafit/julian/pastillero/estado";  // ESP32 -> app

// Pines
const int PIN_SERVO = 18;
const int PIN_LED[3] = {25, 26, 27};
const int PIN_BUZZER = 14;
const int PIN_BTN_CONFIRMAR = 32;
const int PIN_BTN_POSPONER = 33;

// Servo: ángulo de reposo y de cada compartimento
const int ANGULO_REPOSO = 0;
const int ANGULO_COMP[3] = {45, 90, 135};

// Escalamiento (tiempo REAL desde que se dispensa). Valores de demo.
const unsigned long T_SONIDO_MS   = 6000;   // 6 s sin respuesta -> buzzer
const unsigned long T_OMITIDA_MS  = 16000;  // 16 s sin respuesta -> omitida
const unsigned long T_POSPONER_MS = 5000;   // pausa al posponer
const int MAX_POSPOSICIONES = 1;
const unsigned long T_AVISO_INICIAL_MS = 800;  // 2 pitidos cortos al dispensar

// ---------- Estado ----------
WiFiClient wifi;
PubSubClient mqtt(wifi);
Servo servo;

bool enAlerta = false;
String tomaId = "";
String tomaMed = "";
int tomaComp = 1;
unsigned long tInicio = 0;
unsigned long posponeHasta = 0;  // 0 = no pospuesta
int posposiciones = 0;
bool sonando = false;
bool tonoActivo = false;

struct Boton {
  int pin;
  bool previo;
  unsigned long ultimo;
};
Boton btnConfirmar = {PIN_BTN_CONFIRMAR, false, 0};
Boton btnPosponer = {PIN_BTN_POSPONER, false, 0};

// ---------- Utilidades ----------
void publicar(const char* evento, const char* canal = "") {
  JsonDocument doc;
  doc["evento"] = evento;
  if (tomaId.length() > 0) {
    doc["id"] = tomaId;
    doc["med"] = tomaMed;
    doc["comp"] = tomaComp;
  }
  if (strlen(canal) > 0) doc["canal"] = canal;
  char buf[256];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(TOPIC_ESTADO, (const uint8_t*)buf, n, false);
  Serial.print("-> ");
  Serial.println(buf);
}

void silenciar() {
  noTone(PIN_BUZZER);
  tonoActivo = false;
  sonando = false;
}

void apagarTodo() {
  silenciar();
  for (int i = 0; i < 3; i++) digitalWrite(PIN_LED[i], LOW);
  servo.write(ANGULO_REPOSO);
}

void iniciarToma(const String& id, const String& med, int comp) {
  tomaId = id;
  tomaMed = med;
  tomaComp = constrain(comp, 1, 3);
  posponeHasta = 0;
  posposiciones = 0;
  sonando = false;
  tInicio = millis();
  enAlerta = true;
  servo.write(ANGULO_COMP[tomaComp - 1]);
  digitalWrite(PIN_LED[tomaComp - 1], HIGH);
  publicar("dispensado");
}

void cerrarToma(const char* evento, const char* canal) {
  publicar(evento, canal);  // publica antes de borrar el id
  apagarTodo();
  enAlerta = false;
  tomaId = "";
}

void posponer(const char* canal) {
  if (posposiciones >= MAX_POSPOSICIONES) {
    Serial.println("Sin posposiciones disponibles");
    return;
  }
  posposiciones++;
  posponeHasta = millis() + T_POSPONER_MS;
  silenciar();
  publicar("pospuesta", canal);
}

// ---------- MQTT ----------
void onMensaje(char* topic, byte* payload, unsigned int len) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) return;
  const char* accion = doc["accion"] | "";

  if (strcmp(accion, "dispensar") == 0) {
    if (enAlerta) cerrarToma("omitida", "esp32");  // la anterior queda omitida
    String id = doc["id"] | "";
    String med = doc["med"] | "";
    iniciarToma(id, med, doc["comp"] | 1);
  } else if (strcmp(accion, "confirmar") == 0) {
    if (enAlerta) cerrarToma("confirmada", "app_boton");
  } else if (strcmp(accion, "posponer") == 0) {
    if (enAlerta) posponer("app_boton");
  }
}

void asegurarMqtt() {
  if (mqtt.connected()) return;
  static unsigned long ultimo = 0;
  if (millis() - ultimo < 2000) return;
  ultimo = millis();
  String cid = "esp32-pastillero-" + String((uint32_t)esp_random(), HEX);
  Serial.print("Conectando MQTT... ");
  if (mqtt.connect(cid.c_str())) {
    Serial.println("ok");
    mqtt.subscribe(TOPIC_CMD);
    publicar("online");
  } else {
    Serial.print("fallo rc=");
    Serial.println(mqtt.state());
  }
}

// ---------- Botones y alerta ----------
bool flanco(Boton& b) {
  bool ahora = digitalRead(b.pin) == LOW;  // INPUT_PULLUP
  bool pulso = ahora && !b.previo && (millis() - b.ultimo > 250);
  if (pulso) b.ultimo = millis();
  b.previo = ahora;
  return pulso;
}

void revisarBotones() {
  if (flanco(btnConfirmar)) {
    if (enAlerta) cerrarToma("confirmada", "pulsador_fisico");
    else Serial.println("Confirmar: no hay toma pendiente");
  }
  if (flanco(btnPosponer)) {
    if (enAlerta) posponer("pulsador_fisico");
  }
}

void ponerTono(bool encender) {
  if (encender && !tonoActivo) {
    tone(PIN_BUZZER, 1000);
    tonoActivo = true;
  } else if (!encender && tonoActivo) {
    noTone(PIN_BUZZER);
    tonoActivo = false;
  }
}

void actualizarAlerta() {
  if (!enAlerta) return;
  unsigned long ahora = millis();

  if (posponeHasta != 0) {  // pospuesta: LED encendido, sin sonido
    if ((long)(ahora - posponeHasta) >= 0) {
      posponeHasta = 0;
      tInicio = ahora;  // reinicia el escalamiento
    }
    return;
  }

  unsigned long t = ahora - tInicio;
  if (t >= T_OMITIDA_MS) {
    cerrarToma("omitida", "esp32");
    return;
  }
  if (t >= T_SONIDO_MS) {
    if (!sonando) {
      sonando = true;
      publicar("sonando", "buzzer");
    }
    ponerTono(((ahora / 300) % 2) == 0);  // pitido intermitente continuo
  } else if (t < T_AVISO_INICIAL_MS) {
    ponerTono((t % 400) < 200);  // aviso inicial: 2 pitidos cortos
  } else {
    ponerTono(false);  // silencio hasta que toque escalar
  }
}

// ---------- Arduino ----------
void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) pinMode(PIN_LED[i], OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BTN_CONFIRMAR, INPUT_PULLUP);
  pinMode(PIN_BTN_POSPONER, INPUT_PULLUP);

  servo.attach(PIN_SERVO, 500, 2400);
  servo.write(ANGULO_REPOSO);

  Serial.print("WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.println(" conectado");

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMensaje);
  mqtt.setBufferSize(512);
}

void loop() {
  asegurarMqtt();
  mqtt.loop();
  revisarBotones();
  actualizarAlerta();
}
