"""Logging estructurado base (FR-008: trazabilidad de mensajes).

Cada mensaje procesado debe terminar en uno de los estados de SC-004:
entregado, rechazado/dead-letter, duplicado descartado, o fallido tras
agotar entregas. Este módulo centraliza el formato de esos logs.
"""
from __future__ import annotations

import logging
import sys


def configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("notificaciones")
    if logger.handlers:
        return logger  # ya configurado

    logger.setLevel(nivel)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def log_evento(
    logger: logging.Logger,
    estado: str,
    id_mensaje: int | None = None,
    canal: str | None = None,
    detalle: str | None = None,
) -> None:
    """Log estructurado de un evento de procesamiento de mensaje.

    estado esperado: uno de "enviado", "rechazado", "duplicado_descartado",
    "reencolado", "dead_letter".
    """
    logger.info(
        "evento=%s id_mensaje=%s canal=%s detalle=%s",
        estado,
        id_mensaje,
        canal,
        detalle,
    )
