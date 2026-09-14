# Pruebas manuales del worker de notificaciones

Este documento explica cómo probar el worker "a mano" (sin depender de la suite
automatizada de `pytest`), para que cualquiera pueda ver el funcionamiento real
sin necesidad de leer el código.

Ver también:
- `specs/002-worker-notificaciones/quickstart.md` — guía técnica de referencia,
  ejemplos de payloads y detalles de diseño (dedup, dead-letter, etc.)
- `README.md` — instrucciones generales de setup del proyecto

## Requisitos previos

- Repo clonado, con el entorno virtual creado e instalado:
  ```bash
  python3 -m venv .venv
  .venv/bin/pip install -r requirements-dev.txt
  ```
- Docker corriendo (para RabbitMQ y Mailpit).

## Opción rápida: un solo comando

```bash
./scripts/ejecutar_prueba_manual.sh
```

Este script:
1. Levanta RabbitMQ y Mailpit si no están corriendo (`docker-compose.test.yml`).
2. Arranca el worker en background si no está corriendo (log en `worker.log`,
   PID guardado en `worker.pid`).
3. Publica, uno por uno, los 4 casos de prueba "seguros" (mail válido, mensaje
   inválido, canal no soportado, duplicado). El caso `push` se deja aparte
   (ver más abajo) porque sin credenciales VAPID reales reintenta
   indefinidamente y ensucia la demo.
4. Muestra el resultado en el log del worker.

Al final, revisá:
- **Mailpit** (http://localhost:8025): ahí debería aparecer el mail de prueba
  "Notificación de prueba" enviado a `prueba@ejemplo.com`.
- **`worker.log`**: ahí quedan registrados todos los eventos (`enviado`,
  `rechazado`, `duplicado_descartado`, `reencolado`, `dead_letter`).

Para detener el worker cuando termines:
```bash
kill $(cat worker.pid)
```

## Opción paso a paso (para entender cada parte)

### 1. Levantar la infraestructura

```bash
docker compose -f docker-compose.test.yml up -d
```

Esto levanta:
- **RabbitMQ** (`recome-rabbitmq`): panel de administración en
  http://localhost:15672 (usuario/clave `guest`/`guest`), puerto AMQP `5672`.
- **Mailpit** (`recome-mailpit`): servidor SMTP falso — no manda mails reales,
  los captura para poder verlos. UI en http://localhost:8025, SMTP en `1025`.

### 2. Arrancar el worker

En una terminal (queda corriendo, mostrando el log en vivo):
```bash
.venv/bin/python -m src.consumer.worker
```

O en background:
```bash
nohup .venv/bin/python -m src.consumer.worker > worker.log 2>&1 &
disown
tail -f worker.log   # para ver el log en vivo
```

### 3. Publicar mensajes de prueba

Se incluye un script (`scripts/publicar_prueba.py`) para no tener que escribir
el JSON del mensaje a mano cada vez:

```bash
# Mensaje válido por mail (aparece en Mailpit)
.venv/bin/python scripts/publicar_prueba.py mail

# Mensaje válido por mail, a una dirección específica
.venv/bin/python scripts/publicar_prueba.py mail --mail otra@direccion.com

# Mensaje válido por push (no hay servidor push real de prueba;
# se espera un fallo_transitorio real de pywebpush, y RabbitMQ lo reencola)
.venv/bin/python scripts/publicar_prueba.py push

# Mensaje inválido (sin el campo 'canal') -> se espera 'rechazado'
.venv/bin/python scripts/publicar_prueba.py invalido

# Mensaje con canal no soportado (ej. "sms") -> se espera 'rechazado'
.venv/bin/python scripts/publicar_prueba.py canal-no-soportado

# Mismo id_mensaje publicado dos veces -> la 2da vez 'duplicado_descartado'
.venv/bin/python scripts/publicar_prueba.py duplicado
```

También podés usar la consola web de RabbitMQ para publicar mensajes a mano:
http://localhost:15672 → **Queues and Streams** → `notificaciones` →
**Publish message** → pegar un JSON como los de `quickstart.md`.

### 4. Qué esperar en cada caso

| Caso | Comando | Resultado esperado en `worker.log` | Verificable también en |
|------|---------|-------------------------------------|--------------------------|
| Mail válido | `publicar_prueba.py mail` | `evento=enviado canal=mail` | Mailpit (http://localhost:8025) — aparece el mail |
| Mensaje inválido | `publicar_prueba.py invalido` | `evento=rechazado` (sin canal ni destino) | — |
| Canal no soportado | `publicar_prueba.py canal-no-soportado` | `evento=rechazado` | — |
| Duplicado | `publicar_prueba.py duplicado` | 1ra vez `evento=enviado`, 2da vez `evento=duplicado_descartado` | Mailpit solo tiene 1 mail, no 2 |
| Push (ver nota abajo) | `publicar_prueba.py push` | `evento=reencolado canal=push` **repetido indefinidamente** | — |

**⚠️ Nota importante sobre `push`**: no existe un equivalente a Mailpit para Web
Push (ver `research.md` §7), y esta iteración **no configura un límite de
entregas** (`x-delivery-limit`) para la cola — es una limitación conocida,
documentada en `quickstart.md`. Como consecuencia, publicar un mensaje `push`
con un `push_sub` de prueba (o sin `VAPID_PRIVATE_KEY` configurada) hace que
`pywebpush` falle de verdad, y el worker lo reencola en un **loop indefinido**
(reintenta para siempre, sin backoff propio — por diseño, el worker delega
todo el reintento a RabbitMQ). Por eso:

- El script `ejecutar_prueba_manual.sh` **no incluye el caso `push`** en su
  corrida automática.
- Si querés probarlo igual (para ver el comportamiento de reencolado nativo en
  acción), corré en otra terminal:
  ```bash
  .venv/bin/python scripts/publicar_prueba.py push
  tail -f worker.log   # vas a ver 'evento=reencolado' repetirse sin parar
  ```
- Cuando termines de observarlo, **purgá la cola** para no dejarlo reintentando
  para siempre:
  ```bash
  .venv/bin/python -c "
  import pika
  c = pika.BlockingConnection(pika.URLParameters('amqp://guest:guest@localhost:5672/'))
  c.channel().queue_purge(queue='notificaciones')
  c.close()
  "
  ```
- Para probar un push que efectivamente se entregue (`evento=enviado`), hace
  falta configurar `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY` reales en `.env` y
  usar un `push_sub` de una Web Push Subscription real generada desde un
  navegador — queda fuera del alcance de esta guía de pruebas rápidas.

**Nota sobre la deduplicación y corridas repetidas**: el registro de
`id_mensaje` procesados vive en un archivo SQLite persistente
(`data/processed_messages.db`, ver `SQLITE_DEDUP_PATH`). El script
`publicar_prueba.py duplicado` usa un `id_mensaje` **aleatorio** por defecto
en cada corrida (no fijo), justamente para que la primera publicación de cada
corrida se vea como `enviado` y no como `duplicado_descartado` por culpa de
una corrida anterior. Si necesitás reiniciar el estado de deduplicación desde
cero, borrá el archivo:
```bash
rm -f data/processed_messages.db
```

### 5. Probar el reencolado / dead-letter (comportamiento nativo de RabbitMQ)

El worker declara automáticamente, para la cola `notificaciones`, un exchange
de dead-letter (`notificaciones.dlx`) y una cola `notificaciones.dead-letter`
(ver `src/consumer/worker.py`, método `run`). Podés inspeccionar ambas en la
consola de RabbitMQ (http://localhost:15672 → Queues and Streams).

- Un mensaje **inválido** (rechazado, `nack(requeue=False)`) termina
  directamente en `notificaciones.dead-letter`.
- Un mensaje con **fallo transitorio** (ej. push contra un endpoint que no
  existe) se reencola en `notificaciones` (`nack(requeue=True)`) y el worker
  lo vuelve a intentar — podés verlo reintentarse repetidamente en el log si
  lo dejás corriendo.

### 6. Detener todo

```bash
kill $(cat worker.pid)                     # si usaste el script/nohup
docker compose -f docker-compose.test.yml down   # baja RabbitMQ y Mailpit
```

## Alternativa: correr la suite automatizada

Si preferís simplemente confirmar que "todo funciona" sin hacerlo a mano:

```bash
.venv/bin/python -m pytest tests -v
```

- `tests/unit` (🟢): validación de payload, dedup, enrutamiento — no requieren
  infraestructura.
- `tests/integration` (🟡): cliente push (mockeado) y cliente mail (contra
  Mailpit real).
- `tests/contract` (🔴): flujo completo contra RabbitMQ real (mensaje válido,
  inválido, duplicado, reencolado).

Los tests de `integration`/`contract` que dependen de Mailpit/RabbitMQ se
saltean automáticamente (`skip`) si esos servicios no están disponibles.
