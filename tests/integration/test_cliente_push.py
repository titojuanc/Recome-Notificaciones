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


def _cliente():
    return ClientePush(vapid_private_key="clave-privada", vapid_claims_sub="mailto:a@b.com")


def _falla_http(codigo):
    from unittest.mock import MagicMock

    from pywebpush import WebPushException

    respuesta = MagicMock(status_code=codigo, text="x")
    return WebPushException(f"Push failed: {codigo}", response=respuesta)


def test_cliente_push_incluye_url_en_el_payload():
    import json

    contenido = Contenido(titulo="Hola", cuerpo="Mundo", url="https://recome.example/catalogo/1")
    with patch("src.services.canales.push.webpush") as mock_webpush:
        _cliente().enviar(SUB, contenido)
    assert json.loads(mock_webpush.call_args.kwargs["data"])["url"] == "https://recome.example/catalogo/1"


def test_cliente_push_sin_url_no_la_envia():
    import json

    with patch("src.services.canales.push.webpush") as mock_webpush:
        _cliente().enviar(SUB, CONTENIDO)
    assert "url" not in json.loads(mock_webpush.call_args.kwargs["data"])


def test_suscripcion_caducada_404_y_410_son_definitivas():
    for codigo in (404, 410):
        with patch("src.services.canales.push.webpush", side_effect=_falla_http(codigo)):
            resultado = _cliente().enviar(SUB, CONTENIDO)
        assert resultado.estado == "fallo_definitivo"
        assert resultado.suscripcion_caducada is True


def test_429_y_5xx_son_transitorios():
    for codigo in (429, 500, 503):
        with patch("src.services.canales.push.webpush", side_effect=_falla_http(codigo)):
            resultado = _cliente().enviar(SUB, CONTENIDO)
        assert resultado.estado == "fallo_transitorio"
        assert resultado.suscripcion_caducada is False


def test_otros_4xx_son_definitivos_sin_marcar_caducada():
    for codigo in (400, 401, 403, 413):
        with patch("src.services.canales.push.webpush", side_effect=_falla_http(codigo)):
            resultado = _cliente().enviar(SUB, CONTENIDO)
        assert resultado.estado == "fallo_definitivo"
        assert resultado.suscripcion_caducada is False


def test_error_de_red_es_transitorio():
    import requests

    with patch("src.services.canales.push.webpush", side_effect=requests.ConnectionError("caído")):
        resultado = _cliente().enviar(SUB, CONTENIDO)
    assert resultado.estado == "fallo_transitorio"


def test_clave_vapid_invalida_es_definitiva_y_no_lanza():
    with patch("src.services.canales.push.webpush", side_effect=ValueError("clave inválida")):
        resultado = _cliente().enviar(SUB, CONTENIDO)
    assert resultado.estado == "fallo_definitivo"
