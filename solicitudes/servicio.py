"""Reglas de negocio de la mesa de servicio."""

from datetime import datetime, timedelta

from .codigo import generar_codigo, normalizar_codigo
from .errores import ErrorValidacion, SolicitudNoEncontrada
from .validacion import (
    ESTADOS,
    texto,
    validar_no_final,
    validar_solicitud,
    validar_tecnico,
    validar_transicion,
)

USUARIO_SOPORTE = "soporte"
USUARIO_SISTEMA = "sistema"

# Regla de vencimiento (versión 1.1): una solicitud de prioridad crítica que no
# pasa a "en_proceso" dentro de 4 horas desde su registro se marca como vencida.
PRIORIDAD_CON_PLAZO = "critica"
PLAZO_ATENCION = timedelta(hours=4)
ESTADOS_SIN_ATENDER = ("registrada", "asignada")
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


class ServicioSolicitudes:
    def __init__(self, repositorio, reloj=None):
        self.repo = repositorio
        self._reloj = reloj or datetime.now

    def _ahora(self):
        return self._reloj().strftime(FORMATO_FECHA)

    def marcar_vencidas(self):
        """Marca como vencidas las solicitudes críticas no atendidas a tiempo.

        Devuelve cuántas se marcaron. Se ejecuta antes de listar o consultar, así
        el estado mostrado siempre está al día sin depender de un proceso aparte.
        """
        momento = self._reloj()
        marcadas = 0
        for s in self.repo.criticas_sin_atender(PRIORIDAD_CON_PLAZO, ESTADOS_SIN_ATENDER):
            limite = datetime.strptime(s["fecha_creacion"], FORMATO_FECHA) + PLAZO_ATENCION
            if momento >= limite:
                fecha = limite.strftime(FORMATO_FECHA)
                self.repo.marcar_vencida(s["id"], fecha, {
                    "fecha": fecha,
                    "accion": "vencimiento",
                    "detalle": "Solicitud crítica sin atender en 4 horas: marcada como vencida.",
                    "estado_anterior": None,
                    "estado_nuevo": None,
                    "usuario": USUARIO_SISTEMA,
                })
                marcadas += 1
        return marcadas

    def registrar(self, datos):
        """Valida y registra una nueva solicitud. Devuelve la solicitud creada."""
        limpios = validar_solicitud(datos)
        fecha = self._ahora()
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
        self.marcar_vencidas()
        solicitud = self.repo.obtener(normalizar_codigo(escrito))
        if solicitud is None:
            raise SolicitudNoEncontrada(escrito)
        return solicitud

    def consultar(self, codigo):
        """Devuelve la solicitud con su historial. Acepta minúsculas y espacios."""
        solicitud = self._obtener(codigo)
        solicitud["historial"] = self.repo.historial(solicitud.pop("id"))
        return solicitud

    def listar(self, estado=None, codigo=None, solo_vencidas=False):
        """Lista solicitudes filtrando por estado, parte del código y vencimiento."""
        self.marcar_vencidas()
        estado = texto(estado).lower()
        if estado not in ESTADOS:
            estado = None
        return self.repo.listar(estado, normalizar_codigo(codigo) or None, solo_vencidas)

    def _guardar_cambio(self, solicitud, cambios, accion, detalle, usuario):
        """Guarda el cambio y su entrada de historial en una sola transacción."""
        fecha = self._ahora()
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
        if anterior and anterior.casefold() == tecnico.casefold():
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
