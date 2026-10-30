"""Pruebas del inicio de sesión del personal de soporte (versión 1.1)."""

import sqlite3

import pytest

from solicitudes.autenticacion import crear_usuario, verificar
from solicitudes.errores import ErrorValidacion
from solicitudes.usuarios import main as comando_usuarios


def test_panel_de_soporte_exige_iniciar_sesion(cliente_anonimo):
    r = cliente_anonimo.get("/soporte")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_api_de_gestion_exige_sesion(cliente_anonimo, datos_validos):
    codigo = cliente_anonimo.post("/api/solicitudes", json=datos_validos).get_json()["codigo"]
    r = cliente_anonimo.put(f"/api/solicitudes/{codigo}/tecnico", json={"tecnico": "Luis"})
    assert r.status_code == 401
    r = cliente_anonimo.put(f"/api/solicitudes/{codigo}/estado", json={"estado": "cancelada"})
    assert r.status_code == 401


def test_portal_sigue_abierto_para_solicitantes(cliente_anonimo, datos_validos):
    assert cliente_anonimo.get("/portal").status_code == 200
    r = cliente_anonimo.post("/api/solicitudes", json=datos_validos)
    assert r.status_code == 201
    assert cliente_anonimo.get(f"/api/solicitudes/{r.get_json()['codigo']}").status_code == 200


def test_contrasena_incorrecta_no_inicia_sesion(cliente_anonimo):
    r = cliente_anonimo.post("/login", data={"usuario": "soporte", "contrasena": "equivocada"})
    assert r.status_code == 401
    assert "Usuario o contraseña incorrectos." in r.get_data(as_text=True)
    assert cliente_anonimo.get("/soporte").status_code == 302


def test_usuario_inexistente_da_el_mismo_mensaje(cliente_anonimo):
    r = cliente_anonimo.post("/login", data={"usuario": "nadie", "contrasena": "lo-que-sea-123"})
    assert r.status_code == 401
    assert "Usuario o contraseña incorrectos." in r.get_data(as_text=True)


def test_login_correcto_y_el_historial_registra_al_usuario_real(app, cliente_anonimo, datos_validos):
    crear_usuario(app.extensions["servicio"].repo, "maria", "contrasena-segura")
    r = cliente_anonimo.post(
        "/login", data={"usuario": "Maria", "contrasena": "contrasena-segura", "siguiente": "/soporte"}
    )
    assert r.status_code == 302 and r.headers["Location"].endswith("/soporte")
    codigo = cliente_anonimo.post("/api/solicitudes", json=datos_validos).get_json()["codigo"]
    s = cliente_anonimo.put(f"/api/solicitudes/{codigo}/tecnico", json={"tecnico": "Luis"}).get_json()
    assert s["historial"][-1]["usuario"] == "maria"


def test_cerrar_sesion(cliente):
    assert cliente.get("/soporte").status_code == 200
    cliente.post("/logout")
    assert cliente.get("/soporte").status_code == 302


def test_no_redirige_a_sitios_externos(cliente_anonimo):
    r = cliente_anonimo.post(
        "/login",
        data={"usuario": "soporte", "contrasena": "clave-de-prueba-123", "siguiente": "//sitio-malicioso.com"},
    )
    assert r.headers["Location"].endswith("/soporte")


def test_la_contrasena_no_se_guarda_en_texto_plano(app, ruta_db):
    con = sqlite3.connect(ruta_db)
    guardado = con.execute("SELECT hash_contrasena FROM usuarios_soporte WHERE usuario='soporte'").fetchone()[0]
    con.close()
    assert "clave-de-prueba-123" not in guardado


@pytest.mark.parametrize(
    "usuario, contrasena, campo",
    [("ab", "contrasena-larga", "usuario"), ("con espacio", "contrasena-larga", "usuario"),
     ("valido", "corta", "contrasena"), ("soporte", "contrasena-larga", "usuario")],
)
def test_crear_usuario_valida_los_datos(app, usuario, contrasena, campo):
    with pytest.raises(ErrorValidacion) as error:
        crear_usuario(app.extensions["servicio"].repo, usuario, contrasena)
    assert campo in error.value.detalles


def test_verificar_ignora_mayusculas_en_el_usuario(app):
    assert verificar(app.extensions["servicio"].repo, " SOPORTE ", "clave-de-prueba-123") == "soporte"


def test_comando_para_crear_usuarios(ruta_db, monkeypatch, capsys):
    monkeypatch.setenv("SOLICITUDES_DB", str(ruta_db))
    monkeypatch.setattr("solicitudes.usuarios.getpass", lambda _: "contrasena-nueva")
    assert comando_usuarios(["crear", "tecnico1"]) == 0
    assert comando_usuarios(["listar"]) == 0
    assert "tecnico1" in capsys.readouterr().out
