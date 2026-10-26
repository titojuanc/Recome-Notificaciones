"""Unit test T011: selección de canal (enrutamiento)."""
from unittest.mock import MagicMock

from src.models.mensaje import Contenido, MensajeNotificacion
from src.services.enrutador import enrutar

CONTENIDO = Contenido(titulo="t", cuerpo="c")


def _mensaje_mail():
    return MensajeNotificacion(
        id_mensaje=1,
        canal="mail",
        destinatario=1,
        mail="a@b.com",
        push_sub=None,
        contenido=CONTENIDO,
    )


def _mensaje_push():
    return MensajeNotificacion(
        id_mensaje=2,
        canal="push",
        destinatario=1,
        mail=None,
        push_sub={
            "endpoint": "https://example.com/ep",
            "keys": {"p256dh": "x", "auth": "y"},
        },
        contenido=CONTENIDO,
    )


def test_enruta_a_cliente_mail():
    cliente_mail = MagicMock()
    cliente_push = MagicMock()
    enrutar(_mensaje_mail(), cliente_push=cliente_push, cliente_mail=cliente_mail)
    cliente_mail.enviar.assert_called_once()
    cliente_push.enviar.assert_not_called()


def test_enruta_a_cliente_push():
    cliente_mail = MagicMock()
    cliente_push = MagicMock()
    enrutar(_mensaje_push(), cliente_push=cliente_push, cliente_mail=cliente_mail)
    cliente_push.enviar.assert_called_once()
    cliente_mail.enviar.assert_not_called()
