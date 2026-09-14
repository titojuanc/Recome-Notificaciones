"""Modelo de entrada: MensajeNotificacion, PushSubscription, Contenido.

Ver data-model.md §1 y contracts/mensaje-notificacion.schema.json.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, model_validator


class PushKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    keys: PushKeys


class Contenido(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo: str
    cuerpo: str


class MensajeNotificacion(BaseModel):
    """Payload consumido desde la cola de RabbitMQ.

    Validación estricta (Principio IV): extra="forbid" en todos los niveles,
    sin valores por defecto que "inventen" datos faltantes.
    """

    model_config = ConfigDict(extra="forbid")

    id_mensaje: int
    canal: Literal["push", "mail"]
    destinatario: int
    mail: EmailStr | None = None
    push_sub: PushSubscription | None = None
    contenido: Contenido

    @model_validator(mode="after")
    def validar_canal_contacto(self) -> MensajeNotificacion:
        """FR-013: validación cruzada canal / mail / push_sub."""
        if self.canal == "mail":
            if self.mail is None:
                raise ValueError("canal 'mail' requiere el campo 'mail' presente")
            if self.push_sub is not None:
                raise ValueError("canal 'mail' no debe traer 'push_sub'")
        elif self.canal == "push":
            if self.push_sub is None:
                raise ValueError("canal 'push' requiere el campo 'push_sub' presente")
            if self.mail is not None:
                raise ValueError("canal 'push' no debe traer 'mail'")
        return self
