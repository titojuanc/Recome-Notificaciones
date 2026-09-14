"""Integration test T012: cliente push, mockeando pywebpush (research.md §7)."""
from unittest.mock import patch

from src.models.mensaje import Contenido, PushSubscription
from src.services.canales.push import ClientePush

SUB = PushSubscription(
    endpoint="https://fcm.googleapis.com/fcm/send/ejemplo",
    keys={"p256dh": "clave-publica", "auth": "secreto"},
)
CONTENIDO = Contenido(titulo="Hola", cuerpo="Mundo")


def test_cliente_push_envia_correctamente():
    cliente = ClientePush(vapid_private_key="clave-privada", vapid_claims_sub="mailto:a@b.com")
    with patch("src.services.canales.push.webpush") as mock_webpush:
        resultado = cliente.enviar(SUB, CONTENIDO)

    mock_webpush.assert_called_once()
    _, kwargs = mock_webpush.call_args
    assert kwargs["subscription_info"]["endpoint"] == SUB.endpoint
    assert kwargs["subscription_info"]["keys"]["p256dh"] == "clave-publica"
    assert kwargs["subscription_info"]["keys"]["auth"] == "secreto"
    assert "Hola" in kwargs["data"]
    assert resultado.estado == "exitoso"


def test_cliente_push_fallo_transitorio():
    from pywebpush import WebPushException

    cliente = ClientePush(vapid_private_key="clave-privada", vapid_claims_sub="mailto:a@b.com")
    with patch("src.services.canales.push.webpush", side_effect=WebPushException("timeout")):
        resultado = cliente.enviar(SUB, CONTENIDO)

    assert resultado.estado == "fallo_transitorio"
