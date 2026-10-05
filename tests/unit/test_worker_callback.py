"""Unit tests: Worker.procesar_mensaje invoca el callback tras un envío
exitoso de mail (Spec 4), y no lo invoca si el mensaje no trae callback_url.

Se evita RabbitMQ real: se prueba directamente `procesar_mensaje`, que no
depende de la conexión (solo `run()` la usa).
"""
from __future__ import annotations

import json
from dataclasses import replace

import pytest

from src.config import Config
from src.consumer import worker as worker_module
from src.consumer.worker import Worker
from src.models.resultado import ResultadoEnvio


@pytest.fixture()
def config(tmp_path):
    return replace(
        Config.from_env(),
        sqlite_dedup_path=str(tmp_path / "dedup.db"),
        service_api_key="clave-test",
        callback_timeout_seconds=1,
    )


def _mensaje(callback_url: str | None) -> dict:
    payload = {
        "id_mensaje": 123,
        "canal": "mail",
        "destinatario": 1,
        "mail": "vendedor@ejemplo.com",
        "push_sub": None,
        "contenido": {"titulo": "t", "cuerpo": "c"},
    }
    if callback_url is not None:
        payload["callback_url"] = callback_url
    return payload


def test_envio_exitoso_con_callback_url_invoca_confirmar_envio(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(
        worker._cliente_mail, "enviar",
        lambda mail, contenido, adjunto=None: ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="mail"),
    )
    llamadas = []
    monkeypatch.setattr(
        worker_module, "confirmar_envio",
        lambda url, key, timeout, logger=None: llamadas.append((url, key, timeout)) or True,
    )

    accion, mensaje = worker.procesar_mensaje(
        json.dumps(_mensaje("http://localhost:8080/internal/reportes/x/notificado")).encode()
    )

    assert accion == "ack"
    assert len(llamadas) == 1
    url, key, timeout = llamadas[0]
    assert url == "http://localhost:8080/internal/reportes/x/notificado"
    assert key == "clave-test"
    assert timeout == 1


def test_envio_exitoso_sin_callback_url_no_invoca_confirmar_envio(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(
        worker._cliente_mail, "enviar",
        lambda mail, contenido, adjunto=None: ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="mail"),
    )
    llamadas = []
    monkeypatch.setattr(
        worker_module, "confirmar_envio",
        lambda *a, **kw: llamadas.append((a, kw)) or True,
    )

    accion, mensaje = worker.procesar_mensaje(json.dumps(_mensaje(None)).encode())

    assert accion == "ack"
    assert llamadas == []


def test_callback_fallido_no_afecta_el_ack(config, monkeypatch):
    """El mail ya se envió: un callback fallido no debe convertir el ack en nack
    (evita reenviar el mail duplicado por un simple problema de red en el callback)."""
    worker = Worker(config)
    monkeypatch.setattr(
        worker._cliente_mail, "enviar",
        lambda mail, contenido, adjunto=None: ResultadoEnvio(id_mensaje=0, estado="exitoso", canal="mail"),
    )
    monkeypatch.setattr(worker_module, "confirmar_envio", lambda *a, **kw: False)

    accion, _ = worker.procesar_mensaje(
        json.dumps(_mensaje("http://localhost:1/no-existe")).encode()
    )

    assert accion == "ack"
