"""Contract test T033/T034: reencolado nativo de RabbitMQ ante fallo
transitorio, y verificación de que el mensaje llega a la dead-letter
exchange configurada por el worker (src/consumer/worker.py Worker.run)."""
import json
import time
import uuid
from dataclasses import replace
from unittest.mock import patch

import pika
import pytest

from src.config import Config
from src.consumer.worker import Worker
from src.models.resultado import ResultadoEnvio

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


@pytest.fixture()
def worker(tmp_path):
    config = replace(
        Config.from_env(),
        rabbitmq_url=RABBITMQ_URL,
        rabbitmq_queue=f"test-reencolado-{uuid.uuid4().hex[:8]}",
        rabbitmq_prefetch_count=1,
        rabbitmq_delivery_limit=3,
        sqlite_dedup_path=str(tmp_path / "dedup.db"),
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="test@recome.local",
        vapid_private_key="",
        vapid_public_key="",
        vapid_claims_sub="mailto:test@recome.local",
    )
    return Worker(config)


def test_mensaje_con_fallo_transitorio_se_reencola(worker):
    queue = worker._config.rabbitmq_queue
    conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal = conexion.channel()
    dlx = f"{queue}.dlx"
    dlq = f"{queue}.dead-letter"
    canal.exchange_declare(exchange=dlx, exchange_type="fanout", durable=True)
    canal.queue_declare(queue=dlq, durable=True)
    canal.queue_bind(queue=dlq, exchange=dlx)
    canal.queue_declare(
        queue=queue,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": dlx,
            "x-delivery-limit": worker._config.rabbitmq_delivery_limit,
        },
    )

    mensaje = {
        "id_mensaje": 1,
        "canal": "mail",
        "destinatario": 1,
        "mail": "destino@ejemplo.com",
        "push_sub": None,
        "contenido": {"titulo": "t", "cuerpo": "c"},
    }
    canal.basic_publish(
        exchange="", routing_key=queue, body=json.dumps(mensaje),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conexion.close()

    # Forzamos que el primer intento falle de forma transitoria (mockeando el
    # cliente mail), luego dejamos que el segundo (tras el reencolado nativo
    # de RabbitMQ) proceda normalmente.
    llamadas = {"n": 0}
    enviar_original = worker._cliente_mail.enviar

    def enviar_mock(mail, contenido):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            from src.models.resultado import ResultadoEnvio

            return ResultadoEnvio(id_mensaje=0, estado="fallo_transitorio", canal="mail")
        return enviar_original(mail, contenido)

    conexion2 = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal2 = conexion2.channel()

    acciones = []

    def callback(ch, method, properties, body):
        with patch.object(worker._cliente_mail, "enviar", side_effect=enviar_mock):
            accion, _ = worker.procesar_mensaje(body)
        acciones.append(accion)
        if accion == "ack":
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=(accion == "nack_con_requeue"))
        if len(acciones) >= 2:
            ch.stop_consuming()

    canal2.basic_consume(queue=queue, on_message_callback=callback)
    inicio = time.time()
    while len(acciones) < 2 and time.time() - inicio < 10:
        conexion2.process_data_events(time_limit=1)
    conexion2.close()

    assert acciones == ["nack_con_requeue", "ack"]


def test_mensaje_que_agota_reintentos_termina_en_dead_letter(worker):
    """T034: un mensaje que falla siempre (fallo transitorio persistente)
    agota el x-delivery-limit configurado y termina en la dead-letter
    exchange, en vez de reencolarse indefinidamente."""
    queue = worker._config.rabbitmq_queue
    limite = worker._config.rabbitmq_delivery_limit
    dlx = f"{queue}.dlx"
    dlq = f"{queue}.dead-letter"

    conexion = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal = conexion.channel()
    canal.exchange_declare(exchange=dlx, exchange_type="fanout", durable=True)
    canal.queue_declare(queue=dlq, durable=True)
    canal.queue_bind(queue=dlq, exchange=dlx)
    canal.queue_declare(
        queue=queue,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-dead-letter-exchange": dlx,
            "x-delivery-limit": limite,
        },
    )

    mensaje = {
        "id_mensaje": 2,
        "canal": "mail",
        "destinatario": 1,
        "mail": "destino@ejemplo.com",
        "push_sub": None,
        "contenido": {"titulo": "t", "cuerpo": "c"},
    }
    canal.basic_publish(
        exchange="", routing_key=queue, body=json.dumps(mensaje),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    conexion.close()

    # El cliente mail falla siempre -> el worker devuelve nack_con_requeue en
    # cada entrega, hasta que RabbitMQ agota el x-delivery-limit y manda el
    # mensaje a la dead-letter exchange por su cuenta (el worker deja de
    # recibirlo).
    conexion2 = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal2 = conexion2.channel()
    acciones = []

    def callback(ch, method, properties, body):
        with patch.object(
            worker._cliente_mail,
            "enviar",
            return_value=ResultadoEnvio(id_mensaje=0, estado="fallo_transitorio", canal="mail"),
        ):
            accion, _ = worker.procesar_mensaje(body)
        acciones.append(accion)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    canal2.basic_consume(queue=queue, on_message_callback=callback)
    inicio = time.time()
    # x-delivery-limit=N permite N *reentregas* además de la entrega inicial
    # (total = N + 1 entregas) antes de mandar a dead-letter. Esperamos ese
    # total, con margen.
    total_entregas_esperado = limite + 1
    while len(acciones) < total_entregas_esperado and time.time() - inicio < 15:
        conexion2.process_data_events(time_limit=1)
    canal2.stop_consuming()
    conexion2.close()

    assert len(acciones) == total_entregas_esperado
    assert all(a == "nack_con_requeue" for a in acciones)

    # El mensaje ya no debería estar en la cola principal: quedó en dead-letter.
    conexion3 = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    canal3 = conexion3.channel()
    metodo, _, cuerpo = canal3.basic_get(queue=dlq, auto_ack=True)
    conexion3.close()
    assert metodo is not None
    assert json.loads(cuerpo)["id_mensaje"] == 2
