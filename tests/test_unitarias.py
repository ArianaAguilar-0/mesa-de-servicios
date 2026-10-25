"""Pruebas unitarias: validación, código y reglas de estado."""

import re
from datetime import date

import pytest

from solicitudes.codigo import es_codigo_valido, generar_codigo, normalizar_codigo
from solicitudes.errores import ErrorValidacion
from solicitudes.validacion import (
    TRANSICIONES,
    validar_solicitud,
    validar_transicion,
)


# --- Validación de datos ---------------------------------------------------

def test_validacion_correcta_devuelve_datos_limpios():
    datos = validar_solicitud(
        {
            "solicitante": "  Ana Pérez ",
            "categoria": " Hardware",
            "descripcion": "  La impresora no imprime.  ",
            "prioridad": "MEDIA ",
        }
    )
    assert datos == {
        "solicitante": "Ana Pérez",
        "categoria": "hardware",
        "descripcion": "La impresora no imprime.",
        "prioridad": "media",
    }


def test_datos_incompletos_informa_todos_los_errores_a_la_vez():
    with pytest.raises(ErrorValidacion) as error:
        validar_solicitud({"descripcion": "corta"})

    detalles = error.value.detalles
    assert set(detalles) == {"solicitante", "categoria", "descripcion", "prioridad"}
    assert detalles["categoria"] == "Falta la categoría; es un campo obligatorio."
    assert detalles["descripcion"] == (
        "La descripción es muy corta; escriba al menos 10 caracteres "
        "explicando el problema."
    )


def test_datos_vacios_o_ausentes():
    with pytest.raises(ErrorValidacion) as error:
        validar_solicitud(None)
    assert len(error.value.detalles) == 4


def test_categoria_y_prioridad_invalidas(datos_validos):
    datos_validos.update(categoria="impresoras", prioridad="urgente")
    with pytest.raises(ErrorValidacion) as error:
        validar_solicitud(datos_validos)

    detalles = error.value.detalles
    assert set(detalles) == {"categoria", "prioridad"}
    assert "'impresoras' no es válida" in detalles["categoria"]
    assert "hardware, software, redes, accesos, otro" in detalles["categoria"]
    assert "baja, media, alta, critica" in detalles["prioridad"]


@pytest.mark.parametrize(
    "campo, valor, valido",
    [
        ("descripcion", "x" * 9, False),
        ("descripcion", "x" * 10, True),
        ("descripcion", "x" * 1000, True),
        ("descripcion", "x" * 1001, False),
        ("solicitante", "x" * 100, True),
        ("solicitante", "x" * 101, False),
    ],
    ids=[
        "descripcion-9-caracteres",
        "descripcion-10-caracteres",
        "descripcion-1000-caracteres",
        "descripcion-1001-caracteres",
        "solicitante-100-caracteres",
        "solicitante-101-caracteres",
    ],
)
def test_limites_de_longitud(datos_validos, campo, valor, valido):
    datos_validos[campo] = valor
    if valido:
        assert validar_solicitud(datos_validos)[campo] == valor
    else:
        with pytest.raises(ErrorValidacion) as error:
            validar_solicitud(datos_validos)
        assert set(error.value.detalles) == {campo}


# --- Código de solicitud ---------------------------------------------------

def test_formato_del_codigo():
    codigo = generar_codigo(lambda c: False, fecha=date(2026, 10, 22))
    assert re.fullmatch(r"SOL-20261022-[0-9A-F]{6}", codigo)
    assert es_codigo_valido(codigo)


def test_codigo_unico_reintenta_si_ya_existe():
    probados = []

    def existe(codigo):
        probados.append(codigo)
        return len(probados) < 3  # los dos primeros "ya existen"

    codigo = generar_codigo(existe)
    assert len(probados) == 3
    assert codigo == probados[-1]


def test_codigo_falla_si_no_encuentra_uno_libre():
    with pytest.raises(RuntimeError):
        generar_codigo(lambda c: True)


def test_normalizar_codigo_acepta_minusculas_y_espacios():
    assert normalizar_codigo("  sol-20261022-ab12cd \n") == "SOL-20261022-AB12CD"


# --- Transiciones de estado ------------------------------------------------

def test_transicion_no_permitida():
    with pytest.raises(ErrorValidacion) as error:
        validar_transicion("registrada", "cerrada", None, "listo")
    assert error.value.detalles["estado"] == (
        "No se puede cambiar de 'registrada' a 'cerrada'. "
        "Desde 'registrada' solo puede pasar a: asignada, cancelada."
    )


@pytest.mark.parametrize(
    "actual, nuevo",
    [(a, n) for a, destinos in TRANSICIONES.items() for n in destinos],
)
def test_transiciones_permitidas(actual, nuevo):
    assert validar_transicion(actual, nuevo, "Luis", "Comentario")[0] == nuevo


@pytest.mark.parametrize("final", ["cerrada", "cancelada"])
def test_estados_finales_no_admiten_cambios(final):
    with pytest.raises(ErrorValidacion) as error:
        validar_transicion(final, "en_proceso", "Luis", "")
    assert "ya no admite cambios" in error.value.detalles["estado"]


def test_estado_desconocido():
    with pytest.raises(ErrorValidacion) as error:
        validar_transicion("asignada", "pausada", "Luis", "")
    assert "'pausada' no es válido" in error.value.detalles["estado"]


def test_requiere_tecnico_asignado():
    with pytest.raises(ErrorValidacion) as error:
        validar_transicion("registrada", "asignada", None, "")
    assert "primero asigne un técnico" in error.value.detalles["tecnico"]


def test_comentario_obligatorio_al_cerrar():
    with pytest.raises(ErrorValidacion) as error:
        validar_transicion("resuelta", "cerrada", "Luis", "   ")
    assert error.value.detalles == {
        "comentario": "Para cerrar la solicitud escriba un comentario que "
        "explique cómo se resolvió."
    }


@pytest.mark.parametrize(
    "actual, nuevo",
    [
        ("registrada", "cancelada"),
        ("asignada", "en_proceso"),
        ("en_proceso", "resuelta"),
        ("resuelta", "en_proceso"),
    ],
)
def test_comentario_opcional_en_los_demas_casos(actual, nuevo):
    assert validar_transicion(actual, nuevo, "Luis", None) == (nuevo, "")

def test_fallo_intencionSSal():
    assert False, "Prueba que falla a propósito para comprobar el bloqueo del pipeline"