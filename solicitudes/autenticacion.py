"""Cuentas del personal de soporte técnico.

Las contraseñas nunca se guardan: solo su hash (werkzeug, con sal aleatoria).
"""

import re
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .errores import ErrorValidacion
from .validacion import texto

MIN_CONTRASENA = 8
PATRON_USUARIO = re.compile(r"^[a-z0-9._-]{3,30}$")
# Hash de relleno: si el usuario no existe se verifica igual, para que la respuesta
# tarde lo mismo y no revele qué usuarios existen.
_HASH_RELLENO = generate_password_hash("relleno-sin-uso")


def crear_usuario(repo, usuario, contrasena):
    """Crea una cuenta de soporte. Lanza ErrorValidacion si los datos no sirven."""
    usuario = texto(usuario).lower()
    contrasena = contrasena or ""
    errores = {}
    if not PATRON_USUARIO.match(usuario):
        errores["usuario"] = (
            "El usuario debe tener entre 3 y 30 caracteres: letras sin tilde, números, punto, guion o guion bajo."
        )
    elif repo.obtener_usuario(usuario):
        errores["usuario"] = f"Ya existe una cuenta con el usuario '{usuario}'."
    if len(contrasena) < MIN_CONTRASENA:
        errores["contrasena"] = f"La contraseña debe tener al menos {MIN_CONTRASENA} caracteres."
    if errores:
        raise ErrorValidacion(errores)
    repo.crear_usuario(
        usuario, generate_password_hash(contrasena), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    return usuario


def verificar(repo, usuario, contrasena):
    """Devuelve el nombre de usuario si las credenciales son correctas; si no, None."""
    usuario = texto(usuario).lower()
    cuenta = repo.obtener_usuario(usuario) if usuario else None
    hash_guardado = cuenta["hash_contrasena"] if cuenta else _HASH_RELLENO
    correcta = check_password_hash(hash_guardado, contrasena or "")
    return usuario if (cuenta and correcta) else None
