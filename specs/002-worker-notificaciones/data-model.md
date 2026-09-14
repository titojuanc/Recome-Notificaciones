# Data Model: Worker de Notificaciones (Push/Mail)

**Feature**: `002-worker-notificaciones` | **Date**: 2026-09-10

Este documento define las entidades conceptuales de la spec (`spec.md` § Key
Entities) en términos de modelos concretos (pydantic) y esquema de storage local.

## 1. `MensajeNotificacion` (entrada, validado con pydantic)

Representa el payload recibido desde la cola de RabbitMQ. Corresponde a la entidad
"Mensaje de notificación" de `spec.md`.

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `id_mensaje` | `int` | Sí | Identificador único numérico del mensaje; usado para deduplicación (FR-011). |
| `canal` | `Literal["push", "mail"]` | Sí | Canal de envío. Cualquier otro valor es inválido (FR-005). |
| `destinatario` | `int` | Sí | Id numérico del usuario. Usado solo para trazabilidad/logging — no es el dato de contacto real usado para enviar. |
| `mail` | `EmailStr \| None` (pydantic `email-validator`) | Condicional | Dirección de correo ya resuelta por el emisor. Obligatoria si y solo si `canal = "mail"`; debe estar ausente/`None` si `canal = "push"` (FR-013). Formato inválido → rechazo (FR-015). |
| `push_sub` | `PushSubscription \| None` | Condicional | Web Push Subscription ya resuelta por el emisor. Obligatorio si y solo si `canal = "push"`; debe estar ausente/`None` si `canal = "mail"` (FR-013). |
| `contenido` | `Contenido` (modelo anidado) | Sí | Datos necesarios para armar la notificación. Estructura exacta pendiente del contrato externo (Principio III); en esta iteración se valida como mínimo `titulo: str` y `cuerpo: str`. |

### Submodelo `PushSubscription`

Formato estándar de Web Push Subscription del navegador:

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `endpoint` | `str` | Sí | URL del servicio push del navegador (FCM, Mozilla, etc.). |
| `keys.p256dh` | `str` | Sí | Clave pública de cifrado, base64. |
| `keys.auth` | `str` | Sí | Secreto de autenticación, base64. |

**Reglas de validación**:
- Modelo con `extra="forbid"` (a todos los niveles, incluido `push_sub` y
  `contenido`): cualquier campo no declarado provoca error de validación (rechazo del
  mensaje, FR-005 / Principio IV).
- Ningún campo tiene valor por defecto que "invente" datos faltantes.
- `canal` se valida contra un enum cerrado (`push` | `mail`); cualquier otro string
  es rechazado.
- **Validación cruzada (model validator)**: si `canal = "mail"` → `mail` debe estar
  presente (no `None`) y `push_sub` debe ser `None`; si `canal = "push"` → `push_sub`
  debe estar presente (no `None`) y `mail` debe ser `None`. Cualquier otra
  combinación falla la validación (FR-013).
- El mensaje **no** incluye ni valida ningún campo de "tipo de evento" (FR-014) — ese
  concepto es ajeno a este repo.

**Transiciones de estado** (no es una entidad persistida, es el payload de entrada):
`recibido` → `validado` → (`duplicado` | `enviado` | `rechazado` | `reencolado`)

## 2. `ResultadoEnvio` (interno, no persistido salvo logging)

Representa el resultado de intentar entregar la notificación por el canal indicado.
Corresponde a la entidad "Resultado de envío" de `spec.md`.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id_mensaje` | `int` | Referencia al mensaje procesado. |
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
| `id_mensaje` | `INTEGER` | `PRIMARY KEY` | Identificador único numérico del mensaje ya procesado exitosamente. |
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
