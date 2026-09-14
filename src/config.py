"""Configuración del worker vía variables de entorno.

No lanza excepción al importar (permite cargarla en tests sin todas las env
vars presentes); usa valores por defecto razonables para desarrollo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    valor = os.environ.get(name)
    return int(valor) if valor else default


@dataclass(frozen=True)
class Config:
    rabbitmq_url: str
    rabbitmq_queue: str
    rabbitmq_prefetch_count: int
    sqlite_dedup_path: str
    smtp_host: str
    smtp_port: int
    smtp_from: str
    vapid_private_key: str
    vapid_public_key: str
    vapid_claims_sub: str

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            rabbitmq_url=os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            rabbitmq_queue=os.environ.get("RABBITMQ_QUEUE_NOTIFICACIONES", "notificaciones"),
            rabbitmq_prefetch_count=_get_int("RABBITMQ_PREFETCH_COUNT", 10),
            sqlite_dedup_path=os.environ.get(
                "SQLITE_DEDUP_PATH", "data/processed_messages.db"
            ),
            smtp_host=os.environ.get("SMTP_HOST", "localhost"),
            smtp_port=_get_int("SMTP_PORT", 1025),
            smtp_from=os.environ.get("SMTP_FROM", "notificaciones@recome.local"),
            vapid_private_key=os.environ.get("VAPID_PRIVATE_KEY", ""),
            vapid_public_key=os.environ.get("VAPID_PUBLIC_KEY", ""),
            vapid_claims_sub=os.environ.get("VAPID_CLAIMS_SUB", "mailto:admin@recome.local"),
        )
