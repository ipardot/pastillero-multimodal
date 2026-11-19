from datetime import datetime

import streamlit as st

import core

# Page config must be the first Streamlit command
st.set_page_config(page_title="Pastillero multimodal", page_icon="💊")

# Init database and open the MQTT connection (one per process)
try:
    core.init_db()
    core.client()
except Exception as e:
    st.error(f"Error al iniciar la app: {str(e)}")
    st.stop()


@st.fragment(run_every=1)
def reloj():
    # Simulated clock: every second compute the time and fire due doses
    try:
        now = core.tick()
        st.metric("Hora simulada", now.strftime("%H:%M:%S"))
        st.caption(f"Velocidad: 1 s real = {core.get_speed():g} s simulados")
        if core.conectado():
            st.caption("🟢 MQTT conectado")
        else:
            st.caption("🔴 MQTT sin conexión")
    except Exception as e:
        st.error(f"Error en el reloj: {str(e)}")


with st.sidebar:
    st.subheader("💊 Pastillero multimodal")
    st.caption(
        "Simula un pastillero conectado: la app decide cuándo toca cada toma, "
        "el ESP32 (Wokwi) avisa con servo, LED y buzzer, y el historial guarda "
        "cómo se confirmó cada toma."
    )
    reloj()

    # MQTT settings (must match wokwi/sketch.ino)
    with st.expander("Conexión MQTT"):
        cfg = core.mqtt_config()
        broker = st.text_input("Broker", cfg["broker"])
        port = st.number_input("Puerto", min_value=1, max_value=65535, value=cfg["port"])
        prefix = st.text_input("Prefijo de tópicos", cfg["prefix"])
        cid = st.text_input("Client ID", cfg["client_id"])
        if st.button("Aplicar conexión"):
            ok = False
            try:
                core.set_mqtt_config(broker, port, prefix, cid)
                ok = True
            except Exception as e:
                st.error(f"Error al guardar la conexión: {str(e)}")
            if ok:
                st.rerun()

    st.subheader("Panel de demo")
    velocidades = [1, 10, 60, 300]
    actual = core.get_speed()
    if actual not in velocidades:
        velocidades.append(actual)
    vel = st.selectbox(
        "Velocidad del reloj",
        velocidades,
        index=velocidades.index(actual),
        format_func=lambda v: f"x{v:g}",
    )
    if vel != actual:
        core.cambiar_velocidad(vel)
        st.rerun()

    t_ini = st.time_input("Fijar hora simulada", value=core.hora_sim().time(), step=60)
    if st.button("Fijar hora"):
        core.set_clock(datetime.combine(core.hora_sim().date(), t_ini), core.get_speed())
        st.rerun()

    receta = core.get_receta()
    if receta:
        sel = st.selectbox(
            "Toma a simular",
            receta,
            format_func=lambda t: f"{t['med']} ({t['hora']}, comp. {t['comp']})",
        )
        if st.button("Simular toma ahora"):
            try:
                if core.simular_toma(sel):
                    st.toast("Orden enviada al pastillero")
                else:
                    st.error("Sin conexión MQTT: no se envió la orden")
            except Exception as e:
                st.error(f"Error al enviar la orden: {str(e)}")

    if st.button("Reiniciar demo"):
        core.reiniciar_demo()
        st.rerun()

pg = st.navigation(
    [
        st.Page("dia_a_dia.py", title="Día a día", icon="💊", default=True),
        st.Page("configuracion.py", title="Configuración", icon="⚙️"),
        st.Page("historial.py", title="Historial", icon="📋"),
    ]
)
pg.run()
