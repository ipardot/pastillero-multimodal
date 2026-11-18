"""Pastillero multimodal - app Streamlit (ambiente digital).

Ejecutar desde la carpeta app/:  streamlit run app.py
"""

from datetime import datetime
from pathlib import Path

import streamlit as st

import core

BASE = Path(__file__).resolve().parent

st.set_page_config(page_title="Pastillero", page_icon="💊", layout="wide")
core.init_db()


client = core.get_client()  # un solo cliente MQTT (st.cache_resource)


@st.fragment(run_every=1)
def panel_reloj():
    core.tick(client)
    ahora = core.hora_simulada()
    st.metric("Hora simulada", ahora.strftime("%H:%M:%S"), help=ahora.strftime("%Y-%m-%d"))
    st.caption(f"Velocidad x{core.velocidad()}")
    if client.is_connected():
        st.success("MQTT conectado", icon="🟢")
    else:
        st.error("MQTT desconectado", icon="🔴")
    online = core.ultimo_online()
    st.caption(f"Último 'online' del ESP32: {online or 'nunca'}")


def cambiar_velocidad():
    core.set_velocidad(st.session_state["vel"])


with st.sidebar:
    st.header("💊 Pastillero")
    panel_reloj()
    st.caption(f"Tópicos: `{core.PREFIX}/…`")

    st.divider()
    st.subheader("Reloj de la demo")
    vels = list(core.VELOCIDADES)
    actual = core.velocidad()
    st.selectbox(
        "Velocidad", vels, index=vels.index(actual) if actual in vels else 0,
        format_func=lambda v: f"x{v}", key="vel", on_change=cambiar_velocidad,
    )

    nueva_hora = st.time_input("Fijar hora simulada", value=core.hora_simulada().time().replace(second=0, microsecond=0), step=60)
    if st.button("Fijar hora"):
        hoy = core.hora_simulada().date()
        core.fijar_hora(datetime.combine(hoy, nueva_hora))
        st.rerun()

    receta = core.listar_receta()
    if receta:
        elegido = st.selectbox(
            "Medicamento a simular", receta,
            format_func=lambda r: f"{r['med']} (comp {r['comp']})",
        )
        if st.button("Simular toma ahora"):
            core.simular_toma_ahora(client, elegido["id"])
            if not client.is_connected():
                st.warning("Sin conexión MQTT: la orden no se envió.")

    if st.button("Reiniciar demo", type="secondary"):
        core.reiniciar_demo()
        st.toast("Eventos y disparos borrados")

pg = st.navigation([
    st.Page(str(BASE / "views" / "dia_a_dia.py"), title="Día a día", icon="📅", default=True),
    st.Page(str(BASE / "views" / "configuracion.py"), title="Configuración", icon="⚙️"),
    st.Page(str(BASE / "views" / "historial.py"), title="Historial", icon="📜"),
])
pg.run()
