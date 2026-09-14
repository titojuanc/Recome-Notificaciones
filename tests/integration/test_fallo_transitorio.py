"""Integration test T032: fallo transitorio simulado en clientes push/mail."""
from unittest.mock import patch

from pywebpush import WebPushException

from src.models.mensaje import Contenido, PushSubscription
from src.services.canales.mail import ClienteMail
from src.services.canales.push import ClientePush

CONTENIDO = Contenido(titulo="t", cuerpo="c")


def test_cliente_push_fallo_transitorio_por_timeout():
    cliente = ClientePush(vapid_private_key="k", vapid_claims_sub="mailto:a@b.com")
    sub = PushSubscription(endpoint="https://x", keys={"p256dh": "a", "auth": "b"})
    with patch("src.services.canales.push.webpush", side_effect=WebPushException("timeout")):
        resultado = cliente.enviar(sub, CONTENIDO)
    assert resultado.estado == "fallo_transitorio"


def test_cliente_mail_fallo_transitorio_por_conexion():
    cliente = ClienteMail(smtp_host="host-inexistente.invalid", smtp_port=1025, smtp_from="a@b.com")
    resultado = cliente.enviar("destino@ejemplo.com", CONTENIDO)
    assert resultado.estado == "fallo_transitorio"
