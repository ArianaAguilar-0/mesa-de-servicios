"""Generación y normalización de códigos de solicitud (SOL-AAAAMMDD-XXXXXX)."""

import re
import secrets
from datetime import date

PATRON_CODIGO = re.compile(r"^SOL-\d{8}-[0-9A-F]{6}$")
MAX_INTENTOS = 100


def normalizar_codigo(codigo):
    """Quita espacios alrededor y pasa a mayúsculas."""
    return str(codigo or "").strip().upper()


def es_codigo_valido(codigo):
    return bool(PATRON_CODIGO.match(codigo or ""))


def generar_codigo(existe, fecha=None):
    """Genera un código que no exista todavía.

    `existe` es una función que recibe un código y devuelve True si ya está
    registrado en la base de datos.
    """
    fecha = fecha or date.today()
    prefijo = f"SOL-{fecha:%Y%m%d}-"
    for _ in range(MAX_INTENTOS):
        codigo = prefijo + secrets.token_hex(3).upper()
        if not existe(codigo):
            return codigo
    raise RuntimeError("No se pudo generar un código único para la solicitud.")
