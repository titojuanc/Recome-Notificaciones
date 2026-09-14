"""Script de utilidad para publicar mensajes de prueba en la cola de
notificaciones, sin tener que escribir el JSON a mano cada vez.

Uso:
    .venv/bin/python scripts/publicar_prueba.py mail
    .venv/bin/python scripts/publicar_prueba.py push
    .venv/bin/python scripts/publicar_prueba.py invalido
    .venv/bin/python scripts/publicar_prueba.py duplicado --id 12345

Requiere RabbitMQ corriendo en localhost:5672 (ver quickstart.md).
"""
from __future__ import annotations

import argparse
import json
import random
import sys

import pika

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"
QUEUE = "notificaciones"


def _publicar(mensaje_o_dict: dict, raw_body: str | None = None) -> None:
    conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal = conexion.channel()
    body = raw_body if raw_body is not None else json.dumps(mensaje_o_dict, ensure_ascii=False)
    canal.basic_publish(
        exchange="",
        routing_key=QUEUE,
        body=body,
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conexion.close()
    print(f"Mensaje publicado en la cola '{QUEUE}':")
    print(body)


def mensaje_mail(id_mensaje: int, mail: str) -> dict:
    return {
        "id_mensaje": id_mensaje,
        "canal": "mail",
        "destinatario": 1,
        "mail": mail,
        "push_sub": None,
        "contenido": {
            "titulo": "Notificación de prueba",
            "cuerpo": "Este es un mensaje de prueba generado por scripts/publicar_prueba.py",
        },
    }


def mensaje_push(id_mensaje: int) -> dict:
    return {
        "id_mensaje": id_mensaje,
        "canal": "push",
        "destinatario": 1,
        "mail": None,
        "push_sub": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/endpoint-de-prueba",
            "keys": {"p256dh": "clave-publica-de-prueba", "auth": "secreto-de-prueba"},
        },
        "contenido": {
            "titulo": "Notificación de prueba",
            "cuerpo": "Este es un mensaje de prueba generado por scripts/publicar_prueba.py",
        },
    }


def mensaje_invalido(id_mensaje: int) -> dict:
    # Sin 'canal' -> falla la validación pydantic (payload inválido, FR-005).
    return {
        "id_mensaje": id_mensaje,
        "destinatario": 1,
        "contenido": {"titulo": "Inválido", "cuerpo": "Falta el campo canal"},
    }


def mensaje_canal_no_soportado(id_mensaje: int) -> dict:
    return {
        "id_mensaje": id_mensaje,
        "canal": "sms",
        "destinatario": 1,
        "mail": None,
        "push_sub": None,
        "contenido": {"titulo": "Inválido", "cuerpo": "Canal sms no soportado"},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "tipo",
        choices=["mail", "push", "invalido", "canal-no-soportado", "duplicado"],
        help="Tipo de mensaje de prueba a publicar",
    )
    parser.add_argument(
        "--id",
        type=int,
        default=None,
        help="id_mensaje a usar (por defecto: aleatorio, salvo en 'duplicado')",
    )
    parser.add_argument(
        "--mail",
        default="prueba@ejemplo.com",
        help="Dirección de mail a usar para tipo='mail' (default: prueba@ejemplo.com)",
    )
    args = parser.parse_args()

    id_mensaje = args.id if args.id is not None else random.randint(10_000, 999_999)

    if args.tipo == "mail":
        _publicar(mensaje_mail(id_mensaje, args.mail))
    elif args.tipo == "push":
        _publicar(mensaje_push(id_mensaje))
    elif args.tipo == "invalido":
        _publicar(mensaje_invalido(id_mensaje))
    elif args.tipo == "canal-no-soportado":
        _publicar(mensaje_canal_no_soportado(id_mensaje))
    elif args.tipo == "duplicado":
        # Publica el mismo mensaje dos veces con el mismo id_mensaje, para
        # probar la deduplicación (ver data-model.md §3). Se usa un id
        # aleatorio por defecto (salvo que se pase --id) para que, incluso si
        # se corre este script varias veces, el registro de dedup (SQLite,
        # persistente entre corridas) no haga que la PRIMERA publicación ya
        # aparezca como duplicada.
        id_fijo = args.id if args.id is not None else id_mensaje
        msg = mensaje_mail(id_fijo, args.mail)
        print(f"Publicando dos veces el mismo id_mensaje={id_fijo}...")
        _publicar(msg)
        _publicar(msg)
        print(
            "\nEsperado en el log del worker: la primera vez 'evento=enviado', "
            "la segunda 'evento=duplicado_descartado'."
        )


if __name__ == "__main__":
    sys.exit(main())
