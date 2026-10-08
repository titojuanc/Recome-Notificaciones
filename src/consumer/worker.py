"""Consumer RabbitMQ (T018): valida, enruta y hace ack/nack.

Orquestación 🔴: wiring central extendido incrementalmente por US2/US3/US4
(ver tasks.md, notas de dependencia).
"""
from __future__ import annotations

import json
import logging

import pika
from pydantic import ValidationError

from src.config import Config
from src.logging_config import configurar_logging, log_evento
from src.models.mensaje import MensajeNotificacion
from src.services.callback import confirmar_envio
from src.services.canales.mail import ClienteMail
from src.services.canales.push import ClientePush
from src.services.dedup import RegistroMensajeProcesado
from src.services.enrutador import enrutar


class Worker:
    def __init__(self, config: Config, logger: logging.Logger | None = None) -> None:
        self._config = config
        self._logger = logger or configurar_logging()
        self._cliente_push = ClientePush(
            vapid_private_key=config.vapid_private_key,
            vapid_claims_sub=config.vapid_claims_sub,
        )
        self._cliente_mail = ClienteMail(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_from=config.smtp_from,
        )
        self._dedup = RegistroMensajeProcesado(config.sqlite_dedup_path)

    def procesar_mensaje(self, cuerpo: bytes) -> tuple[str, MensajeNotificacion | None]:
        """Valida y procesa un mensaje. Devuelve (accion, mensaje_o_None).

        accion ∈ {"ack", "nack_sin_requeue", "nack_con_requeue"}
        """
        try:
            payload = json.loads(cuerpo)
            mensaje = MensajeNotificacion.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            log_evento(self._logger, "rechazado", detalle=str(exc))
            return "nack_sin_requeue", None

        if self._dedup.existe(mensaje.id_mensaje):
            log_evento(
                self._logger,
                "duplicado_descartado",
                id_mensaje=mensaje.id_mensaje,
                canal=mensaje.canal,
            )
            return "ack", mensaje

        resultado = enrutar(
            mensaje, cliente_push=self._cliente_push, cliente_mail=self._cliente_mail
        )

        if resultado.estado == "exitoso":
            self._dedup.registrar(mensaje.id_mensaje, mensaje.canal)
            log_evento(self._logger, "enviado", id_mensaje=mensaje.id_mensaje, canal=mensaje.canal)
            if mensaje.callback_url:
                exito_callback = confirmar_envio(
                    mensaje.callback_url,
                    self._config.service_api_key,
                    self._config.callback_timeout_seconds,
                    self._logger,
                )
                log_evento(
                    self._logger,
                    "callback_confirmado" if exito_callback else "callback_fallido",
                    id_mensaje=mensaje.id_mensaje,
                    canal=mensaje.canal,
                )
            return "ack", mensaje

        if resultado.estado == "fallo_transitorio":
            log_evento(
                self._logger,
                "reencolado",
                id_mensaje=mensaje.id_mensaje,
                canal=mensaje.canal,
                detalle=resultado.detalle,
            )
            return "nack_con_requeue", mensaje

        log_evento(
            self._logger,
            "dead_letter",
            id_mensaje=mensaje.id_mensaje,
            canal=mensaje.canal,
            detalle=resultado.detalle,
        )
        return "nack_sin_requeue", mensaje

    def _on_message(self, channel, method_frame, header_frame, body) -> None:
        accion, _ = self.procesar_mensaje(body)
        if accion == "ack":
            channel.basic_ack(delivery_tag=method_frame.delivery_tag)
        elif accion == "nack_con_requeue":
            channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
        else:
            channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=False)

    def run(self) -> None:
        parametros = pika.URLParameters(self._config.rabbitmq_url)
        conexion = pika.BlockingConnection(parametros)
        canal = conexion.channel()

        # Dead-letter exchange/queue (US2/US3, FR-007): mensajes rechazados
        # (nack sin requeue), que agotan el límite de entregas, o que exceden
        # el TTL configurado terminan acá, en vez de perderse o vivir/
        # reintentarse indefinidamente. Ver quickstart.md y research.md.
        dlx_name = f"{self._config.rabbitmq_queue}.dlx"
        dlq_name = f"{self._config.rabbitmq_queue}.dead-letter"
        canal.exchange_declare(exchange=dlx_name, exchange_type="fanout", durable=True)
        canal.queue_declare(queue=dlq_name, durable=True)
        canal.queue_bind(queue=dlq_name, exchange=dlx_name)

        # Cola tipo quorum (requerido por RabbitMQ para poder usar
        # x-delivery-limit): tras agotar RABBITMQ_DELIVERY_LIMIT reintentos de
        # un fallo transitorio, o tras RABBITMQ_MESSAGE_TTL_MS sin poder
        # procesarse, el mensaje se manda a la dead-letter exchange en vez de
        # reencolarse/vivir para siempre (evita colapsar el sistema).
        canal.queue_declare(
            queue=self._config.rabbitmq_queue,
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-dead-letter-exchange": dlx_name,
                "x-delivery-limit": self._config.rabbitmq_delivery_limit,
                "x-message-ttl": self._config.rabbitmq_message_ttl_ms,
            },
        )
        canal.basic_qos(prefetch_count=self._config.rabbitmq_prefetch_count)
        canal.basic_consume(
            queue=self._config.rabbitmq_queue,
            on_message_callback=self._on_message,
        )
        try:
            canal.start_consuming()
        except KeyboardInterrupt:
            canal.stop_consuming()
        finally:
            conexion.close()


def main() -> None:
    config = Config.from_env()
    worker = Worker(config)
    worker.run()


if __name__ == "__main__":
    main()
