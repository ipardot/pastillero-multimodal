"""Shared helpers: SQLite storage, simulated clock and MQTT client.

State lives in SQLite (not st.session_state) because the paho callback
runs in another thread and cannot touch session_state.
"""
import json
import os
import sqlite3
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

# DB goes to the temp folder (Streamlit Cloud: ephemeral, resets on restart)
DB_PATH = os.getenv(
    "PASTILLERO_DB", os.path.join(tempfile.gettempdir(), "pastillero.db")
)
FMT = "%Y-%m-%d %H:%M:%S"

# Default MQTT settings (editable from the sidebar).
# The prefix MUST match the topics in wokwi/sketch.ino.
MQTT_DEFAULTS = {
    "mqtt_broker": "broker.hivemq.com",
    "mqtt_port": "1883",
    "mqtt_prefix": "eafit/julian/pastillero",
}

# Sample prescription: (id, medicine, time, compartment)
RECETA_EJEMPLO = [
    ("t1", "Vitamina D", "08:00", 1),
    ("t2", "Omega 3", "12:00", 2),
    ("t3", "Vitamina C", "20:00", 3),
]


# ------------------------------------------------------------------ database
@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with db() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS receta (
                id TEXT PRIMARY KEY, med TEXT NOT NULL,
                hora TEXT NOT NULL, comp INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, hora_sim TEXT,
                toma_id TEXT, med TEXT, comp INTEGER, evento TEXT, canal TEXT);
            CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS disparos (clave TEXT PRIMARY KEY);
            """
        )
        vacia = con.execute("SELECT COUNT(*) FROM receta").fetchone()[0] == 0
    # Seed the sample prescription only once, so the user can empty it for good
    if kv_get("receta_sembrada") is None:
        if vacia:
            cargar_ejemplo()
        kv_set(receta_sembrada="1")
    if kv_get("mqtt_client_id") is None:
        kv_set(mqtt_client_id="pastillero-app-" + uuid.uuid4().hex[:6])
    if kv_get("sim_start") is None:
        set_clock(_inicio_por_defecto(), 60)


def kv_get(k, default=None):
    with db() as con:
        row = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return row["v"] if row else default


def kv_set(**items):
    with db() as con:
        for k, v in items.items():
            con.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, str(v)))


# -------------------------------------------------------------- prescription
def get_receta():
    with db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM receta ORDER BY hora, comp")]


def add_toma(med: str, hora: str, comp: int):
    """Add a dose. Returns (ok, message). Rules: one dose per time,
    one compartment = one medicine."""
    med = med.strip()
    comp = int(comp)
    if not med:
        return False, "Escribe el nombre del medicamento o vitamina."
    receta = get_receta()
    for t in receta:  # rule 1: one dose per time
        if t["hora"] == hora:
            return False, (
                f"Ya hay una toma a las {hora} ({t['med']}). "
                "El pastillero atiende una toma a la vez."
            )
    for t in receta:  # rule 2: one compartment = one medicine
        if t["comp"] == comp and t["med"].lower() != med.lower():
            return False, (
                f"El compartimento {comp} ya contiene {t['med']}. "
                "Un compartimento = un medicamento."
            )
        if t["med"].lower() == med.lower() and t["comp"] != comp:
            return False, (
                f"{t['med']} ya está en el compartimento {t['comp']}. "
                "Usa ese mismo compartimento."
            )
    with db() as con:
        con.execute(
            "INSERT INTO receta VALUES (?,?,?,?)",
            ("t" + uuid.uuid4().hex[:6], med, hora, comp),
        )
    return True, f"Guardado: {med} a las {hora} (compartimento {comp})."


def cargar_ejemplo():
    """Replace the prescription with the sample one."""
    with db() as con:
        con.execute("DELETE FROM receta")
        con.executemany("INSERT INTO receta VALUES (?,?,?,?)", RECETA_EJEMPLO)


def vaciar_receta():
    with db() as con:
        con.execute("DELETE FROM receta")


def delete_toma(toma_id: str):
    with db() as con:
        con.execute("DELETE FROM receta WHERE id=?", (toma_id,))


def guia_de_carga(n_comp: int = 3):
    """Per compartment: medicine and its times, to guide loading the pills."""
    guia = []
    receta = get_receta()
    for c in range(1, n_comp + 1):
        tomas = [t for t in receta if t["comp"] == c]
        guia.append(
            {
                "comp": c,
                "med": tomas[0]["med"] if tomas else None,
                "horas": ", ".join(t["hora"] for t in tomas),
            }
        )
    return guia


def proxima_toma(now: datetime):
    """Return (dose, datetime) of the next dose after `now`."""
    receta = get_receta()
    if not receta:
        return None, None
    candidatas = []
    for t in receta:
        h, m = map(int, t["hora"].split(":"))
        due = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
        candidatas.append((due, t))
    due, t = min(candidatas, key=lambda x: x[0])
    return t, due


# ------------------------------------------------------------ simulated clock
def _inicio_por_defecto():
    return datetime.now().replace(hour=7, minute=55, second=0, microsecond=0)


def set_clock(start: datetime, speed: float, reset_window: bool = True):
    items = dict(
        sim_start=start.strftime(FMT), sim_anchor=time.time(), sim_speed=speed
    )
    if reset_window:
        items["sim_last"] = start.strftime(FMT)
    kv_set(**items)


def get_speed() -> float:
    return float(kv_get("sim_speed", 60))


def hora_sim() -> datetime:
    start = datetime.strptime(kv_get("sim_start"), FMT)
    anchor = float(kv_get("sim_anchor"))
    return start + timedelta(seconds=(time.time() - anchor) * get_speed())


def cambiar_velocidad(speed: float):
    """Re-anchor: current simulated time becomes the new start (no jumps)."""
    set_clock(hora_sim(), speed, reset_window=False)


def tick() -> datetime:
    """Advance the engine: fire doses whose time fell in (last, now]."""
    now = hora_sim()
    last = datetime.strptime(kv_get("sim_last"), FMT)
    if now <= last:
        return now
    for toma in get_receta():
        h, m = map(int, toma["hora"].split(":"))
        d = last.date()
        while d <= now.date():
            due = datetime.combine(d, datetime.min.time()).replace(hour=h, minute=m)
            if last < due <= now:
                _disparar(toma, due)
            d += timedelta(days=1)
    kv_set(sim_last=now.strftime(FMT))
    return now


def _disparar(toma: dict, due: datetime):
    clave = f"{toma['id']}@{due:%Y%m%d%H%M}"
    with db() as con:
        nuevo = con.execute("INSERT OR IGNORE INTO disparos VALUES (?)", (clave,)).rowcount == 1
    if nuevo:
        enviar_dispensar(toma, clave)


# ----------------------------------------------------------------------- MQTT
def mqtt_config():
    return {
        "broker": kv_get("mqtt_broker", MQTT_DEFAULTS["mqtt_broker"]),
        "port": int(kv_get("mqtt_port", MQTT_DEFAULTS["mqtt_port"])),
        "prefix": kv_get("mqtt_prefix", MQTT_DEFAULTS["mqtt_prefix"]),
        "client_id": kv_get("mqtt_client_id"),
    }


def set_mqtt_config(broker: str, port: int, prefix: str, client_id: str):
    broker, prefix, client_id = broker.strip(), prefix.strip().strip("/"), client_id.strip()
    if not broker or not prefix or not client_id:
        raise ValueError("Broker, prefijo y client ID no pueden estar vacíos.")
    kv_set(mqtt_broker=broker, mqtt_port=int(port), mqtt_prefix=prefix, mqtt_client_id=client_id)


def topic_cmd() -> str:  # app -> ESP32
    return f"{mqtt_config()['prefix']}/cmd"


def topic_estado() -> str:  # ESP32 -> app
    return f"{mqtt_config()['prefix']}/estado"


def _on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe(f"{userdata['prefix']}/estado", qos=0)


def _on_message(client, userdata, msg):
    handle_estado(msg.payload)


# One client per process; rebuilt only when the MQTT settings change
_cli = {"key": None, "c": None}
_lock = threading.Lock()


def client():
    cfg = mqtt_config()
    key = (cfg["broker"], cfg["port"], cfg["prefix"], cfg["client_id"])
    with _lock:
        if _cli["key"] != key:
            if _cli["c"] is not None:  # close the previous connection
                try:
                    _cli["c"].loop_stop()
                    _cli["c"].disconnect()
                except Exception:
                    pass
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cfg["client_id"])
            c.user_data_set({"prefix": cfg["prefix"]})
            c.on_connect = _on_connect
            c.on_message = _on_message
            c.reconnect_delay_set(1, 10)
            c.connect_async(cfg["broker"], cfg["port"], keepalive=30)
            c.loop_start()
            _cli.update(key=key, c=c)
    return _cli["c"]


def conectado() -> bool:
    return client().is_connected()


def publicar(payload: dict) -> bool:
    """Publish a command (QoS 0, only if connected, to avoid stale orders)."""
    try:
        c = client()
        if not c.is_connected():
            return False
        return c.publish(topic_cmd(), json.dumps(payload), qos=0).rc == mqtt.MQTT_ERR_SUCCESS
    except Exception:
        return False


# --------------------------------------------------------------------- events
def registrar_evento(toma_id, med, comp, evento, canal=None):
    try:
        hs = hora_sim().strftime(FMT)
    except Exception:
        hs = None
    with db() as con:
        con.execute(
            "INSERT INTO eventos (ts, hora_sim, toma_id, med, comp, evento, canal) "
            "VALUES (?,?,?,?,?,?,?)",
            (datetime.now().strftime(FMT), hs, toma_id, med, comp, evento, canal),
        )


def handle_estado(raw: bytes):
    """Process a message from the ESP32 (runs in the paho thread)."""
    try:
        d = json.loads(raw)
    except ValueError:
        return
    if not isinstance(d, dict) or not d.get("evento"):
        return
    registrar_evento(d.get("id"), d.get("med"), d.get("comp"), d["evento"], d.get("canal"))


def enviar_dispensar(toma: dict, toma_id: str) -> bool:
    ok = publicar(
        {"accion": "dispensar", "id": toma_id, "med": toma["med"], "comp": toma["comp"]}
    )
    registrar_evento(
        toma_id, toma["med"], toma["comp"], "enviada" if ok else "error_envio", "app"
    )
    return ok


def simular_toma(toma: dict) -> bool:
    return enviar_dispensar(toma, f"manual-{uuid.uuid4().hex[:6]}")


def pendiente():
    """Last dose sent that was not yet confirmed or missed."""
    with db() as con:
        row = con.execute(
            "SELECT * FROM eventos WHERE evento='enviada' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        cerrada = con.execute(
            "SELECT 1 FROM eventos WHERE toma_id=? AND evento IN ('confirmada','omitida')",
            (row["toma_id"],),
        ).fetchone()
    return None if cerrada else dict(row)


def ultimo_evento(toma_id: str):
    with db() as con:
        row = con.execute(
            "SELECT evento FROM eventos WHERE toma_id=? AND evento!='enviada' "
            "ORDER BY id DESC LIMIT 1",
            (toma_id,),
        ).fetchone()
    return row["evento"] if row else None


def comando_toma(accion: str) -> bool:
    """Confirm/snooze from the app; the ESP32 answers and that gets logged."""
    p = pendiente()
    if not p:
        return False
    return publicar({"accion": accion, "id": p["toma_id"]})


def estado_dia(dia):
    """Status of every dose for one simulated day (used by the day timeline)."""
    salida = []
    with db() as con:
        for t in get_receta():
            clave = f"{t['id']}@{dia:%Y%m%d}{t['hora'].replace(':', '')}"
            evs = [
                r["evento"]
                for r in con.execute(
                    "SELECT evento FROM eventos WHERE toma_id=? ORDER BY id", (clave,)
                ).fetchall()
            ]
            if "confirmada" in evs:
                estado = "confirmada"
            elif "omitida" in evs:
                estado = "omitida"
            elif evs:
                estado = "en_curso"
            else:
                estado = "sin_disparar"
            salida.append({**t, "estado": estado, "pospuestas": evs.count("pospuesta")})
    return salida


def eventos(solo_finales: bool = True, limite: int = 500):
    filtro = "WHERE evento IN ('confirmada','pospuesta','omitida')" if solo_finales else ""
    with db() as con:
        rows = con.execute(
            f"SELECT hora_sim, ts, med, comp, evento, canal FROM eventos {filtro} "
            f"ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(r) for r in rows]


def reiniciar_demo():
    with db() as con:
        con.execute("DELETE FROM eventos")
        con.execute("DELETE FROM disparos")
    set_clock(_inicio_por_defecto(), get_speed())
