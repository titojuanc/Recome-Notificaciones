"""Adaptador de envío push vía pywebpush (T015).

Interfaz simple: enviar(push_sub, contenido) -> ResultadoEnvio
"""
from __future__ import annotations

import json

from pywebpush import WebPushException, webpush

from src.models.mensaje import Contenido, PushSubscription
from src.models.resultado import ResultadoEnvio


class ClientePush:
    def __init__(self, vapid_private_key: str, vapid_claims_sub: str) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_claims_sub = vapid_claims_sub

    def enviar(self, push_sub: PushSubscription, contenido: Contenido) -> ResultadoEnvio:
        subscription_info = {
            "endpoint": push_sub.endpoint,
            "keys": {
                "p256dh": push_sub.keys.p256dh,
                "auth": push_sub.keys.auth,
            },
        }
        payload = json.dumps({"titulo": contenido.titulo, "cuerpo": contenido.cuerpo})

        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=self._vapid_private_key or None,
                vapid_claims={"sub": self._vapid_claims_sub},
            )
        except WebPushException as exc:
            return ResultadoEnvio(
                id_mensaje=0,
                estado="fallo_transitorio",
                canal="push",
                detalle=str(exc),
            )

        return ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="push")
