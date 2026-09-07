---

description: "Task list for Notificaciones Push/Mail y Reportes Exportables"
---

# Tasks: Notificaciones Push/Mail y Reportes Exportables

**Input**: Design documents from `/specs/001-notificaciones-reportes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Incluidos explícitamente — la constitution (Principio V, NON-NEGOTIABLE) exige
TDD para lógica propia y contract/integration testing obligatorio antes de cualquier deploy.

## Nivel de rigor TDD por tarea

No todas las tareas de implementación se benefician igual de un ciclo TDD unitario
estricto (test unitario → falla → implementación). Cada tarea de implementación está
etiquetada con uno de estos niveles (criterio acordado y registrado en
`.specify/memory/constitution.md`, sección "Rigor de TDD por tipo de tarea"):

- **🟢 TDD estricto**: lógica pura/determinística, fácil de aislar sin mocks de
  infraestructura pesada (rate limiting, dedup, agregación de estado, resolución de
  idioma, timeout/reintento diferenciado, validación de contratos). Se exige ciclo
  red-green-refactor: escribir el test unitario, verlo fallar, recién ahí implementar.
- **🟡 Test-first de integración**: lógica que envuelve un SDK/proveedor externo
  (providers FCM/SendGrid, generadores de reporte, cliente MinIO). Se define primero la
  interfaz/contrato (mock-first) y su test, pero el detalle fino se valida mejor con un
  test de integración que con TDD unitario puro.
- **🔴 Test-first de contrato/orquestación**: consumers de RabbitMQ y endpoints FastAPI
  que coordinan servicios ya testeados por separado. Se escribe primero el contract test
  y/o integration test correspondiente (ya presentes en las secciones "Tests for User
  Story N" de este archivo), pero no se exige TDD unitario línea a línea sobre el wiring.

En todos los casos (🟢/🟡/🔴) el test correspondiente se escribe **antes** que el código
de implementación — la diferencia es el nivel de granularidad exigido, no si se hace
test-first o no.

**Organization**: Tareas agrupadas por user story (US1–US4 de `spec.md`) para permitir
implementación y entrega independiente de cada una.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias)
- **[Story]**: US1 (Notificaciones evento), US2 (Notificaciones REST síncrono), US3
  (Reportes: generar+descargar), US4 (Reportes: consulta de estado)
- Se incluyen paths exactos de archivo, siguiendo la estructura de `plan.md`

## Path Conventions

Proyecto backend único: `src/`, `tests/` en la raíz del repo, con paquetes independientes
`src/broker/`, `src/notificaciones/`, `src/reportes/`, `src/shared/` (ver `plan.md`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto y estructura base

- [ ] T001 Crear estructura de directorios `src/broker/`, `src/notificaciones/`,
      `src/reportes/`, `src/shared/`, `tests/{unit,contract,integration}/` según `plan.md`
- [ ] T002 Inicializar proyecto Python 3.12 con `pyproject.toml`/`requirements.txt`:
      `fastapi`, `pika`, `httpx`, `jsonschema`, `redis`, `minio`, `jinja2`, `firebase-admin`,
      SDK de SendGrid, `WeasyPrint`/`openpyxl`/`reportlab`, `pytest`, `pytest-asyncio`,
      `testcontainers`, `respx`
- [ ] T003 [P] Configurar linting/formatting (`ruff`/`black`) y pre-commit hooks
- [ ] T004 [P] Crear `docker-compose.yml` de desarrollo con RabbitMQ, Redis y MinIO locales
      (soporta `quickstart.md`)
- [ ] T005 [P] Crear `.env.example` con todas las variables listadas en `quickstart.md`
      (`RABBITMQ_URL`, `REDIS_URL`, `MINIO_*`, `API_GENERAL_BASE_URL`,
      `API_GENERAL_INTERNAL_API_KEY`, `FCM_CREDENTIALS_PATH`, `SENDGRID_API_KEY`,
      `ENVIRONMENT`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura núcleo que DEBE estar completa antes de cualquier user story

**⚠️ CRITICAL**: Ninguna user story puede comenzar hasta que esta fase esté completa

- [ ] T006 Implementar `src/broker/connection.py`: conexión `pika` con reconexión y
      declaración idempotente de exchanges/colas (FR-020)
- [ ] T007 Implementar declaración de Dead Letter Exchange por cola en
      `src/broker/connection.py`, con colas `durable=true` y mensajes
      `delivery_mode=persistent` (FR-017, FR-018)
- [ ] T008 [P] Copiar los JSON Schemas DRAFT a `src/broker/schemas/` (desde
      `specs/001-notificaciones-reportes/contracts/*.draft.schema.json`) y crear
      `src/broker/schema_validator.py` con función genérica de validación vía `jsonschema`
      (FR-022)
- [ ] T009 [P] Implementar `src/shared/config.py`: carga de variables de entorno,
      incluyendo modo mock vs real por `ENVIRONMENT` (FR-023)
- [ ] T010 [P] Implementar `src/shared/logging.py`: logging estructurado compartido
      (necesario para alertas de DLQ, FR-018, y trazabilidad de fallback de idioma)
- [ ] T011 [P] Implementar `src/shared/api_general_client.py`: cliente `httpx` autenticado
      con `X-Internal-Api-Key` hacia `api-general`, con reintento/backoff para fallos
      transitorios (usado por US1 para opt-out y por US3 para datos de reporte)
- [ ] T012 [P] Implementar `src/shared/redis_client.py`: cliente Redis compartido (dedup,
      cache de opt-out, contadores de rate limit, estado transitorio de reportes)
- [ ] T013 [P] Implementar `src/shared/auth.py`: middleware/dependencia FastAPI para
      validar `X-Internal-Api-Key` en todos los endpoints expuestos (Principio IV)
- [ ] T014 Crear app FastAPI base en `src/notificaciones/api/app.py` y
      `src/reportes/api/app.py`, montando el middleware de auth de T013

**Checkpoint**: Infraestructura lista — las user stories pueden comenzar en paralelo

---

## Phase 3: User Story 1 - Recibir una notificación relevante (Push/Mail) (Priority: P1) 🎯 MVP

**Goal**: Consumir `notificacion.enviar`, resolver template/idioma, respetar opt-out,
rate limit y dedup, enviar por push/mail con reintento y agregación de estado por canal.

**Independent Test**: Publicar `notificacion.enviar` válido contra el broker y verificar
push/mail (mocks) enviados, opt-out respetado, sin duplicados ante redelivery.

### Tests for User Story 1 ⚠️

- [ ] T015 [P] [US1] Contract test del payload `notificacion.enviar` contra
      `contracts/notificacion.enviar.draft.schema.json` en
      `tests/contract/test_notificacion_enviar_schema.py`
- [ ] T016 [P] [US1] Contract test de `NotificacionEnviarResponse`
      (`estado_entrega`/`resultados_por_canal`) contra `contracts/openapi.draft.yaml` en
      `tests/contract/test_notificacion_enviar_response_schema.py`
- [ ] T017 [P] [US1] Unit test de resolución de idioma: prioridad `idioma` del payload >
      preferencia de `api-general` > fallback default `es` (cuando falta template del
      idioma resuelto Y cuando no hay preferencia registrada) (FR-002, FR-009) en
      `tests/unit/test_template_resolver.py`
- [ ] T018 [P] [US1] Unit test de agregación de `estado_entrega`
      (`enviado`/`parcial`/`fallido`/`descartado_rate_limit`) en
      `tests/unit/test_estado_entrega_aggregation.py`
- [ ] T019 [P] [US1] Unit test de rate limiting independiente por canal (20/hora c/u,
      FR-007) en `tests/unit/test_rate_limiter.py`
- [ ] T020 [P] [US1] Unit test de dedup por `event_id` con TTL en
      `tests/unit/test_dedup.py`
- [ ] T021 [US1] Integration test: evento válido sin opt-out → push+mail enviados (mocks)
      en `tests/integration/test_notificacion_enviar_flow.py` (Acceptance Scenario 1)
- [ ] T022 [US1] Integration test: usuario con opt-out → no se envía, se registra
      `descartado por preferencia` en `tests/integration/test_notificacion_opt_out.py`
      (Acceptance Scenario 2)
- [ ] T023 [US1] Integration test: mismo `event_id` dos veces (redelivery) → sin envío
      duplicado en `tests/integration/test_notificacion_dedup.py` (Acceptance Scenario 3)
- [ ] T024 [US1] Integration test: canal supera rate limit → descartado sin reintento,
      otro canal no afectado en `tests/integration/test_notificacion_rate_limit.py`
      (Acceptance Scenario 4)
- [ ] T025 [US1] Integration test: fallo transitorio de proveedor → backoff hasta 5
      intentos → DLQ del canal en `tests/integration/test_notificacion_retry_dlq.py`
      (Acceptance Scenario 5)
- [ ] T026 [US1] Integration test: éxito en push + fallo definitivo en mail →
      `estado_entrega = parcial` en `tests/integration/test_notificacion_parcial.py`
      (Clarification #1)

### Implementation for User Story 1

- [ ] T027 [P] [US1] Modelo `Notificacion` y `EstadoCanal` en
      `src/notificaciones/models/notificacion.py` (según `data-model.md`)
- [ ] T028 [P] [US1] Modelo `Preferencia` (opt-out) en
      `src/notificaciones/models/preferencia.py`
- [ ] T029 [P] [US1] Registro de templates `tipo_evento+idioma+canal → template` en
      `src/notificaciones/templates/registry.py`, con templates Jinja2 mínimos en `es`/`en`
      para al menos un `tipo_evento` de ejemplo, en `src/notificaciones/templates/es/` y
      `src/notificaciones/templates/en/`
- [ ] T030 [US1] 🟢 Servicio de resolución de idioma con fallback a `es` (por template
      faltante o por ausencia de preferencia registrada) en
      `src/notificaciones/services/template_resolver.py` (depende de T027, T029)
- [ ] T031 [US1] 🟡 Servicio de consulta de opt-out con cache Redis 5 min en
      `src/notificaciones/services/opt_out_service.py` (depende de T011, T012, T028)
- [ ] T032 [US1] 🟢 Servicio de rate limiting independiente por canal en
      `src/notificaciones/services/rate_limiter.py` (depende de T012)
- [ ] T033 [US1] 🟢 Servicio de dedup por `event_id` en
      `src/notificaciones/services/dedup_service.py` (depende de T012)
- [ ] T034 [P] [US1] 🟡 `PushProvider` (FCM real + mock) en
      `src/notificaciones/providers/push_provider.py`
- [ ] T035 [P] [US1] 🟡 `MailProvider` (SendGrid real + mock) en
      `src/notificaciones/providers/mail_provider.py`
- [ ] T036 [US1] 🟡 Servicio de envío por canal con backoff exponencial (máx. 5 intentos) en
      `src/notificaciones/services/canal_sender.py` (depende de T030, T034, T035)
- [ ] T037 [US1] 🟢 Servicio de agregación de `estado_entrega` a partir de
      `resultados_por_canal` en `src/notificaciones/services/estado_aggregator.py`
      (depende de T027)
- [ ] T038 [US1] 🔴 Consumer de `notificacion.enviar` en
      `src/notificaciones/consumers/notificacion_consumer.py`: valida schema (T008),
      dedup (T033), opt-out (T031), rate limit (T032), envío por canal (T036), agregación
      (T037), publica resultado a `api-general` (FR-008), maneja rechazo de `tipo_evento`
      no soportado (edge case) — depende de T006, T007, T027–T037
- [ ] T039 [US1] 🟡 Reporte de estado de entrega vía `api_general_client` (T011) al finalizar
      cada notificación, en `src/notificaciones/services/delivery_reporter.py`
- [ ] T040 [US1] Logging estructurado de fallback de idioma, rate-limit descartado, y
      paso a DLQ por canal (usa T010)

**Checkpoint**: User Story 1 completamente funcional y testeable de forma independiente

---

## Phase 4: User Story 2 - Solicitar envío inmediato vía REST (Priority: P2)

**Goal**: Endpoint REST síncrono para envío inmediato, reutilizando la misma lógica de
templates/opt-out/rate-limit/dedup que la vía asíncrona.

**Independent Test**: Invocar el endpoint con API key válida/ inválida y verificar
respuesta síncrona y autenticación.

### Tests for User Story 2 ⚠️

- [ ] T041 [P] [US2] Contract test de `POST /notificaciones/enviar` contra
      `contracts/openapi.draft.yaml` en `tests/contract/test_notificaciones_enviar_endpoint.py`
- [ ] T042 [US2] Integration test: llamada autenticada válida → respuesta síncrona con
      resultado de envío en `tests/integration/test_notificacion_endpoint_sync.py`
      (Acceptance Scenario 1)
- [ ] T043 [US2] Integration test: llamada sin API key / inválida → 401, no se procesa
      envío en `tests/integration/test_notificacion_endpoint_auth.py` (Acceptance Scenario 2)

### Implementation for User Story 2

- [ ] T044 [US2] 🔴 Endpoint `POST /notificaciones/enviar` en
      `src/notificaciones/api/routes.py`, protegido por `auth.py` (T013), reutilizando
      `template_resolver`, `opt_out_service`, `rate_limiter`, `canal_sender`,
      `estado_aggregator` (T030–T037) de forma síncrona — depende de Phase 3 completa
- [ ] T045 [US2] Registrar el router de T044 en `src/notificaciones/api/app.py` (T014)

**Checkpoint**: User Stories 1 y 2 funcionan de forma independiente

---

## Phase 5: User Story 3 - Generar un reporte exportable y descargarlo (Priority: P1) 🎯 MVP

**Goal**: Consumir `reporte.generar`, obtener datos vía REST a `api-general`, generar
PDF/Excel, subirlo a MinIO, publicar `reporte.listo`, exponer descarga vía signed URL.

**Independent Test**: Publicar `reporte.generar`, verificar generación, publicación de
`reporte.listo` y flujo de descarga autenticado.

### Tests for User Story 3 ⚠️

- [ ] T046 [P] [US3] Contract test de `reporte.generar` contra
      `contracts/reporte.generar.draft.schema.json` en
      `tests/contract/test_reporte_generar_schema.py`
- [ ] T047 [P] [US3] Contract test de `reporte.listo` contra
      `contracts/reporte.listo.draft.schema.json` (incluye `motivo` enum) en
      `tests/contract/test_reporte_listo_schema.py`
- [ ] T048 [P] [US3] Contract test de `GET /reportes/{id}/descarga` contra
      `contracts/openapi.draft.yaml` en `tests/contract/test_reporte_descarga_endpoint.py`
- [ ] T049 [P] [US3] Unit test de cada generador (ventas, actividad_usuario,
      catalogo_uso, recomendaciones) en `tests/unit/test_generadores_reporte.py`
- [ ] T050 [P] [US3] Unit test de cancelación activa del proceso al cumplir timeout
      (FR-012) en `tests/unit/test_reporte_timeout.py`
- [ ] T051 [P] [US3] Unit test de reintento automático solo para fallos transitorios,
      no para timeout (FR-012a) en `tests/unit/test_reporte_retry_transitorio.py`
- [ ] T051a [P] [US3] Unit test de rechazo definitivo por límite de tamaño excedido
      (`motivo: limite_tamano_excedido`, sin truncar, sin reintento — FR-013a; ver T083)
      en `tests/unit/test_reporte_limite_tamano.py`
- [ ] T052 [US3] Integration test: `reporte.generar` válido → archivo en MinIO bajo
      `tipo/fecha/usuario`, `reporte.listo` con `estado: ready` en
      `tests/integration/test_reporte_generar_ready.py` (Acceptance Scenario 1)
- [ ] T053 [US3] Integration test: job excede timeout → `failed`/`motivo: timeout`,
      `reporte.listo` con `estado: error`, sin reintento en
      `tests/integration/test_reporte_timeout_flow.py` (Acceptance Scenario 2)
- [ ] T054 [US3] Integration test: solicitud de descarga autenticada → signed URL de 15
      min en `tests/integration/test_reporte_descarga.py` (Acceptance Scenario 3)
- [ ] T055 [US3] Integration test: job de limpieza borra reporte vencido (>30 días) en
      `tests/integration/test_reporte_retencion.py` (Acceptance Scenario 5)
- [ ] T056 [US3] Integration test: `api-general` no responde al pedir datos → reintento
      transitorio → `failed`/`motivo: dependencia_no_disponible` en
      `tests/integration/test_reporte_dependencia_no_disponible.py` (Edge case)

### Implementation for User Story 3

- [ ] T057 [P] [US3] 🟡 Modelo `Reporte` (con `intentos`, `motivo`, `fecha_expiracion`) en
      `src/reportes/models/reporte.py` (según `data-model.md`)
- [ ] T058 [P] [US3] 🟡 Cliente MinIO: subida, signed URL 15 min, listado por prefijo en
      `src/reportes/storage/minio_client.py` (depende de T009)
- [ ] T059 [P] [US3] 🟡 Registro extensible de generadores en
      `src/reportes/generators/registry.py`
- [ ] T060 [P] [US3] 🟡 Generador `ventas` en `src/reportes/generators/ventas.py`
- [ ] T061 [P] [US3] 🟡 Generador `actividad_usuario` en
      `src/reportes/generators/actividad_usuario.py`
- [ ] T062 [P] [US3] 🟡 Generador `catalogo_uso` en `src/reportes/generators/catalogo_uso.py`
- [ ] T063 [P] [US3] 🟡 Generador `recomendaciones` en
      `src/reportes/generators/recomendaciones.py`
- [ ] T064 [US3] 🟢 Servicio de ejecución de job con timeout configurable y cancelación
      activa del proceso en `src/reportes/services/job_runner.py` (FR-012; depende de
      T057, T059–T063; incluye validación de límite de tamaño antes de generar, vía T083)
- [ ] T065 [US3] 🟢 Servicio de reintento con backoff para fallos transitorios (no aplica a
      timeout ni a límite de tamaño excedido) en `src/reportes/services/retry_service.py`
      (FR-012a; depende de T064)
- [ ] T066 [US3] 🟡 Servicio de paginación de datos vía `api_general_client` (T011) en
      `src/reportes/services/data_fetcher.py` (FR-011)
- [ ] T067 [US3] 🔴 Consumer de `reporte.generar` en
      `src/reportes/consumers/reporte_consumer.py`: valida schema (T008), ejecuta job
      (T064–T066, T083), sube a MinIO (T058), publica `reporte.listo`
      (`ready`/`error`+`motivo`, incluyendo `limite_tamano_excedido`), maneja
      `tipo_no_soportado` (edge case) — depende de T006, T007, T057–T066, T083
- [ ] T068 [US3] 🔴 Endpoint `GET /reportes/{reporte_id}/descarga` en
      `src/reportes/api/routes.py`, protegido por auth (T013), genera signed URL solo si
      `estado == ready` (depende de T058, T067)
- [ ] T069 [US3] 🟡 Job periódico de limpieza por retención (default 30 días, override por
      tipo) en `src/reportes/services/retention_cleanup.py` (FR-013; depende de T058)
- [ ] T070 [US3] Registrar el router de T068 en `src/reportes/api/app.py` (T014)
- [ ] T083 [P] [US3] 🟢 Servicio de validación de límite de tamaño por tipo (conteo de
      registros contra `limite_registros` del generador, FR-013a) en
      `src/reportes/services/size_limit_validator.py` (depende de T057, T059; consumido
      por T064 antes de invocar el generador)
- [ ] T084 [US3] Integration test: datos a exportar exceden el límite configurado →
      `failed`/`motivo: limite_tamano_excedido`, sin archivo generado, sin reintento en
      `tests/integration/test_reporte_limite_tamano_flow.py` (Clarification #2)

**Checkpoint**: User Stories 1, 2 y 3 funcionan de forma independiente

---

## Phase 6: User Story 4 - Consultar el estado de un reporte (Priority: P2)

**Goal**: Endpoint REST para consultar `pending`/`processing`/`ready`/`failed` de un
reporte sin esperar la notificación.

**Independent Test**: Consultar el endpoint de estado en cada fase del job y verificar
consistencia con lo publicado en `reporte.listo`.

### Tests for User Story 4 ⚠️

- [ ] T071 [P] [US4] Contract test de `GET /reportes/{id}/estado` contra
      `contracts/openapi.draft.yaml` en `tests/contract/test_reporte_estado_endpoint.py`
- [ ] T072 [US4] Integration test: estado `pending`/`processing`/`ready`/`failed`
      consistente en cada fase en `tests/integration/test_reporte_estado_flow.py`
      (Acceptance Scenarios 1–3)

### Implementation for User Story 4

- [ ] T073 [US4] 🟡 Servicio de lectura de estado desde Redis (transitorio) + MinIO
      (terminal) en `src/reportes/services/estado_reader.py` (depende de T057, T058)
- [ ] T074 [US4] 🔴 Endpoint `GET /reportes/{reporte_id}/estado` en
      `src/reportes/api/routes.py`, protegido por auth (T013) — depende de T073
- [ ] T075 [US4] Actualizar `job_runner` (T064) para persistir transición de estado en
      Redis en cada paso (`pending → processing → ready|failed`) para que T073 pueda leerla

**Checkpoint**: Todas las user stories (US1–US4) funcionan de forma independiente

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras transversales a todas las user stories

- [ ] T076 [P] Exponer métricas de RabbitMQ (colas, consumidores, mensajes en espera,
      tasa de DLQ) vía plugin de management + exporter Prometheus (FR-021)
- [ ] T077 [P] Documentar en `README.md` cómo correr cada módulo localmente (referenciar
      `quickstart.md`)
- [ ] T078 [P] Revisar y limpiar imports/lint en `src/` (usar T003)
- [ ] T079 Ejecutar validación completa de `quickstart.md` end-to-end (RabbitMQ + Redis +
      MinIO + mocks de api-general/FCM/SendGrid)
- [ ] T080 [P] Tests de seguridad: verificar que URLs no firmadas/expiradas de reportes
      son rechazadas (SC-004) en `tests/integration/test_reporte_descarga_seguridad.py`
- [ ] T081 [P] Test de verificación de cero pérdida silenciosa: 100% de mensajes que
      agotan reintentos terminan en su DLQ con alerta (SC-005) en
      `tests/integration/test_dlq_alerting.py`
- [ ] T082 Revisión final de Constitution Check (Principios I–VI) contra la
      implementación final antes de mergear

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciar de inmediato
- **Foundational (Phase 2)**: Depende de Setup — BLOQUEA todas las user stories
- **User Stories (Phase 3–6)**: Todas dependen de Foundational completa
  - US1 (P1) y US3 (P1) son el MVP; pueden avanzar en paralelo si hay capacidad de equipo
  - US2 (P2) depende de que los servicios de US1 (T030–T037) existan
  - US4 (P2) depende de que `job_runner`/modelos de US3 (T057, T058, T064) existan
- **Polish (Phase 7)**: Depende de que las user stories deseadas estén completas

### User Story Dependencies

- **US1 (P1)**: Puede iniciar tras Foundational — sin dependencia de otras stories
- **US2 (P2)**: Requiere que los servicios internos de US1 (template resolver, opt-out,
  rate limiter, canal sender, estado aggregator) ya existan, ya que reutiliza esa lógica
  de forma síncrona
- **US3 (P1)**: Puede iniciar tras Foundational — sin dependencia de otras stories
- **US4 (P2)**: Requiere el modelo `Reporte` y `job_runner`/`minio_client` de US3

### Dentro de cada User Story

- Tests DEBEN escribirse y fallar antes de la implementación (TDD, Principio V)
- Para tareas 🟢 (TDD estricto): ciclo red-green-refactor obligatorio, test unitario
  específico antes de cada función/método
- Para tareas 🟡/🔴: el test de integración/contrato correspondiente (ya listado en
  "Tests for User Story N") se escribe y debe fallar antes de tocar la implementación,
  sin exigir granularidad unitaria línea a línea
- Modelos antes que servicios
- Servicios antes que endpoints/consumers
- Implementación core antes de integración con otras stories

### Oportunidades de Paralelismo

- Todas las tareas de Setup marcadas [P] pueden correr en paralelo
- Todas las tareas Foundational marcadas [P] pueden correr en paralelo (dentro de Phase 2)
- Tras completar Foundational: US1 y US3 (ambas P1) pueden trabajarse en paralelo por
  equipos distintos; US2 y US4 quedan bloqueadas hasta que sus dependencias internas
  (dentro de US1/US3 respectivamente) estén listas
- Todos los tests [P] de una user story pueden correr en paralelo entre sí
- Los generadores de reporte (T060–T063) pueden implementarse en paralelo entre sí

---

## Implementation Strategy

### MVP First (User Stories 1 y 3 en paralelo)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (CRÍTICO — bloquea todo lo demás)
3. Completar Phase 3: User Story 1 (Notificaciones vía evento) — **STOP y VALIDAR**
4. Completar Phase 5: User Story 3 (Reportes: generar+descargar) — **STOP y VALIDAR**
5. En este punto ya hay un MVP funcional: notificaciones asíncronas + reportes exportables
6. Agregar Phase 4 (US2: envío REST síncrono) y Phase 6 (US4: consulta de estado) como
   incrementos sobre el MVP
7. Cada fase adicional se agrega sin romper las anteriores

### Entrega Incremental

1. Setup + Foundational → Base lista
2. Agregar US1 → Probar independientemente → Entregar/Demo (notificaciones asíncronas)
3. Agregar US3 → Probar independientemente → Entregar/Demo (reportes exportables)
4. Agregar US2 → Probar independientemente → Entregar/Demo (envío REST síncrono)
5. Agregar US4 → Probar independientemente → Entregar/Demo (consulta de estado)
6. Cada historia agrega valor incremental sin romper las previas
