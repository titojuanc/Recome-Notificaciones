# Quickstart: Worker de Notificaciones (Push/Mail)

**Feature**: `002-worker-notificaciones`

## Qué hace este worker

Consume mensajes de una cola RabbitMQ, valida su esquema, envía la notificación por
el canal indicado (push o mail), evita reenviar duplicados, y delega los reintentos
ante fallos transitorios al propio RabbitMQ.

## Requisitos previos

- Python 3.11+
- Un RabbitMQ accesible (local vía Docker para desarrollo/tests, o el de
  infraestructura compartida en otros ambientes)
- Mailpit (servidor SMTP falso, para probar el canal `mail` sin enviar correos
  reales durante desarrollo/tests)
- Variables de entorno (ver `.env.example`, a crear en fase de implementación):
  - `RABBITMQ_URL`
  - `RABBITMQ_QUEUE_NOTIFICACIONES`
  - `SQLITE_DEDUP_PATH`
  - `SMTP_HOST`, `SMTP_PORT` (apuntan a Mailpit en desarrollo/tests)
  - Credenciales de push real (VAPID keys para `pywebpush`, a definir en
    implementación)

## Levantar RabbitMQ y Mailpit localmente (para desarrollo/tests)

Se usa una red Docker dedicada para que, en el futuro, el worker (corriendo también
en un contenedor) pueda resolver estos servicios por nombre en vez de IP.

```bash
docker network create recome-notificaciones-net

docker run -d --name recome-rabbitmq --network recome-notificaciones-net \
  -p 5672:5672 -p 15672:15672 rabbitmq:3-management

docker run -d --name recome-mailpit --network recome-notificaciones-net \
  -p 1025:1025 -p 8025:8025 axllent/mailpit
```

**RabbitMQ**:
- Panel de administración: `http://localhost:15672` (usuario/clave por defecto:
  `guest`/`guest`)
- Puerto AMQP (para `pika`, o `RABBITMQ_URL`): `5672`

**Mailpit** (servidor SMTP falso para el canal `mail`):
- Puerto SMTP (para el cliente de mail del worker, `SMTP_HOST`/`SMTP_PORT`): `1025`
- UI web para ver los mails "enviados": `http://localhost:8025` — ningún mail sale
  realmente a internet, todo queda capturado acá.

Si el worker corre como contenedor en la misma red, usar `recome-rabbitmq` y
`recome-mailpit` como hostnames (en vez de `localhost`).

## Estrategia de testing por canal (sin depender de proveedores reales)

| Canal | Nivel de test | Estrategia |
|-------|---------------|------------|
| `mail` | 🟡 Integración | Contra **Mailpit** (SMTP real, pero capturado localmente — sin salir a internet) |
| `push` | 🟡 Integración | **Mock de `pywebpush`** (se verifica que se llama con los parámetros correctos; no existe un "servidor push falso" estándar como Mailpit) |
| Ambos | 🔴 Contrato/consumer | El "envío" en sí sigue usando Mailpit (mail) o mock (push); lo que se valida acá es el wiring completo contra RabbitMQ real |

Para probar el flujo real de push de punta a punta (no automatizado, exploratorio),
se puede generar una Push Subscription real desde un navegador de prueba y enviarle
un push real — pero esto no es apto para CI, solo para validación manual puntual.

## Ejecutar el worker (una vez implementado)

```bash
pip install -r requirements.txt
python -m src.consumer.worker
```

## Publicar un mensaje de prueba manualmente

Usando la consola de management de RabbitMQ (`http://localhost:15672`) o `pika`
desde un script, publicar en la cola configurada un mensaje como:

```json
{
  "id_mensaje": 1001,
  "canal": "mail",
  "destinatario": 42,
  "mail": "usuario@ejemplo.com",
  "push_sub": null,
  "contenido": {
    "titulo": "Nuevo lanzamiento recomendado",
    "cuerpo": "Encontramos un juego que podría interesarte."
  }
}
```

O, para canal push:

```json
{
  "id_mensaje": 1002,
  "canal": "push",
  "destinatario": 42,
  "mail": null,
  "push_sub": {
    "endpoint": "https://fcm.googleapis.com/fcm/send/ejemplo-endpoint",
    "keys": {
      "p256dh": "clave-publica-base64",
      "auth": "secreto-auth-base64"
    }
  },
  "contenido": {
    "titulo": "Nuevo lanzamiento recomendado",
    "cuerpo": "Encontramos un juego que podría interesarte."
  }
}
```

El worker debería: validarlo, verificar que `id_mensaje` no fue procesado antes,
enviar el mail (real o mockeado según el ambiente), registrar el `id_mensaje` como
procesado, y hacer `ack`.

## Probar deduplicación

Publicar el mismo mensaje (mismo `id_mensaje`) una segunda vez. El worker debe
descartarlo sin generar un segundo envío (ver `data-model.md` § 3).

## Probar rechazo de mensaje inválido

Publicar un mensaje sin `canal`, o con `canal: "sms"` (no soportado). El worker debe
rechazarlo/enviarlo a dead-letter sin intentar ningún envío (FR-005).

También se rechaza un mensaje con `canal: "mail"` que traiga `push_sub` (o le falte
`mail`), o `canal: "push"` que traiga `mail` (o le falte `push_sub`) — validación
cruzada estricta (FR-013).

## Correr tests

```bash
pytest tests/unit          # 🟢 validación, dedup, enrutamiento (sin infraestructura)
pytest tests/integration   # 🟡 clientes push/mail (mockeados o sandbox real)
pytest tests/contract      # 🔴 contra el schema de contracts/ + RabbitMQ real (Docker)
```

## Dead-letter exchange

El worker declara, para la cola configurada (`RABBITMQ_QUEUE_NOTIFICACIONES`), un
exchange `<queue>.dlx` (fanout) enlazado a una cola `<queue>.dead-letter`, y declara
la cola principal con el argumento `x-dead-letter-exchange` apuntando a ese exchange
(ver `src/consumer/worker.py`, método `run`). Así:

- Un mensaje rechazado por el worker (`nack(requeue=False)`, ej. payload inválido)
  termina en `<queue>.dead-letter` automáticamente.
- Un mensaje con fallo transitorio (`nack(requeue=True)`) es reencolado por
  RabbitMQ en la cola principal (comportamiento nativo, sin lógica de reintento
  propia del worker).

**Limitación conocida**: esta iteración no configura un límite de entregas
(`x-delivery-limit`, disponible en colas quorum) para forzar el paso automático a
dead-letter tras N reintentos — un mensaje con fallo transitorio persistente se
reencola indefinidamente salvo que el proveedor deje de fallar. Se documenta como
mejora futura si se requiere ese límite.

## Limitaciones conocidas de esta iteración

- La deduplicación usa SQLite local por instancia del worker: si se corren múltiples
  instancias concurrentes (competing consumers), no hay dedup compartida entre ellas
  (ver `research.md` § 2, nota de escalado futuro).
- El mecanismo de plantillas de `contenido` no está resuelto; se asume contenido ya
  armado (`titulo` + `cuerpo`) en el mensaje.
- El esquema de `contracts/mensaje-notificacion.schema.json` es un mínimo de trabajo,
  no el contrato oficial — sujeto a alineación con el repo puerta de entrada.
