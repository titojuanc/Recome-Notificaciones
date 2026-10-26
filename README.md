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

## Migración de la cola `notificaciones` (clásica → quorum)

La cola la declara únicamente este worker. Antes de `dev` se declaraba clásica con solo
`x-dead-letter-exchange`; ahora es `quorum` con `x-dead-letter-exchange`,
`x-delivery-limit` y `x-message-ttl`. RabbitMQ rechaza redeclarar una cola con otros
argumentos (`PRECONDITION_FAILED`), así que en cada entorno donde ya exista hay que
**borrarla antes de desplegar** (se pierden los mensajes pendientes):

1. Detener los publicadores (api-general, Recos-Auto) y este worker.
2. Borrar `notificaciones`, `notificaciones.dead-letter` y el exchange `notificaciones.dlx`
   (UI de management o `rabbitmqadmin delete queue name=notificaciones`, etc.).
3. Desplegar primero este worker (crea la topología nueva) y luego los publicadores.

Ni api-general ni Recos-Auto declaran esta cola: solo publican.

## Operar el broker de otros equipos

Este equipo opera el RabbitMQ compartido: crea el vhost por entorno, los usuarios y sus
permisos (RD-120). Ver [docs/BROKER_RABBITMQ.md](docs/BROKER_RABBITMQ.md) y
`infra/rabbitmq/provision.sh`.

## Correr los tests

```bash
pytest tests/unit          # 🟢 validación, dedup, enrutamiento (sin infraestructura)
pytest tests/integration   # 🟡 clientes push (mock) / mail (Mailpit real)
pytest tests/contract      # 🔴 contra RabbitMQ real (se saltean si no está disponible)
```

Ver `specs/002-worker-notificaciones/quickstart.md` para ejemplos de mensajes,
detalles de deduplicación, dead-letter exchange y limitaciones conocidas.

## SMTP con autenticación (Gmail)

Variables: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_SECURITY` (`none`|`starttls`|`ssl`), `SMTP_TIMEOUT_SECONDS`.
Gmail: `smtp.gmail.com`, `587`, `starttls`, usuario = cuenta y contraseña de aplicación de 16 caracteres (se ignoran los espacios).
Validaciones: usuario sin contraseña o autenticación con `SMTP_SECURITY=none` se rechazan. La contraseña nunca aparece en los logs.
