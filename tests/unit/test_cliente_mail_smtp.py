"""Unit: ClienteMail con SMTP autenticado (Gmail: smtp.gmail.com con contraseña de aplicación).

`smtplib` se reemplaza por dobles: no hay red ni credenciales reales.
"""
import smtplib

import pytest

from src.models.mensaje import Contenido
from src.services.canales import mail as mail_mod
from src.services.canales.mail import ClienteMail

CONTENIDO = Contenido(titulo="Asunto", cuerpo="Cuerpo")


class FakeSMTP:
    """Doble de smtplib.SMTP / SMTP_SSL que registra las llamadas."""

    instancias: list["FakeSMTP"] = []
    login_error: Exception | None = None
    send_error: Exception | None = None

    def __init__(self, host, port, timeout=None, **kwargs):
        self.host, self.port, self.timeout, self.kwargs = host, port, timeout, kwargs
        self.llamadas: list[str] = []
        self.enviado = None
        FakeSMTP.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        self.llamadas.append("ehlo")

    def starttls(self, **kw):
        self.llamadas.append("starttls")

    def login(self, user, password):
        self.llamadas.append(f"login:{user}")
        if FakeSMTP.login_error:
            raise FakeSMTP.login_error

    def send_message(self, msg):
        self.llamadas.append("send")
        if FakeSMTP.send_error:
            raise FakeSMTP.send_error
        self.enviado = msg


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instancias = []
    FakeSMTP.login_error = None
    FakeSMTP.send_error = None
    monkeypatch.setattr(mail_mod.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mail_mod.smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def _gmail(**extra):
    return ClienteMail(
        smtp_host="smtp.gmail.com", smtp_port=587, smtp_from="recome@gmail.com",
        smtp_user="recome@gmail.com", smtp_password="abcd efgh ijkl mnop",
        smtp_security="starttls", **extra,
    )


def test_starttls_con_login_y_envio_en_orden():
    r = _gmail().enviar("dest@ejemplo.com", CONTENIDO)
    assert r.estado == "exitoso"
    assert FakeSMTP.instancias[0].llamadas == [
        "ehlo", "starttls", "ehlo", "login:recome@gmail.com", "send",
    ]


def test_contrasena_de_aplicacion_se_normaliza_sin_espacios(monkeypatch):
    visto = {}
    monkeypatch.setattr(FakeSMTP, "login", lambda self, u, p: visto.update(p=p))
    _gmail().enviar("dest@ejemplo.com", CONTENIDO)
    assert visto["p"] == "abcdefghijklmnop"  # Google la muestra en grupos de 4 con espacios


def test_ssl_implicito_puerto_465_no_hace_starttls():
    c = ClienteMail("smtp.gmail.com", 465, "recome@gmail.com", smtp_user="recome@gmail.com",
                    smtp_password="x" * 16, smtp_security="ssl")
    assert c.enviar("dest@ejemplo.com", CONTENIDO).estado == "exitoso"
    assert "starttls" not in FakeSMTP.instancias[0].llamadas
    assert "login:recome@gmail.com" in FakeSMTP.instancias[0].llamadas


def test_sin_credenciales_ni_tls_no_hace_login_mailpit():
    c = ClienteMail("localhost", 1025, "n@recome.local")
    assert c.enviar("dest@ejemplo.com", CONTENIDO).estado == "exitoso"
    assert FakeSMTP.instancias[0].llamadas == ["send"]


def test_credenciales_sin_tls_se_rechazan_al_construir():
    with pytest.raises(ValueError, match="SMTP_SECURITY"):
        ClienteMail(
            "smtp.gmail.com", 587, "a@gmail.com",
            smtp_user="a@gmail.com", smtp_password="x" * 16,
        )


def test_security_invalida_se_rechaza():
    with pytest.raises(ValueError, match="SMTP_SECURITY"):
        ClienteMail("h", 25, "a@b.com", smtp_security="tls13")


def test_usuario_sin_password_se_rechaza():
    with pytest.raises(ValueError, match="SMTP_PASSWORD"):
        ClienteMail("h", 587, "a@b.com", smtp_user="a@b.com", smtp_security="starttls")


def test_auth_fallida_es_transitoria_y_recuperable_desde_dlq():
    FakeSMTP.login_error = smtplib.SMTPAuthenticationError(
        535, b"5.7.8 Username and Password not accepted"
    )
    r = _gmail().enviar("dest@ejemplo.com", CONTENIDO)
    assert r.estado == "fallo_transitorio"  # credencial a corregir: no se pierde el mensaje
    assert "535" in r.detalle
    assert "abcd" not in r.detalle  # nunca se filtra la contraseña


def test_destinatario_rechazado_es_definitivo():
    FakeSMTP.send_error = smtplib.SMTPRecipientsRefused(
        {"x@y.com": (550, b"5.1.1 The email account does not exist")}
    )
    r = _gmail().enviar("x@y.com", CONTENIDO)
    assert r.estado == "fallo_definitivo"


def test_limite_diario_de_gmail_es_transitorio():
    FakeSMTP.send_error = smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded")
    assert _gmail().enviar("a@b.com", CONTENIDO).estado == "fallo_transitorio"


def test_error_5xx_generico_de_datos_es_definitivo():
    FakeSMTP.send_error = smtplib.SMTPDataError(554, b"5.7.1 Message rejected as spam")
    assert _gmail().enviar("a@b.com", CONTENIDO).estado == "fallo_definitivo"


def test_error_4xx_y_de_red_son_transitorios():
    FakeSMTP.send_error = smtplib.SMTPServerDisconnected("conexion cerrada")
    assert _gmail().enviar("a@b.com", CONTENIDO).estado == "fallo_transitorio"
    FakeSMTP.send_error = smtplib.SMTPDataError(421, b"4.7.0 Try again later")
    assert _gmail().enviar("a@b.com", CONTENIDO).estado == "fallo_transitorio"


def test_remitente_gmail_se_usa_en_from():
    _gmail().enviar("dest@ejemplo.com", CONTENIDO)
    assert FakeSMTP.instancias[0].enviado["From"] == "recome@gmail.com"
