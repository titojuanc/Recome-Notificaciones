"""Cliente de eventos hacia api-general (spec 013): avisa cada notificación enviada con éxito.

Alimenta el CTR del panel de analytics del admin. Mismo criterio que `callback.py`: solo librería
estándar y un fallo nunca se propaga, porque el mensaje ya se envió y reintentarlo duplicaría la
notificación al usuario. La API key viaja en `X-Internal-API-Key` y nunca se loguea.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

RUTA_EVENTOS = "/internal/v1/notification-events"


def reportar_envio(
    base_url: str,
    service_api_key: str,
    timeout_seconds: int,
    *,
    tipo: str,
    canal: str,
    id_mensaje: int,
    logger: logging.Logger | None = None,
) -> bool:
    """POST JSON a `<base_url>/internal/v1/notification-events`. True solo si responde 2xx."""
    log = logger or logging.getLogger(__name__)
    cuerpo = json.dumps({"tipo": tipo, "canal": canal, "id_mensaje": id_mensaje}).encode("utf-8")
    url = base_url.rstrip("/") + RUTA_EVENTOS
    request = urllib.request.Request(
        url,
        data=cuerpo,
        method="POST",
        headers={"Content-Type": "application/json", "X-Internal-API-Key": service_api_key},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            exito = 200 <= response.status < 300
            if not exito:
                log.warning("evento url=%s respondió status=%s", url, response.status)
            return exito
    except urllib.error.HTTPError as exc:
        log.warning("evento url=%s falló con HTTPError status=%s", url, exc.code)
        return False
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        log.warning("evento url=%s falló: %s", url, exc)
        return False
