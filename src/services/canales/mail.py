"""Adaptador de envío mail vía SMTP (T016).

Interfaz simple: enviar(mail, contenido) -> ResultadoEnvio

Apunta a Mailpit en desarrollo/tests (SMTP falso) o a un SMTP real en
producción, según configuración (SMTP_HOST/SMTP_PORT).
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage

from src.models.mensaje import Contenido
from src.models.resultado import ResultadoEnvio


class ClienteMail:
    def __init__(self, smtp_host: str, smtp_port: int, smtp_from: str) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_from = smtp_from

    def enviar(self, mail: str, contenido: Contenido) -> ResultadoEnvio:
        msg = EmailMessage()
        msg["From"] = self._smtp_from
        msg["To"] = mail
        msg["Subject"] = contenido.titulo
        msg.set_content(contenido.cuerpo)

        try:
            with smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=5) as smtp:
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            return ResultadoEnvio(
                id_mensaje=0,
                estado="fallo_transitorio",
                canal="mail",
                detalle=str(exc),
            )

        return ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="mail")
