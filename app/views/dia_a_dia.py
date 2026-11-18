import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import core  # noqa: E402

core.init_db()
client = core.get_client()

st.title("📅 Día a día")

ETIQUETAS = {
    "enviada": "Orden enviada",
    "sin_conexion": "No enviada (sin MQTT)",
    "dispensado": "Dispensada",
    "sonando": "Sonando",
    "pospuesta": "Pospuesta",
    "confirmada": "Confirmada",
    "omitida": "Omitida",
    "online": "ESP32 en línea",
}


def _enviar(accion: str, toma_id: str):
    if not core.publicar(client, {"accion": accion, "id": toma_id}):
        st.warning("Sin conexión MQTT: no se pudo enviar al pastillero.")
    else:
        st.toast("Enviado al pastillero. Esperando respuesta del ESP32…")


@st.fragment(run_every=1)
def estado_actual():
    toma = core.toma_pendiente()
    if toma:
        st.warning(f"**Toma pendiente:** {toma['med']} — compartimento {toma['comp']}", icon="💊")
        if toma["estado"] == "sonando":
            st.error("🔔 El pastillero está sonando.")
        elif toma["estado"] == "pospuesta":
            st.info("⏸️ Toma pospuesta. Volverá a avisar en unos segundos.")
        elif toma["estado"] == "dispensado":
            st.info("El compartimento está abierto.")
        else:
            st.caption("Esperando confirmación del ESP32…")
        c1, c2 = st.columns(2)
        if c1.button("✅ Ya la tomé", key=f"conf-{toma['id']}", type="primary"):
            _enviar("confirmar", toma["id"])
        if c2.button("⏰ Posponer", key=f"posp-{toma['id']}"):
            _enviar("posponer", toma["id"])
    else:
        st.success("Sin tomas pendientes", icon="✅")
        prox = core.proxima_toma()
        if prox:
            st.write(
                f"Próxima toma: **{prox['med']}** a las **{prox['hora']}** "
                f"(compartimento {prox['comp']})."
            )
        else:
            st.write("No hay medicamentos en la receta. Agrégalos en Configuración.")

    st.subheader("Últimos eventos")
    eventos = core.ultimos_eventos(6)
    if eventos:
        df = pd.DataFrame(eventos)
        df["evento"] = df["evento"].map(lambda e: ETIQUETAS.get(e, e))
        df.columns = ["Hora simulada", "Medicamento", "Comp.", "Evento", "Canal"]
        st.dataframe(df, hide_index=True)
    else:
        st.caption("Aún no hay eventos.")


estado_actual()
