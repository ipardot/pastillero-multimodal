"""Smoke tests de app.py y las 3 páginas con streamlit.testing.v1.AppTest (rutas absolutas).

El broker apunta a 127.0.0.1:1 para no depender de la red: la app debe funcionar
mostrando "MQTT desconectado".
"""

import json
import os
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))


@pytest.fixture(autouse=True)
def entorno(tmp_path, monkeypatch):
    import core

    db = str(tmp_path / "smoke.db")
    monkeypatch.setenv("PASTILLERO_DB", db)
    monkeypatch.setattr(core, "DB_PATH", db)
    monkeypatch.setattr(core, "BROKER", "127.0.0.1")
    monkeypatch.setattr(core, "PORT", 1)
    core.get_client.clear()
    yield core
    core.get_client.clear()


def correr(ruta):
    at = AppTest.from_file(str(APP / ruta), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def textos(at):
    partes = [m.value for m in at.markdown] + [m.value for m in at.caption]
    for tipo in (at.success, at.warning, at.info, at.error):
        partes += [m.value for m in tipo]
    return "\n".join(partes)


def test_app_principal(entorno):
    at = correr("app.py")
    assert "Sin tomas pendientes" in textos(at)
    assert "MQTT desconectado" in textos(at)
    assert [m.label for m in at.sidebar.metric] == ["Hora simulada"]
    assert at.sidebar.selectbox(key="vel").options == ["x1", "x60", "x300", "x600"]
    # cambiar velocidad, simular toma y reiniciar sin excepciones
    at.sidebar.selectbox(key="vel").set_value(600).run()
    assert not at.exception and entorno.velocidad() == 600
    next(b for b in at.sidebar.button if b.label == "Simular toma ahora").click().run()
    assert not at.exception
    assert "la orden no se envió" in textos(at)
    next(b for b in at.sidebar.button if b.label == "Fijar hora").click().run()
    assert not at.exception
    next(b for b in at.sidebar.button if b.label == "Reiniciar demo").click().run()
    assert not at.exception


def test_dia_a_dia_con_toma_pendiente(entorno):
    entorno.init_db()
    entorno.registrar_evento("enviada", "t1", "Omega 3", 2, "app")
    entorno.procesar_estado(json.dumps({"evento": "sonando", "id": "t1", "canal": "buzzer"}))
    at = correr("views/dia_a_dia.py")
    t = textos(at)
    assert "Omega 3" in t and "sonando" in t
    etiquetas = [b.label for b in at.button]
    assert "✅ Ya la tomé" in etiquetas and "⏰ Posponer" in etiquetas
    next(b for b in at.button if b.label == "✅ Ya la tomé").click().run()
    assert not at.exception
    assert "Sin conexión MQTT" in textos(at)
    assert len(at.dataframe) == 1


def test_dia_a_dia_sin_pendientes(entorno):
    at = correr("views/dia_a_dia.py")
    assert "Sin tomas pendientes" in textos(at) and "Próxima toma" in textos(at)


def test_configuracion(entorno):
    at = correr("views/configuracion.py")
    n0 = len(entorno.listar_receta())
    at.text_input[0].set_value("   ")
    at.button[0].click().run()          # submit del formulario
    assert not at.exception
    assert any("nombre" in e.value for e in at.error)
    assert len(entorno.listar_receta()) == n0

    at.text_input[0].set_value("Magnesio")
    at.button[0].click().run()
    assert not at.exception
    assert len(entorno.listar_receta()) == n0 + 1

    borrar = [b for b in at.button if b.label == "🗑️"]
    assert len(borrar) == n0 + 1
    borrar[0].click().run()
    assert not at.exception
    assert len(entorno.listar_receta()) == n0


def test_historial(entorno):
    entorno.init_db()
    entorno.registrar_evento("enviada", "t1", "Vitamina D", 1, "app")
    entorno.procesar_estado(json.dumps(
        {"evento": "confirmada", "id": "t1", "med": "Vitamina D", "comp": 1, "canal": "app_boton"}))
    at = correr("views/historial.py")
    assert "el sistema no verifica que se haya ingerido" in textos(at)
    assert [m.value for m in at.metric] == ["1", "0", "0"]
    df = at.dataframe[0].value
    assert list(df.columns) == ["Hora simulada", "Medicamento", "Comp.", "Estado", "Canal"]
    assert df.iloc[0]["Estado"] == "Confirmada" and df.iloc[0]["Canal"] == "app_boton"
    at.multiselect[0].set_value(["omitida"]).run()
    assert not at.exception


def test_sin_use_container_width():
    for f in [APP / "app.py", *(APP / "views").glob("*.py")]:
        assert "use_container_width" not in f.read_text(encoding="utf-8")
