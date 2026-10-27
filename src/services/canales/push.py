"""Adaptador de envío push vía pywebpush (T015).

Interfaz simple: enviar(push_sub, contenido) -> ResultadoEnvio

Clasificación de fallos (igual criterio que el canal mail):
  - 404/410 del servicio push: la suscripción ya no existe -> definitivo y
    `suscripcion_caducada` (el enrutador usa el mail de respaldo, si vino).
  - 429, 5xx y errores de red/timeout -> transitorio (se reencola hasta el límite).
  - Cualquier otro 4xx (payload o VAPID rechazados) y errores locales (clave VAPID
    mal formada, suscripción inválida) -> definitivo: reintentar no lo arregla.
"""
from __future__ import annotations

import json

import requests
from pywebpush import WebPushException, webpush

from src.models.mensaje import Contenido, PushSubscription
from src.models.resultado import ResultadoEnvio

_SUSCRIPCION_CADUCADA = (404, 410)


class ClientePush:
    def __init__(self, vapid_private_key: str, vapid_claims_sub: str) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_claims_sub = vapid_claims_sub

    @staticmethod
    def _resultado(
        estado: str, detalle: str | None = None, caducada: bool = False
    ) -> ResultadoEnvio:
        return ResultadoEnvio(
            id_mensaje=0,
            estado=estado,
            canal="push",
            detalle=detalle,
            suscripcion_caducada=caducada,
        )

    def enviar(self, push_sub: PushSubscription, contenido: Contenido) -> ResultadoEnvio:
        subscription_info = {
            "endpoint": push_sub.endpoint,
            "keys": {
                "p256dh": push_sub.keys.p256dh,
                "auth": push_sub.keys.auth,
            },
        }
        cuerpo = {"titulo": contenido.titulo, "cuerpo": contenido.cuerpo}
        if contenido.url:
            cuerpo["url"] = contenido.url
        payload = json.dumps(cuerpo)

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._vapid_private_key or None,
                vapid_claims={"sub": self._vapid_claims_sub},
            )
        except WebPushException as exc:
            estado_http = exc.status_code
            if estado_http in _SUSCRIPCION_CADUCADA:
                return self._resultado("fallo_definitivo", str(exc), caducada=True)
            if estado_http is None or estado_http == 429 or estado_http >= 500:
                return self._resultado("fallo_transitorio", str(exc))
            return self._resultado("fallo_definitivo", str(exc))
        except requests.RequestException as exc:
            return self._resultado("fallo_transitorio", f"red: {type(exc).__name__}")
        except Exception as exc:  # noqa: BLE001 - clave VAPID o suscripción mal formadas
            return self._resultado("fallo_definitivo", f"{type(exc).__name__}: {exc}")

        return self._resultado("exitoso")
