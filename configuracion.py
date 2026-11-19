from datetime import time

import pandas as pd
import streamlit as st

import core

st.title("⚙️ Configuración de la receta")
st.caption("Ingresa tu receta fija una vez. El sistema no valida dosis ni interacciones.")

# New dose form (one dose per time, one compartment = one medicine)
with st.form("nueva_toma", clear_on_submit=True):
    med = st.text_input("Medicamento o vitamina")
    c1, c2 = st.columns(2)
    hora = c1.time_input("Hora de la toma", value=time(8, 0), step=60)
    comp = c2.selectbox("Compartimento", [1, 2, 3])
    ok = st.form_submit_button("Confirmar y guardar")

if ok:
    try:
        guardado, msg = core.add_toma(med, hora.strftime("%H:%M"), comp)
        if guardado:
            st.success(msg)
        else:
            st.error(msg)
    except Exception as e:
        st.error(f"Error al guardar la toma: {str(e)}")

st.subheader("Receta actual")
receta = core.get_receta()
if not receta:
    st.info("Aún no hay tomas.")
for t in receta:
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    c1.write(f"**{t['med']}**")
    c2.write(t["hora"])
    c3.write(f"Comp. {t['comp']}")
    if c4.button("🗑️", key=f"del_{t['id']}"):
        core.delete_toma(t["id"])
        st.rerun()

# Loading guide: which pill goes in which compartment
st.subheader("Guía de carga del pastillero")
st.caption("Carga cada medicamento en su compartimento numerado. El sistema no puede verificar qué hay dentro.")
guia = pd.DataFrame(core.guia_de_carga())
guia["med"] = guia["med"].fillna("— vacío —")
guia = guia.rename(columns={"comp": "Compartimento", "med": "Contiene", "horas": "Horas de toma"})
st.dataframe(guia, hide_index=True)
