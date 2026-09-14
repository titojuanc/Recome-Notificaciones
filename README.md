# Recome-Notificaciones

Módulo de notificaciones del sistema RecoMe.

Worker de notificaciones (push/mail): consume mensajes de una cola RabbitMQ,
valida el payload estrictamente, envía la notificación por el canal indicado
(push o mail), evita reenviar duplicados, y delega los reintentos ante fallos
transitorios al mecanismo nativo de RabbitMQ (nack/requeue + dead-letter).

Ver la especificación completa en
[`specs/002-worker-notificaciones/`](specs/002-worker-notificaciones/) (spec, plan,
research, data-model, contracts, quickstart, tasks).

## Requisitos

- Python 3.11+
- Docker (para RabbitMQ y Mailpit en desarrollo/tests)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env  # y completar valores si aplica
```

## Levantar infraestructura de desarrollo/tests

```bash
docker compose -f docker-compose.test.yml up -d
```

Esto levanta:
- **RabbitMQ** (`recome-rabbitmq`): panel en `http://localhost:15672`
  (usuario/clave `guest`/`guest`), AMQP en `5672`.
- **Mailpit** (`recome-mailpit`): SMTP falso en `1025`, UI web en
  `http://localhost:8025`.

## Correr el worker

```bash
python -m src.consumer.worker
```

## Correr los tests

```bash
pytest tests/unit          # 🟢 validación, dedup, enrutamiento (sin infraestructura)
pytest tests/integration   # 🟡 clientes push (mock) / mail (Mailpit real)
pytest tests/contract      # 🔴 contra RabbitMQ real (se saltean si no está disponible)
```

Ver `specs/002-worker-notificaciones/quickstart.md` para ejemplos de mensajes,
detalles de deduplicación, dead-letter exchange y limitaciones conocidas.
