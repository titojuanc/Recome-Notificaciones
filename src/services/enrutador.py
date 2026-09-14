"""Enrutador (T017): selecciona el cliente de canal según MensajeNotificacion."""
from __future__ import annotations

from src.models.mensaje import MensajeNotificacion
from src.models.resultado import ResultadoEnvio


def enrutar(mensaje: MensajeNotificacion, cliente_push, cliente_mail) -> ResultadoEnvio:
    if mensaje.canal == "push":
        resultado = cliente_push.enviar(mensaje.push_sub, mensaje.contenido)
    else:
        resultado = cliente_mail.enviar(mensaje.mail, mensaje.contenido)

    # Aseguramos que el id_mensaje/canal del resultado reflejen el mensaje real.
    return resultado.model_copy(update={"id_mensaje": mensaje.id_mensaje, "canal": mensaje.canal})
