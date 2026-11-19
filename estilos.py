"""Visual layer: CSS and small HTML components. No business logic here."""
from html import escape

import streamlit as st

# Tone -> (rgb, label). Backgrounds use alpha so they work in light and dark themes.
TONOS = {
    "ok": "22, 163, 74",
    "aviso": "217, 119, 6",
    "alerta": "220, 38, 38",
    "info": "37, 99, 235",
    "neutro": "113, 113, 122",
}

ESTADOS = {
    "confirmada": ("✅", "Confirmada", "ok"),
    "pospuesta": ("⏰", "Pospuesta", "aviso"),
    "omitida": ("⚠️", "Omitida", "alerta"),
    "enviada": ("📤", "Enviada", "info"),
    "dispensado": ("💊", "Dispensada", "info"),
    "sonando": ("🔊", "Sonando", "alerta"),
    "online": ("🟢", "En línea", "ok"),
    "error_envio": ("📡", "Sin conexión", "alerta"),
}

CANALES = {
    "pulsador_fisico": "🔘 Pulsador físico",
    "app_boton": "📱 Botón de la app",
    "buzzer": "🔊 Buzzer",
    "esp32": "🤖 ESP32",
}

CSS = """
<style>
.block-container { padding-top: 2rem; max-width: 980px; }

/* Hero card: main status of the pill box */
.p-hero {
  border-radius: 18px; padding: 1.4rem 1.6rem; margin-bottom: 1rem;
  border: 1px solid rgba(var(--tono), 0.40);
  background: linear-gradient(135deg, rgba(var(--tono), 0.16), rgba(var(--tono), 0.05));
}
.p-hero .p-kicker { font-size: 0.8rem; letter-spacing: .08em; text-transform: uppercase; opacity: .7; }
.p-hero .p-titulo { font-size: 1.9rem; font-weight: 700; line-height: 1.2; margin: .15rem 0; }
.p-hero .p-detalle { opacity: .85; font-size: 1rem; }
.p-hero.p-pulso { animation: p-pulso 1.2s ease-in-out infinite; }
@keyframes p-pulso {
  0%, 100% { box-shadow: 0 0 0 0 rgba(var(--tono), .45); }
  50% { box-shadow: 0 0 0 10px rgba(var(--tono), 0); }
}

/* Compartment cards */
.p-comps { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin: .4rem 0 1.2rem; }
.p-comp {
  border-radius: 14px; padding: .9rem 1rem;
  border: 1px solid rgba(113, 113, 122, .35);
  background: var(--secondary-background-color);
}
.p-comp.activo {
  border: 2px solid rgba(var(--tono), .9);
  background: rgba(var(--tono), .14);
}
.p-comp .p-num { font-size: .75rem; opacity: .65; text-transform: uppercase; letter-spacing: .08em; }
.p-comp .p-med { font-size: 1.1rem; font-weight: 650; margin: .1rem 0; }
.p-comp .p-horas { font-size: .85rem; opacity: .75; }
.p-comp.vacio .p-med { opacity: .45; font-weight: 400; }
@media (max-width: 640px) { .p-comps { grid-template-columns: 1fr; } }

/* Badges and event rows */
.p-badge {
  display: inline-block; padding: .12rem .6rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
  background: rgba(var(--tono), .16); border: 1px solid rgba(var(--tono), .45);
}
.p-fila {
  display: flex; align-items: center; gap: .8rem; padding: .6rem .8rem; margin-bottom: .4rem;
  border-radius: 12px; background: var(--secondary-background-color);
}
.p-fila .p-hora { font-variant-numeric: tabular-nums; opacity: .7; min-width: 4.2rem; }
.p-fila .p-med { font-weight: 600; flex: 1; }
.p-fila .p-canal { font-size: .8rem; opacity: .7; }

/* Stat cards (history) */
.p-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: .8rem; margin-bottom: 1rem; }
.p-stat {
  border-radius: 14px; padding: .9rem 1rem; text-align: center;
  background: rgba(var(--tono), .12); border: 1px solid rgba(var(--tono), .35);
}
.p-stat .p-n { font-size: 2rem; font-weight: 700; line-height: 1.1; }
.p-stat .p-l { font-size: .8rem; opacity: .75; text-transform: uppercase; letter-spacing: .06em; }

/* Sidebar clock */
.p-reloj { text-align: center; padding: .8rem; border-radius: 14px; background: var(--secondary-background-color); }
.p-reloj .p-t { font-size: 2.2rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; }
.p-reloj .p-s { font-size: .8rem; opacity: .7; }
.p-pill { display: inline-block; font-size: .75rem; padding: .1rem .55rem; border-radius: 999px;
  background: rgba(var(--tono), .16); border: 1px solid rgba(var(--tono), .45); margin-top: .35rem; }

/* Bigger tap targets for the main actions */
div[data-testid="stButton"] > button { border-radius: 12px; min-height: 2.8rem; font-weight: 600; }
</style>
"""


def aplicar():
    """Inject the CSS once per page run."""
    st.markdown(CSS, unsafe_allow_html=True)


def _tono(nombre):
    return f"--tono: {TONOS.get(nombre, TONOS['neutro'])};"


def hero(kicker, titulo, detalle="", tono="neutro", pulso=False):
    clase = "p-hero p-pulso" if pulso else "p-hero"
    st.markdown(
        f'<div class="{clase}" style="{_tono(tono)}">'
        f'<div class="p-kicker">{escape(kicker)}</div>'
        f'<div class="p-titulo">{escape(titulo)}</div>'
        f'<div class="p-detalle">{escape(detalle)}</div></div>',
        unsafe_allow_html=True,
    )


def compartimentos(guia, activo=None, tono_activo="aviso"):
    """guia: list of {comp, med, horas}. activo: compartment number to highlight."""
    tarjetas = []
    for g in guia:
        vacio = not g.get("med")
        clases = "p-comp"
        if vacio:
            clases += " vacio"
        if g["comp"] == activo:
            clases += " activo"
        med = "Vacío" if vacio else escape(g["med"])
        horas = "Sin tomas" if vacio else escape(g["horas"])
        tarjetas.append(
            f'<div class="{clases}" style="{_tono(tono_activo)}">'
            f'<div class="p-num">Compartimento {g["comp"]}</div>'
            f'<div class="p-med">{med}</div><div class="p-horas">🕒 {horas}</div></div>'
        )
    st.markdown(f'<div class="p-comps">{"".join(tarjetas)}</div>', unsafe_allow_html=True)


def badge(estado):
    icono, texto, tono = ESTADOS.get(estado, ("•", str(estado), "neutro"))
    return f'<span class="p-badge" style="{_tono(tono)}">{icono} {escape(texto)}</span>'


def filas_eventos(eventos):
    """Compact timeline of events (newest first)."""
    filas = []
    for e in eventos:
        canal = CANALES.get(e.get("canal"), "")
        filas.append(
            '<div class="p-fila">'
            f'<span class="p-hora">{escape(str(e["hora_sim"])[-8:-3] if e.get("hora_sim") else "")}</span>'
            f'<span class="p-med">{escape(str(e["med"]))}</span>'
            f'{badge(e["evento"])}'
            f'<span class="p-canal">{escape(canal)}</span></div>'
        )
    st.markdown("".join(filas), unsafe_allow_html=True)


def estadisticas(confirmadas, pospuestas, omitidas):
    datos = [(confirmadas, "Confirmadas", "ok"), (pospuestas, "Pospuestas", "aviso"), (omitidas, "Omitidas", "alerta")]
    tarjetas = "".join(
        f'<div class="p-stat" style="{_tono(t)}"><div class="p-n">{n}</div><div class="p-l">{l}</div></div>'
        for n, l, t in datos
    )
    st.markdown(f'<div class="p-stats">{tarjetas}</div>', unsafe_allow_html=True)


def reloj(hora, velocidad, conectado):
    tono = "ok" if conectado else "alerta"
    estado = "🟢 MQTT conectado" if conectado else "🔴 MQTT sin conexión"
    st.markdown(
        f'<div class="p-reloj" style="{_tono(tono)}">'
        '<div class="p-s">Hora simulada</div>'
        f'<div class="p-t">{escape(hora)}</div>'
        f'<div class="p-s">1 s real = {velocidad:g} s simulados</div>'
        f'<span class="p-pill">{estado}</span></div>',
        unsafe_allow_html=True,
    )
