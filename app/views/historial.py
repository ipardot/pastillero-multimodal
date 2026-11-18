import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import core  # noqa: E402

core.init_db()

st.title("📜 Historial de tomas")
st.info("Las tomas se registran como confirmadas por el usuario; el sistema no verifica que se haya ingerido")

ESTADOS = {"confirmada": "Confirmada", "pospuesta": "Pospuesta", "omitida": "Omitida"}

filas = core.historial()
df = pd.DataFrame(filas, columns=["hora_sim", "med", "comp", "evento", "canal"])

c1, c2, c3 = st.columns(3)
c1.metric("Confirmadas", int((df["evento"] == "confirmada").sum()))
c2.metric("Pospuestas", int((df["evento"] == "pospuesta").sum()))
c3.metric("Omitidas", int((df["evento"] == "omitida").sum()))

elegidos = st.multiselect(
    "Filtrar por estado", list(ESTADOS), default=list(ESTADOS), format_func=ESTADOS.get
)
df = df[df["evento"].isin(elegidos)].copy()
df["evento"] = df["evento"].map(ESTADOS)
df.columns = ["Hora simulada", "Medicamento", "Comp.", "Estado", "Canal"]

if df.empty:
    st.caption("No hay registros con ese filtro.")
else:
    st.dataframe(df, hide_index=True)

st.download_button(
    "Descargar CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="historial_pastillero.csv",
    mime="text/csv",
)
