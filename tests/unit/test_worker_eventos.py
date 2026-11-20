"""Unit tests: el worker avisa a api-general cada envío exitoso de un mensaje con `tipo`.

(Spec 013 de api-general.)

Se prueba `procesar_mensaje` (sin RabbitMQ) y el cliente HTTP contra un servidor local efímero.
"""
from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from pydantic import ValidationError

from src.config import Config
from src.consumer import worker as worker_module
from src.consumer.worker import Worker
from src.models.mensaje import MensajeNotificacion
from src.models.resultado import ResultadoEnvio
from src.services.eventos import reportar_envio


@pytest.fixture()
def config(tmp_path):
    return replace(
        Config.from_env(),
        sqlite_dedup_path=str(tmp_path / "dedup.db"),
        service_api_key="test.clave-test",
        callback_timeout_seconds=1,
        api_general_base_url="http://api-general.test/api/v1",
    )


def _mensaje(**extra) -> dict:
    payload = {
        "id_mensaje": 77,
        "canal": "mail",
        "destinatario": 1,
        "mail": "ana@ejemplo.com",
        "push_sub": None,
        "contenido": {"titulo": "t", "cuerpo": "c", "url": "/descubrir?n=recomendacion_dia"},
    }
    payload.update(extra)
    return payload


def _exitoso(canal: str = "mail"):
    return lambda *a, **kw: ResultadoEnvio(id_mensaje=0, estado="exitoso", canal=canal)


def _fallido(*a, **kw):
    return ResultadoEnvio(
        id_mensaje=0, estado="fallo_definitivo", canal="mail", detalle="rechazado"
    )


def _espiar(monkeypatch, retorno=True):
    llamadas = []
    monkeypatch.setattr(
        worker_module,
        "reportar_envio",
        lambda *a, **kw: llamadas.append((a, kw)) or retorno,
    )
    return llamadas


def test_mensaje_con_tipo_reporta_el_envio(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(worker._cliente_mail, "enviar", _exitoso())
    llamadas = _espiar(monkeypatch)

    accion, _ = worker.procesar_mensaje(json.dumps(_mensaje(tipo="recomendacion_dia")).encode())

    assert accion == "ack"
    assert len(llamadas) == 1
    args, kw = llamadas[0]
    assert args == ("http://api-general.test/api/v1", "test.clave-test", 1)
    assert (kw["tipo"], kw["canal"], kw["id_mensaje"]) == ("recomendacion_dia", "mail", 77)


def test_reporta_el_canal_que_realmente_se_uso(config, monkeypatch):
    """Un push cuya suscripción caducó sale por mail de respaldo: el evento lleva `mail`."""
    worker = Worker(config)
    monkeypatch.setattr(worker_module, "enrutar", lambda *a, **kw: ResultadoEnvio(
        id_mensaje=77, estado="exitoso", canal="mail"))
    llamadas = _espiar(monkeypatch)
    mensaje = _mensaje(tipo="anuncio", canal="push", push_sub={
        "endpoint": "https://push.example/1", "keys": {"p256dh": "k", "auth": "a"}})

    worker.procesar_mensaje(json.dumps(mensaje).encode())

    assert llamadas[0][1]["canal"] == "mail"


def test_mensaje_sin_tipo_no_reporta(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(worker._cliente_mail, "enviar", _exitoso())
    llamadas = _espiar(monkeypatch)

    accion, _ = worker.procesar_mensaje(json.dumps(_mensaje()).encode())

    assert accion == "ack"
    assert llamadas == []


def test_sin_url_de_api_general_no_reporta(config, monkeypatch):
    worker = Worker(replace(config, api_general_base_url=""))
    monkeypatch.setattr(worker._cliente_mail, "enviar", _exitoso())
    llamadas = _espiar(monkeypatch)

    accion, _ = worker.procesar_mensaje(json.dumps(_mensaje(tipo="anuncio")).encode())

    assert accion == "ack"
    assert llamadas == []


def test_un_envio_fallido_no_se_reporta(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(worker._cliente_mail, "enviar", _fallido)
    llamadas = _espiar(monkeypatch)

    accion, _ = worker.procesar_mensaje(json.dumps(_mensaje(tipo="anuncio")).encode())

    assert accion == "nack_sin_requeue"
    assert llamadas == []


def test_un_duplicado_no_se_vuelve_a_reportar(config, monkeypatch):
    worker = Worker(config)
    monkeypatch.setattr(worker._cliente_mail, "enviar", _exitoso())
    llamadas = _espiar(monkeypatch)
    cuerpo = json.dumps(_mensaje(tipo="anuncio")).encode()

    worker.procesar_mensaje(cuerpo)
    worker.procesar_mensaje(cuerpo)

    assert len(llamadas) == 1


def test_reporte_fallido_no_afecta_el_ack(config, monkeypatch):
    """El envío ya ocurrió: un aviso fallido a api-general no debe convertir el ack en nack."""
    worker = Worker(config)
    monkeypatch.setattr(worker._cliente_mail, "enviar", _exitoso())
    _espiar(monkeypatch, retorno=False)

    accion, _ = worker.procesar_mensaje(json.dumps(_mensaje(tipo="anuncio")).encode())

    assert accion == "ack"


def test_tipo_desconocido_se_rechaza_como_mensaje_invalido():
    with pytest.raises(ValidationError):
        MensajeNotificacion.model_validate(_mensaje(tipo="codigo_de_verificacion"))


# --- Cliente HTTP ----------------------------------------------------------------------


class _Receptor(BaseHTTPRequestHandler):
    recibidos: list[dict] = []
    status = 204

    def do_POST(self):  # noqa: N802 (API de http.server)
        largo = int(self.headers.get("Content-Length", 0))
        _Receptor.recibidos.append({
            "path": self.path,
            "clave": self.headers.get("X-Internal-API-Key"),
            "tipo_contenido": self.headers.get("Content-Type"),
            "cuerpo": json.loads(self.rfile.read(largo)),
        })
        self.send_response(_Receptor.status)
        self.end_headers()

    def log_message(self, *a):  # silencio
        pass


@pytest.fixture()
def servidor():
    _Receptor.recibidos = []
    _Receptor.status = 204
    http = HTTPServer(("127.0.0.1", 0), _Receptor)
    hilo = threading.Thread(target=http.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{http.server_address[1]}/api/v1"
    http.shutdown()


def test_el_cliente_manda_json_con_la_clave_en_el_header_correcto(servidor):
    ok = reportar_envio(servidor, "test.secreto", 2, tipo="anuncio", canal="push", id_mensaje=5)
    assert ok is True

    [recibido] = _Receptor.recibidos
    assert recibido["path"] == "/api/v1/internal/v1/notification-events"
    assert recibido["clave"] == "test.secreto"
    assert recibido["tipo_contenido"] == "application/json"
    assert recibido["cuerpo"] == {"tipo": "anuncio", "canal": "push", "id_mensaje": 5}


def test_el_cliente_devuelve_false_ante_un_error_http(servidor):
    _Receptor.status = 401
    assert reportar_envio(servidor, "mala", 2, tipo="anuncio", canal="push", id_mensaje=5) is False


def test_el_cliente_devuelve_false_si_api_general_no_responde():
    ok = reportar_envio(
        "http://127.0.0.1:1/api/v1", "k", 1, tipo="anuncio", canal="mail", id_mensaje=1
    )
    assert ok is False


def test_el_cliente_no_loguea_la_clave(servidor, caplog):
    _Receptor.status = 500
    with caplog.at_level("WARNING"):
        reportar_envio(
            servidor,
            "test.secreto-que-no-debe-salir",
            2,
            tipo="anuncio",
            canal="mail",
            id_mensaje=1,
        )
    assert "secreto-que-no-debe-salir" not in caplog.text
