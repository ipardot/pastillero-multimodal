"""Lógica del pastillero: SQLite, reloj simulado y cliente MQTT.

Reglas importantes:
- Se abre una conexión SQLite por llamada: el callback de paho corre en otro hilo.
- El hilo de MQTT nunca toca st.session_state; registra directo en SQLite.
- El reloj vive aquí (no en el ESP32). tick() procesa la ventana (sim_last, ahora].
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("PASTILLERO_DB", str(BASE_DIR / "pastillero.db"))
PREFIX = os.environ.get("PASTILLERO_PREFIX", "eafit/julian/pastillero").rstrip("/")
BROKER = os.environ.get("PASTILLERO_BROKER", "broker.hivemq.com")
PORT = int(os.environ.get("PASTILLERO_PORT", "1883"))

EVENTOS_ESP32 = {"online", "dispensado", "sonando", "pospuesta", "confirmada", "omitida"}
CANALES = {"pulsador_fisico", "app_boton", "buzzer", "esp32"}
EVENTOS_CIERRE = ("confirmada", "omitida")
EVENTOS_HISTORIAL = ("confirmada", "pospuesta", "omitida")
VELOCIDADES = (1, 60, 300, 600)
# Si pasan más de estos segundos reales entre dos tick(), la app estuvo cerrada:
# se avanza la ventana sin disparar lo atrasado (evita una ráfaga de tomas viejas).
MAX_HUECO_REAL_S = 30

RECETA_EJEMPLO = [
    ("Vitamina D", "08:00", 1),
    ("Omega 3", "12:00", 2),
    ("Vitamina C", "20:00", 3),
]

FMT = "%Y-%m-%dT%H:%M:%S"


# ---------------------------------------------------------------- SQLite
def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with closing(_conn()) as con, con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS receta(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                med TEXT NOT NULL,
                hora TEXT NOT NULL,
                comp INTEGER NOT NULL CHECK(comp BETWEEN 1 AND 3)
            );
            CREATE TABLE IF NOT EXISTS eventos(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                hora_sim TEXT,
                toma_id TEXT,
                med TEXT,
                comp INTEGER,
                evento TEXT NOT NULL,
                canal TEXT
            );
            CREATE TABLE IF NOT EXISTS kv(
                clave TEXT PRIMARY KEY,
                valor TEXT
            );
            CREATE TABLE IF NOT EXISTS disparos(
                clave TEXT PRIMARY KEY
            );
            """
        )
        if con.execute("SELECT COUNT(*) FROM receta").fetchone()[0] == 0:
            con.executemany("INSERT INTO receta(med, hora, comp) VALUES (?,?,?)", RECETA_EJEMPLO)
    _init_reloj()


def kv_get(clave: str, defecto: str | None = None) -> str | None:
    with closing(_conn()) as con:
        fila = con.execute("SELECT valor FROM kv WHERE clave=?", (clave,)).fetchone()
    return fila["valor"] if fila else defecto


def kv_set_many(valores: dict[str, str]) -> None:
    with closing(_conn()) as con, con:
        con.executemany(
            "INSERT INTO kv(clave, valor) VALUES (?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            list(valores.items()),
        )


# ---------------------------------------------------------------- Receta
def listar_receta() -> list[dict]:
    with closing(_conn()) as con:
        filas = con.execute("SELECT id, med, hora, comp FROM receta ORDER BY hora, id").fetchall()
    return [dict(f) for f in filas]


def agregar_receta(med: str, hora: str, comp: int) -> None:
    med = (med or "").strip()
    if not med:
        raise ValueError("El nombre del medicamento no puede estar vacío.")
    datetime.strptime(hora, "%H:%M")  # valida formato
    if int(comp) not in (1, 2, 3):
        raise ValueError("El compartimento debe ser 1, 2 o 3.")
    with closing(_conn()) as con, con:
        con.execute("INSERT INTO receta(med, hora, comp) VALUES (?,?,?)", (med, hora, int(comp)))


def eliminar_receta(receta_id: int) -> None:
    with closing(_conn()) as con, con:
        con.execute("DELETE FROM receta WHERE id=?", (receta_id,))


# ---------------------------------------------------------------- Eventos
def registrar_evento(evento: str, toma_id=None, med=None, comp=None, canal=None,
                     ahora_real: float | None = None) -> None:
    ts = datetime.fromtimestamp(ahora_real if ahora_real is not None else time.time())
    hora_sim = hora_simulada(ahora_real).strftime(FMT)
    with closing(_conn()) as con, con:
        con.execute(
            "INSERT INTO eventos(ts, hora_sim, toma_id, med, comp, evento, canal) "
            "VALUES (?,?,?,?,?,?,?)",
            (ts.strftime(FMT), hora_sim, toma_id, med, comp, evento, canal),
        )


def ultimos_eventos(n: int = 6) -> list[dict]:
    with closing(_conn()) as con:
        filas = con.execute(
            "SELECT hora_sim, med, comp, evento, canal FROM eventos ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
    return [dict(f) for f in filas]


def historial() -> list[dict]:
    marcas = ",".join("?" * len(EVENTOS_HISTORIAL))
    with closing(_conn()) as con:
        filas = con.execute(
            f"SELECT hora_sim, med, comp, evento, canal FROM eventos "
            f"WHERE evento IN ({marcas}) ORDER BY id DESC",
            EVENTOS_HISTORIAL,
        ).fetchall()
    return [dict(f) for f in filas]


def toma_pendiente() -> dict | None:
    """Última toma 'enviada' que aún no tiene 'confirmada' ni 'omitida'.

    Devuelve dict con id, med, comp y 'estado' (último evento de esa toma).
    """
    with closing(_conn()) as con:
        env = con.execute(
            "SELECT toma_id, med, comp FROM eventos WHERE evento='enviada' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if env is None:
            return None
        cerrada = con.execute(
            "SELECT 1 FROM eventos WHERE toma_id=? AND evento IN (?,?) LIMIT 1",
            (env["toma_id"], *EVENTOS_CIERRE),
        ).fetchone()
        if cerrada:
            return None
        ultimo = con.execute(
            "SELECT evento FROM eventos WHERE toma_id=? ORDER BY id DESC LIMIT 1",
            (env["toma_id"],),
        ).fetchone()
    return {"id": env["toma_id"], "med": env["med"], "comp": env["comp"], "estado": ultimo["evento"]}


def ultimo_online() -> str | None:
    with closing(_conn()) as con:
        fila = con.execute(
            "SELECT ts FROM eventos WHERE evento='online' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return fila["ts"] if fila else None


def reiniciar_demo() -> None:
    with closing(_conn()) as con, con:
        con.execute("DELETE FROM eventos")
        con.execute("DELETE FROM disparos")


# ---------------------------------------------------------------- Reloj simulado
def _init_reloj() -> None:
    if kv_get("sim_start") is not None:
        return
    ahora = time.time()
    inicio = datetime.fromtimestamp(ahora).replace(microsecond=0).strftime(FMT)
    kv_set_many({"sim_start": inicio, "sim_anchor": repr(ahora), "sim_speed": "1", "sim_last": inicio})


def velocidad() -> int:
    return int(float(kv_get("sim_speed", "1")))


def hora_simulada(ahora_real: float | None = None) -> datetime:
    ahora_real = time.time() if ahora_real is None else ahora_real
    with closing(_conn()) as con:  # una sola lectura para no mezclar estados
        kv = dict(con.execute(
            "SELECT clave, valor FROM kv WHERE clave IN ('sim_start','sim_anchor','sim_speed')"
        ).fetchall())
    if "sim_start" not in kv:
        return datetime.fromtimestamp(ahora_real)
    avance = (ahora_real - float(kv["sim_anchor"])) * float(kv.get("sim_speed", 1))
    return datetime.strptime(kv["sim_start"], FMT) + timedelta(seconds=avance)


def set_velocidad(nueva: int, ahora_real: float | None = None) -> None:
    """Reancla el reloj: la hora simulada no salta y la ventana (sim_last) no se toca."""
    ahora_real = time.time() if ahora_real is None else ahora_real
    actual = hora_simulada(ahora_real)
    kv_set_many({"sim_start": actual.strftime(FMT), "sim_anchor": repr(ahora_real),
                 "sim_speed": str(int(nueva))})


def fijar_hora(nueva: datetime, ahora_real: float | None = None) -> None:
    """Salta a una hora simulada. La ventana arranca ahí: no dispara lo saltado."""
    ahora_real = time.time() if ahora_real is None else ahora_real
    s = nueva.replace(microsecond=0).strftime(FMT)
    kv_set_many({"sim_start": s, "sim_anchor": repr(ahora_real), "sim_last": s,
                 "tick_real": repr(ahora_real)})


def proxima_toma(ahora_sim: datetime | None = None) -> dict | None:
    ahora_sim = ahora_sim or hora_simulada()
    mejor = None
    for r in listar_receta():
        h, m = map(int, r["hora"].split(":"))
        dt = ahora_sim.replace(hour=h, minute=m, second=0, microsecond=0)
        if dt <= ahora_sim:
            dt += timedelta(days=1)
        if mejor is None or dt < mejor["cuando"]:
            mejor = {**r, "cuando": dt}
    return mejor


# ---------------------------------------------------------------- MQTT
def topic(sufijo: str) -> str:
    return f"{PREFIX}/{sufijo}"


def publicar(client, mensaje: dict) -> bool:
    """Publica en /cmd con QoS 0 solo si el cliente está conectado (no encola órdenes viejas)."""
    if client is None or not client.is_connected():
        return False
    info = client.publish(topic("cmd"), json.dumps(mensaje, ensure_ascii=False), qos=0)
    return getattr(info, "rc", 0) == 0


def enviar_toma(client, toma_id: str, med: str, comp: int, ahora_real: float | None = None) -> bool:
    ok = publicar(client, {"accion": "dispensar", "id": toma_id, "med": med, "comp": int(comp)})
    registrar_evento("enviada" if ok else "sin_conexion", toma_id, med, comp, "app", ahora_real)
    return ok


def tick(client, ahora_real: float | None = None) -> list[str]:
    """Dispara cada toma cuya hora cae en (sim_last, ahora]. Devuelve los ids disparados."""
    ahora_real = time.time() if ahora_real is None else ahora_real
    ahora = hora_simulada(ahora_real)
    ultimo_s = kv_get("sim_last")
    if ultimo_s is None:
        return []
    ultimo = datetime.strptime(ultimo_s, FMT)
    if ahora <= ultimo:
        return []
    tick_previo = kv_get("tick_real")
    kv_set_many({"tick_real": repr(ahora_real)})
    if tick_previo is not None and ahora_real - float(tick_previo) > MAX_HUECO_REAL_S:
        kv_set_many({"sim_last": ahora.strftime(FMT)})
        return []

    candidatas = []
    receta = listar_receta()
    dia = ultimo.date()
    while dia <= ahora.date():
        for r in receta:
            h, m = map(int, r["hora"].split(":"))
            dt = datetime(dia.year, dia.month, dia.day, h, m)
            if ultimo < dt <= ahora:  # ventana semiabierta: nunca "=="
                candidatas.append((dt, r))
        dia += timedelta(days=1)
    candidatas.sort(key=lambda c: c[0])

    disparadas = []
    for dt, r in candidatas:
        toma_id = f"{dt.strftime('%Y-%m-%dT%H:%M')}-r{r['id']}"
        with closing(_conn()) as con, con:
            nuevo = con.execute("INSERT OR IGNORE INTO disparos(clave) VALUES (?)", (toma_id,)).rowcount
        if nuevo:
            enviar_toma(client, toma_id, r["med"], r["comp"], ahora_real)
            disparadas.append(toma_id)

    kv_set_many({"sim_last": ahora.strftime(FMT)})
    return disparadas


def simular_toma_ahora(client, receta_id: int) -> str | None:
    r = next((x for x in listar_receta() if x["id"] == receta_id), None)
    if r is None:
        return None
    toma_id = f"manual-{datetime.now().strftime('%H%M%S')}-r{r['id']}"
    enviar_toma(client, toma_id, r["med"], r["comp"])
    return toma_id


def procesar_estado(payload) -> bool:
    """Registra un mensaje de {prefijo}/estado. Ignora basura sin lanzar excepciones."""
    try:
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8")
        datos = json.loads(payload)
        if not isinstance(datos, dict):
            return False
        evento = datos.get("evento")
        if evento not in EVENTOS_ESP32:
            return False
        canal = datos.get("canal")
        canal = canal if canal in CANALES else None
        if evento == "online":
            registrar_evento("online", canal=canal or "esp32")
            return True
        toma_id = datos.get("id")
        if not isinstance(toma_id, str) or not toma_id:
            return False
        comp = datos.get("comp")
        comp = comp if isinstance(comp, int) else None
        med = datos.get("med")
        med = med if isinstance(med, str) else None
        registrar_evento(evento, toma_id, med, comp, canal)
        return True
    except Exception:
        return False


def crear_cliente():
    """Crea y arranca el cliente MQTT (llamar una sola vez, vía st.cache_resource)."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"pastillero-app-{uuid.uuid4().hex[:8]}")

    def on_connect(c, userdata, flags, reason_code, properties):
        if not reason_code.is_failure:
            c.subscribe(topic("estado"), qos=0)

    def on_message(c, userdata, msg):
        procesar_estado(msg.payload)

    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    try:
        client.connect_async(BROKER, PORT, keepalive=30)
        client.loop_start()
    except Exception:
        pass  # sin red: la app sigue funcionando, el estado mostrará "desconectado"
    return client



@st.cache_resource(show_spinner=False)
def get_client():
    """Cliente MQTT único por proceso. Lo usan app.py y las páginas."""
    return crear_cliente()
