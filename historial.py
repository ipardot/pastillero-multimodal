import pandas as pd
import streamlit as st

import core

st.title("📋 Historial de tomas")
st.caption(
    "Las tomas se registran como **confirmadas por el usuario** (pulsador o botón). "
    "El sistema no verifica que la pastilla se haya ingerido."
)


@st.fragment(run_every=2)
def tabla():
    try:
        ev = core.eventos(solo_finales=True)
        if not ev:
            st.info("Aún no hay registros. Simula una toma desde el panel lateral.")
            return
        df = pd.DataFrame(ev)
        c1, c2, c3 = st.columns(3)
        c1.metric("Confirmadas", int((df["evento"] == "confirmada").sum()))
        c2.metric("Pospuestas", int((df["evento"] == "pospuesta").sum()))
        c3.metric("Omitidas", int((df["evento"] == "omitida").sum()))

        filtro = st.multiselect(
            "Filtrar por estado",
            ["confirmada", "pospuesta", "omitida"],
            default=["confirmada", "pospuesta", "omitida"],
        )
        vista = df[df["evento"].isin(filtro)][["hora_sim", "med", "comp", "evento", "canal"]]
        vista = vista.rename(
            columns={
                "hora_sim": "Hora (simulada)",
                "med": "Medicamento",
                "comp": "Comp.",
                "evento": "Estado",
                "canal": "Canal",
            }
        )
        st.dataframe(vista, hide_index=True)
        st.download_button(
            "Descargar CSV",
            vista.to_csv(index=False).encode("utf-8"),
            file_name="historial_pastillero.csv",
            mime="text/csv",
        )
    except Exception as e:
        st.error(f"Error al cargar el historial: {str(e)}")


tabla()
