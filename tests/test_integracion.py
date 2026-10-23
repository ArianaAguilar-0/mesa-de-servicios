"""Pruebas de integración: servicio + SQLite y API JSON."""

import sqlite3

import pytest

from solicitudes.errores import ErrorValidacion, SolicitudNoEncontrada
from solicitudes.repositorio import Repositorio
from solicitudes.servicio import ServicioSolicitudes


# --- Persistencia en SQLite ------------------------------------------------

def test_datos_persisten_en_sqlite(servicio, ruta_db, datos_validos):
    codigo = servicio.registrar(datos_validos)["codigo"]

    # Una instancia nueva, sobre el mismo archivo, encuentra la solicitud.
    otra = ServicioSolicitudes(Repositorio(ruta_db))
    guardada = otra.consultar(codigo)
    assert guardada["solicitante"] == "Ana Pérez"
    assert guardada["estado"] == "registrada"

    con = sqlite3.connect(ruta_db)
    fila = con.execute(
        "SELECT categoria, prioridad FROM solicitudes WHERE codigo = ?", (codigo,)
    ).fetchone()
    historial = con.execute("SELECT accion, estado_nuevo FROM historial").fetchall()
    con.close()
    assert fila == ("redes", "alta")
    assert historial == [("registro", "registrada")]


def test_codigos_unicos_en_la_base(servicio, datos_validos):
    codigos = {servicio.registrar(datos_validos)["codigo"] for _ in range(30)}
    assert len(codigos) == 30


def test_consulta_acepta_minusculas_y_espacios(servicio, datos_validos):
    codigo = servicio.registrar(datos_validos)["codigo"]
    assert servicio.consultar(f"  {codigo.lower()}  ")["codigo"] == codigo


def test_consulta_con_codigo_inexistente(servicio):
    with pytest.raises(SolicitudNoEncontrada) as error:
        servicio.consultar("SOL-00000000-000000")
    assert str(error.value) == (
        "No existe ninguna solicitud con el código 'SOL-00000000-000000'. "
        "Verifique que esté bien escrito."
    )


def test_asignar_y_reasignar_tecnico(servicio, datos_validos):
    codigo = servicio.registrar(datos_validos)["codigo"]

    asignada = servicio.asignar_tecnico(codigo, "Luis")
    assert (asignada["estado"], asignada["tecnico"]) == ("asignada", "Luis")

    servicio.cambiar_estado(codigo, "en_proceso")
    reasignada = servicio.asignar_tecnico(codigo, "Marta")
    assert (reasignada["estado"], reasignada["tecnico"]) == ("en_proceso", "Marta")

    ultima = reasignada["historial"][-1]
    assert ultima["accion"] == "asignacion"
    assert ultima["detalle"] == "Técnico reasignado de Luis a Marta."


def test_historial_registra_cada_cambio(servicio, datos_validos):
    codigo = servicio.registrar(datos_validos)["codigo"]
    servicio.asignar_tecnico(codigo, "Luis", usuario="coordinador")
    servicio.cambiar_estado(codigo, "cancelada", "Duplicada")

    historial = servicio.consultar(codigo)["historial"]
    assert [h["accion"] for h in historial] == ["registro", "asignacion", "cambio_estado"]
    assert historial[1]["usuario"] == "coordinador"
    assert historial[2]["estado_anterior"] == "asignada"
    assert historial[2]["estado_nuevo"] == "cancelada"
    assert "Duplicada" in historial[2]["detalle"]
    assert all(h["fecha"] for h in historial)


def test_cambio_e_historial_en_la_misma_transaccion(
    servicio, datos_validos, monkeypatch
):
    codigo = servicio.registrar(datos_validos)["codigo"]

    def fallar(*args):
        raise sqlite3.OperationalError("falla simulada al guardar el historial")

    monkeypatch.setattr(Repositorio, "_insertar_historial", staticmethod(fallar))
    with pytest.raises(sqlite3.OperationalError):
        servicio.asignar_tecnico(codigo, "Luis")
    monkeypatch.undo()

    # El cambio de estado se revirtió junto con el historial.
    solicitud = servicio.consultar(codigo)
    assert solicitud["estado"] == "registrada"
    assert solicitud["tecnico"] is None
    assert len(solicitud["historial"]) == 1


def test_registro_invalido_no_guarda_nada(servicio, datos_validos):
    datos_validos["categoria"] = ""
    with pytest.raises(ErrorValidacion):
        servicio.registrar(datos_validos)
    assert servicio.listar() == []


def test_listar_filtra_por_estado_y_codigo(servicio, datos_validos):
    primera = servicio.registrar(datos_validos)["codigo"]
    segunda = servicio.registrar(datos_validos)["codigo"]
    servicio.asignar_tecnico(segunda, "Luis")

    assert [s["codigo"] for s in servicio.listar("asignada")] == [segunda]
    assert [s["codigo"] for s in servicio.listar(codigo=primera[-6:].lower())] == [primera]
    assert len(servicio.listar()) == 2


# --- API JSON --------------------------------------------------------------

def test_api_registrar_y_consultar(cliente, datos_validos):
    respuesta = cliente.post("/api/solicitudes", json=datos_validos)
    assert respuesta.status_code == 201
    creada = respuesta.get_json()
    assert creada["estado"] == "registrada"

    respuesta = cliente.get(f"/api/solicitudes/{creada['codigo'].lower()}")
    assert respuesta.status_code == 200
    consultada = respuesta.get_json()
    assert consultada["codigo"] == creada["codigo"]
    assert consultada["descripcion"] == datos_validos["descripcion"]
    assert consultada["historial"][0]["accion"] == "registro"


def test_api_datos_incompletos_responde_400(cliente):
    respuesta = cliente.post("/api/solicitudes", json={"solicitante": "Ana"})
    assert respuesta.status_code == 400
    cuerpo = respuesta.get_json()
    assert cuerpo["error"] == "Los datos enviados no son válidos."
    assert set(cuerpo["detalles"]) == {"categoria", "descripcion", "prioridad"}
    assert cuerpo["detalles"]["categoria"] == "Falta la categoría; es un campo obligatorio."


def test_api_cuerpo_que_no_es_json_responde_400(cliente):
    respuesta = cliente.post("/api/solicitudes", data="texto plano")
    assert respuesta.status_code == 400
    assert "cuerpo" in respuesta.get_json()["detalles"]


def test_api_codigo_inexistente_responde_404(cliente):
    respuesta = cliente.get("/api/solicitudes/SOL-NOEXISTE")
    assert respuesta.status_code == 404
    assert respuesta.get_json() == {
        "error": "No existe ninguna solicitud con el código 'SOL-NOEXISTE'. "
        "Verifique que esté bien escrito."
    }


def test_api_asignar_tecnico_y_cambiar_estado(cliente, datos_validos):
    codigo = cliente.post("/api/solicitudes", json=datos_validos).get_json()["codigo"]

    respuesta = cliente.put(f"/api/solicitudes/{codigo}/tecnico", json={"tecnico": "Luis"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "asignada"

    respuesta = cliente.put(f"/api/solicitudes/{codigo}/estado", json={"estado": "cerrada"})
    assert respuesta.status_code == 400
    assert "Desde 'asignada' solo puede pasar a" in respuesta.get_json()["detalles"]["estado"]

    respuesta = cliente.put(f"/api/solicitudes/{codigo}/estado", json={"estado": "en_proceso"})
    assert respuesta.status_code == 200
    assert respuesta.get_json()["estado"] == "en_proceso"

    respuesta = cliente.put("/api/solicitudes/SOL-X/tecnico", json={"tecnico": "Luis"})
    assert respuesta.status_code == 404
