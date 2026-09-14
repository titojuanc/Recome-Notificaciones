"""Contract test T014: flujo feliz completo contra RabbitMQ real.

Requiere RabbitMQ corriendo (docker-compose.test.yml o contenedor manual
`recome-rabbitmq`) en localhost:5672. Se saltea si no está disponible.
"""
import json
import time
import uuid

import pika
import pytest

from src.config import Config
from src.consumer.worker import Worker

RABBITMQ_URL = "amqp://guest:guest@localhost:5672/"


def _rabbitmq_disponible() -> bool:
    try:
        conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        conexion.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _rabbitmq_disponible(), reason="RabbitMQ no disponible en localhost:5672"
)


def _publicar(queue: str, mensaje: dict) -> None:
    conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal = conexion.channel()
    canal.queue_declare(queue=queue, durable=True)
    canal.basic_publish(
        exchange="",
        routing_key=queue,
        body=json.dumps(mensaje),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conexion.close()


def _consumir_uno(queue: str, worker: Worker, timeout: float = 5.0) -> str:
    conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal = conexion.channel()
    canal.queue_declare(queue=queue, durable=True)

    resultado = {"accion": None}

    def callback(ch, method, properties, body):
        accion, _ = worker.procesar_mensaje(body)
        resultado["accion"] = accion
        if accion == "ack":
            ch.basic_ack(delivery_tag=method.delivery_tag)
        elif accion == "nack_con_requeue":
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        ch.stop_consuming()

    canal.basic_consume(queue=queue, on_message_callback=callback)

    inicio = time.time()
    while resultado["accion"] is None and time.time() - inicio < timeout:
        conexion.process_data_events(time_limit=1)

    conexion.close()
    return resultado["accion"]


@pytest.fixture()
def worker(tmp_path):
    config = Config.from_env()
    config = Config(
        rabbitmq_url=config.rabbitmq_url,
        rabbitmq_queue=f"test-notificaciones-{uuid.uuid4().hex[:8]}",
        rabbitmq_prefetch_count=1,
        sqlite_dedup_path=str(tmp_path / "dedup.db"),
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="test@recome.local",
        vapid_private_key="",
        vapid_public_key="",
        vapid_claims_sub="mailto:test@recome.local",
    )
    return Worker(config)


def test_mensaje_valido_mail_se_envia_y_confirma(worker):
    mensaje = {
        "id_mensaje": int(uuid.uuid4().int % 1_000_000),
        "canal": "mail",
        "destinatario": 1,
        "mail": "destino@ejemplo.com",
        "push_sub": None,
        "contenido": {"titulo": "Prueba contrato", "cuerpo": "Cuerpo de prueba"},
    }
    _publicar(worker._config.rabbitmq_queue, mensaje)
    accion = _consumir_uno(worker._config.rabbitmq_queue, worker)
    assert accion == "ack"
