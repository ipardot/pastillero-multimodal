"""Logic tests with a fake MQTT client. Run: python test_core.py"""
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime

logging.getLogger("streamlit").setLevel(logging.ERROR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["PASTILLERO_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import core


class FakeClient:
    """Captures what the app publishes; always 'connected'."""

    def __init__(self):
        self.sent = []

    def is_connected(self):
        return True

    def publish(self, topic, payload, qos=0):
        self.sent.append(json.loads(payload))

        class Info:
            rc = 0

        return Info()


fake = FakeClient()
core.client = lambda: fake
core.init_db()
assert len(core.get_receta()) == 3
print("OK: receta de ejemplo")

# 1) Clock: start 07:58, x600 (1 s real = 10 min simulated)
core.set_clock(datetime(2026, 11, 22, 7, 58), 600)
time.sleep(1.3)
core.tick()
disp = [m for m in fake.sent if m["accion"] == "dispensar"]
assert len(disp) == 1 and disp[0]["med"] == "Vitamina D" and disp[0]["comp"] == 1, disp
core.tick()
core.tick()
assert len(fake.sent) == 1
print("OK: dispara las 08:00 una sola vez")

# 2) Does not fire doses earlier than the start of the window (06:00 < 07:58)
ok, _ = core.add_toma("Vitamina D", "06:00", 1)
assert ok
core.tick()
assert not any(m["id"].endswith("0600") for m in fake.sent), fake.sent
print("OK: no dispara tomas anteriores al inicio")

# 3) Speed change without jumps
a = core.hora_sim()
core.cambiar_velocidad(60)
b = core.hora_sim()
assert abs((b - a).total_seconds()) < 5, (a, b)
print("OK: cambio de velocidad sin saltos")

# 4) Pending dose + ESP32 events + confirm from the app
p = core.pendiente()
assert p and p["med"] == "Vitamina D", p
tid = p["toma_id"]
core.handle_estado(json.dumps({"evento": "dispensado", "id": tid, "med": "Vitamina D", "comp": 1}).encode())
core.handle_estado(json.dumps({"evento": "sonando", "id": tid, "canal": "buzzer"}).encode())
assert core.ultimo_evento(tid) == "sonando"
assert core.comando_toma("confirmar") is True
assert fake.sent[-1] == {"accion": "confirmar", "id": tid}
core.handle_estado(
    json.dumps({"evento": "confirmada", "id": tid, "med": "Vitamina D", "comp": 1, "canal": "app_boton"}).encode()
)
assert core.pendiente() is None
fin = core.eventos(True)
assert len(fin) == 1 and fin[0]["canal"] == "app_boton" and fin[0]["evento"] == "confirmada"
print("OK: confirmar desde la app queda en el historial con su canal")

# 5) Garbage does not break anything
for basura in (b"no es json", b"{}", b"[]", b"null", b'"texto"'):
    core.handle_estado(basura)
assert len(core.eventos(False)) >= 3
print("OK: mensajes basura ignorados")

# 6) Simulated dose + missed
assert core.simular_toma(core.get_receta()[0]) is True
p = core.pendiente()
assert p
core.handle_estado(
    json.dumps({"evento": "omitida", "id": p["toma_id"], "med": p["med"], "comp": p["comp"], "canal": "esp32"}).encode()
)
assert core.pendiente() is None
assert [e["evento"] for e in core.eventos(True)] == ["omitida", "confirmada"]
print("OK: simular toma y omitida")

# 7) Next dose
t, due = core.proxima_toma(datetime(2026, 11, 22, 9, 0))
assert t["med"] == "Omega 3" and due.hour == 12
t, due = core.proxima_toma(datetime(2026, 11, 22, 21, 0))
assert due.day == 23
print("OK: proxima_toma")

# 8) Prescription validation
ok, msg = core.add_toma("Zinc", "08:00", 1)
assert not ok and "08:00" in msg  # one dose per time
ok, msg = core.add_toma("Zinc", "09:00", 2)
assert not ok and "Omega 3" in msg  # compartment 2 already holds Omega 3
ok, msg = core.add_toma("omega 3", "10:00", 3)
assert not ok  # Omega 3 is already in compartment 2
ok, msg = core.add_toma("  ", "10:00", 1)
assert not ok
ok, msg = core.add_toma("Vitamina D", "16:00", 1)  # same medicine, same compartment, other time
assert ok, msg
guia = core.guia_de_carga()
assert guia[0]["med"] == "Vitamina D" and guia[0]["horas"] == "06:00, 08:00, 16:00"
print("OK: validaciones de la receta y guía de carga")

# 8b) Day status for the timeline (08:00 was confirmed in step 4)
dia = datetime(2026, 11, 22).date()
est = {e["med"] + e["hora"]: e["estado"] for e in core.estado_dia(dia)}
assert est["Vitamina D08:00"] == "confirmada" and est["Omega 312:00"] == "sin_disparar", est
seis = [e for e in core.estado_dia(dia) if e["hora"] == "06:00"][0]
tid = f"{seis['id']}@202611220600"
core.registrar_evento(tid, "Vitamina D", 1, "enviada")
core.registrar_evento(tid, "Vitamina D", 1, "omitida", "esp32")
assert [e for e in core.estado_dia(dia) if e["hora"] == "06:00"][0]["estado"] == "omitida"
print("OK: estado del día")

# 9) MQTT settings
core.set_mqtt_config(" broker.test ", 1884, "/eafit/prueba/pastillero/", "cid-1")
cfg = core.mqtt_config()
assert cfg == {"broker": "broker.test", "port": 1884, "prefix": "eafit/prueba/pastillero", "client_id": "cid-1"}
assert core.topic_cmd() == "eafit/prueba/pastillero/cmd"
assert core.topic_estado() == "eafit/prueba/pastillero/estado"
try:
    core.set_mqtt_config("", 1883, "x", "y")
    raise AssertionError("debió fallar con broker vacío")
except ValueError:
    pass
print("OK: configuración MQTT")

# 10) Reset
core.reiniciar_demo()
assert core.eventos(False) == []
print("OK: reiniciar demo")

print("\nTODAS LAS PRUEBAS PASARON")
