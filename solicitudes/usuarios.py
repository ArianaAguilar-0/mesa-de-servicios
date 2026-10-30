"""Administrar cuentas de soporte técnico desde la terminal.

Uso:
    python -m solicitudes.usuarios crear NOMBRE   (pide la contraseña sin mostrarla)
    python -m solicitudes.usuarios listar
"""

import os
import sys
from getpass import getpass

from .autenticacion import crear_usuario
from .errores import ErrorValidacion
from .repositorio import Repositorio


def main(argumentos=None):
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    repo = Repositorio(os.environ.get("SOLICITUDES_DB") or "solicitudes.db")

    if argumentos[:1] == ["listar"]:
        cuentas = repo.listar_usuarios()
        for c in cuentas:
            print(f"{c['usuario']}  (creada el {c['fecha_creacion']})")
        if not cuentas:
            print("No hay cuentas de soporte. Cree una con: python -m solicitudes.usuarios crear NOMBRE")
        return 0

    if len(argumentos) == 2 and argumentos[0] == "crear":
        contrasena = getpass("Contraseña (mínimo 8 caracteres): ")
        if contrasena != getpass("Repita la contraseña: "):
            print("Las contraseñas no coinciden. No se creó la cuenta.")
            return 1
        try:
            usuario = crear_usuario(repo, argumentos[1], contrasena)
        except ErrorValidacion as e:
            print("No se creó la cuenta: " + " ".join(e.detalles.values()))
            return 1
        print(f"Cuenta '{usuario}' creada.")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
