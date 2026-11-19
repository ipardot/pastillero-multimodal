from datetime import time

import streamlit as st

import core
import estilos

estilos.aplicar()

st.title("Configuración de la receta")
st.caption("Ingresa tu receta fija una vez. El sistema no valida dosis ni interacciones.")

# New dose form (one dose per time, one compartment = one medicine)
with st.form("nueva_toma", clear_on_submit=True, border=True):
    med = st.text_input("Medicamento o vitamina")
    c1, c2 = st.columns(2)
    hora = c1.time_input("Hora de la toma", value=time(8, 0), step=60)
    comp = c2.selectbox("Compartimento", [1, 2, 3])
    ok = st.form_submit_button("Guardar toma", type="primary")

if ok:
    try:
        guardado, msg = core.add_toma(med, hora.strftime("%H:%M"), comp)
        if guardado:
            st.success(msg)
        else:
            st.error(msg)
    except Exception as e:
        st.error(f"Error al guardar la toma: {str(e)}")

st.subheader("Receta por compartimento")
st.caption("Carga cada medicamento en su compartimento numerado. El sistema no puede verificar qué hay dentro.")
receta = core.get_receta()
if not receta:
    st.info("Aún no hay tomas. Agrega la primera con el formulario o carga la receta de ejemplo.")
for k in (1, 2, 3):
    tomas = [t for t in receta if t["comp"] == k]
    with st.container(key=f"carril{k}"):
        nombre = tomas[0]["med"] if tomas else "vacío"
        st.markdown(
            f'<div class="p-carril-t">Compartimento {k}<small>{nombre}</small></div>',
            unsafe_allow_html=True,
        )
        if not tomas:
            st.caption("Sin tomas. Asigna este compartimento con el formulario.")
        for t in tomas:
            c1, c2 = st.columns([6, 1], vertical_alignment="center")
            c1.markdown(f'<span class="p-hora-grande">{t["hora"]}</span>', unsafe_allow_html=True)
            if c2.button("Quitar", key=f"del_{t['id']}", help="Eliminar esta toma"):
                core.delete_toma(t["id"])
                st.rerun()

st.write("")
b1, b2 = st.columns(2)
if b1.button("Cargar receta de ejemplo", width="stretch", help="Reemplaza la receta actual por una de ejemplo"):
    core.cargar_ejemplo()
    st.rerun()
if receta and b2.button("Vaciar receta", width="stretch", help="Elimina todas las tomas"):
    core.vaciar_receta()
    st.rerun()
