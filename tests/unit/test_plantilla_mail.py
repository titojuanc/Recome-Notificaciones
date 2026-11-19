"""Unit: plantilla HTML de los mails y su integración en ClienteMail."""
from src.models.mensaje import Contenido
from src.services.canales import mail as mail_mod
from src.services.canales.mail import ClienteMail
from src.services.canales.plantilla_mail import html_mail, texto_plano


class _SMTP:
    enviado = None

    def __init__(self, *a, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def send_message(self, msg):
        _SMTP.enviado = msg


def test_html_escapa_el_contenido_y_separa_parrafos():
    html = html_mail(Contenido(titulo="Hola <b>", cuerpo="Uno & dos\n\nTres\ncuatro"))
    assert "Hola &lt;b&gt;" in html
    assert "Uno &amp; dos</p>" in html
    assert "Tres<br>cuatro</p>" in html
    assert "<b>" not in html


def test_destacado_aparece_resaltado_en_html_y_en_texto():
    contenido = Contenido(titulo="Código", cuerpo="Usalo ya.", destacado="123456")
    assert "letter-spacing:8px" in html_mail(contenido)
    assert ">123456</span>" in html_mail(contenido)
    assert texto_plano(contenido).startswith("Usalo ya.\n\n123456\n\n")


def test_sin_destacado_no_hay_caja():
    assert "letter-spacing:8px" not in html_mail(Contenido(titulo="t", cuerpo="c"))


def test_cliente_mail_envia_texto_y_html(monkeypatch):
    monkeypatch.setattr(mail_mod.smtplib, "SMTP", _SMTP)
    cliente = ClienteMail(smtp_host="localhost", smtp_port=1025, smtp_from="r@x.com")
    contenido = Contenido(titulo="Asunto", cuerpo="Cuerpo", destacado="654321")
    assert cliente.enviar("a@b.com", contenido).estado == "exitoso"
    msg = _SMTP.enviado
    assert msg.get_content_type() == "multipart/alternative"
    assert "654321" in msg.get_body(preferencelist=("plain",)).get_content()
    assert "654321" in msg.get_body(preferencelist=("html",)).get_content()
