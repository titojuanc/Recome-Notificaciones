# Implementation Plan: Worker de Notificaciones (Push/Mail)

**Branch**: `002-worker-notificaciones` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-worker-notificaciones/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Worker Python que consume mensajes de una cola RabbitMQ dedicada a notificaciones,
valida estrictamente cada mensaje contra un esquema mínimo (`id_mensaje`, `canal`,
`destinatario`, `mail`, `push_sub`, `contenido`, con validación cruzada entre
`canal` y los campos de contacto), enruta el envío al canal indicado (push o mail)
usando el dato de contacto ya resuelto en el propio mensaje (sin consultar ninguna
BDD ajena), descarta duplicados por `id_mensaje` vía un registro local (SQLite
embebido, propio de este worker), y delega todo reintento ante fallo transitorio al
mecanismo nativo de RabbitMQ (`nack`/requeue + dead-letter exchange), sin lógica de
reintento propia. No implementa lógica de negocio de "cuándo" notificar, resolución
de plantillas, ni ningún campo de "tipo de evento" (decisiones fuera de alcance).

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: `pika` (cliente RabbitMQ), `pydantic` v2 (validación
estricta de payload, incluyendo validación cruzada `canal`/`mail`/`push_sub`),
`pywebpush` (cliente Web Push real contra el `push_sub` del mensaje), `pytest` +
`pytest-mock` (tests)

**Storage**: SQLite embebido (archivo local del worker) exclusivamente para el
registro de `id_mensaje` ya procesados (deduplicación); no es una base de datos de
dominio y no se expone a otros repos (Principio II de la Constitution)

**Testing**: `pytest` para unit/contract tests; `pytest` + contenedor RabbitMQ real
(via Docker, ej. `testcontainers-python` o `docker-compose` de test) para integration
tests

**Target Platform**: Linux server, contenedorizado (Docker)

**Project Type**: single project (worker/consumer, sin frontend)

**Performance Goals**: Sin SLA numérico fijo en esta iteración (ver `research.md` §1);
el worker procesa mensajes con `prefetch_count` bajo configurable, sin bloquear la
cola ante un proveedor lento. Escalado futuro vía competing consumers si se requiere.

**Constraints**: sin acceso directo a bases de datos ajenas (Principio II); sin
lógica de reintento propia (delegado a RabbitMQ, ver Clarifications de spec.md); sin
exposición directa a frontends (Principio V)

**Scale/Scope**: worker único, 2 canales de envío (push, mail), sin necesidad
prevista de escalado horizontal complejo en esta primera iteración

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Chequeo | Estado |
|-----------|---------|--------|
| I. Responsabilidad acotada | El plan NO incluye reportes, scheduling, storage de archivos, ni lógica de negocio ajena. Solo worker + validación + envío. | ✅ PASS |
| II. Cero acceso a DB ajena | Toda la data llega en el payload del mensaje. El único storage propio (SQLite dedup) es estado operativo del worker, no una DB de dominio. | ✅ PASS |
| III. Contratos como fuente externa | El esquema del mensaje se trata como mínimo de trabajo, sujeto a validación contra el repo puerta de entrada (documentado en spec.md Assumptions). | ✅ PASS |
| IV. Validación estricta de payloads | `pydantic` con modelos estrictos (`extra="forbid"`, sin defaults inventados); mensajes inválidos → reject/dead-letter (FR-005). | ✅ PASS |
| V. No accesible por frontends | No se expone ningún endpoint REST en esta iteración (no hay necesidad concreta identificada); solo consumo de cola. | ✅ PASS |
| VI. Test-First + TDD por rigor | Tareas se clasificarán 🟢/🟡/🔴 en tasks.md: validación/dedup/enrutamiento = 🟢; clientes push/mail = 🟡; consumer RabbitMQ = 🔴. | ✅ PASS (a aplicar en tasks.md) |
| VII. Simplicidad | No se agrega FastAPI/REST especulativo; SQLite en vez de un servicio de storage externo, por ser la opción más simple que cumple II. | ✅ PASS |

**Resultado**: Sin violaciones. No se requiere Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-worker-notificaciones/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── models/           # Esquemas pydantic: MensajeNotificacion, ResultadoEnvio
├── services/
│   ├── dedup.py       # Registro de mensajes procesados (SQLite)
│   ├── validacion.py  # Validación estricta de payload
│   └── canales/
│       ├── push.py    # Cliente/adaptador de envío push
│       └── mail.py    # Cliente/adaptador de envío mail
├── consumer/
│   └── worker.py       # Consumer RabbitMQ: orquesta validación → dedup → envío → ack/nack
└── config.py          # Configuración (conexión RabbitMQ, paths SQLite, credenciales proveedores)

tests/
├── unit/              # 🟢 validación de payload, lógica de dedup, selección de canal
├── integration/        # 🟡 clientes push/mail contra proveedor real o sandbox
└── contract/           # 🔴 contract tests contra el schema de mensaje documentado + RabbitMQ real
```

**Structure Decision**: Proyecto único (single project). No hay frontend ni backend
separado — es un worker/consumer standalone. Se separa `models/`, `services/`
(lógica pura + adaptadores de canal) y `consumer/` (orquestación/wiring) para
alinear la estructura de carpetas con la clasificación de rigor TDD 🟢/🟡/🔴 de la
Constitution (Principio VI).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Sin violaciones — tabla no aplica.
