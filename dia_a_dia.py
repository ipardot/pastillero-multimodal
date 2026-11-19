import streamlit as st
from PIL import Image

import core
import estilos

estilos.aplicar()
st.title("💊 Día a día")


@st.fragment(run_every=1)
def estado():
    try:
        now = core.hora_sim()
        p = core.pendiente()
        guia = core.guia_de_carga()

        if p:
            ult = core.ultimo_evento(p["toma_id"])
            if ult == "sonando":
                estilos.hero(
                    "Atención", f"Toma {p['med']} ahora",
                    f"El pastillero está sonando · compartimento {p['comp']}", "alerta", pulso=True,
                )
            elif ult == "pospuesta":
                estilos.hero(
                    "Pospuesta", f"{p['med']}",
                    f"Volverá a avisar en unos segundos · compartimento {p['comp']}", "aviso",
                )
            else:
                estilos.hero(
                    "Es hora de tu toma", f"{p['med']}",
                    f"Toma la pastilla del compartimento {p['comp']}", "aviso", pulso=True,
                )
            c1, c2 = st.columns(2)
            if c1.button("✅ Ya la tomé", type="primary", width="stretch"):
                if core.comando_toma("confirmar"):
                    st.toast("Confirmación enviada al pastillero")
                else:
                    st.error("Sin conexión MQTT: no se envió la confirmación")
            if c2.button("⏰ Posponer", width="stretch"):
                if core.comando_toma("posponer"):
                    st.toast("Posposición enviada")
                else:
                    st.error("Sin conexión MQTT: no se envió la posposición")
            estilos.compartimentos(guia, activo=p["comp"], tono_activo="alerta" if ult == "sonando" else "aviso")
        else:
            toma, due = core.proxima_toma(now)
            if toma:
                estilos.hero(
                    "Todo al día · próxima toma", f"{toma['med']} a las {due:%H:%M}",
                    f"Compartimento {toma['comp']}", "ok",
                )
            else:
                estilos.hero("Sin receta", "No hay tomas configuradas", "Ve a Configuración para agregarlas.", "info")
            estilos.compartimentos(guia, activo=toma["comp"] if toma else None, tono_activo="ok")

        st.subheader("Últimos eventos")
        ev = core.eventos(solo_finales=False, limite=6)
        if ev:
            estilos.filas_eventos(ev)
        else:
            st.caption("Aún no hay eventos. Usa «Simular toma ahora» en el panel lateral.")
    except Exception as e:
        st.error(f"Error al mostrar el estado: {str(e)}")


estado()

# Optional concept image: add pastillero.png to the repo root
try:
    image = Image.open("pastillero.png")
    with st.expander("Concepto del producto"):
        st.image(image, width=350, caption="Concepto ilustrativo (no es el prototipo real)")
except Exception:
    pass
