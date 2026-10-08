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
    rabbitmq_delivery_limit: int
    rabbitmq_message_ttl_ms: int
    sqlite_dedup_path: str
    smtp_host: str
    smtp_port: int
    smtp_from: str
    vapid_private_key: str
    vapid_public_key: str
    vapid_claims_sub: str
    service_api_key: str
    callback_timeout_seconds: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            rabbitmq_url=os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            rabbitmq_queue=os.environ.get("RABBITMQ_QUEUE_NOTIFICACIONES", "notificaciones"),
            rabbitmq_prefetch_count=_get_int("RABBITMQ_PREFETCH_COUNT", 10),
            # Límite de reintentos (requiere cola tipo quorum, ver worker.py):
            # tras agotar estas entregas, el mensaje se manda a dead-letter en
            # vez de reencolarse indefinidamente (ver quickstart.md).
            rabbitmq_delivery_limit=_get_int("RABBITMQ_DELIVERY_LIMIT", 5),
            # TTL en milisegundos: un mensaje que lleva más de este tiempo sin
            # poder ser procesado se descarta (va a dead-letter) en vez de
            # vivir indefinidamente en la cola. Default: 24hs.
            rabbitmq_message_ttl_ms=_get_int("RABBITMQ_MESSAGE_TTL_MS", 24 * 60 * 60 * 1000),
            sqlite_dedup_path=os.environ.get(
                "SQLITE_DEDUP_PATH", "data/processed_messages.db"
            ),
            smtp_host=os.environ.get("SMTP_HOST", "localhost"),
            smtp_port=_get_int("SMTP_PORT", 1025),
            smtp_from=os.environ.get("SMTP_FROM", "notificaciones@recome.local"),
            vapid_private_key=os.environ.get("VAPID_PRIVATE_KEY", ""),
            vapid_public_key=os.environ.get("VAPID_PUBLIC_KEY", ""),
            vapid_claims_sub=os.environ.get("VAPID_CLAIMS_SUB", "mailto:admin@recome.local"),
            # Clave compartida con recome-api-general (header X-Service-Api-Key)
            # usada para autenticar el callback de confirmación de envío de mail
            # (ver ReporteInternalController / ServiceApiKeyFilter en ese repo).
            service_api_key=os.environ.get("RECOMMENDATIONS_SERVICE_API_KEY", ""),
            callback_timeout_seconds=_get_int("CALLBACK_TIMEOUT_SECONDS", 5),
        )
