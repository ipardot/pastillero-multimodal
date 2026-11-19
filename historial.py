import pandas as pd
import streamlit as st

import core
import estilos

estilos.aplicar()
st.title("📋 Historial de tomas")
st.info(
    "Las tomas se registran como **confirmadas por el usuario** (pulsador o botón). "
    "El sistema no verifica que la pastilla se haya ingerido."
)

ETIQUETA = {k: f"{v[0]} {v[1]}" for k, v in estilos.ESTADOS.items()}


@st.fragment(run_every=2)
def tabla():
    try:
        ev = core.eventos(solo_finales=True)
        if not ev:
            st.info("Aún no hay registros. Simula una toma desde el panel lateral.")
            return
        df = pd.DataFrame(ev)
        estilos.estadisticas(
            int((df["evento"] == "confirmada").sum()),
            int((df["evento"] == "pospuesta").sum()),
            int((df["evento"] == "omitida").sum()),
        )

        filtro = st.pills(
            "Filtrar por estado",
            ["confirmada", "pospuesta", "omitida"],
            default=["confirmada", "pospuesta", "omitida"],
            selection_mode="multi",
            format_func=lambda e: ETIQUETA[e],
        )
        vista = df[df["evento"].isin(filtro or [])][["hora_sim", "med", "comp", "evento", "canal"]].copy()
        vista["evento"] = vista["evento"].map(ETIQUETA)
        vista["canal"] = vista["canal"].map(estilos.CANALES).fillna("—")
        vista = vista.rename(
            columns={
                "hora_sim": "Hora (simulada)",
                "med": "Medicamento",
                "comp": "Comp.",
                "evento": "Estado",
                "canal": "Canal",
            }
        )
        st.dataframe(vista, hide_index=True, width="stretch")
        st.download_button(
            "⬇️ Descargar CSV para el doctor",
            vista.to_csv(index=False).encode("utf-8"),
            file_name="historial_pastillero.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.error(f"Error al cargar el historial: {str(e)}")


tabla()
