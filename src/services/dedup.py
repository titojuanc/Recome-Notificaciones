"""Registro de mensajes procesados (T029, dedup): SQLite embebido.

Ver data-model.md §3.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing


class RegistroMensajeProcesado:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        directorio = os.path.dirname(db_path)
        if directorio:
            os.makedirs(directorio, exist_ok=True)
        self._inicializar()

    def _conectar(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _inicializar(self) -> None:
        with closing(self._conectar()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    id_mensaje INTEGER PRIMARY KEY,
                    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    canal TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def existe(self, id_mensaje: int) -> bool:
        with closing(self._conectar()) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM processed_messages WHERE id_mensaje = ?", (id_mensaje,)
            )
            return cursor.fetchone() is not None

    def registrar(self, id_mensaje: int, canal: str) -> None:
        with closing(self._conectar()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_messages (id_mensaje, canal) VALUES (?, ?)",
                (id_mensaje, canal),
            )
            conn.commit()
