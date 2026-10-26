"""Adaptador de envío mail vía SMTP (T016).

Interfaz simple: enviar(mail, contenido) -> ResultadoEnvio

Tres modos, según configuración:
  - Mailpit en desarrollo/tests: SMTP_HOST=localhost, SMTP_PORT=1025, sin usuario ni TLS.
  - Gmail (SMTP de Google): SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_SECURITY=starttls
    (o 465 con ssl), SMTP_USER=<cuenta>@gmail.com y SMTP_PASSWORD=<contraseña de aplicación>.
    Requiere verificación en dos pasos y una «contraseña de aplicación» de 16 caracteres
    (https://myaccount.google.com/apppasswords); la contraseña normal de la cuenta NO funciona.
    Gmail reescribe el remitente a la cuenta autenticada, así que SMTP_FROM debe ser esa cuenta
    (o un alias «Enviar como» ya verificado).
  - Otro SMTP real (SES, SendGrid, ...): mismas variables.

Clasificación de errores:
  - Destinatario rechazado o 5xx permanente (dirección inexistente, spam) -> fallo_definitivo
    (dead-letter).
  - Todo lo demás -> fallo_transitorio (reencola hasta el límite de entregas). Incluye una
    autenticación fallida: es un error de configuración, y así el mensaje termina en la DLQ,
    desde donde se reprocesa al corregir la credencial, en lugar de perderse.
  - Límite diario de Gmail (550 5.4.5) -> transitorio: es un tope temporal, no una dirección mala.
"""
from __future__ import annotations

import base64
import smtplib
from email.message import EmailMessage

from src.models.mensaje import Adjunto, Contenido
from src.models.resultado import ResultadoEnvio

_SEGURIDADES = ("none", "starttls", "ssl")
_LIMITES_TEMPORALES = ("5.4.5", "daily user sending limit", "rate limit", "too many")


def _es_limite_temporal(texto: str) -> bool:
    t = texto.lower()
    return any(marca in t for marca in _LIMITES_TEMPORALES)


class ClienteMail:
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_from: str,
        smtp_user: str = "",
        smtp_password: str = "",
        smtp_security: str = "none",
        smtp_timeout_seconds: float = 5,
    ) -> None:
        if smtp_security not in _SEGURIDADES:
            raise ValueError(
                f"SMTP_SECURITY inválido: {smtp_security!r} (usar {', '.join(_SEGURIDADES)})"
            )
        if smtp_user and not smtp_password:
            raise ValueError("SMTP_USER requiere SMTP_PASSWORD")
        if smtp_user and smtp_security == "none":
            raise ValueError(
                "SMTP_USER sin cifrado: la contraseña viajaría en claro; "
                "configurar SMTP_SECURITY=starttls o ssl"
            )
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_from = smtp_from
        self._smtp_user = smtp_user
        # Google muestra la contraseña de aplicación en grupos de 4 separados por espacios.
        self._smtp_password = smtp_password.replace(" ", "")
        self._smtp_security = smtp_security
        self._timeout = smtp_timeout_seconds

    def _conectar(self) -> smtplib.SMTP:
        if self._smtp_security == "ssl":
            return smtplib.SMTP_SSL(self._smtp_host, self._smtp_port, timeout=self._timeout)
        return smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=self._timeout)

    def enviar(
        self, mail: str, contenido: Contenido, adjunto: Adjunto | None = None
    ) -> ResultadoEnvio:
        msg = EmailMessage()
        msg["From"] = self._smtp_from
        msg["To"] = mail
        msg["Subject"] = contenido.titulo
        msg.set_content(contenido.cuerpo)

        if adjunto is not None:
            maintype, _, subtype = adjunto.content_type.partition("/")
            msg.add_attachment(
                base64.b64decode(adjunto.contenido_base64),
                maintype=maintype or "application",
                subtype=subtype or "octet-stream",
                filename=adjunto.nombre_archivo,
            )

        try:
            with self._conectar() as smtp:
                if self._smtp_security == "starttls":
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.ehlo()
                if self._smtp_user:
                    smtp.login(self._smtp_user, self._smtp_password)
                smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            texto = str(exc)
            estado = "fallo_transitorio" if _es_limite_temporal(texto) else "fallo_definitivo"
            return ResultadoEnvio(
                id_mensaje=0,
                estado=estado,
                canal="mail",
                detalle=self._sin_secreto(texto),
            )
        except smtplib.SMTPAuthenticationError as exc:
            return ResultadoEnvio(
                id_mensaje=0,
                estado="fallo_transitorio",
                canal="mail",
                detalle=self._sin_secreto(
                    f"autenticación SMTP rechazada ({exc.smtp_code}): {exc.smtp_error!r}"
                ),
            )
        except smtplib.SMTPResponseException as exc:
            texto = f"{exc.smtp_code} {exc.smtp_error!r}"
            permanente = 500 <= exc.smtp_code < 600 and not _es_limite_temporal(texto)
            return ResultadoEnvio(
                id_mensaje=0,
                estado="fallo_definitivo" if permanente else "fallo_transitorio",
                canal="mail",
                detalle=self._sin_secreto(texto),
            )
        except (OSError, smtplib.SMTPException) as exc:
            return ResultadoEnvio(
                id_mensaje=0,
                estado="fallo_transitorio",
                canal="mail",
                detalle=self._sin_secreto(str(exc)),
            )

        return ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="mail")

    def _sin_secreto(self, texto: str) -> str:
        """Los detalles terminan en logs: la contraseña nunca debe aparecer."""
        return texto.replace(self._smtp_password, "***") if self._smtp_password else texto
