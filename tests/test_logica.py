"""Pruebas de lógica con un cliente MQTT falso. Ejecutar: python -m pytest tests/ -v"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import core  # noqa: E402

T = 1_800_000_000.0  # instante real de referencia


class FakeClient:
    def __init__(self, conectado=True):
        self.conectado = conectado
        self.mensajes = []

    def is_connected(self):
        return self.conectado

    def publish(self, topic, payload, qos=0):
        self.mensajes.append((topic, json.loads(payload), qos))

        class Info:
            rc = 0

        return Info()

    def dispensados(self):
        return [m for _, m, _ in self.mensajes if m["accion"] == "dispensar"]


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", str(tmp_path / "test.db"))
    core.init_db()
    yield


def dt(h, m, s=0, dia=18):
    return datetime(2026, 11, dia, h, m, s)


def eventos(tipo=None):
    import sqlite3

    con = sqlite3.connect(core.DB_PATH)
    con.row_factory = sqlite3.Row
    q = "SELECT * FROM eventos" + (" WHERE evento=?" if tipo else "") + " ORDER BY id"
    filas = [dict(r) for r in con.execute(q, (tipo,) if tipo else ())]
    con.close()
    return filas


def test_receta_de_ejemplo():
    meds = [(r["med"], r["hora"], r["comp"]) for r in core.listar_receta()]
    assert meds == core.RECETA_EJEMPLO


def test_tick_dispara_0800_una_sola_vez():
    c = FakeClient()
    core.fijar_hora(dt(7, 59), ahora_real=T)
    core.set_velocidad(60, ahora_real=T)
    for k in range(1, 31):              # 30 s reales = 30 min simulados
        core.tick(c, ahora_real=T + k)
    core.tick(c, ahora_real=T + 30)     # repetir el mismo instante
    core.tick(c, ahora_real=T + 30)
    d = c.dispensados()
    assert len(d) == 1
    assert d[0]["med"] == "Vitamina D" and d[0]["comp"] == 1
    assert d[0]["id"].startswith("2026-11-18T08:00")
    assert c.mensajes[0][0] == f"{core.PREFIX}/cmd" and c.mensajes[0][2] == 0
    assert len(eventos("enviada")) == 1


def test_tick_justo_en_la_hora_y_ventana_semiabierta():
    c = FakeClient()
    core.fijar_hora(dt(7, 59, 59), ahora_real=T)
    core.tick(c, ahora_real=T + 1)      # llega exactamente a 08:00:00 -> dispara
    assert len(c.dispensados()) == 1
    core.fijar_hora(dt(8, 0, 0), ahora_real=T + 2)  # ventana empieza EN 08:00 (abierta)
    core.tick(c, ahora_real=T + 3)
    assert len(c.dispensados()) == 1


def test_no_dispara_tomas_anteriores_al_inicio():
    c = FakeClient()
    core.fijar_hora(dt(8, 30), ahora_real=T)   # ya pasó la de 08:00
    core.set_velocidad(600, ahora_real=T)
    for k in range(1, 19):                      # avanza hasta 11:30
        core.tick(c, ahora_real=T + k)
    assert c.dispensados() == []
    assert core.hora_simulada(T + 18) == dt(11, 30)


def test_cambiar_velocidad_no_produce_saltos():
    core.fijar_hora(dt(10, 0), ahora_real=T)
    core.set_velocidad(600, ahora_real=T)
    antes = core.hora_simulada(T + 10)
    assert antes == dt(11, 40)
    last = core.kv_get("sim_last")
    core.set_velocidad(1, ahora_real=T + 10)
    assert core.hora_simulada(T + 10) == antes             # sin salto
    assert core.hora_simulada(T + 11) == antes + timedelta(seconds=1)
    assert core.kv_get("sim_last") == last                 # la ventana no se reinicia
    core.set_velocidad(300, ahora_real=T + 11)
    assert core.hora_simulada(T + 11) == antes + timedelta(seconds=1)


def test_cambio_de_velocidad_no_pierde_tomas():
    c = FakeClient()
    core.fijar_hora(dt(11, 58), ahora_real=T)
    core.set_velocidad(1, ahora_real=T)
    core.tick(c, ahora_real=T + 1)
    core.set_velocidad(600, ahora_real=T + 1)
    core.tick(c, ahora_real=T + 2)                         # 11:58:01 -> 12:08:01
    assert [d["med"] for d in c.dispensados()] == ["Omega 3"]


def test_cruza_medianoche_sin_duplicar():
    c = FakeClient()
    core.fijar_hora(dt(19, 59), ahora_real=T)
    core.set_velocidad(600, ahora_real=T)
    for k in range(1, 75):                                 # ~12.3 h simuladas
        core.tick(c, ahora_real=T + k)
    meds = [d["med"] for d in c.dispensados()]
    assert meds == ["Vitamina C", "Vitamina D"]
    assert c.dispensados()[1]["id"].startswith("2026-11-19T08:00")


def test_app_cerrada_mucho_tiempo_no_dispara_rafaga():
    c = FakeClient()
    core.fijar_hora(dt(7, 0), ahora_real=T)
    core.tick(c, ahora_real=T + 1)
    core.tick(c, ahora_real=T + 6 * 3600)                  # 6 h después (pasó 08:00 y 12:00)
    assert c.dispensados() == []
    core.tick(c, ahora_real=T + 6 * 3600 + 1)
    assert c.dispensados() == []


def test_confirmada_del_esp32_cierra_pendiente_y_va_al_historial():
    c = FakeClient()
    core.fijar_hora(dt(7, 59, 59), ahora_real=T)
    core.tick(c, ahora_real=T + 1)
    toma = core.toma_pendiente()
    assert toma and toma["med"] == "Vitamina D" and toma["estado"] == "enviada"
    tid = toma["id"]

    assert core.procesar_estado(json.dumps(
        {"evento": "dispensado", "id": tid, "med": "Vitamina D", "comp": 1, "canal": "esp32"}))
    assert core.procesar_estado(json.dumps(
        {"evento": "sonando", "id": tid, "med": "Vitamina D", "comp": 1, "canal": "buzzer"}).encode())
    assert core.toma_pendiente()["estado"] == "sonando"

    assert core.procesar_estado(json.dumps(
        {"evento": "confirmada", "id": tid, "med": "Vitamina D", "comp": 1, "canal": "pulsador_fisico"}))
    assert core.toma_pendiente() is None
    h = core.historial()
    assert len(h) == 1
    assert h[0]["evento"] == "confirmada" and h[0]["canal"] == "pulsador_fisico" and h[0]["med"] == "Vitamina D"


def test_omitida_cierra_y_pospuesta_no():
    c = FakeClient()
    core.simular_toma_ahora(c, core.listar_receta()[0]["id"])
    tid = c.dispensados()[0]["id"]
    core.procesar_estado(json.dumps({"evento": "pospuesta", "id": tid, "canal": "app_boton"}))
    assert core.toma_pendiente()["estado"] == "pospuesta"
    core.procesar_estado(json.dumps({"evento": "omitida", "id": tid, "canal": "esp32"}))
    assert core.toma_pendiente() is None
    assert [e["evento"] for e in core.historial()] == ["omitida", "pospuesta"]


@pytest.mark.parametrize("basura", [
    b"\xff\xfe", "no es json", "[]", "123", "null", "", None,
    '{"evento":"hackeo","id":"x"}', '{"evento":"confirmada"}', '{"evento":"confirmada","id":5}',
    '{"sin":"evento"}',
])
def test_json_basura_no_rompe(basura):
    assert core.procesar_estado(basura) is False
    assert eventos() == []


def test_online_sin_id_se_registra():
    assert core.procesar_estado('{"evento":"online","canal":"esp32"}')
    assert core.ultimo_online() is not None
    assert core.toma_pendiente() is None


def test_desconectado_no_publica():
    c = FakeClient(conectado=False)
    core.fijar_hora(dt(7, 59, 59), ahora_real=T)
    core.tick(c, ahora_real=T + 1)
    assert c.mensajes == []
    assert len(eventos("sin_conexion")) == 1
    assert core.toma_pendiente() is None
    assert core.publicar(None, {"accion": "confirmar", "id": "x"}) is False


def test_validacion_receta():
    with pytest.raises(ValueError):
        core.agregar_receta("   ", "08:00", 1)
    with pytest.raises(ValueError):
        core.agregar_receta("Zinc", "08:00", 4)
    core.agregar_receta(" Zinc ", "09:15", 2)
    assert any(r["med"] == "Zinc" and r["hora"] == "09:15" for r in core.listar_receta())


def test_reiniciar_demo():
    c = FakeClient()
    core.simular_toma_ahora(c, core.listar_receta()[0]["id"])
    core.reiniciar_demo()
    assert eventos() == [] and core.toma_pendiente() is None


def test_on_message_del_cliente_real_registra_en_sqlite(monkeypatch):
    """El callback de paho (sin red) escribe en SQLite."""
    monkeypatch.setattr(core, "BROKER", "127.0.0.1")
    monkeypatch.setattr(core, "PORT", 1)
    cli = core.crear_cliente()
    try:
        class Msg:
            payload = b'{"evento":"online","canal":"esp32"}'
        cli.on_message(cli, None, Msg())
        assert len(eventos("online")) == 1
        assert cli.is_connected() is False
        assert core.publicar(cli, {"accion": "confirmar", "id": "x"}) is False
    finally:
        cli.loop_stop()
