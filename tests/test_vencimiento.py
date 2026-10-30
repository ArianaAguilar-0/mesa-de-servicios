"""Pruebas del requisito de vencimiento (versión 1.1) y de los defectos corregidos.

Una solicitud de prioridad crítica que no pasa a "en_proceso" dentro de 4 horas
desde su registro se marca como vencida. Se usa un reloj simulado para no esperar.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from solicitudes.app import create_app
from solicitudes.autenticacion import crear_usuario
from solicitudes.repositorio import Repositorio
from solicitudes.servicio import ServicioSolicitudes


class Reloj:
    def __init__(self):
        self.momento = datetime(2026, 10, 29, 8, 0, 0)

    def __call__(self):
        return self.momento

    def avanzar(self, **kwargs):
        self.momento += timedelta(**kwargs)


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def servicio_reloj(ruta_db, reloj):
    return ServicioSolicitudes(Repositorio(ruta_db), reloj=reloj)


def _registrar(servicio, datos_validos, prioridad="critica"):
    return servicio.registrar({**datos_validos, "prioridad": prioridad})["codigo"]


def test_critica_sin_atender_4_horas_queda_vencida(servicio_reloj, reloj, datos_validos):
    codigo = _registrar(servicio_reloj, datos_validos)
    reloj.avanzar(hours=4)
    s = servicio_reloj.consultar(codigo)
    assert s["vencida_en"] == "2026-10-29 12:00:00"
    assert s["historial"][-1]["accion"] == "vencimiento"
    assert s["historial"][-1]["usuario"] == "sistema"


def test_critica_antes_de_4_horas_no_vence(servicio_reloj, reloj, datos_validos):
    codigo = _registrar(servicio_reloj, datos_validos)
    reloj.avanzar(hours=3, minutes=59, seconds=59)
    assert servicio_reloj.consultar(codigo)["vencida_en"] is None


def test_critica_asignada_pero_no_atendida_tambien_vence(servicio_reloj, reloj, datos_validos):
    codigo = _registrar(servicio_reloj, datos_validos)
    servicio_reloj.asignar_tecnico(codigo, "Luis")
    reloj.avanzar(hours=5)
    assert servicio_reloj.consultar(codigo)["vencida_en"] is not None


def test_critica_atendida_a_tiempo_no_vence(servicio_reloj, reloj, datos_validos):
    codigo = _registrar(servicio_reloj, datos_validos)
    servicio_reloj.asignar_tecnico(codigo, "Luis")
    reloj.avanzar(hours=2)
    servicio_reloj.cambiar_estado(codigo, "en_proceso")
    reloj.avanzar(hours=10)
    assert servicio_reloj.consultar(codigo)["vencida_en"] is None


@pytest.mark.parametrize("prioridad", ["baja", "media", "alta"])
def test_otras_prioridades_no_vencen(servicio_reloj, reloj, datos_validos, prioridad):
    codigo = _registrar(servicio_reloj, datos_validos, prioridad)
    reloj.avanzar(hours=24)
    assert servicio_reloj.consultar(codigo)["vencida_en"] is None


def test_vencimiento_se_conserva_y_se_registra_una_sola_vez(servicio_reloj, reloj, datos_validos):
    codigo = _registrar(servicio_reloj, datos_validos)
    reloj.avanzar(hours=6)
    servicio_reloj.asignar_tecnico(codigo, "Luis")
    servicio_reloj.cambiar_estado(codigo, "en_proceso")
    servicio_reloj.listar()
    s = servicio_reloj.consultar(codigo)
    assert s["vencida_en"] == "2026-10-29 12:00:00"  # sigue marcada aunque ya se atiende
    assert [h["accion"] for h in s["historial"]].count("vencimiento") == 1


def test_listar_solo_vencidas(servicio_reloj, reloj, datos_validos):
    vencida = _registrar(servicio_reloj, datos_validos)
    reloj.avanzar(hours=5)
    _registrar(servicio_reloj, datos_validos)  # crítica nueva, todavía en plazo
    codigos = [s["codigo"] for s in servicio_reloj.listar(solo_vencidas=True)]
    assert codigos == [vencida]


def test_base_de_datos_anterior_se_migra(ruta_db):
    """Una base creada con la versión 1.0 (sin columna vencida_en) sigue funcionando."""
    con = sqlite3.connect(ruta_db)
    con.executescript(
        """CREATE TABLE solicitudes (id INTEGER PRIMARY KEY AUTOINCREMENT,
           codigo TEXT NOT NULL UNIQUE, solicitante TEXT NOT NULL, categoria TEXT NOT NULL,
           descripcion TEXT NOT NULL, prioridad TEXT NOT NULL, estado TEXT NOT NULL,
           tecnico TEXT, fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL);"""
    )
    con.close()
    Repositorio(ruta_db)
    con = sqlite3.connect(ruta_db)
    columnas = {f[1] for f in con.execute("PRAGMA table_info(solicitudes)")}
    con.close()
    assert "vencida_en" in columnas


def test_panel_de_soporte_muestra_vencidas(ruta_db, reloj, datos_validos):
    app = create_app(ruta_db, secret_key="clave-solo-para-pruebas")
    servicio = app.extensions["servicio"]
    servicio._reloj = reloj
    codigo = _registrar(servicio, datos_validos)
    reloj.avanzar(hours=4, minutes=30)
    crear_usuario(servicio.repo, "soporte", "clave-de-prueba-123")
    cliente = app.test_client()
    cliente.post("/login", data={"usuario": "soporte", "contrasena": "clave-de-prueba-123"})
    html = cliente.get("/soporte?vencidas=1").get_data(as_text=True)
    assert codigo in html and "Vencida" in html
    assert "Vencida desde" in cliente.get(f"/soporte/{codigo}").get_data(as_text=True)


# --- Defectos corregidos en la versión 1.1 -----------------------------------

def test_def01_api_no_permite_elegir_el_usuario_del_historial(cliente, datos_validos):
    codigo = cliente.post("/api/solicitudes", json=datos_validos).get_json()["codigo"]
    r = cliente.put(f"/api/solicitudes/{codigo}/tecnico", json={"tecnico": "Luis", "usuario": "Rector"})
    assert r.get_json()["historial"][-1]["usuario"] == "soporte"


def test_def02_mismo_tecnico_con_otras_mayusculas_no_es_reasignacion(servicio, datos_validos):
    codigo = servicio.registrar(datos_validos)["codigo"]
    servicio.asignar_tecnico(codigo, "Luis")
    with pytest.raises(Exception) as error:
        servicio.asignar_tecnico(codigo, "luis")
    assert "ya está asignada" in str(error.value.detalles["tecnico"])
