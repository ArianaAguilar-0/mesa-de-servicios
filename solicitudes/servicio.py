"""Reglas de negocio de la mesa de servicio."""

from datetime import datetime

from .codigo import generar_codigo, normalizar_codigo
from .errores import ErrorValidacion, SolicitudNoEncontrada
from .validacion import texto, validar_solicitud


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
