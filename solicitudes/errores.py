"""Errores del dominio con mensajes comprensibles para el usuario."""


class ErrorSolicitud(Exception):
    """Error base de la mesa de servicio."""


class ErrorValidacion(ErrorSolicitud):
    """Uno o varios datos no son válidos.

    `detalles` es un diccionario {campo: mensaje} para poder mostrar
    cada mensaje junto al campo correspondiente.
    """

    def __init__(self, detalles):
        self.detalles = dict(detalles)
        super().__init__(" ".join(self.detalles.values()))


class SolicitudNoEncontrada(ErrorSolicitud):
    """No existe una solicitud con el código indicado."""

    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(
            f"No existe ninguna solicitud con el código '{codigo}'. "
            "Verifique que esté bien escrito."
        )
