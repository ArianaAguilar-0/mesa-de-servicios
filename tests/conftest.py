"""Configuración común: cada prueba usa una base de datos SQLite temporal."""

import pytest

from solicitudes.app import create_app
from solicitudes.repositorio import Repositorio
from solicitudes.servicio import ServicioSolicitudes


@pytest.fixture
def ruta_db(tmp_path):
    return tmp_path / "prueba.db"


@pytest.fixture
def servicio(ruta_db):
    return ServicioSolicitudes(Repositorio(ruta_db))


@pytest.fixture
def app(ruta_db):
    app = create_app(ruta_db, secret_key="clave-solo-para-pruebas")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def cliente(app):
    return app.test_client()


@pytest.fixture
def datos_validos():
    return {
        "solicitante": "Ana Pérez",
        "categoria": "redes",
        "descripcion": "No hay conexión a internet en el laboratorio 3.",
        "prioridad": "alta",
    }
