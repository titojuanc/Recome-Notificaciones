# Research: Worker de Notificaciones (Push/Mail)

**Feature**: `002-worker-notificaciones` | **Date**: 2026-09-10

Este documento resuelve las incógnitas técnicas (`NEEDS CLARIFICATION`) dejadas en
`plan.md` y documenta las decisiones de diseño tomadas para esta feature.

## 1. Throughput / Performance Goals

**Pregunta**: `plan.md` dejaba abierto el volumen esperado de mensajes/segundo.

**Decisión**: No se fija un número objetivo de mensajes/segundo para esta primera
iteración. Se define un criterio funcional en su lugar: el worker debe procesar
mensajes uno a la vez (o con prefetch bajo configurable, ej. `prefetch_count=10` en
pika) sin bloquear indefinidamente la cola ante un proveedor lento.

**Racional**: No hay datos de volumen real del sistema todavía (es una feature
inicial de un repo nuevo). Fijar un número arbitrario violaría el Principio VII
(simplicidad — no sobre-diseñar sin necesidad concreta). Si en el futuro se requiere
alto throughput, se puede escalar horizontalmente agregando más instancias del mismo
worker consumiendo de la misma cola (patrón estándar de RabbitMQ competing
consumers), sin cambios de diseño.

**Alternativas consideradas**:
- Fijar un SLA arbitrario (ej. "1000 msg/s") — rechazado por falta de datos reales.
- Procesamiento batch de mensajes — rechazado por complejidad innecesaria en esta
  iteración (Principio VII).

## 2. Mecanismo de deduplicación (registro de mensajes procesados)

**Pregunta**: ¿Cómo implementar el registro de `id_mensaje` ya procesados sin violar
el Principio II (cero acceso a DB ajena) ni introducir infraestructura innecesaria?

**Decisión**: SQLite embebido, un único archivo local propiedad exclusiva de este
worker (ej. `data/processed_messages.db`), con una tabla simple
`(id_mensaje TEXT PRIMARY KEY, processed_at TIMESTAMP)`. Antes de procesar un
mensaje, se verifica si el `id_mensaje` ya existe; si existe, se descarta (ack sin
reenviar). Si no existe, se procesa y se inserta al confirmar el envío exitoso.

**Racional**: SQLite es embebido (no requiere un servicio de base de datos separado
ni credenciales compartidas), es propiedad exclusiva de este repo (no es una "base de
datos de dominio" compartida — es estado operativo interno, permitido explícitamente
por el Principio II), y es la opción más simple que cumple el requisito (Principio
VII). Evita depender de infraestructura adicional (ej. Redis) sin necesidad
demostrada.

**Alternativas consideradas**:
- **In-memory (dict/set en proceso)**: rechazado — se pierde el registro ante un
  reinicio del worker, permitiendo duplicados justo en el escenario que motiva este
  requisito (crash antes del ack).
- **Redis**: rechazado por ahora — agrega una dependencia de infraestructura externa
  sin necesidad demostrada; se puede reconsiderar si el worker escala a múltiples
  instancias y se necesita un registro de dedup compartido entre ellas (hoy no hay
  ese requisito).
- **Tabla en una base de datos compartida de otro repo**: rechazado — viola
  directamente el Principio II.

**Nota de escalado futuro**: Si el worker corre con múltiples instancias
concurrentes (competing consumers), SQLite local por instancia ya no sería
suficiente para deduplicación consistente entre instancias. Esto queda fuera de
alcance de esta iteración y se documenta como limitación conocida (ver
`quickstart.md`).

## 3. Cliente RabbitMQ: `pika` (síncrono) vs. alternativas asíncronas

**Decisión**: `pika` en modo síncrono con `BlockingConnection`, consumiendo con
`basic_consume` y `prefetch_count` bajo.

**Racional**: Ya está fijado en la Constitution ("Stack tecnológico": Python + pika).
Es la opción estándar, madura, y suficiente para el volumen esperado (ver punto 1).

**Alternativas consideradas**: `aio-pika` (async) — no requerido por la Constitution
ni por ningún requisito de concurrencia identificado en la spec; se descarta por
Principio VII (simplicidad).

## 4. Validación de payload: `pydantic`

**Decisión**: Modelos `pydantic` v2 con `model_config = ConfigDict(extra="forbid")`
para el mensaje de entrada, de forma que cualquier campo inesperado o faltante
provoque un error de validación explícito (nunca se "adivina" un valor faltante,
cumpliendo el Principio IV).

**Racional**: `pydantic` es el estándar de facto en Python para validación
declarativa de esquemas, genera errores claros y estructurados (útil para logging de
mensajes rechazados, FR-008), y se integra bien con testing (`pytest`).

**Alternativas consideradas**: `jsonschema` puro — más verboso para este caso de uso;
`dataclasses` + validación manual — reinventa lo que `pydantic` ya resuelve.

## 5. Testing de integración contra RabbitMQ

**Decisión**: Usar un RabbitMQ real corriendo en un contenedor Docker durante CI e
integration tests locales (ej. vía `docker-compose.test.yml` o `testcontainers-python`
si se prefiere gestión automática desde el propio test).

**Racional**: La Constitution exige pruebas de integración contra RabbitMQ real o
equivalente de test (Principio VI); mockear completamente el broker no detectaría
problemas reales de wiring (exchanges, colas, dead-letter).

**Alternativas consideradas**: Mock completo de `pika` — rechazado como único método
de testing (no cumple el mandato de integration tests reales de la Constitution),
aunque se usa complementariamente para unit tests 🟢 de lógica pura.

## 6. Testing del canal `mail`: Mailpit

**Decisión**: Usar [Mailpit](https://github.com/axllent/mailpit) como servidor SMTP
falso, corriendo en un contenedor Docker (`recome-mailpit`, en la misma red que
RabbitMQ). El worker le apunta a Mailpit (`SMTP_HOST`/`SMTP_PORT`) en desarrollo y
en integration tests; Mailpit expone una UI web (`:8025`) para inspeccionar los
mails capturados, sin enviar nada real a internet.

**Racional**: Es el estándar de facto para testear envío de mail sin depender de un
proveedor real ni arriesgar mandar correos de verdad durante tests automatizados.
Permite un test de integración 🟡 genuino (contra un servidor SMTP real, no un mock)
sin salir de la red local.

**Alternativas consideradas**: Mock completo del cliente SMTP — se usa
complementariamente para unit tests 🟢, pero no reemplaza el test de integración 🟡
contra un servidor SMTP real (Mailpit cumple ese rol sin riesgo de envío real).

## 7. Testing del canal `push`: mock de `pywebpush`

**Decisión**: Para tests de integración 🟡, mockear la librería `pywebpush` en el
punto de llamada (verificar que se invoca con el `endpoint`/`keys`/payload
correctos), en lugar de pegarle a un servicio push real (FCM, Mozilla, etc.).

**Racional**: A diferencia de mail, no existe un equivalente ampliamente adoptado a
"Mailpit para push" — los servicios push reales (FCM, Mozilla Push Service) no
tienen un modo sandbox trivial de levantar en Docker para CI. Mockear la llamada de
`pywebpush` es la opción más simple (Principio VII) que sigue verificando la lógica
propia del adaptador (armado de payload, manejo de errores del SDK).

**Validación manual complementaria (no automatizada)**: para confirmar el flujo real
de punta a punta al menos una vez, se puede generar una Web Push Subscription real
desde un navegador de prueba y enviar un push real — queda documentado como paso
exploratorio en `quickstart.md`, no como parte de la suite de tests de CI.

**Alternativas consideradas**: Levantar un servidor push falso propio — rechazado
por complejidad desproporcionada para el beneficio (Principio VII); no hay
herramienta estándar madura para esto en el ecosistema.

## Resumen de decisiones para `plan.md`

| Aspecto | Resuelto como |
|---------|---------------|
| Performance Goals | Sin SLA numérico fijo; prefetch bajo configurable; escalado horizontal futuro vía competing consumers |
| Storage (dedup) | SQLite embebido local, tabla `id_mensaje` + timestamp |
| Cliente RabbitMQ | `pika` síncrono, `BlockingConnection` |
| Validación | `pydantic` v2, `extra="forbid"` |
| Integration testing (RabbitMQ) | RabbitMQ real vía Docker en CI/local (`recome-rabbitmq`) |
| Integration testing (mail) | Mailpit (SMTP falso) vía Docker (`recome-mailpit`) |
| Integration testing (push) | Mock de `pywebpush`; validación manual real como paso exploratorio complementario |

Todas las incógnitas de `plan.md` quedan resueltas; no quedan `NEEDS CLARIFICATION`
pendientes para avanzar a Phase 1 (data-model, contracts, quickstart).
