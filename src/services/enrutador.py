"""Enrutador (T017): selecciona el cliente de canal según MensajeNotificacion."""
from __future__ import annotations

from src.models.mensaje import MensajeNotificacion
from src.models.resultado import ResultadoEnvio


def enrutar(mensaje: MensajeNotificacion, cliente_push, cliente_mail) -> ResultadoEnvio:
    if mensaje.canal == "push":
        resultado = cliente_push.enviar(mensaje.push_sub, mensaje.contenido)
        # Suscripción dada de baja o vencida: si el emisor mandó un mail de respaldo, el aviso
        # no se pierde y sale por mail (sin adjunto).
        if resultado.suscripcion_caducada is True and mensaje.mail:
            resultado = cliente_mail.enviar(mensaje.mail, mensaje.contenido, mensaje.adjunto)
    else:
        resultado = cliente_mail.enviar(mensaje.mail, mensaje.contenido, mensaje.adjunto)

    # Aseguramos que el id_mensaje del resultado refleje el mensaje real. El canal es el que
    # efectivamente se usó (puede ser mail si hubo respaldo).
    return resultado.model_copy(update={"id_mensaje": mensaje.id_mensaje})
