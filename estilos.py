"""Visual layer: CSS and HTML components. No business logic here.

Design idea: the physical pill box is the hero. A rotating carousel shows which
compartment sits under the opening; each compartment keeps its own color across
the whole app (carousel, day line, history, configuration).
"""
from html import escape

import streamlit as st

INK = "#172033"
FOIL = "#DCE2E9"
OK = "#2E9E6B"
BAD = "#D9473F"

# One color per compartment (not status colors, so they never clash with them)
COMP = {1: "#E8A33D", 2: "#8E6BBF", 3: "#3B82C4"}

ESTADOS = {
    "confirmada": ("Confirmada", OK),
    "pospuesta": ("Pospuesta", "#8A6D1F"),
    "omitida": ("Omitida", BAD),
    "enviada": ("Enviada", "#5B6B82"),
    "dispensado": ("Dispensada", "#5B6B82"),
    "sonando": ("Sonando", BAD),
    "online": ("Pastillero en línea", OK),
    "error_envio": ("Sin conexión", BAD),
}

CANALES = {
    "pulsador_fisico": "Pulsador del pastillero",
    "app_boton": "Botón de la app",
    "buzzer": "Buzzer",
    "esp32": "ESP32",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800&display=swap');

:root {{ --ink: {INK}; --foil: {FOIL}; --ok: {OK}; --bad: {BAD};
  --c1: {COMP[1]}; --c2: {COMP[2]}; --c3: {COMP[3]}; }}

.stApp, .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, .stApp button,
.stApp li, .stApp [data-testid="stMarkdownContainer"] {{
  font-family: 'Bricolage Grotesque', 'Segoe UI', system-ui, sans-serif;
}}
.stApp h1, .stApp h2, .stApp h3 {{ font-weight: 750; letter-spacing: -0.01em; font-variation-settings: "wdth" 88; }}
.block-container {{ padding-top: 2.2rem; max-width: 1020px; }}

/* ---------- Carousel ---------- */
.p-car {{ position: relative; width: 300px; height: 300px; margin: .4rem auto; }}
.p-car .p-casco {{ position: absolute; inset: 0; border-radius: 50%; background: var(--ink);
  box-shadow: 0 14px 30px -14px rgba(23,32,51,.55); }}
.p-car .p-disco {{ position: absolute; inset: 16px; border-radius: 50%;
  transform: rotate(var(--giro)); transition: transform 1.4s cubic-bezier(.55,0,.15,1); }}
.p-car .p-lab {{ position: absolute; left: 50%; top: 50%; width: 92px; margin-left: -46px; height: 54px; margin-top: -27px;
  text-align: center; line-height: 1.1; color: var(--ink);
  transform: rotate(var(--a)) translateY(-96px) rotate(calc(var(--a) * -1)) rotate(calc(var(--giro) * -1));
  transition: transform 1.4s cubic-bezier(.55,0,.15,1); }}
.p-car .p-lab b {{ display: block; font-size: 1.55rem; font-weight: 800; }}
.p-car .p-lab span {{ display: block; font-size: .78rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.p-car .p-lab.on {{ color: #fff; }}
.p-car .p-lab.vacio {{ opacity: .5; }}
.p-car .p-hub {{ position: absolute; inset: 31%; border-radius: 50%; background: var(--ink); color: #fff;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  box-shadow: 0 0 0 5px rgba(255,255,255,.9); }}
.p-car .p-hub b {{ font-size: 1.6rem; font-weight: 750; font-variant-numeric: tabular-nums; line-height: 1; }}
.p-car .p-hub span {{ font-size: .7rem; opacity: .7; font-variant-numeric: tabular-nums; }}
.p-car .p-boca {{ position: absolute; top: -9px; left: 50%; width: 54px; height: 26px; margin-left: -27px;
  background: #fff; border: 3px solid var(--ink); border-radius: 0 0 16px 16px; border-top: none; z-index: 2; }}
.p-car .p-boca::after {{ content: ""; position: absolute; left: 50%; bottom: -11px; margin-left: -7px;
  border: 7px solid transparent; border-top-color: var(--ink); border-bottom: none; }}
.p-car.alerta .p-casco {{ animation: p-alerta 1.1s ease-in-out infinite; }}
@keyframes p-alerta {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(217,71,63,.55); }}
  50% {{ box-shadow: 0 0 0 16px rgba(217,71,63,0); }}
}}
.p-car.llamada .p-casco {{ animation: p-llamada 1.6s ease-in-out infinite; }}
@keyframes p-llamada {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(232,163,61,.6); }}
  50% {{ box-shadow: 0 0 0 14px rgba(232,163,61,0); }}
}}

/* ---------- Status headline ---------- */
.p-estado .p-titulo {{ font-size: clamp(2.1rem, 5vw, 3.1rem); font-weight: 800; line-height: 1.02;
  letter-spacing: -0.025em; font-variation-settings: "wdth" 84; margin-bottom: .5rem; }}
.p-estado .p-detalle {{ font-size: 1.1rem; line-height: 1.4; color: #44516A; max-width: 28rem; }}
.p-estado .p-sello {{ display: inline-block; width: .9rem; height: .9rem; border-radius: 50%; margin-right: .5rem;
  vertical-align: .08em; background: var(--sello); }}

/* ---------- Day line ---------- */
.p-dia {{ position: relative; height: 128px; margin: 1.2rem 22px .6rem; }}
.p-dia .p-eje {{ position: absolute; left: 0; right: 0; top: 46px; height: 4px; border-radius: 2px; background: var(--foil); }}
.p-dia .p-hecho {{ position: absolute; left: 0; top: 46px; height: 4px; border-radius: 2px; background: var(--ink);
  transition: width 1s linear; }}
.p-dia .p-ahora {{ position: absolute; top: 8px; width: 2px; height: 82px; margin-left: -1px; background: var(--ink);
  transition: left 1s linear; }}
.p-dia .p-ahora i {{ position: absolute; top: -22px; left: 50%; transform: translateX(-50%); font-style: normal;
  font-size: .8rem; font-weight: 700; background: var(--ink); color: #fff; border-radius: 6px; padding: 1px 7px;
  font-variant-numeric: tabular-nums; }}
.p-dia .p-dosis {{ position: absolute; top: 34px; width: 28px; height: 28px; margin-left: -14px; border-radius: 50%;
  border: 3px solid var(--c); background: #fff; display: flex; align-items: center; justify-content: center;
  font-size: .85rem; font-weight: 800; color: #fff; z-index: 1; }}
.p-dia .p-dosis.confirmada {{ background: var(--ok); border-color: var(--ok); }}
.p-dia .p-dosis.omitida {{ background: var(--bad); border-color: var(--bad); }}
.p-dia .p-dosis.en_curso {{ background: var(--c); animation: p-latido 1.2s ease-in-out infinite; }}
.p-dia .p-dosis.saltada {{ border-style: dashed; opacity: .55; }}
@keyframes p-latido {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(23,32,51,.35); }} 50% {{ box-shadow: 0 0 0 9px rgba(23,32,51,0); }} }}
.p-dia .p-dl {{ position: absolute; top: 70px; transform: translateX(-50%); text-align: center; line-height: 1.2; white-space: nowrap; }}
.p-dia .p-dl b {{ display: block; font-size: .92rem; }}
.p-dia .p-dl span {{ font-size: .8rem; color: #5B6B82; font-variant-numeric: tabular-nums; }}
.p-leyenda {{ font-size: .82rem; color: #5B6B82; margin: 0 22px 1rem; }}

/* ---------- Event log ---------- */
.p-log {{ border-top: 2px solid var(--ink); }}
.p-log .p-fila {{ display: grid; grid-template-columns: 4.2rem 1fr auto; gap: .9rem; align-items: baseline;
  padding: .7rem .1rem; border-bottom: 1px solid var(--foil); }}
.p-log .p-hora {{ font-variant-numeric: tabular-nums; color: #5B6B82; }}
.p-log .p-med {{ font-weight: 700; }}
.p-log .p-med i {{ display: inline-block; width: .6rem; height: .6rem; border-radius: 50%; margin-right: .5rem; background: var(--c); }}
.p-log .p-med small {{ font-weight: 400; color: #5B6B82; margin-left: .6rem; }}
.p-log .p-est {{ font-weight: 700; color: var(--e); text-align: right; }}

/* ---------- Adherence (history) ---------- */
.p-adh .p-frase {{ font-size: clamp(1.8rem, 4.5vw, 2.6rem); font-weight: 800; letter-spacing: -0.02em; line-height: 1.1;
  font-variation-settings: "wdth" 86; }}
.p-adh .p-barra {{ display: flex; height: 18px; border-radius: 9px; overflow: hidden; margin: .9rem 0 .5rem; background: var(--foil); gap: 3px; }}
.p-adh .p-barra div {{ min-width: 6px; }}
.p-adh .p-nota {{ color: #44516A; font-size: .95rem; margin-bottom: 1.2rem; }}

/* ---------- Compartment lanes (configuration) ---------- */
[class*="st-key-carril"] {{ border-left: 7px solid var(--c); border-radius: 4px 16px 16px 4px; padding: .4rem 1rem .5rem 1.1rem;
  margin-bottom: .8rem; background: color-mix(in srgb, var(--c) 10%, white); }}
.st-key-carril1 {{ --c: var(--c1); }}
.st-key-carril2 {{ --c: var(--c2); }}
.st-key-carril3 {{ --c: var(--c3); }}
.p-carril-t {{ font-size: 1.15rem; font-weight: 750; margin: .2rem 0 .1rem; }}
.p-carril-t small {{ font-weight: 500; color: #44516A; margin-left: .5rem; }}
.p-hora-grande {{ font-size: 1.5rem; font-weight: 750; font-variant-numeric: tabular-nums; }}

/* ---------- Sidebar clock ---------- */
.p-reloj {{ margin-bottom: .8rem; border-radius: 14px; padding: .7rem .9rem; background: var(--ink); color: #fff; }}
.p-reloj b {{ display: block; font-size: 2.1rem; font-weight: 750; line-height: 1.05; font-variant-numeric: tabular-nums; }}
.p-reloj span {{ font-size: .8rem; opacity: .75; }}
.p-reloj .p-con {{ display: inline-block; width: .55rem; height: .55rem; border-radius: 50%; margin-right: .4rem; background: var(--k); }}

div[data-testid="stButton"] > button {{ border-radius: 12px; min-height: 2.8rem; font-weight: 650; }}

@media (prefers-reduced-motion: reduce) {{
  .p-car .p-disco, .p-car .p-lab, .p-dia .p-hecho, .p-dia .p-ahora {{ transition: none; }}
  .p-car .p-casco, .p-dia .p-dosis.en_curso {{ animation: none; }}
}}
</style>
"""


def aplicar():
    """Inject the CSS once per page run."""
    st.markdown(CSS, unsafe_allow_html=True)


def _h(*partes):
    # One line only: Markdown treats indented lines as code blocks
    return "".join(partes)


def carrusel(guia, activo=None, hora="--:--", segundos="", alerta=False):
    """Carousel: the active compartment rotates under the opening; at rest the tray is closed."""
    giro = -(activo - 1) * 120 if activo else 60
    tramos, etiquetas = [], []
    for g in guia:
        k = g["comp"]
        vacio = not g.get("med")
        if vacio:
            color = FOIL
        elif activo == k:
            color = COMP[k]
        else:
            color = f"color-mix(in srgb, {COMP[k]} 38%, white)"
        a, b = (k - 1) * 120 - 60 + 60, (k - 1) * 120 + 60 + 60  # angles relative to "from -60deg"
        tramos.append(f"{color} {a + 2}deg {b - 2}deg, {INK} {b - 2}deg {b + 2}deg")
        clases = "p-lab" + (" on" if activo == k else "") + (" vacio" if vacio else "")
        nombre = "vacío" if vacio else escape(g["med"])
        etiquetas.append(
            f'<div class="{clases}" style="--a:{(k - 1) * 120}deg"><b>{k}</b><span>{nombre}</span></div>'
        )
    gradiente = f"conic-gradient(from -60deg, {INK} 0deg 2deg, " + ", ".join(tramos) + ")"
    clase = "p-car" + (" alerta" if alerta else (" llamada" if activo else ""))
    st.markdown(
        _h(
            f'<div class="{clase}" style="--giro:{giro}deg">',
            '<div class="p-casco"></div>',
            f'<div class="p-disco" style="background:{gradiente}">{"".join(etiquetas)}</div>',
            f'<div class="p-hub"><b>{escape(hora)}</b><span>{escape(segundos)}</span></div>',
            '<div class="p-boca"></div></div>',
        ),
        unsafe_allow_html=True,
    )


def estado(titulo, detalle="", color=INK):
    st.markdown(
        _h(
            f'<div class="p-estado" style="--sello:{color}">',
            f'<div class="p-titulo"><span class="p-sello"></span>{escape(titulo)}</div>',
            f'<div class="p-detalle">{escape(detalle)}</div></div>',
        ),
        unsafe_allow_html=True,
    )


def linea_del_dia(tomas, ahora):
    """Horizontal day line: one marker per dose, a cursor for the simulated clock."""
    if not tomas:
        return
    minutos = [int(t["hora"][:2]) * 60 + int(t["hora"][3:]) for t in tomas]
    now_m = ahora.hour * 60 + ahora.minute + ahora.second / 60
    lo = max(0, (int(min(minutos + [now_m])) // 60 - 1) * 60)
    hi = min(24 * 60, ((int(max(minutos + [now_m])) + 59) // 60 + 1) * 60)
    pos = lambda m: (m - lo) / (hi - lo) * 100  # noqa: E731

    marcas = []
    for t, m in zip(tomas, minutos):
        est = t["estado"]
        if est == "sin_disparar" and m < now_m:
            est = "saltada"
        glifo = {"confirmada": "✓", "omitida": "×"}.get(est, "")
        marcas.append(
            _h(
                f'<div class="p-dosis {est}" style="left:{pos(m):.2f}%;--c:{COMP[t["comp"]]}">{glifo}</div>',
                f'<div class="p-dl" style="left:{pos(m):.2f}%"><b>{escape(t["med"])}</b><span>{t["hora"]}</span></div>',
            )
        )
    st.markdown(
        _h(
            '<div class="p-dia">',
            '<div class="p-eje"></div>',
            f'<div class="p-hecho" style="width:{pos(now_m):.2f}%"></div>',
            f'<div class="p-ahora" style="left:{pos(now_m):.2f}%"><i>{ahora:%H:%M}</i></div>',
            "".join(marcas),
            "</div>",
            '<div class="p-leyenda">Hoy, en hora simulada. ✓ confirmada · × omitida · punto vacío: aún no llega · '
            "punto lleno que late: en curso.</div>",
        ),
        unsafe_allow_html=True,
    )


def filas_eventos(eventos):
    """Event log, newest first. Hairlines instead of cards."""
    filas = []
    for e in eventos:
        texto, color = ESTADOS.get(e["evento"], (str(e["evento"]), INK))
        canal = CANALES.get(e.get("canal"), "")
        hora = str(e["hora_sim"])[-8:-3] if e.get("hora_sim") else ""
        c = COMP.get(e.get("comp"), FOIL)
        filas.append(
            _h(
                '<div class="p-fila">',
                f'<span class="p-hora">{escape(hora)}</span>',
                f'<span class="p-med"><i style="--c:{c}"></i>{escape(str(e["med"]))}',
                f"<small>{escape(canal)}</small></span>",
                f'<span class="p-est" style="--e:{color}">{escape(texto)}</span></div>',
            )
        )
    st.markdown(f'<div class="p-log">{"".join(filas)}</div>', unsafe_allow_html=True)


def adherencia(confirmadas, omitidas, pospuestas):
    total = confirmadas + omitidas
    if total:
        frase = f"{confirmadas} de {total} {'toma confirmada' if total == 1 else 'tomas confirmadas'}"
    else:
        frase = "Aún sin tomas cerradas"
    barra = ""
    if total:
        barra = _h(
            f'<div style="flex:{confirmadas};background:{OK}"></div>' if confirmadas else "",
            f'<div style="flex:{omitidas};background:{BAD}"></div>' if omitidas else "",
        )
    nota = f"{omitidas} omitidas · {pospuestas} posposiciones registradas"
    st.markdown(
        _h(
            '<div class="p-adh">',
            f'<div class="p-frase">{frase}</div>',
            f'<div class="p-barra">{barra}</div>',
            f'<div class="p-nota">{nota}</div></div>',
        ),
        unsafe_allow_html=True,
    )


def reloj(hora, velocidad, conectado):
    k = OK if conectado else BAD
    estado_mqtt = "MQTT conectado" if conectado else "MQTT sin conexión"
    st.markdown(
        _h(
            '<div class="p-reloj">',
            "<span>Hora simulada</span>",
            f"<b>{escape(hora)}</b>",
            f'<span>1 s real = {velocidad:g} s simulados</span><br>',
            f'<span><i class="p-con" style="--k:{k}"></i>{estado_mqtt}</span></div>',
        ),
        unsafe_allow_html=True,
    )
