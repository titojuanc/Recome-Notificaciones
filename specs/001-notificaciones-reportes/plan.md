# Implementation Plan: Notificaciones Push/Mail y Reportes Exportables

**Branch**: `001-notificaciones-reportes` | **Date**: 2026-09-07 | **Spec**: `specs/001-notificaciones-reportes/spec.md`

**Input**: Feature specification from `/specs/001-notificaciones-reportes/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Implementar, dentro del repo `Recome-Notificaciones`, dos workers Python independientes
(Notificaciones Push/Mail y Reportes Exportables) que consumen/publican eventos sobre una
infraestructura RabbitMQ propia (durable, con DLQ por cola, una instancia por ambiente), y
exponen endpoints REST livianos (FastAPI) autenticados con API key interna de servicio para:
solicitud síncrona de envío de notificación, consulta de estado de reporte, y generación de
signed URLs de descarga contra MinIO. Ambos módulos son consumidores estrictos de datos vía
REST a `api-general` (preferencias de opt-out, datos a exportar) — nunca acceden a sus bases
de datos directamente — y validan todo payload de entrada/salida contra el JSON Schema/OpenAPI
(DRAFT mientras no exista versión formal) acordado con ese equipo, según Principios II–IV de
la constitution.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI (endpoints REST), pika (consumo/publicación RabbitMQ),
`httpx` (llamadas REST salientes a `api-general`), `jsonschema` (validación de contratos DRAFT),
`redis` (cache de opt-out, dedup por `event_id`, contadores de rate limit), `minio` SDK
(subida y signed URLs), `WeasyPrint` u `openpyxl`/`reportlab` (generación PDF/Excel según
tipo de reporte), `jinja2` (render de templates de notificación), cliente FCM oficial
(`firebase-admin`) y SDK de SendGrid.

**Storage**: MinIO (bucket `recome-reportes`, único, con prefijo `tipo/fecha/usuario`) para
archivos de reportes. Redis para estado operativo de corto plazo (dedup de `event_id`, cache
de preferencias de opt-out con TTL 5 min, contadores de rate limit, estado transitorio de
jobs de reporte mientras están `pending`/`processing`). No hay base de datos relacional propia
en el MVP: el estado terminal de reportes (`ready`/`failed`) se resuelve vía el evento
`reporte.listo` y la consulta REST de estado se resuelve leyendo Redis + MinIO; no se
persisten datos que otros repos deban considerar fuente de verdad.

**Testing**: `pytest` + `pytest-asyncio` para unitarios; contract tests con `jsonschema`
contra los DRAFT schemas de `notificacion.enviar`, `reporte.generar`, `reporte.listo` y los
specs OpenAPI de los endpoints expuestos; pruebas de integración con `pytest` +
`testcontainers` (RabbitMQ y MinIO reales en contenedor) + mocks HTTP (`respx`/`responses`)
para las llamadas salientes a `api-general`, FCM y SendGrid.

**Target Platform**: Linux server (contenedores Docker), un despliegue por ambiente
(dev/staging/prod), broker RabbitMQ dedicado por ambiente.

**Project Type**: Backend de servicios asíncronos (workers) + API REST liviana — no hay
frontend en este repo.

**Performance Goals**: 95% de notificaciones válidas entregadas en <30s desde la publicación
del evento (SC-001, objetivo no SLA duro); generación de reportes dentro de timeout
configurable por tipo (default 5 min, SC-002).

**Constraints**: Cero acceso directo a bases de datos de otros repos (Principio II); ningún
contrato de evento/endpoint se implementa con campos "adivinados" — solo contra el DRAFT
acordado y referenciado en el PR (Principio III/IV, FR-022); Nginx nunca expuesto
directamente al usuario final, solo signed URLs de vida corta (FR-014); rate limit default
20 notificaciones/hora por usuario y por canal de forma **independiente** (push y mail no
comparten cupo, FR-007); reintento/backoff/DLQ de notificaciones aplicado **por canal
individual** (FR-004), con estado agregado del evento en `enviado`/`parcial`/`fallido`/
`descartado_rate_limit` (FR-008); fallback automático a template en `es` si falta el
template del idioma resuelto, y `es` como idioma default cuando no hay `idioma` en el
payload ni preferencia registrada en `api-general` (FR-002, FR-009); retención default 30
días para reportes en MinIO (FR-013); límite máximo configurable por tipo de reporte sobre el
volumen de datos exportables, con fallo definitivo `limite_tamano_excedido` sin truncar el
archivo (FR-013a); timeout de reporte (default 5 min) cancela activamente el proceso y es
definitivo, sin reintento automático (FR-012), mientras que fallos transitorios de reporte sí
se reintentan con backoff antes de marcar `failed` (FR-012a); sin deduplicación por contenido/
filtros entre `reporte_id` distintos (solo se deduplica por `reporte_id` repetido).

**Scale/Scope**: 2 módulos (Notificaciones, Reportes) + infraestructura de broker compartida;
soporta como mínimo 4 tipos de reporte y un registro extensible de templates de notificación
por `tipo_evento` + idioma (mínimo `es`/`en`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Chequeo | Resultado |
|---|---|---|
| I. Responsabilidad acotada del repo | ¿El plan implementa solo Notificaciones, Reportes, broker, MinIO/Nginx, sin lógica de recomendación/catálogo/auth de usuarios? | ✅ PASS |
| I. Responsabilidad acotada del repo | ¿Ningún endpoint queda expuesto directo a los frontends (solo vía `api-general`)? | ✅ PASS — todo acceso externo pasa por `api-general` |
| II. Cero acceso directo a DB ajena | ¿Se accede a datos de usuarios/catálogo/preferencias solo vía REST a `api-general`? | ✅ PASS — `httpx` contra endpoints REST, nunca contra Postgres/Cassandra ajenos |
| II. Cero acceso directo a DB ajena | ¿Otros repos acceden a MinIO solo vía REST de este repo? | ✅ PASS — Nginx no expuesto; signed URLs on-demand vía endpoint propio |
| III. Contratos como fuente externa de verdad | ¿Se reconoce que el schema formal vive en `api-general` y aún no existe? | ✅ PASS — se documenta uso de DRAFT acordado (ver Assumptions de la spec) |
| IV. Fidelidad de implementación a contratos | ¿Se valida cada payload de entrada/salida contra el schema/OpenAPI vigente antes de procesar? | ✅ PASS — `jsonschema` + contract tests obligatorios en CI |
| V. Test-First + Contract/Integration testing | ¿El plan de testing incluye contract tests y pruebas de integración contra RabbitMQ/MinIO reales? | ✅ PASS — `testcontainers`, contract tests con `jsonschema`, TDD para lógica propia |
| VI. Simplicidad y aislamiento operativo | ¿Los dos módulos son desplegables independientemente sin código de negocio compartido más allá de utilidades? | ✅ PASS — servicios separados, comparten solo cliente de broker/config |
| Stack tecnológico fijado | ¿Se respeta Python + pika + FastAPI + MinIO + Nginx sin reabrir decisiones? | ✅ PASS |

No se detectan violaciones. No aplica la sección de Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-notificaciones-reportes/
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
├── broker/                     # Infraestructura RabbitMQ compartida
│   ├── connection.py           # Conexión pika, declaración idempotente de exchanges/colas/DLQ
│   └── schemas/                # JSON Schemas DRAFT de eventos (notificacion.enviar, reporte.generar, reporte.listo)
│
├── notificaciones/              # Módulo de Notificaciones Push/Mail
│   ├── api/                    # Endpoint REST síncrono (FastAPI), auth API key interna
│   ├── consumers/               # Consumer de notificacion.enviar
│   ├── providers/               # FCM y SendGrid detrás de MailProvider/PushProvider
│   ├── templates/               # Templates por tipo_evento + idioma
│   ├── services/                # Rate limiting, dedup, consulta opt-out a api-general
│   └── models/                  # Entidades de dominio (Notificacion, Preferencia)
│
├── reportes/                    # Módulo de Reportes Exportables
│   ├── api/                    # Endpoints REST: estado, solicitud de descarga (signed URL)
│   ├── consumers/               # Consumer de reporte.generar
│   ├── generators/               # Registro extensible por tipo (ventas, actividad, catálogo, recomendaciones)
│   ├── storage/                  # Cliente MinIO (subida, signed URL, limpieza por retención)
│   └── models/                   # Entidades de dominio (Reporte, EstadoReporte)
│
└── shared/                      # Utilidades comunes explícitas (cliente httpx a api-general, config, logging)

tests/
├── contract/                    # Contract tests contra JSON Schema/OpenAPI DRAFT
├── integration/                 # RabbitMQ + MinIO reales (testcontainers) + mocks de api-general/FCM/SendGrid
└── unit/                        # Lógica de rate limiting, templates, generadores, dedup
```

**Structure Decision**: Proyecto backend único (no hay frontend en este repo). Se separan los
dos módulos (`notificaciones/`, `reportes/`) como paquetes independientes dentro de `src/`,
cada uno con su propio consumer, API y modelos, compartiendo solo `broker/` (infraestructura
de colas) y `shared/` (config, logging, cliente REST a `api-general`), en línea con el
Principio VI (simplicidad y aislamiento operativo) de la constitution.

## Complexity Tracking

> No aplica — no se detectaron violaciones a la constitution en este plan.
