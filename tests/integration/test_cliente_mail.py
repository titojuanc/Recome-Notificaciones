"""Integration test T013: cliente mail contra Mailpit real (research.md §6).

Requiere Mailpit corriendo (docker-compose.test.yml o contenedor manual
`recome-mailpit`) en localhost:1025 (SMTP) / localhost:8025 (API HTTP).
Se saltea automáticamente si Mailpit no está disponible.
"""
import smtplib
import urllib.error
import urllib.request

import pytest

from src.models.mensaje import Contenido
from src.services.canales.mail import ClienteMail

SMTP_HOST = "localhost"
SMTP_PORT = 1025
MAILPIT_API = "http://localhost:8025/api/v1/messages"


def _mailpit_disponible() -> bool:
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not _mailpit_disponible(), reason="Mailpit no disponible en localhost:1025"
)


def _limpiar_mailpit():
    req = urllib.request.Request(MAILPIT_API.replace("/api/v1/", "/api/v1/") , method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=2)
    except (urllib.error.URLError, OSError):
        pass


def test_cliente_mail_envia_correctamente():
    _limpiar_mailpit()
    cliente = ClienteMail(
        smtp_host=SMTP_HOST, smtp_port=SMTP_PORT, smtp_from="notificaciones@recome.local"
    )
    contenido = Contenido(titulo="Asunto de prueba", cuerpo="Cuerpo de prueba")

    resultado = cliente.enviar("destino@ejemplo.com", contenido)

    assert resultado.estado == "exitoso"
