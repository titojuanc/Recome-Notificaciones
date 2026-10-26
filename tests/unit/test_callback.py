"""Unit tests: confirmar_envio (Spec 4 - callback hacia recome-api-general).

Usa http.server local en vez de mockear urllib, para validar el
comportamiento real (headers enviados, manejo de status codes y timeouts).
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.services.callback import confirmar_envio


class _Handler(BaseHTTPRequestHandler):
    status_a_responder = 204
    headers_recibidos: dict[str, str] = {}

    def do_POST(self):  # noqa: N802 (nombre impuesto por BaseHTTPRequestHandler)
        _Handler.headers_recibidos = dict(self.headers)
        self.send_response(_Handler.status_a_responder)
        self.end_headers()

    def log_message(self, format, *args):  # silencia logs del servidor de prueba
        pass


@pytest.fixture()
def servidor():
    httpd = HTTPServer(("localhost", 0), _Handler)
    hilo = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo.start()
    yield httpd
    httpd.shutdown()
    hilo.join(timeout=2)


def test_confirmar_envio_exitoso_envia_header_api_key(servidor):
    _Handler.status_a_responder = 204
    puerto = servidor.server_address[1]
    ok = confirmar_envio(f"http://localhost:{puerto}/callback", "clave-secreta", timeout_seconds=2)
    assert ok is True
    assert _Handler.headers_recibidos.get("X-Service-Api-Key") == "clave-secreta"


def test_confirmar_envio_status_error_devuelve_false(servidor):
    _Handler.status_a_responder = 401
    puerto = servidor.server_address[1]
    ok = confirmar_envio(f"http://localhost:{puerto}/callback", "clave-invalida", timeout_seconds=2)
    assert ok is False


def test_confirmar_envio_conexion_fallida_devuelve_false():
    # Puerto sin nada escuchando: la conexión debe fallar de inmediato.
    ok = confirmar_envio("http://localhost:1/callback", "clave", timeout_seconds=1)
    assert ok is False
