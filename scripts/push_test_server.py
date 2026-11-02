"""Servidor local de prueba para el push (solo para verificar credenciales VAPID).

Uso, desde Recome-Notificaciones/:
    .venv/bin/python scripts/push_test_server.py

Lee las claves de .env.vapid y atiende a la página recome-Frontend/public/push-test.html:
    GET  /vapid-public-key -> {"publicKey": "..."}
    POST /enviar           -> {"subscription": {...}, "titulo": "...", "cuerpo": "..."}
Envía con ClientePush (el mismo adaptador que usa el worker). Solo escucha en 127.0.0.1.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.models.mensaje import Contenido, PushSubscription  # noqa: E402
from src.services.canales.push import ClientePush  # noqa: E402

PUERTO = 8765
ORIGENES = ("http://localhost:5173", "http://127.0.0.1:5173")


def _leer_env(ruta: Path) -> dict[str, str]:
    valores = {}
    for linea in ruta.read_text().splitlines():
        if "=" in linea and not linea.lstrip().startswith("#"):
            clave, _, valor = linea.partition("=")
            valores[clave.strip()] = valor.strip().strip('"').strip("'")
    return valores


ENV = _leer_env(RAIZ / ".env.vapid")
CLIENTE = ClientePush(ENV["VAPID_PRIVATE_KEY"], ENV.get("VAPID_CLAIMS_SUB", "mailto:admin@recome.local"))


class Handler(BaseHTTPRequestHandler):
    def _responder(self, codigo: int, cuerpo: dict) -> None:
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        origen = self.headers.get("Origin")
        if origen in ORIGENES:
            self.send_header("Access-Control-Allow-Origin", origen)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_OPTIONS(self) -> None:  # preflight CORS
        self.send_response(204)
        origen = self.headers.get("Origin")
        if origen in ORIGENES:
            self.send_header("Access-Control-Allow-Origin", origen)
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/vapid-public-key":
            self._responder(200, {"publicKey": ENV["VAPID_PUBLIC_KEY"]})
        else:
            self._responder(404, {"error": "no encontrado"})

    def do_POST(self) -> None:
        if self.path != "/enviar":
            return self._responder(404, {"error": "no encontrado"})
        try:
            largo = int(self.headers.get("Content-Length", 0))
            pedido = json.loads(self.rfile.read(largo))
            sub = PushSubscription(**pedido["subscription"])
            contenido = Contenido(
                titulo=pedido.get("titulo") or "Prueba push RECOME",
                cuerpo=pedido.get("cuerpo") or "Si ves esto, las credenciales VAPID funcionan.",
            )
        except Exception as exc:  # pedido mal formado
            return self._responder(400, {"error": f"pedido inválido: {exc}"})
        resultado = CLIENTE.enviar(sub, contenido)
        self._responder(
            200,
            {
                "estado": resultado.estado,
                "detalle": resultado.detalle,
                "suscripcion_caducada": resultado.suscripcion_caducada,
            },
        )


if __name__ == "__main__":
    print(f"Servidor de prueba push en http://127.0.0.1:{PUERTO} (Ctrl+C para salir)")
    HTTPServer(("127.0.0.1", PUERTO), Handler).serve_forever()
