import streamlit as st
from PIL import Image

import core
import estilos

estilos.aplicar()


@st.fragment(run_every=1)
def tablero():
    try:
        now = core.hora_sim()
        p = core.pendiente()
        guia = core.guia_de_carga()
        ult = core.ultimo_evento(p["toma_id"]) if p else None

        izq, der = st.columns([1, 1], vertical_alignment="center", gap="large")
        with izq:
            estilos.carrusel(
                guia,
                activo=p["comp"] if p else None,
                hora=now.strftime("%H:%M"),
                segundos=now.strftime(":%S"),
                alerta=(ult == "sonando"),
            )
        with der:
            if p:
                if ult == "sonando":
                    estilos.estado("Suena en el pastillero", f"Toma {p['med']} del compartimento {p['comp']} y confírmalo.", estilos.BAD)
                elif ult == "pospuesta":
                    estilos.estado("Pospuesta", f"Volverá a avisar para {p['med']} (compartimento {p['comp']}).", "#8A6D1F")
                else:
                    estilos.estado(f"Toca {p['med']}", f"Está en el compartimento {p['comp']}, justo bajo la abertura.", estilos.COMP[p["comp"]])
                st.write("")
                if st.button("Ya la tomé", type="primary", width="stretch"):
                    if core.comando_toma("confirmar"):
                        st.toast("Confirmación enviada al pastillero")
                    else:
                        st.error("Sin conexión MQTT: no se envió la confirmación")
                if st.button("Posponer", width="stretch"):
                    if core.comando_toma("posponer"):
                        st.toast("Posposición enviada")
                    else:
                        st.error("Sin conexión MQTT: no se envió la posposición")
            else:
                toma, due = core.proxima_toma(now)
                if toma:
                    estilos.estado(
                        "Todo al día",
                        f"Próxima toma: {toma['med']} a las {due:%H:%M}, compartimento {toma['comp']}.",
                        estilos.OK,
                    )
                else:
                    estilos.estado("Sin receta", "Agrega tus tomas en Configuración.")

        st.subheader("Hoy")
        estilos.linea_del_dia(core.estado_dia(now.date()), now)

        st.subheader("Últimos eventos")
        ev = core.eventos(solo_finales=False, limite=6)
        if ev:
            estilos.filas_eventos(ev)
        else:
            st.caption("Aún no hay eventos. Usa «Simular toma ahora» en el panel lateral.")
    except Exception as e:
        st.error(f"Error al mostrar el estado: {str(e)}")


tablero()

# Optional concept image: add pastillero.png to the repo root
try:
    image = Image.open("pastillero.png")
    with st.expander("Concepto del producto"):
        st.image(image, width=350, caption="Concepto ilustrativo (no es el prototipo real)")
except Exception:
    pass
