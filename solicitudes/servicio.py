"""Reglas de negocio de la mesa de servicio."""

from datetime import datetime

from .codigo import generar_codigo, normalizar_codigo
from .errores import ErrorValidacion, SolicitudNoEncontrada
from .validacion import (
    texto,
    validar_no_final,
    validar_solicitud,
    validar_tecnico,
    validar_transicion,
)

USUARIO_SOPORTE = "soporte"


def ahora():
    return datetime.now().isoformat(sep=" ", timespec="seconds")


class ServicioSolicitudes:
    def __init__(self, repositorio):
        self.repo = repositorio

    def registrar(self, datos):
        """Valida y registra una nueva solicitud. Devuelve la solicitud creada."""
        limpios = validar_solicitud(datos)
        fecha = ahora()
        solicitud = {
            **limpios,
            "codigo": generar_codigo(self.repo.existe_codigo),
            "estado": "registrada",
            "tecnico": None,
            "fecha_creacion": fecha,
            "fecha_actualizacion": fecha,
        }
        entrada = {
            "fecha": fecha,
            "accion": "registro",
            "detalle": "Solicitud registrada.",
            "estado_anterior": None,
            "estado_nuevo": "registrada",
            "usuario": limpios["solicitante"],
        }
        self.repo.crear(solicitud, entrada)
        return self.consultar(solicitud["codigo"])

    def _obtener(self, codigo):
        escrito = texto(codigo)
        if not escrito:
            raise ErrorValidacion(
                {"codigo": "Escriba el código de la solicitud que desea consultar."}
            )
        solicitud = self.repo.obtener(normalizar_codigo(escrito))
        if solicitud is None:
            raise SolicitudNoEncontrada(escrito)
        return solicitud

    def consultar(self, codigo):
        """Devuelve la solicitud con su historial. Acepta minúsculas y espacios."""
        solicitud = self._obtener(codigo)
        solicitud["historial"] = self.repo.historial(solicitud.pop("id"))
        return solicitud

    def _guardar_cambio(self, solicitud, cambios, accion, detalle, usuario):
        """Guarda el cambio y su entrada de historial en una sola transacción."""
        fecha = ahora()
        entrada = {
            "fecha": fecha,
            "accion": accion,
            "detalle": detalle,
            "estado_anterior": solicitud["estado"],
            "estado_nuevo": cambios.get("estado", solicitud["estado"]),
            "usuario": usuario,
        }
        self.repo.actualizar(
            solicitud["id"], {**cambios, "fecha_actualizacion": fecha}, entrada
        )
        return self.consultar(solicitud["codigo"])

    def asignar_tecnico(self, codigo, tecnico, usuario=None):
        """Asigna o reasigna un técnico. Si está 'registrada', pasa a 'asignada'."""
        solicitud = self._obtener(codigo)
        validar_no_final(solicitud["estado"])
        tecnico = validar_tecnico(tecnico)

        anterior = solicitud["tecnico"]
        if anterior == tecnico:
            raise ErrorValidacion(
                {"tecnico": f"La solicitud ya está asignada a {tecnico}."}
            )
        if anterior:
            detalle = f"Técnico reasignado de {anterior} a {tecnico}."
        else:
            detalle = f"Técnico asignado: {tecnico}."

        cambios = {"tecnico": tecnico}
        if solicitud["estado"] == "registrada":
            cambios["estado"] = "asignada"
        return self._guardar_cambio(
            solicitud, cambios, "asignacion", detalle, texto(usuario) or USUARIO_SOPORTE
        )

    def cambiar_estado(self, codigo, estado, comentario=None, usuario=None):
        """Cambia el estado respetando las transiciones permitidas."""
        solicitud = self._obtener(codigo)
        nuevo, comentario = validar_transicion(
            solicitud["estado"], estado, solicitud["tecnico"], comentario
        )
        detalle = f"Estado cambiado de '{solicitud['estado']}' a '{nuevo}'."
        if comentario:
            detalle += f" Comentario: {comentario}"
        return self._guardar_cambio(
            solicitud,
            {"estado": nuevo},
            "cambio_estado",
            detalle,
            texto(usuario) or USUARIO_SOPORTE,
        )
