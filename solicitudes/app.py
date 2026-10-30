"""Aplicación web de la mesa de servicio.

Ejecutar con: python -m solicitudes.app
"""

import os
import secrets

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from .errores import ErrorValidacion, SolicitudNoEncontrada
from .repositorio import Repositorio
from .servicio import ServicioSolicitudes
from .validacion import CATEGORIAS, ESTADOS, PRIORIDADES, estados_permitidos

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
    "vencimiento": "Vencimiento",
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
        return {
            "CATEGORIAS": CATEGORIAS,
            "PRIORIDADES": PRIORIDADES,
            "ESTADOS": ESTADOS,
        }

    @app.get("/")
    def inicio():
        return render_template("inicio.html")

    _rutas_portal(app, servicio)
    _rutas_soporte(app, servicio)
    _rutas_api(app, servicio)
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


def _rutas_soporte(app, servicio):
    @app.get("/soporte")
    def soporte():
        estado = request.args.get("estado", "")
        codigo = request.args.get("codigo", "")
        vencidas = request.args.get("vencidas") == "1"
        return render_template(
            "soporte.html",
            solicitudes=servicio.listar(estado, codigo, vencidas),
            estado=estado,
            codigo=codigo,
            vencidas=vencidas,
        )

    def mostrar_detalle(codigo, datos=None, errores=None, estado_http=200):
        try:
            solicitud = servicio.consultar(codigo)
        except (ErrorValidacion, SolicitudNoEncontrada) as e:
            flash(str(e), "error")
            return redirect(url_for("soporte"))
        html = render_template(
            "soporte_detalle.html",
            solicitud=solicitud,
            permitidos=estados_permitidos(solicitud["estado"]),
            datos=datos or {},
            errores=errores or {},
        )
        return html, estado_http

    @app.get("/soporte/<codigo>")
    def soporte_detalle(codigo):
        return mostrar_detalle(codigo)

    def aplicar(codigo, accion, mensaje_ok):
        try:
            solicitud = accion()
        except SolicitudNoEncontrada as e:
            flash(str(e), "error")
            return redirect(url_for("soporte"))
        except ErrorValidacion as e:
            return mostrar_detalle(codigo, request.form, e.detalles, 400)
        flash(mensaje_ok, "ok")
        return redirect(url_for("soporte_detalle", codigo=solicitud["codigo"]))

    @app.post("/soporte/<codigo>/tecnico")
    def soporte_asignar(codigo):
        return aplicar(
            codigo,
            lambda: servicio.asignar_tecnico(codigo, request.form.get("tecnico")),
            "El técnico quedó asignado.",
        )

    @app.post("/soporte/<codigo>/estado")
    def soporte_estado(codigo):
        return aplicar(
            codigo,
            lambda: servicio.cambiar_estado(
                codigo, request.form.get("estado"), request.form.get("comentario")
            ),
            "El estado de la solicitud se actualizó.",
        )


def _rutas_api(app, servicio):
    def cuerpo_json():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            raise ErrorValidacion(
                {"cuerpo": "Envíe los datos en formato JSON, como un objeto con sus campos."}
            )
        return datos

    @app.errorhandler(ErrorValidacion)
    def error_validacion(e):
        return (
            jsonify({"error": "Los datos enviados no son válidos.", "detalles": e.detalles}),
            400,
        )

    @app.errorhandler(SolicitudNoEncontrada)
    def no_encontrada(e):
        return jsonify({"error": str(e)}), 404

    @app.post("/api/solicitudes")
    def api_registrar():
        return jsonify(servicio.registrar(cuerpo_json())), 201

    @app.get("/api/solicitudes/<codigo>")
    def api_consultar(codigo):
        return jsonify(servicio.consultar(codigo))

    @app.put("/api/solicitudes/<codigo>/tecnico")
    def api_asignar(codigo):
        datos = cuerpo_json()
        return jsonify(
            servicio.asignar_tecnico(codigo, datos.get("tecnico"))
        )

    @app.put("/api/solicitudes/<codigo>/estado")
    def api_estado(codigo):
        datos = cuerpo_json()
        return jsonify(
            servicio.cambiar_estado(
                codigo, datos.get("estado"), datos.get("comentario")
            )
        )


def main():
    puerto = int(os.environ.get("SOLICITUDES_PORT") or 5000)
    create_app().run(host="127.0.0.1", port=puerto)


if __name__ == "__main__":
    main()
