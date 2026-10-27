"""Unit test T011: selección de canal (enrutamiento)."""
from unittest.mock import MagicMock

from src.models.mensaje import Contenido, MensajeNotificacion
from src.models.resultado import ResultadoEnvio
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


def _push_con_respaldo():
    mensaje = _mensaje_push()
    return mensaje.model_copy(update={"mail": "respaldo@b.com"})


def _resultado(canal, estado="exitoso", caducada=False):
    return ResultadoEnvio(
        id_mensaje=0, estado=estado, canal=canal, suscripcion_caducada=caducada
    )


def test_push_caducado_con_mail_de_respaldo_envia_por_mail():
    cliente_push = MagicMock()
    cliente_push.enviar.return_value = _resultado("push", "fallo_definitivo", caducada=True)
    cliente_mail = MagicMock()
    cliente_mail.enviar.return_value = _resultado("mail")

    resultado = enrutar(_push_con_respaldo(), cliente_push=cliente_push, cliente_mail=cliente_mail)

    cliente_mail.enviar.assert_called_once()
    assert cliente_mail.enviar.call_args.args[0] == "respaldo@b.com"
    assert resultado.estado == "exitoso"
    assert resultado.canal == "mail"
    assert resultado.id_mensaje == 2


def test_push_caducado_sin_mail_de_respaldo_es_definitivo():
    cliente_push = MagicMock()
    cliente_push.enviar.return_value = _resultado("push", "fallo_definitivo", caducada=True)
    cliente_mail = MagicMock()

    resultado = enrutar(_mensaje_push(), cliente_push=cliente_push, cliente_mail=cliente_mail)

    cliente_mail.enviar.assert_not_called()
    assert resultado.estado == "fallo_definitivo"
    assert resultado.canal == "push"


def test_push_con_fallo_transitorio_no_usa_el_respaldo():
    cliente_push = MagicMock()
    cliente_push.enviar.return_value = _resultado("push", "fallo_transitorio")
    cliente_mail = MagicMock()

    resultado = enrutar(_push_con_respaldo(), cliente_push=cliente_push, cliente_mail=cliente_mail)

    cliente_mail.enviar.assert_not_called()
    assert resultado.estado == "fallo_transitorio"
