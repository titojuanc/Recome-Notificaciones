"""Unit tests: MensajeNotificacion.

Cubre T010 (payload válido), T020/T021/T022 (rechazos básicos), T022b
(validación cruzada canal/mail/push_sub, FR-013), T022c (formato de mail,
FR-015).
"""
import pytest
from pydantic import ValidationError

from src.models.mensaje import MensajeNotificacion

CONTENIDO = {"titulo": "Nuevo lanzamiento", "cuerpo": "Te podría interesar"}

MENSAJE_MAIL_VALIDO = {
    "id_mensaje": 1,
    "canal": "mail",
    "destinatario": 42,
    "mail": "usuario@ejemplo.com",
    "push_sub": None,
    "contenido": CONTENIDO,
}

MENSAJE_PUSH_VALIDO = {
    "id_mensaje": 2,
    "canal": "push",
    "destinatario": 42,
    "mail": None,
    "push_sub": {
        "endpoint": "https://fcm.googleapis.com/fcm/send/ejemplo",
        "keys": {"p256dh": "clave-publica", "auth": "secreto"},
    },
    "contenido": CONTENIDO,
}


# --- T010: payload válido ---


def test_mensaje_mail_valido():
    msg = MensajeNotificacion.model_validate(MENSAJE_MAIL_VALIDO)
    assert msg.id_mensaje == 1
    assert msg.canal == "mail"
    assert msg.mail == "usuario@ejemplo.com"
    assert msg.push_sub is None


def test_mensaje_push_valido():
    msg = MensajeNotificacion.model_validate(MENSAJE_PUSH_VALIDO)
    assert msg.canal == "push"
    assert msg.push_sub.endpoint.startswith("https://")
    assert msg.mail is None


# --- T020: falta canal ---


def test_rechaza_sin_canal():
    payload = dict(MENSAJE_MAIL_VALIDO)
    del payload["canal"]
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


# --- T021: canal no soportado ---


def test_rechaza_canal_no_soportado():
    payload = dict(MENSAJE_MAIL_VALIDO)
    payload["canal"] = "sms"
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


# --- T022: campo extra no declarado ---


def test_rechaza_campo_extra():
    payload = dict(MENSAJE_MAIL_VALIDO)
    payload["tipo_evento"] = "juego_recomendado"
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


# --- T022b: validación cruzada canal/mail/push_sub (FR-013) ---


def test_rechaza_mail_sin_campo_mail():
    payload = dict(MENSAJE_MAIL_VALIDO)
    payload["mail"] = None
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


def test_rechaza_mail_con_push_sub_presente():
    payload = dict(MENSAJE_MAIL_VALIDO)
    payload["push_sub"] = MENSAJE_PUSH_VALIDO["push_sub"]
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


def test_rechaza_push_sin_push_sub():
    payload = dict(MENSAJE_PUSH_VALIDO)
    payload["push_sub"] = None
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


def test_rechaza_push_con_mail_presente():
    payload = dict(MENSAJE_PUSH_VALIDO)
    payload["mail"] = "usuario@ejemplo.com"
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)


# --- T022c: formato de mail inválido (FR-015) ---


def test_rechaza_mail_formato_invalido():
    payload = dict(MENSAJE_MAIL_VALIDO)
    payload["mail"] = "no-es-un-mail"
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(payload)
