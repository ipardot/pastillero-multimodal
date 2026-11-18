# 💊 Pastillero multimodal

Proyecto final de **Interfaces Multimodales** (EAFIT) — entrega 22 de noviembre de 2026.

Pastillero para adultos con receta fija (medicamentos o vitaminas) con dos ambientes conectados por MQTT:

- **Digital:** app Streamlit multipágina (`app/`).
- **Físico:** ESP32 simulado en [Wokwi](https://wokwi.com) con firmware Arduino C++ (`wokwi/`).

> **Prototipo de baja fidelidad.** Registra tomas *confirmadas por el usuario*, no *verificadas*. No valida dosis ni interacciones y **no es un dispositivo médico**.

## Decisión de diseño: el reloj vive en la app

El ESP32 **no conoce la hora real**. Streamlit decide cuándo toca cada toma y envía la orden `dispensar`. El ESP32 solo reacciona y mide su escalamiento (buzzer, omisión) con `millis()` en tiempo real. Para la demo, la app tiene un **reloj simulado acelerado** (x1, x60, x300, x600).

```
 Streamlit (reloj + receta + historial)  ──cmd──▶  broker.hivemq.com  ──▶  ESP32 (servo, LEDs, buzzer, pulsadores)
                SQLite  ◀──estado──────────────────────────────────────────┘
```

## Estructura

```
├── README.md
├── .gitignore
├── wokwi/
│   ├── sketch.ino        firmware (máquina de estados con millis())
│   ├── diagram.json      circuito
│   └── libraries.txt     PubSubClient, ArduinoJson, ESP32Servo
├── app/
│   ├── app.py            entrada: panel lateral (reloj, MQTT) + navegación
│   ├── core.py           SQLite, reloj simulado, cliente MQTT
│   ├── requirements.txt
│   └── views/
│       ├── dia_a_dia.py
│       ├── configuracion.py
│       └── historial.py
└── tests/                pruebas de lógica y smoke tests (pytest)
```

## 1. Correr el ESP32 en Wokwi

1. Entra a https://wokwi.com → **New Project** → **ESP32**.
2. Reemplaza el contenido de `sketch.ino` y `diagram.json` por los de la carpeta `wokwi/`.
3. En el panel de archivos crea `libraries.txt` (o usa **Library Manager**) con: `PubSubClient`, `ArduinoJson`, `ESP32Servo`.
4. Si cambias el prefijo de tópicos, edita `PREFIJO` al inicio de `sketch.ino`.
5. Pulsa ▶. En el monitor serie deberías ver `[mqtt] conectando como pastillero-esp32-…` y luego `[pub] {"evento":"online",…}`.

## 2. Correr la app

```bash
cd app
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Opcional: prefijo único (debe coincidir con PREFIJO del firmware)
# Windows PowerShell: $env:PASTILLERO_PREFIX="eafit/julian/pastillero"
# macOS/Linux:        export PASTILLERO_PREFIX="eafit/julian/pastillero"
streamlit run app.py
```

Variables de entorno opcionales: `PASTILLERO_PREFIX` (por defecto `eafit/julian/pastillero`), `PASTILLERO_DB` (ruta de SQLite, por defecto `app/pastillero.db`), `PASTILLERO_BROKER` y `PASTILLERO_PORT`.

**La app debe estar abierta** (una pestaña del navegador) para que el reloj avance y dispare tomas.

### Pruebas

```bash
pip install -r app/requirements.txt -r tests/requirements.txt
python -m pytest tests/ -v
```

## Tabla de pines (ESP32 DevKit C v4)

| Componente | GPIO | Notas |
|---|---|---|
| Servo (PWM) | 18 | V+ a 5V, GND a GND. Reposo 0°, comp. 1/2/3 = 45°/90°/135° |
| LED compartimento 1 | 25 | Con resistencia de 220 Ω a GND |
| LED compartimento 2 | 26 | Con resistencia de 220 Ω a GND |
| LED compartimento 3 | 27 | Con resistencia de 220 Ω a GND |
| Buzzer | 14 | Pin "2" = señal, pin "1" = GND |
| Pulsador **Confirmar** | 32 | `INPUT_PULLUP`, otro terminal a GND |
| Pulsador **Posponer** | 33 | `INPUT_PULLUP`, otro terminal a GND |

WiFi simulado: SSID `Wokwi-GUEST`, sin contraseña, canal 6.

### Nombres de pines usados en `diagram.json` (verificar)

No pude abrir Wokwi para validar el diagrama, así que estos nombres son los que conozco de la documentación de Wokwi y **deben comprobarse al cargarlo**:

- ESP32: `esp:18`, `esp:25`, `esp:26`, `esp:27`, `esp:14`, `esp:32`, `esp:33`, `esp:5V`, `esp:GND.1`, `esp:GND.2`, `esp:TX`, `esp:RX`.
  Duda: no estoy seguro de qué numeración (`GND.1`, `GND.2`, `GND.3`) existe en `board-esp32-devkit-c-v4`. Si un cable no aparece, reconéctalo a cualquier GND en el editor.
- Servo: `PWM`, `V+`, `GND`. LED: `A` (ánodo), `C` (cátodo). Resistencia: `1`, `2`. Buzzer: `1` (GND), `2` (señal). Pulsador: `1.l`, `2.l`.
- Las posiciones (`top`/`left`) son aproximadas: puede que haya que mover piezas para que se vea ordenado.

## Contrato MQTT

Broker público `broker.hivemq.com:1883`. El prefijo debe ser **único** (el broker es compartido) e igual en firmware y app.

**`{prefijo}/cmd`** (app → ESP32)

```json
{"accion":"dispensar","id":"2026-11-18T08:00-r1","med":"Vitamina D","comp":1}
{"accion":"confirmar","id":"2026-11-18T08:00-r1"}
{"accion":"posponer","id":"2026-11-18T08:00-r1"}
```

**`{prefijo}/estado`** (ESP32 → app)

```json
{"evento":"dispensado","id":"..","med":"..","comp":1,"canal":"esp32"}
```

`evento ∈ {online, dispensado, sonando, pospuesta, confirmada, omitida}`, `canal ∈ {pulsador_fisico, app_boton, buzzer, esp32}`. `online` no lleva id.
Los comandos se publican con QoS 0 y **solo si el cliente está conectado**, para no encolar órdenes viejas.

## Comportamiento

**ESP32** (constantes al inicio de `sketch.ino`):

1. `dispensar`: si había una toma activa, publica `omitida` para la anterior; mueve el servo, enciende el LED, publica `dispensado` e inicia el cronómetro.
2. 10 s sin respuesta → buzzer intermitente (1000 Hz, alterna cada 300 ms) y publica `sonando` una vez. 25 s → publica `omitida` (canal `esp32`), apaga todo y vuelve el servo a reposo.
3. Confirmar (pulsador o app) → `confirmada` con canal `pulsador_fisico` o `app_boton`. Sin toma activa se ignora.
4. Posponer (máx. 1 vez por toma) → silencia el buzzer 8 s con el LED encendido, publica `pospuesta` y al terminar reinicia el cronómetro.
5. Reconexión no bloqueante cada 2 s, client id aleatorio, publica `online` al conectar. Debounce de 250 ms.
6. Siempre publica el evento **antes** de borrar el id de la toma.

**App:**

- Reloj simulado: `hora_sim = sim_start + (ahora_real − sim_anchor) × velocidad`. Cada segundo `tick()` procesa la ventana `(sim_last, ahora]` y dispara las tomas cuya hora cae dentro, con `INSERT OR IGNORE` en `disparos` para no duplicar. Cambiar la velocidad reancla el reloj sin saltos.
- Si la app estuvo cerrada más de 30 s reales, la ventana avanza sin disparar lo atrasado (evita una ráfaga de tomas viejas al reabrir).
- Una toma está pendiente si su último `enviada` no tiene `confirmada` ni `omitida`. Los botones de la app solo publican el comando; el estado real lo registra la respuesta del ESP32.

## Guion de demo (≈5 min)

1. Abre Wokwi y arranca la simulación; verifica `online` en el monitor serie y en el panel lateral de la app ("Último 'online' del ESP32").
2. En **Configuración**, muestra la receta de ejemplo (Vitamina D 08:00, Omega 3 12:00, Vitamina C 20:00) y agrega un medicamento.
3. En el panel lateral, **Fijar hora** en 07:59 y velocidad **x60**. A los ~1 s reales llega la orden: servo a 45°, LED 1 encendido.
4. En **Día a día**, aparece la toma pendiente. Espera 10 s: suena el buzzer y la app muestra "sonando".
5. Pulsa **Posponer** en Wokwi (canal físico): el buzzer calla 8 s y vuelve.
6. Pulsa **Ya la tomé** en la app (canal digital): el ESP32 apaga todo y la app registra `confirmada / app_boton`.
7. Usa **Simular toma ahora** y no respondas: a los 25 s queda `omitida`.
8. En **Historial**, muestra métricas, el filtro y descarga el CSV.

## Límites y trabajo futuro

- **La app debe estar abierta** para que el reloj dispare tomas; si se cierra, no hay recordatorios.
- **El ESP32 depende de la app para saber la hora**: sin app o sin broker no dispensa.
- El registro es **"confirmado", no "verificado"**: el sistema no comprueba que la pastilla se haya ingerido.
- Si el ESP32 está apagado pero el broker sí está conectado, la toma queda "pendiente" hasta la siguiente orden o "Reiniciar demo".
- Broker público sin autenticación ni cifrado: cualquiera que conozca el prefijo puede leer o publicar.
- Trabajo futuro: base de datos externa, reloj RTC/NTP en el dispositivo, interacción por voz, asistente con LLM, notificaciones a cuidadores, sensor de peso o de apertura para verificar la toma.
