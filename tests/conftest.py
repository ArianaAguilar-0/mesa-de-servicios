"""Configuración común: cada prueba usa una base de datos SQLite temporal."""

import pytest

from solicitudes.app import create_app
from solicitudes.autenticacion import crear_usuario
from solicitudes.repositorio import Repositorio
from solicitudes.servicio import ServicioSolicitudes


@pytest.fixture
def ruta_db(tmp_path):
    return tmp_path / "prueba.db"


@pytest.fixture
def servicio(ruta_db):
    return ServicioSolicitudes(Repositorio(ruta_db))


CONTRASENA_PRUEBA = "clave-de-prueba-123"


@pytest.fixture
def app(ruta_db):
    app = create_app(ruta_db, secret_key="clave-solo-para-pruebas")
    app.config["TESTING"] = True
    crear_usuario(app.extensions["servicio"].repo, "soporte", CONTRASENA_PRUEBA)
    return app


@pytest.fixture
def cliente_anonimo(app):
    """Navegador sin sesión: como un docente o estudiante."""
    return app.test_client()


@pytest.fixture
def cliente(app):
    """Navegador con sesión iniciada como personal de soporte."""
    c = app.test_client()
    c.post("/login", data={"usuario": "soporte", "contrasena": CONTRASENA_PRUEBA})
    return c


@pytest.fixture
def servicio_app(app):
    """El mismo servicio que usa la aplicación web."""
    return app.extensions["servicio"]


@pytest.fixture
def datos_validos():
    return {
        "solicitante": "Ana Pérez",
        "categoria": "redes",
        "descripcion": "No hay conexión a internet en el laboratorio 3.",
        "prioridad": "alta",
    }
