# Data Model: Worker de Notificaciones (Push/Mail)

**Feature**: `002-worker-notificaciones` | **Date**: 2026-09-10

Este documento define las entidades conceptuales de la spec (`spec.md` § Key
Entities) en términos de modelos concretos (pydantic) y esquema de storage local.

## 1. `MensajeNotificacion` (entrada, validado con pydantic)

Representa el payload recibido desde la cola de RabbitMQ. Corresponde a la entidad
"Mensaje de notificación" de `spec.md`.

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `id_mensaje` | `str` (UUID o string único) | Sí | Identificador único del mensaje; usado para deduplicación (FR-011). |
| `canal` | `Literal["push", "mail"]` | Sí | Canal de envío. Cualquier otro valor es inválido (FR-005). |
| `destinatario` | `str` | Sí | Identificador del destinatario para el canal indicado (ej. token push, dirección mail). Se asume ya validado por el emisor (FR-012). |
| `contenido` | `dict` / modelo anidado `Contenido` | Sí | Datos necesarios para armar la notificación. Estructura exacta pendiente del contrato externo (Principio III); en esta iteración se valida como mínimo `titulo: str` y `cuerpo: str`. |

**Reglas de validación**:
- Modelo con `extra="forbid"`: cualquier campo no declarado provoca error de
  validación (rechazo del mensaje, FR-005 / Principio IV).
- Ningún campo tiene valor por defecto que "invente" datos faltantes.
- `canal` se valida contra un enum cerrado (`push` | `mail`); cualquier otro string
  es rechazado.

**Transiciones de estado** (no es una entidad persistida, es el payload de entrada):
`recibido` → `validado` → (`duplicado` | `enviado` | `rechazado` | `reencolado`)

## 2. `ResultadoEnvio` (interno, no persistido salvo logging)

Representa el resultado de intentar entregar la notificación por el canal indicado.
Corresponde a la entidad "Resultado de envío" de `spec.md`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id_mensaje` | `str` | Referencia al mensaje procesado. |
| `estado` | `Literal["exitoso", "fallo_transitorio", "fallo_definitivo"]` | Resultado del intento de envío. |
| `canal` | `Literal["push", "mail"]` | Canal por el que se intentó el envío. |
| `detalle` | `str \| None` | Mensaje de error o detalle técnico, si aplica (para logging, FR-008). |
| `timestamp` | `datetime` | Momento del intento. |

**Mapeo a acción sobre la cola**:
- `exitoso` → `ack` del mensaje.
- `fallo_transitorio` → `nack` sin `requeue=False` (se deja que RabbitMQ reencole
  según configuración de la cola — ver FR-007 / US3).
- `fallo_definitivo` (ej. mensaje inválido, canal no soportado) → `nack` con
  `requeue=False` o publish directo a dead-letter, según configuración elegida en
  implementación.

## 3. `RegistroMensajeProcesado` (persistido, SQLite)

Mecanismo de idempotencia (entidad "Registro de mensajes procesados" de `spec.md`).

**Tabla**: `processed_messages`

| Columna | Tipo SQL | Constraint | Descripción |
|---------|----------|------------|-------------|
| `id_mensaje` | `TEXT` | `PRIMARY KEY` | Identificador único del mensaje ya procesado exitosamente. |
| `processed_at` | `TIMESTAMP` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Momento en que se confirmó el envío exitoso. |
| `canal` | `TEXT` | `NOT NULL` | Canal por el que se envió (para trazabilidad/debug). |

**Operaciones**:
- `existe(id_mensaje) -> bool`: `SELECT 1 FROM processed_messages WHERE id_mensaje = ?`
- `registrar(id_mensaje, canal)`: `INSERT INTO processed_messages (...) VALUES (...)`,
  ejecutado **solo** después de un `ResultadoEnvio.estado == "exitoso"`.

**Nota de diseño**: La escritura en `processed_messages` y el `ack` del mensaje en
RabbitMQ deben ocurrir de forma consistente (si falla la escritura en SQLite después
de un envío exitoso pero antes del `ack`, el mensaje se reprocesará: el envío ya fue
exitoso, así que el peor caso es un posible duplicado en un escenario de fallo muy
específico — aceptable dado que la fuente de verdad es "mejor esfuerzo" según lo
acordado en Clarifications, no una garantía transaccional distribuida).

## 4. Relaciones

```text
MensajeNotificacion (entrada)
        │
        ├──> valida contra RegistroMensajeProcesado.existe(id_mensaje)
        │         │
        │         ├─ existe → descartar (ack, no se genera ResultadoEnvio)
        │         └─ no existe → continuar
        │
        ├──> enruta por `canal` a servicio de envío (push.py | mail.py)
        │
        └──> genera ResultadoEnvio
                  │
                  ├─ exitoso → RegistroMensajeProcesado.registrar(...) + ack
                  ├─ fallo_transitorio → nack (requeue=True, delega a RabbitMQ)
                  └─ fallo_definitivo → nack (requeue=False) / dead-letter
```

## 5. Fuera de alcance (explícito)

- No se modela aquí el mecanismo de resolución de plantillas de `contenido` — sigue
  siendo una decisión de diseño pendiente (ver Constitution).
- No se modela el schema completo/oficial del evento — el modelo aquí definido es un
  mínimo de trabajo sujeto a validación posterior contra el contrato externo del repo
  puerta de entrada (Principio III).
