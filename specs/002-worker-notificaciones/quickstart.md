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
- Variables de entorno (ver `.env.example`, a crear en fase de implementación):
  - `RABBITMQ_URL`
  - `RABBITMQ_QUEUE_NOTIFICACIONES`
  - `SQLITE_DEDUP_PATH`
  - Credenciales de los proveedores push/mail (a definir en implementación)

## Levantar RabbitMQ localmente (para desarrollo/tests)

```bash
docker run -d --name rabbitmq-dev -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

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

## Limitaciones conocidas de esta iteración

- La deduplicación usa SQLite local por instancia del worker: si se corren múltiples
  instancias concurrentes (competing consumers), no hay dedup compartida entre ellas
  (ver `research.md` § 2, nota de escalado futuro).
- El mecanismo de plantillas de `contenido` no está resuelto; se asume contenido ya
  armado (`titulo` + `cuerpo`) en el mensaje.
- El esquema de `contracts/mensaje-notificacion.schema.json` es un mínimo de trabajo,
  no el contrato oficial — sujeto a alineación con el repo puerta de entrada.
