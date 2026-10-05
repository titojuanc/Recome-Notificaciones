"""Cliente de callback (Spec 4): confirma a recome-api-general que un mail
de "reporte listo" fue enviado con éxito, cerrando el loop de feedback
visual del vendedor (polling en /anuncios/{id}/reporte/{solicitudId}).

Usa únicamente la librería estándar (urllib) para no agregar una nueva
dependencia de terceros solo para esto. El fallo del callback NO debe
afectar el ack/nack del mensaje de RabbitMQ: el mail ya fue enviado, así
que reintentar el mensaje completo generaría un mail duplicado. Por eso
cualquier error acá se loggea como advertencia y no se propaga.
"""
from __future__ import annotations

import logging
import urllib.error
import urllib.request


def confirmar_envio(callback_url: str, service_api_key: str, timeout_seconds: int,
                     logger: logging.Logger | None = None) -> bool:
    """POST sin body a `callback_url` con header X-Service-Api-Key.

    Devuelve True si el callback respondió 2xx, False en cualquier otro
    caso (incluye timeouts, errores de red, y respuestas de error HTTP).
    """
    log = logger or logging.getLogger(__name__)
    request = urllib.request.Request(
        callback_url,
        method="POST",
        headers={"X-Service-Api-Key": service_api_key, "Content-Length": "0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            exito = 200 <= response.status < 300
            if not exito:
                log.warning("callback_url=%s respondió status=%s", callback_url, response.status)
            return exito
    except urllib.error.HTTPError as exc:
        log.warning("callback_url=%s falló con HTTPError status=%s", callback_url, exc.code)
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        log.warning("callback_url=%s falló: %s", callback_url, exc)
        return False
