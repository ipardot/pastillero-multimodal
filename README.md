# Pastillero multimodal (Wokwi + Streamlit)

Prototipo de baja fidelidad. Dos ambientes conectados por MQTT: la app (Streamlit) decide
cuándo toca cada toma y el ESP32 simulado en Wokwi avisa con servo, LED y buzzer.

## Estructura
- `app.py`, `dia_a_dia.py`, `configuracion.py`, `historial.py`: la app (3 páginas).
- `core.py`: base de datos, reloj simulado y MQTT (compartido por las páginas).
- `wokwi/`: `sketch.ino`, `diagram.json`, `libraries.txt` (pegar en wokwi.com).
- `test_core.py`: pruebas de la lógica con un MQTT falso.

## 1. Wokwi
1. Proyecto ESP32 (Arduino) en wokwi.com. Pega los 3 archivos de `wokwi/`.
2. En `sketch.ino` cambia el prefijo de tópicos por uno único tuyo (`TOPIC_CMD` y `TOPIC_ESTADO`).
3. Play. El monitor serie debe mostrar `Conectando MQTT... ok`.

| Componente | Pin ESP32 |
|---|---|
| Servo (PWM) | 18 |
| LED comp. 1 / 2 / 3 | 25 / 26 / 27 |
| Buzzer | 14 |
| Pulsador confirmar / posponer | 32 / 33 (otro lado a GND) |

## 2. App en tu computador (Python 3.11 o superior)
```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
En la sidebar, **Conexión MQTT**: pon el mismo prefijo que en `sketch.ino` y pulsa "Aplicar conexión".

Pruebas de lógica: `python test_core.py`

## 3. Despliegue en Streamlit Community Cloud
1. Sube este repo a GitHub (público).
2. En share.streamlit.io: New app, elige el repo, rama `main`, archivo principal `app.py`.
3. En Advanced settings elige Python 3.11 o 3.12.
4. Entra a la app y revisa en la sidebar el prefijo MQTT.

La base de datos es temporal: se borra cuando la app reinicia o se duerme por inactividad.
Abre la app unos minutos antes de la sustentación.

## 4. Guion de demo (~4 min)
1. Configuración: muestra la receta y la guía de carga.
2. Sidebar: velocidad **x60** y "Fijar hora" en 07:58.
3. A las 08:00 simuladas: dos pitidos, gira el servo y se enciende el LED 1. Pulsa **Confirmar** en Wokwi.
4. "Simular toma ahora" con otra toma y no hagas nada: a los 10 s suena el buzzer y a los 25 s queda omitida.
5. Otra toma: **Posponer**, y luego confirma con el botón de la app.
6. Historial: confirmadas, pospuestas y omitidas, con su canal.

No uses velocidades muy altas con tomas separadas pocas horas: a x600 dos tomas 4 h aparte llegan con 24 s de diferencia y la primera se omite.

## Decisiones y límites
- Estado en SQLite y no en `st.session_state`: el callback de MQTT corre en otro hilo.
- El cliente MQTT es único por proceso y se reconstruye al cambiar la configuración.
- La app debe estar abierta para que el reloj dispare tomas; el ESP32 depende de la app para saber la hora.
- Se registra toma *confirmada*, no verificada. No valida dosis ni interacciones. No es un dispositivo médico.
- Un compartimento = un medicamento, y una toma a la vez. El sistema no puede verificar qué hay dentro de cada compartimento.
- Los tiempos de escalamiento del ESP32 (10 s sonido, 25 s omitida, 8 s posponer) son tiempo real y de demo.
