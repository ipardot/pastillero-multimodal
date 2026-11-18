import sys
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

import core  # noqa: E402

core.init_db()

st.title("⚙️ Configuración de la receta")

with st.form("nueva_toma", clear_on_submit=True):
    med = st.text_input("Medicamento o vitamina")
    hora = st.time_input("Hora", value=time(8, 0), step=60)
    comp = st.selectbox("Compartimento", [1, 2, 3])
    enviado = st.form_submit_button("Agregar")

if enviado:
    if not med.strip():
        st.error("Escribe el nombre del medicamento.")
    else:
        core.agregar_receta(med, hora.strftime("%H:%M"), comp)
        st.success(f"Agregado: {med.strip()} a las {hora.strftime('%H:%M')} (comp {comp}).")

st.subheader("Receta actual")
receta = core.listar_receta()
if not receta:
    st.info("La receta está vacía.")
for r in receta:
    c1, c2, c3, c4 = st.columns([4, 2, 2, 1])
    c1.write(f"**{r['med']}**")
    c2.write(r["hora"])
    c3.write(f"Comp. {r['comp']}")
    if c4.button("🗑️", key=f"del-{r['id']}", help="Eliminar"):
        core.eliminar_receta(r["id"])
        st.rerun()

st.caption("Prototipo de baja fidelidad: no valida dosis ni interacciones. No es un dispositivo médico.")
