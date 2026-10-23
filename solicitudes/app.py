"""Aplicación web de la mesa de servicio.

Ejecutar con: python -m solicitudes.app
"""

import os
import secrets

from flask import Flask, flash, redirect, render_template, request, url_for

from .errores import ErrorValidacion, SolicitudNoEncontrada
from .repositorio import Repositorio
from .servicio import ServicioSolicitudes
from .validacion import CATEGORIAS, PRIORIDADES

ETIQUETAS = {
    "registrada": "Registrada",
    "asignada": "Asignada",
    "en_proceso": "En proceso",
    "resuelta": "Resuelta",
    "cerrada": "Cerrada",
    "cancelada": "Cancelada",
    "hardware": "Hardware (equipos, impresoras)",
    "software": "Software (programas, sistemas)",
    "redes": "Redes (internet, wifi)",
    "accesos": "Accesos (cuentas, contraseñas)",
    "otro": "Otro",
    "baja": "Baja",
    "media": "Media",
    "alta": "Alta",
    "critica": "Crítica",
    "registro": "Registro",
    "asignacion": "Asignación",
    "cambio_estado": "Cambio de estado",
}


def create_app(ruta_db=None, secret_key=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = (
        secret_key or os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    )
    app.json.ensure_ascii = False

    ruta_db = ruta_db or os.environ.get("SOLICITUDES_DB") or "solicitudes.db"
    servicio = ServicioSolicitudes(Repositorio(ruta_db))
    app.extensions["servicio"] = servicio

    @app.template_filter("etiqueta")
    def etiqueta(valor):
        return ETIQUETAS.get(valor, valor or "")

    @app.context_processor
    def opciones():
        return {"CATEGORIAS": CATEGORIAS, "PRIORIDADES": PRIORIDADES}

    @app.get("/")
    def inicio():
        return render_template("inicio.html")

    _rutas_portal(app, servicio)
    return app


def _rutas_portal(app, servicio):
    def mostrar_portal(datos=None, errores=None, estado_http=200):
        codigo = request.args.get("codigo")
        solicitud = error_consulta = None
        if codigo is not None:
            try:
                solicitud = servicio.consultar(codigo)
            except ErrorValidacion as e:
                error_consulta = e.detalles["codigo"]
            except SolicitudNoEncontrada as e:
                error_consulta, estado_http = str(e), 404
        html = render_template(
            "portal.html",
            datos=datos or {},
            errores=errores or {},
            codigo=codigo or "",
            solicitud=solicitud,
            error_consulta=error_consulta,
        )
        return html, estado_http

    @app.get("/portal")
    def portal():
        return mostrar_portal()

    @app.post("/portal")
    def portal_registrar():
        try:
            solicitud = servicio.registrar(request.form)
        except ErrorValidacion as e:
            return mostrar_portal(request.form, e.detalles, 400)
        flash(solicitud["codigo"], "registrada")
        return redirect(url_for("portal", codigo=solicitud["codigo"]))


def main():
    puerto = int(os.environ.get("SOLICITUDES_PORT") or 5000)
    create_app().run(host="127.0.0.1", port=puerto)


if __name__ == "__main__":
    main()
