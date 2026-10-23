"""Validación de los datos de una solicitud."""

from .errores import ErrorValidacion

CATEGORIAS = ("hardware", "software", "redes", "accesos", "otro")
PRIORIDADES = ("baja", "media", "alta", "critica")

MAX_SOLICITANTE = 100
MIN_DESCRIPCION = 10
MAX_DESCRIPCION = 1000


def texto(valor):
    """Convierte un valor recibido en texto sin espacios alrededor."""
    if valor is None:
        return ""
    return str(valor).strip()


def _validar_opcion(valor, opciones, nombre, errores, campo):
    if not valor:
        errores[campo] = f"Falta la {nombre}; es un campo obligatorio."
    elif valor not in opciones:
        errores[campo] = (
            f"La {nombre} '{valor}' no es válida. "
            f"Elija una de estas opciones: {', '.join(opciones)}."
        )


def validar_solicitud(datos):
    """Valida los datos de una nueva solicitud.

    Devuelve un diccionario con los datos limpios. Si hay errores, lanza
    ErrorValidacion con todos los mensajes a la vez.
    """
    datos = datos or {}
    solicitante = texto(datos.get("solicitante"))
    categoria = texto(datos.get("categoria")).lower()
    descripcion = texto(datos.get("descripcion"))
    prioridad = texto(datos.get("prioridad")).lower()

    errores = {}

    if not solicitante:
        errores["solicitante"] = (
            "Falta el nombre del solicitante; es un campo obligatorio."
        )
    elif len(solicitante) > MAX_SOLICITANTE:
        errores["solicitante"] = (
            "El nombre del solicitante es muy largo; "
            f"use como máximo {MAX_SOLICITANTE} caracteres."
        )

    _validar_opcion(categoria, CATEGORIAS, "categoría", errores, "categoria")

    if not descripcion:
        errores["descripcion"] = "Falta la descripción; es un campo obligatorio."
    elif len(descripcion) < MIN_DESCRIPCION:
        errores["descripcion"] = (
            "La descripción es muy corta; escriba al menos "
            f"{MIN_DESCRIPCION} caracteres explicando el problema."
        )
    elif len(descripcion) > MAX_DESCRIPCION:
        errores["descripcion"] = (
            "La descripción es muy larga; "
            f"use como máximo {MAX_DESCRIPCION} caracteres."
        )

    _validar_opcion(prioridad, PRIORIDADES, "prioridad", errores, "prioridad")

    if errores:
        raise ErrorValidacion(errores)

    return {
        "solicitante": solicitante,
        "categoria": categoria,
        "descripcion": descripcion,
        "prioridad": prioridad,
    }
