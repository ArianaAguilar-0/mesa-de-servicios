"""Persistencia de solicitudes e historial en SQLite."""

import sqlite3
from contextlib import contextmanager

ESQUEMA = """
CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    solicitante TEXT NOT NULL,
    categoria TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    prioridad TEXT NOT NULL,
    estado TEXT NOT NULL,
    tecnico TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    vencida_en TEXT
);

CREATE TABLE IF NOT EXISTS historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id),
    fecha TEXT NOT NULL,
    accion TEXT NOT NULL,
    detalle TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    usuario TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_historial_solicitud ON historial(solicitud_id);
"""


class Repositorio:
    def __init__(self, ruta_db):
        self.ruta_db = str(ruta_db)
        self.inicializar()

    @contextmanager
    def _conexion(self):
        """Abre una conexión y ejecuta todo en una sola transacción."""
        con = sqlite3.connect(self.ruta_db)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            with con:  # confirma al terminar o revierte si hay un error
                yield con
        finally:
            con.close()

    def inicializar(self):
        with self._conexion() as con:
            con.executescript(ESQUEMA)
            # Migración: bases creadas antes de la versión 1.1 no tienen vencida_en.
            columnas = {f["name"] for f in con.execute("PRAGMA table_info(solicitudes)")}
            if "vencida_en" not in columnas:
                con.execute("ALTER TABLE solicitudes ADD COLUMN vencida_en TEXT")

    def existe_codigo(self, codigo):
        with self._conexion() as con:
            fila = con.execute(
                "SELECT 1 FROM solicitudes WHERE codigo = ?", (codigo,)
            ).fetchone()
        return fila is not None

    @staticmethod
    def _insertar_historial(con, solicitud_id, entrada):
        con.execute(
            """INSERT INTO historial
               (solicitud_id, fecha, accion, detalle, estado_anterior,
                estado_nuevo, usuario)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                solicitud_id,
                entrada["fecha"],
                entrada["accion"],
                entrada["detalle"],
                entrada.get("estado_anterior"),
                entrada.get("estado_nuevo"),
                entrada["usuario"],
            ),
        )

    def crear(self, solicitud, entrada_historial):
        """Guarda la solicitud y su primera entrada de historial juntas."""
        with self._conexion() as con:
            cursor = con.execute(
                """INSERT INTO solicitudes
                   (codigo, solicitante, categoria, descripcion, prioridad,
                    estado, tecnico, fecha_creacion, fecha_actualizacion)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    solicitud["codigo"],
                    solicitud["solicitante"],
                    solicitud["categoria"],
                    solicitud["descripcion"],
                    solicitud["prioridad"],
                    solicitud["estado"],
                    solicitud.get("tecnico"),
                    solicitud["fecha_creacion"],
                    solicitud["fecha_actualizacion"],
                ),
            )
            self._insertar_historial(con, cursor.lastrowid, entrada_historial)

    def actualizar(self, solicitud_id, cambios, entrada_historial):
        """Aplica los cambios y registra el historial en la misma transacción."""
        columnas = ", ".join(f"{campo} = ?" for campo in cambios)
        with self._conexion() as con:
            con.execute(
                f"UPDATE solicitudes SET {columnas} WHERE id = ?",
                (*cambios.values(), solicitud_id),
            )
            self._insertar_historial(con, solicitud_id, entrada_historial)

    def obtener(self, codigo):
        with self._conexion() as con:
            fila = con.execute(
                "SELECT * FROM solicitudes WHERE codigo = ?", (codigo,)
            ).fetchone()
        return dict(fila) if fila else None

    def listar(self, estado=None, codigo=None, solo_vencidas=False):
        """Lista solicitudes, de la más reciente a la más antigua."""
        condiciones, parametros = [], []
        if solo_vencidas:
            condiciones.append("vencida_en IS NOT NULL")
        if estado:
            condiciones.append("estado = ?")
            parametros.append(estado)
        if codigo:
            condiciones.append("instr(codigo, ?) > 0")
            parametros.append(codigo)
        donde = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
        with self._conexion() as con:
            filas = con.execute(
                f"SELECT * FROM solicitudes {donde} ORDER BY id DESC", parametros
            ).fetchall()
        return [dict(f) for f in filas]

    def criticas_sin_atender(self, prioridad, estados):
        """Solicitudes de la prioridad dada, en los estados dados y aún no vencidas."""
        marcas = ", ".join("?" for _ in estados)
        with self._conexion() as con:
            filas = con.execute(
                f"""SELECT id, fecha_creacion FROM solicitudes
                   WHERE prioridad = ? AND estado IN ({marcas}) AND vencida_en IS NULL""",
                (prioridad, *estados),
            ).fetchall()
        return [dict(f) for f in filas]

    def marcar_vencida(self, solicitud_id, fecha, entrada_historial):
        """Marca la solicitud como vencida y lo registra en el historial (una sola vez)."""
        with self._conexion() as con:
            cursor = con.execute(
                "UPDATE solicitudes SET vencida_en = ? WHERE id = ? AND vencida_en IS NULL",
                (fecha, solicitud_id),
            )
            if cursor.rowcount:
                self._insertar_historial(con, solicitud_id, entrada_historial)

    def historial(self, solicitud_id):
        with self._conexion() as con:
            filas = con.execute(
                """SELECT fecha, accion, detalle, estado_anterior, estado_nuevo,
                          usuario
                   FROM historial WHERE solicitud_id = ? ORDER BY id""",
                (solicitud_id,),
            ).fetchall()
        return [dict(f) for f in filas]
