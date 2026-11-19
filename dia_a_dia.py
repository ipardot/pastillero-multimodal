import pandas as pd
import streamlit as st
from PIL import Image

import core

st.title("💊 Día a día")

# Optional header image: add pastillero.png to the repo root
try:
    image = Image.open("pastillero.png")
    st.image(image, width=350)
except Exception:
    pass


@st.fragment(run_every=1)
def estado():
    try:
        now = core.hora_sim()
        p = core.pendiente()

        if p:
            ult = core.ultimo_evento(p["toma_id"])
            st.warning(f"🔔 **Toca: {p['med']}** — compartimento {p['comp']}")
            if ult == "sonando":
                st.error("🔊 El pastillero está sonando. Confirma o pospón.")
            elif ult == "pospuesta":
                st.info("⏰ Pospuesta: volverá a avisar en unos segundos.")
            c1, c2 = st.columns(2)
            if c1.button("✅ Ya la tomé", type="primary"):
                if core.comando_toma("confirmar"):
                    st.toast("Confirmación enviada al pastillero")
                else:
                    st.error("Sin conexión MQTT: no se envió la confirmación")
            if c2.button("⏰ Posponer"):
                if core.comando_toma("posponer"):
                    st.toast("Posposición enviada")
                else:
                    st.error("Sin conexión MQTT: no se envió la posposición")
        else:
            st.success("Sin tomas pendientes")
            toma, due = core.proxima_toma(now)
            if toma:
                st.metric(
                    "Próxima toma",
                    f"{toma['med']} — {due:%H:%M}",
                    f"compartimento {toma['comp']}",
                    delta_color="off",
                )
            else:
                st.info("No hay receta configurada. Ve a Configuración.")

        st.subheader("Últimos eventos")
        ev = core.eventos(solo_finales=False, limite=6)
        if ev:
            df = pd.DataFrame(ev)[["hora_sim", "med", "evento", "canal"]]
            st.dataframe(df, hide_index=True)
        else:
            st.caption("Aún no hay eventos.")
    except Exception as e:
        st.error(f"Error al mostrar el estado: {str(e)}")


estado()
