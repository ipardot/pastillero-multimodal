// Pastillero multimodal - firmware ESP32 (Wokwi)
// Proyecto final Interfaces Multimodales - EAFIT
//
// El ESP32 NO conoce la hora real: la app Streamlit decide cuándo toca cada
// toma y envía "dispensar" por MQTT. Aquí solo se reacciona y se mide el
// escalamiento con millis(). Prototipo de baja fidelidad: no es un dispositivo médico.

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// ---------------- Configuración ----------------
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
const int   WIFI_CANAL = 6;

const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;
// Debe coincidir con PASTILLERO_PREFIX en la app y ser único (broker compartido).
const char* PREFIJO = "eafit/julian/pastillero";

// Tiempos de escalamiento (milisegundos, tiempo real)
const unsigned long T_SONAR_MS      = 10000;  // sin respuesta -> buzzer
const unsigned long T_OMITIR_MS     = 25000;  // sin respuesta -> omitida
const unsigned long T_POSPONER_MS   = 8000;   // silencio al posponer
const unsigned long BEEP_CICLO_MS   = 300;    // ciclo del buzzer intermitente
const unsigned int  BEEP_FREQ_HZ    = 1000;
const unsigned long DEBOUNCE_MS     = 250;
const unsigned long REINTENTO_MS    = 2000;   // reconexión WiFi/MQTT

// Pines
const int PIN_SERVO     = 18;
const int PIN_LED[3]    = {25, 26, 27};
const int PIN_BUZZER    = 14;
const int PIN_CONFIRMAR = 32;
const int PIN_POSPONER  = 33;

// Ángulos del servo
const int ANG_REPOSO  = 0;
const int ANG_COMP[3] = {45, 90, 135};

// ---------------- Estado ----------------
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Servo servo;

String topicCmd;
String topicEstado;

bool   activa = false;           // hay una toma en curso
String tomaId = "";
String tomaMed = "";
int    tomaComp = 0;
unsigned long t0 = 0;            // inicio del cronómetro de escalamiento
bool   sonando = false;          // buzzer en fase intermitente
bool   sonandoPublicado = false;
bool   pospuestaUsada = false;   // máximo 1 posposición por toma
bool   enPosposicion = false;
unsigned long tPosp = 0;

bool   beepOn = false;
unsigned long tBeep = 0;

unsigned long tUltimoIntento = 0;

struct Boton {
  int pin;
  int ultimo;           // última lectura estable
  unsigned long tCambio;
};
Boton btnConfirmar = {PIN_CONFIRMAR, HIGH, 0};
Boton btnPosponer  = {PIN_POSPONER,  HIGH, 0};

// ---------------- Utilidades ----------------
void publicarEvento(const char* evento, const char* canal, bool conToma) {
  if (!mqtt.connected()) return;
  JsonDocument doc;
  doc["evento"] = evento;
  if (conToma) {
    doc["id"] = tomaId;
    doc["med"] = tomaMed;
    doc["comp"] = tomaComp;
  }
  doc["canal"] = canal;
  char buf[256];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(topicEstado.c_str(), (const uint8_t*)buf, n, false);
  Serial.print("[pub] ");
  Serial.println(buf);
}

void buzzerOff() {
  noTone(PIN_BUZZER);
  beepOn = false;
}

void apagarTodo() {
  buzzerOff();
  for (int i = 0; i < 3; i++) digitalWrite(PIN_LED[i], LOW);
  servo.write(ANG_REPOSO);
}

// Regla: publicar SIEMPRE el evento antes de borrar el id de la toma.
void cerrarToma(const char* evento, const char* canal) {
  publicarEvento(evento, canal, true);
  apagarTodo();
  activa = false;
  tomaId = "";
  tomaMed = "";
  tomaComp = 0;
  sonando = false;
  sonandoPublicado = false;
  enPosposicion = false;
  pospuestaUsada = false;
}

// ---------------- Acciones ----------------
void dispensar(const String& id, const String& med, int comp) {
  if (comp < 1 || comp > 3) {
    Serial.println("[cmd] compartimento inválido, ignorado");
    return;
  }
  if (activa) {
    cerrarToma("omitida", "esp32");  // la nueva orden reemplaza a la anterior
  }
  tomaId = id;
  tomaMed = med;
  tomaComp = comp;
  activa = true;
  sonando = false;
  sonandoPublicado = false;
  pospuestaUsada = false;
  enPosposicion = false;
  servo.write(ANG_COMP[comp - 1]);
  digitalWrite(PIN_LED[comp - 1], HIGH);
  publicarEvento("dispensado", "esp32", true);
  t0 = millis();
}

void confirmar(const char* canal) {
  if (!activa) return;
  cerrarToma("confirmada", canal);
}

void posponer(const char* canal) {
  if (!activa || pospuestaUsada) return;
  pospuestaUsada = true;
  enPosposicion = true;
  tPosp = millis();
  sonando = false;
  buzzerOff();                       // LED se mantiene encendido
  publicarEvento("pospuesta", canal, true);
}

// ---------------- MQTT ----------------
void onMensaje(char* topic, byte* payload, unsigned int length) {
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.println("[cmd] JSON inválido");
    return;
  }
  const char* accion = doc["accion"] | "";
  String id = doc["id"] | "";
  Serial.print("[cmd] ");
  Serial.println(accion);

  if (strcmp(accion, "dispensar") == 0) {
    String med = doc["med"] | "";
    int comp = doc["comp"] | 0;
    dispensar(id, med, comp);
  } else if (strcmp(accion, "confirmar") == 0) {
    if (activa && id == tomaId) confirmar("app_boton");
  } else if (strcmp(accion, "posponer") == 0) {
    if (activa && id == tomaId) posponer("app_boton");
  }
}

void mantenerConexion() {
  unsigned long ahora = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (ahora - tUltimoIntento >= REINTENTO_MS) {
      tUltimoIntento = ahora;
      Serial.println("[wifi] reintentando...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CANAL);
    }
    return;
  }
  if (!mqtt.connected()) {
    if (ahora - tUltimoIntento >= REINTENTO_MS) {
      tUltimoIntento = ahora;
      String cid = "pastillero-esp32-" + String((uint32_t)esp_random(), HEX);
      Serial.print("[mqtt] conectando como ");
      Serial.println(cid);
      if (mqtt.connect(cid.c_str())) {
        mqtt.subscribe(topicCmd.c_str());
        publicarEvento("online", "esp32", false);
      } else {
        Serial.print("[mqtt] fallo rc=");
        Serial.println(mqtt.state());
      }
    }
    return;
  }
  mqtt.loop();
}

// ---------------- Pulsadores ----------------
// Devuelve true en el flanco de bajada (pulsado), con debounce.
bool flancoPulsado(Boton& b) {
  int lectura = digitalRead(b.pin);
  unsigned long ahora = millis();
  if (lectura != b.ultimo && ahora - b.tCambio >= DEBOUNCE_MS) {
    b.tCambio = ahora;
    b.ultimo = lectura;
    return lectura == LOW;
  }
  return false;
}

// ---------------- Escalamiento ----------------
void actualizarEscalamiento() {
  if (!activa) return;
  unsigned long ahora = millis();

  if (enPosposicion) {
    if (ahora - tPosp >= T_POSPONER_MS) {
      enPosposicion = false;
      t0 = ahora;                    // reinicia el cronómetro
      sonandoPublicado = false;
    }
    return;
  }

  unsigned long dt = ahora - t0;
  if (dt >= T_OMITIR_MS) {
    cerrarToma("omitida", "esp32");
    return;
  }
  if (dt >= T_SONAR_MS) {
    if (!sonando) {
      sonando = true;
      tBeep = ahora;
      beepOn = true;
      tone(PIN_BUZZER, BEEP_FREQ_HZ);
    }
    if (!sonandoPublicado) {
      sonandoPublicado = true;
      publicarEvento("sonando", "buzzer", true);
    }
    if (ahora - tBeep >= BEEP_CICLO_MS) {
      tBeep = ahora;
      beepOn = !beepOn;
      if (beepOn) tone(PIN_BUZZER, BEEP_FREQ_HZ);
      else noTone(PIN_BUZZER);
    }
  }
}

// ---------------- Setup / loop ----------------
void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 3; i++) {
    pinMode(PIN_LED[i], OUTPUT);
    digitalWrite(PIN_LED[i], LOW);
  }
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_CONFIRMAR, INPUT_PULLUP);
  pinMode(PIN_POSPONER, INPUT_PULLUP);

  servo.setPeriodHertz(50);
  servo.attach(PIN_SERVO, 500, 2400);
  servo.write(ANG_REPOSO);

  topicCmd = String(PREFIJO) + "/cmd";
  topicEstado = String(PREFIJO) + "/estado";

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMensaje);
  mqtt.setBufferSize(512);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS, WIFI_CANAL);
  tUltimoIntento = millis();
  Serial.println("Pastillero iniciado");
}

void loop() {
  mantenerConexion();
  if (flancoPulsado(btnConfirmar)) confirmar("pulsador_fisico");
  if (flancoPulsado(btnPosponer)) posponer("pulsador_fisico");
  actualizarEscalamiento();
}
