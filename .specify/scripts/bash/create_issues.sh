#!/usr/bin/env bash
# Genera issues de GitHub a partir de specs/001-notificaciones-reportes/tasks.md
# Uso: bash .specify/scripts/bash/create_issues.sh
set -euo pipefail

REPO="titojuanc/Recome-Notificaciones"
FEATURE="001-notificaciones-reportes"

create_issue() {
  local id="$1"
  local title="$2"
  local body="$3"
  local labels="$4"
  echo "Creando $id: $title"
  gh issue create --repo "$REPO" \
    --title "[$id] $title" \
    --body "$body" \
    --label "$labels" \
    >/dev/null
}

# ─────────────────────────────────────────────────────────────
# Phase 1: Setup
# ─────────────────────────────────────────────────────────────

create_issue "T001" "Crear estructura de directorios base" \
"Crear estructura de directorios \`src/broker/\`, \`src/notificaciones/\`, \`src/reportes/\`, \`src/shared/\`, \`tests/{unit,contract,integration}/\` según \`plan.md\`.

**Feature**: $FEATURE
**Phase**: 1 - Setup
**Depende de**: Ninguna" \
"phase:setup"

create_issue "T002" "Inicializar proyecto Python 3.12 con dependencias" \
"Inicializar proyecto Python 3.12 con \`pyproject.toml\`/\`requirements.txt\`: \`fastapi\`, \`pika\`, \`httpx\`, \`jsonschema\`, \`redis\`, \`minio\`, \`jinja2\`, \`firebase-admin\`, SDK de SendGrid, \`WeasyPrint\`/\`openpyxl\`/\`reportlab\`, \`pytest\`, \`pytest-asyncio\`, \`testcontainers\`, \`respx\`.

**Feature**: $FEATURE
**Phase**: 1 - Setup
**Depende de**: T001" \
"phase:setup"

create_issue "T003" "[P] Configurar linting/formatting y pre-commit" \
"Configurar linting/formatting (\`ruff\`/\`black\`) y pre-commit hooks.

**Feature**: $FEATURE
**Phase**: 1 - Setup
**Paralelizable**: Sí" \
"phase:setup,parallel"

create_issue "T004" "[P] Crear docker-compose.yml de desarrollo" \
"Crear \`docker-compose.yml\` de desarrollo con RabbitMQ, Redis y MinIO locales (soporta \`quickstart.md\`).

**Feature**: $FEATURE
**Phase**: 1 - Setup
**Paralelizable**: Sí" \
"phase:setup,parallel"

create_issue "T005" "[P] Crear .env.example" \
"Crear \`.env.example\` con todas las variables listadas en \`quickstart.md\` (\`RABBITMQ_URL\`, \`REDIS_URL\`, \`MINIO_*\`, \`API_GENERAL_BASE_URL\`, \`API_GENERAL_INTERNAL_API_KEY\`, \`FCM_CREDENTIALS_PATH\`, \`SENDGRID_API_KEY\`, \`ENVIRONMENT\`).

**Feature**: $FEATURE
**Phase**: 1 - Setup
**Paralelizable**: Sí" \
"phase:setup,parallel"

# ─────────────────────────────────────────────────────────────
# Phase 2: Foundational
# ─────────────────────────────────────────────────────────────

create_issue "T006" "Implementar conexión RabbitMQ (pika)" \
"Implementar \`src/broker/connection.py\`: conexión \`pika\` con reconexión y declaración idempotente de exchanges/colas (FR-020).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO — bloquea todas las user stories)
**Depende de**: Phase 1 completa" \
"phase:foundational"

create_issue "T007" "Declaración de Dead Letter Exchange por cola" \
"Implementar declaración de Dead Letter Exchange por cola en \`src/broker/connection.py\`, con colas \`durable=true\` y mensajes \`delivery_mode=persistent\` (FR-017, FR-018).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Depende de**: T006" \
"phase:foundational"

create_issue "T008" "[P] Schemas DRAFT + schema_validator" \
"Copiar los JSON Schemas DRAFT a \`src/broker/schemas/\` (desde \`specs/001-notificaciones-reportes/contracts/*.draft.schema.json\`) y crear \`src/broker/schema_validator.py\` con función genérica de validación vía \`jsonschema\` (FR-022).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T009" "[P] shared/config.py" \
"Implementar \`src/shared/config.py\`: carga de variables de entorno, incluyendo modo mock vs real por \`ENVIRONMENT\` (FR-023).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T010" "[P] shared/logging.py" \
"Implementar \`src/shared/logging.py\`: logging estructurado compartido (necesario para alertas de DLQ, FR-018, y trazabilidad de fallback de idioma).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T011" "[P] shared/api_general_client.py" \
"Implementar \`src/shared/api_general_client.py\`: cliente \`httpx\` autenticado con \`X-Internal-Api-Key\` hacia \`api-general\`, con reintento/backoff para fallos transitorios (usado por US1 para opt-out y por US3 para datos de reporte).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T012" "[P] shared/redis_client.py" \
"Implementar \`src/shared/redis_client.py\`: cliente Redis compartido (dedup, cache de opt-out, contadores de rate limit, estado transitorio de reportes).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T013" "[P] shared/auth.py" \
"Implementar \`src/shared/auth.py\`: middleware/dependencia FastAPI para validar \`X-Internal-Api-Key\` en todos los endpoints expuestos (Principio IV).

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Paralelizable**: Sí" \
"phase:foundational,parallel"

create_issue "T014" "App FastAPI base (notificaciones + reportes)" \
"Crear app FastAPI base en \`src/notificaciones/api/app.py\` y \`src/reportes/api/app.py\`, montando el middleware de auth de T013.

**Feature**: $FEATURE
**Phase**: 2 - Foundational (⚠️ CRÍTICO)
**Depende de**: T013

**Checkpoint**: Infraestructura lista — las user stories pueden comenzar en paralelo" \
"phase:foundational"

# ─────────────────────────────────────────────────────────────
# Phase 3: US1 - Recibir notificación Push/Mail (P1 MVP)
# ─────────────────────────────────────────────────────────────

create_issue "T015" "[P][US1] Contract test notificacion.enviar schema" \
"Contract test del payload \`notificacion.enviar\` contra \`contracts/notificacion.enviar.draft.schema.json\` en \`tests/contract/test_notificacion_enviar_schema.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🔴 contrato
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:orchestration"

create_issue "T016" "[P][US1] Contract test NotificacionEnviarResponse" \
"Contract test de \`NotificacionEnviarResponse\` (\`estado_entrega\`/\`resultados_por_canal\`) contra \`contracts/openapi.draft.yaml\` en \`tests/contract/test_notificacion_enviar_response_schema.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🔴 contrato
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:orchestration"

create_issue "T017" "[P][US1] Unit test resolución de idioma" \
"Unit test de resolución de idioma: prioridad \`idioma\` del payload > preferencia de \`api-general\` > fallback default \`es\` (cuando falta template del idioma resuelto Y cuando no hay preferencia registrada) (FR-002, FR-009) en \`tests/unit/test_template_resolver.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:strict"

create_issue "T018" "[P][US1] Unit test agregación estado_entrega" \
"Unit test de agregación de \`estado_entrega\` (\`enviado\`/\`parcial\`/\`fallido\`/\`descartado_rate_limit\`) en \`tests/unit/test_estado_entrega_aggregation.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:strict"

create_issue "T019" "[P][US1] Unit test rate limiting por canal" \
"Unit test de rate limiting independiente por canal (20/hora c/u, FR-007) en \`tests/unit/test_rate_limiter.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:strict"

create_issue "T020" "[P][US1] Unit test dedup por event_id" \
"Unit test de dedup por \`event_id\` con TTL en \`tests/unit/test_dedup.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:strict"

create_issue "T021" "[US1] Integration test: envío exitoso sin opt-out" \
"Integration test: evento válido sin opt-out → push+mail enviados (mocks) en \`tests/integration/test_notificacion_enviar_flow.py\` (Acceptance Scenario 1).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T022" "[US1] Integration test: usuario con opt-out" \
"Integration test: usuario con opt-out → no se envía, se registra \`descartado por preferencia\` en \`tests/integration/test_notificacion_opt_out.py\` (Acceptance Scenario 2).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T023" "[US1] Integration test: dedup ante redelivery" \
"Integration test: mismo \`event_id\` dos veces (redelivery) → sin envío duplicado en \`tests/integration/test_notificacion_dedup.py\` (Acceptance Scenario 3).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T024" "[US1] Integration test: rate limit por canal" \
"Integration test: canal supera rate limit → descartado sin reintento, otro canal no afectado en \`tests/integration/test_notificacion_rate_limit.py\` (Acceptance Scenario 4).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T025" "[US1] Integration test: retry + DLQ" \
"Integration test: fallo transitorio de proveedor → backoff hasta 5 intentos → DLQ del canal en \`tests/integration/test_notificacion_retry_dlq.py\` (Acceptance Scenario 5).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T026" "[US1] Integration test: estado parcial" \
"Integration test: éxito en push + fallo definitivo en mail → \`estado_entrega = parcial\` en \`tests/integration/test_notificacion_parcial.py\` (Clarification #1).

**Feature**: $FEATURE | **User Story**: US1" \
"phase:us1"

create_issue "T027" "[P][US1] Modelo Notificacion + EstadoCanal" \
"Modelo \`Notificacion\` y \`EstadoCanal\` en \`src/notificaciones/models/notificacion.py\` (según \`data-model.md\`).

**Feature**: $FEATURE | **User Story**: US1
**Paralelizable**: Sí" \
"phase:us1,parallel"

create_issue "T028" "[P][US1] Modelo Preferencia (opt-out)" \
"Modelo \`Preferencia\` (opt-out) en \`src/notificaciones/models/preferencia.py\`.

**Feature**: $FEATURE | **User Story**: US1
**Paralelizable**: Sí" \
"phase:us1,parallel"

create_issue "T029" "[P][US1] Registro de templates" \
"Registro de templates \`tipo_evento+idioma+canal → template\` en \`src/notificaciones/templates/registry.py\`, con templates Jinja2 mínimos en \`es\`/\`en\` para al menos un \`tipo_evento\` de ejemplo, en \`src/notificaciones/templates/es/\` y \`src/notificaciones/templates/en/\`.

**Feature**: $FEATURE | **User Story**: US1
**Paralelizable**: Sí" \
"phase:us1,parallel"

create_issue "T030" "[US1] Servicio de resolución de idioma" \
"🟢 Servicio de resolución de idioma con fallback a \`es\` (por template faltante o por ausencia de preferencia registrada) en \`src/notificaciones/services/template_resolver.py\` (depende de T027, T029).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto" \
"phase:us1,tdd:strict"

create_issue "T031" "[US1] Servicio de consulta de opt-out con cache" \
"🟡 Servicio de consulta de opt-out con cache Redis 5 min en \`src/notificaciones/services/opt_out_service.py\` (depende de T011, T012, T028).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟡 integración" \
"phase:us1,tdd:integration"

create_issue "T032" "[US1] Servicio de rate limiting por canal" \
"🟢 Servicio de rate limiting independiente por canal en \`src/notificaciones/services/rate_limiter.py\` (depende de T012).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto" \
"phase:us1,tdd:strict"

create_issue "T033" "[US1] Servicio de dedup por event_id" \
"🟢 Servicio de dedup por \`event_id\` en \`src/notificaciones/services/dedup_service.py\` (depende de T012).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto" \
"phase:us1,tdd:strict"

create_issue "T034" "[P][US1] PushProvider (FCM real + mock)" \
"🟡 \`PushProvider\` (FCM real + mock) en \`src/notificaciones/providers/push_provider.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:integration"

create_issue "T035" "[P][US1] MailProvider (SendGrid real + mock)" \
"🟡 \`MailProvider\` (SendGrid real + mock) en \`src/notificaciones/providers/mail_provider.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us1,parallel,tdd:integration"

create_issue "T036" "[US1] Servicio de envío por canal con backoff" \
"🟡 Servicio de envío por canal con backoff exponencial (máx. 5 intentos) en \`src/notificaciones/services/canal_sender.py\` (depende de T030, T034, T035).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟡 integración" \
"phase:us1,tdd:integration"

create_issue "T037" "[US1] Servicio de agregación de estado_entrega" \
"🟢 Servicio de agregación de \`estado_entrega\` a partir de \`resultados_por_canal\` en \`src/notificaciones/services/estado_aggregator.py\` (depende de T027).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟢 estricto" \
"phase:us1,tdd:strict"

create_issue "T038" "[US1] Consumer de notificacion.enviar" \
"🔴 Consumer de \`notificacion.enviar\` en \`src/notificaciones/consumers/notificacion_consumer.py\`: valida schema (T008), dedup (T033), opt-out (T031), rate limit (T032), envío por canal (T036), agregación (T037), publica resultado a \`api-general\` (FR-008), maneja rechazo de \`tipo_evento\` no soportado (edge case).

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🔴 orquestación
**Depende de**: T006, T007, T027–T037" \
"phase:us1,tdd:orchestration"

create_issue "T039" "[US1] Reporte de estado de entrega" \
"🟡 Reporte de estado de entrega vía \`api_general_client\` (T011) al finalizar cada notificación, en \`src/notificaciones/services/delivery_reporter.py\`.

**Feature**: $FEATURE | **User Story**: US1 | **TDD**: 🟡 integración" \
"phase:us1,tdd:integration"

create_issue "T040" "[US1] Logging estructurado de fallback/rate-limit/DLQ" \
"Logging estructurado de fallback de idioma, rate-limit descartado, y paso a DLQ por canal (usa T010).

**Feature**: $FEATURE | **User Story**: US1

**Checkpoint**: User Story 1 completamente funcional y testeable de forma independiente" \
"phase:us1"

# ─────────────────────────────────────────────────────────────
# Phase 4: US2 - REST síncrono (P2)
# ─────────────────────────────────────────────────────────────

create_issue "T041" "[P][US2] Contract test POST /notificaciones/enviar" \
"Contract test de \`POST /notificaciones/enviar\` contra \`contracts/openapi.draft.yaml\` en \`tests/contract/test_notificaciones_enviar_endpoint.py\`.

**Feature**: $FEATURE | **User Story**: US2
**Paralelizable**: Sí" \
"phase:us2,parallel,tdd:orchestration"

create_issue "T042" "[US2] Integration test: llamada autenticada síncrona" \
"Integration test: llamada autenticada válida → respuesta síncrona con resultado de envío en \`tests/integration/test_notificacion_endpoint_sync.py\` (Acceptance Scenario 1).

**Feature**: $FEATURE | **User Story**: US2" \
"phase:us2"

create_issue "T043" "[US2] Integration test: auth inválida → 401" \
"Integration test: llamada sin API key / inválida → 401, no se procesa envío en \`tests/integration/test_notificacion_endpoint_auth.py\` (Acceptance Scenario 2).

**Feature**: $FEATURE | **User Story**: US2" \
"phase:us2"

create_issue "T044" "[US2] Endpoint POST /notificaciones/enviar" \
"🔴 Endpoint \`POST /notificaciones/enviar\` en \`src/notificaciones/api/routes.py\`, protegido por \`auth.py\` (T013), reutilizando \`template_resolver\`, \`opt_out_service\`, \`rate_limiter\`, \`canal_sender\`, \`estado_aggregator\` (T030–T037) de forma síncrona.

**Feature**: $FEATURE | **User Story**: US2 | **TDD**: 🔴 orquestación
**Depende de**: Phase 3 (US1) completa" \
"phase:us2,tdd:orchestration"

create_issue "T045" "[US2] Registrar router en app.py" \
"Registrar el router de T044 en \`src/notificaciones/api/app.py\` (T014).

**Feature**: $FEATURE | **User Story**: US2

**Checkpoint**: User Stories 1 y 2 funcionan de forma independiente" \
"phase:us2"

# ─────────────────────────────────────────────────────────────
# Phase 5: US3 - Reportes exportables (P1 MVP)
# ─────────────────────────────────────────────────────────────

create_issue "T046" "[P][US3] Contract test reporte.generar schema" \
"Contract test de \`reporte.generar\` contra \`contracts/reporte.generar.draft.schema.json\` en \`tests/contract/test_reporte_generar_schema.py\`.

**Feature**: $FEATURE | **User Story**: US3
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:orchestration"

create_issue "T047" "[P][US3] Contract test reporte.listo schema" \
"Contract test de \`reporte.listo\` contra \`contracts/reporte.listo.draft.schema.json\` (incluye \`motivo\` enum) en \`tests/contract/test_reporte_listo_schema.py\`.

**Feature**: $FEATURE | **User Story**: US3
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:orchestration"

create_issue "T048" "[P][US3] Contract test GET /reportes/{id}/descarga" \
"Contract test de \`GET /reportes/{id}/descarga\` contra \`contracts/openapi.draft.yaml\` en \`tests/contract/test_reporte_descarga_endpoint.py\`.

**Feature**: $FEATURE | **User Story**: US3
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:orchestration"

create_issue "T049" "[P][US3] Unit test de generadores" \
"Unit test de cada generador (ventas, actividad_usuario, catalogo_uso, recomendaciones) en \`tests/unit/test_generadores_reporte.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:strict"

create_issue "T050" "[P][US3] Unit test cancelación por timeout" \
"Unit test de cancelación activa del proceso al cumplir timeout (FR-012) en \`tests/unit/test_reporte_timeout.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:strict"

create_issue "T051" "[P][US3] Unit test reintento transitorio" \
"Unit test de reintento automático solo para fallos transitorios, no para timeout (FR-012a) en \`tests/unit/test_reporte_retry_transitorio.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:strict"

create_issue "T051a" "[P][US3] Unit test límite de tamaño excedido" \
"Unit test de rechazo definitivo por límite de tamaño excedido (\`motivo: limite_tamano_excedido\`, sin truncar, sin reintento — FR-013a; ver T083) en \`tests/unit/test_reporte_limite_tamano.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto
**Paralelizable**: Sí
**Nota**: Task agregada en Clarification Round 2" \
"phase:us3,parallel,tdd:strict"

create_issue "T052" "[US3] Integration test: reporte generado ready" \
"Integration test: \`reporte.generar\` válido → archivo en MinIO bajo \`tipo/fecha/usuario\`, \`reporte.listo\` con \`estado: ready\` en \`tests/integration/test_reporte_generar_ready.py\` (Acceptance Scenario 1).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T053" "[US3] Integration test: timeout flow" \
"Integration test: job excede timeout → \`failed\`/\`motivo: timeout\`, \`reporte.listo\` con \`estado: error\`, sin reintento en \`tests/integration/test_reporte_timeout_flow.py\` (Acceptance Scenario 2).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T054" "[US3] Integration test: descarga signed URL" \
"Integration test: solicitud de descarga autenticada → signed URL de 15 min en \`tests/integration/test_reporte_descarga.py\` (Acceptance Scenario 3).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T055" "[US3] Integration test: limpieza por retención" \
"Integration test: job de limpieza borra reporte vencido (>30 días) en \`tests/integration/test_reporte_retencion.py\` (Acceptance Scenario 5).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T056" "[US3] Integration test: dependencia no disponible" \
"Integration test: \`api-general\` no responde al pedir datos → reintento transitorio → \`failed\`/\`motivo: dependencia_no_disponible\` en \`tests/integration/test_reporte_dependencia_no_disponible.py\` (Edge case).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T057" "[P][US3] Modelo Reporte" \
"🟡 Modelo \`Reporte\` (con \`intentos\`, \`motivo\`, \`fecha_expiracion\`) en \`src/reportes/models/reporte.py\` (según \`data-model.md\`).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T058" "[P][US3] Cliente MinIO" \
"🟡 Cliente MinIO: subida, signed URL 15 min, listado por prefijo en \`src/reportes/storage/minio_client.py\` (depende de T009).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T059" "[P][US3] Registro extensible de generadores" \
"🟡 Registro extensible de generadores en \`src/reportes/generators/registry.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T060" "[P][US3] Generador ventas" \
"🟡 Generador \`ventas\` en \`src/reportes/generators/ventas.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T061" "[P][US3] Generador actividad_usuario" \
"🟡 Generador \`actividad_usuario\` en \`src/reportes/generators/actividad_usuario.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T062" "[P][US3] Generador catalogo_uso" \
"🟡 Generador \`catalogo_uso\` en \`src/reportes/generators/catalogo_uso.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T063" "[P][US3] Generador recomendaciones" \
"🟡 Generador \`recomendaciones\` en \`src/reportes/generators/recomendaciones.py\`.

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración
**Paralelizable**: Sí" \
"phase:us3,parallel,tdd:integration"

create_issue "T064" "[US3] Servicio job_runner con timeout" \
"🟢 Servicio de ejecución de job con timeout configurable y cancelación activa del proceso en \`src/reportes/services/job_runner.py\` (FR-012; depende de T057, T059–T063; incluye validación de límite de tamaño antes de generar, vía T083).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto" \
"phase:us3,tdd:strict"

create_issue "T065" "[US3] Servicio de reintento con backoff" \
"🟢 Servicio de reintento con backoff para fallos transitorios (no aplica a timeout ni a límite de tamaño excedido) en \`src/reportes/services/retry_service.py\` (FR-012a; depende de T064).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto" \
"phase:us3,tdd:strict"

create_issue "T066" "[US3] Servicio de paginación de datos" \
"🟡 Servicio de paginación de datos vía \`api_general_client\` (T011) en \`src/reportes/services/data_fetcher.py\` (FR-011).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración" \
"phase:us3,tdd:integration"

create_issue "T067" "[US3] Consumer de reporte.generar" \
"🔴 Consumer de \`reporte.generar\` en \`src/reportes/consumers/reporte_consumer.py\`: valida schema (T008), ejecuta job (T064–T066, T083), sube a MinIO (T058), publica \`reporte.listo\` (\`ready\`/\`error\`+\`motivo\`, incluyendo \`limite_tamano_excedido\`), maneja \`tipo_no_soportado\` (edge case).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🔴 orquestación
**Depende de**: T006, T007, T057–T066, T083" \
"phase:us3,tdd:orchestration"

create_issue "T068" "[US3] Endpoint GET /reportes/{id}/descarga" \
"🔴 Endpoint \`GET /reportes/{reporte_id}/descarga\` en \`src/reportes/api/routes.py\`, protegido por auth (T013), genera signed URL solo si \`estado == ready\` (depende de T058, T067).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🔴 orquestación" \
"phase:us3,tdd:orchestration"

create_issue "T069" "[US3] Job de limpieza por retención" \
"🟡 Job periódico de limpieza por retención (default 30 días, override por tipo) en \`src/reportes/services/retention_cleanup.py\` (FR-013; depende de T058).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟡 integración" \
"phase:us3,tdd:integration"

create_issue "T070" "[US3] Registrar router de descarga en app.py" \
"Registrar el router de T068 en \`src/reportes/api/app.py\` (T014).

**Feature**: $FEATURE | **User Story**: US3" \
"phase:us3"

create_issue "T083" "[P][US3] Servicio de validación de límite de tamaño" \
"🟢 Servicio de validación de límite de tamaño por tipo (conteo de registros contra \`limite_registros\` del generador, FR-013a) en \`src/reportes/services/size_limit_validator.py\` (depende de T057, T059; consumido por T064 antes de invocar el generador).

**Feature**: $FEATURE | **User Story**: US3 | **TDD**: 🟢 estricto
**Paralelizable**: Sí
**Nota**: Task agregada en Clarification Round 2" \
"phase:us3,parallel,tdd:strict"

create_issue "T084" "[US3] Integration test: límite de tamaño excedido" \
"Integration test: datos a exportar exceden el límite configurado → \`failed\`/\`motivo: limite_tamano_excedido\`, sin archivo generado, sin reintento en \`tests/integration/test_reporte_limite_tamano_flow.py\` (Clarification #2).

**Feature**: $FEATURE | **User Story**: US3
**Nota**: Task agregada en Clarification Round 2

**Checkpoint**: User Stories 1, 2 y 3 funcionan de forma independiente" \
"phase:us3"

# ─────────────────────────────────────────────────────────────
# Phase 6: US4 - Consultar estado de reporte (P2)
# ─────────────────────────────────────────────────────────────

create_issue "T071" "[P][US4] Contract test GET /reportes/{id}/estado" \
"Contract test de \`GET /reportes/{id}/estado\` contra \`contracts/openapi.draft.yaml\` en \`tests/contract/test_reporte_estado_endpoint.py\`.

**Feature**: $FEATURE | **User Story**: US4
**Paralelizable**: Sí" \
"phase:us4,parallel,tdd:orchestration"

create_issue "T072" "[US4] Integration test: estado consistente en cada fase" \
"Integration test: estado \`pending\`/\`processing\`/\`ready\`/\`failed\` consistente en cada fase en \`tests/integration/test_reporte_estado_flow.py\` (Acceptance Scenarios 1–3).

**Feature**: $FEATURE | **User Story**: US4" \
"phase:us4"

create_issue "T073" "[US4] Servicio de lectura de estado" \
"🟡 Servicio de lectura de estado desde Redis (transitorio) + MinIO (terminal) en \`src/reportes/services/estado_reader.py\` (depende de T057, T058).

**Feature**: $FEATURE | **User Story**: US4 | **TDD**: 🟡 integración" \
"phase:us4,tdd:integration"

create_issue "T074" "[US4] Endpoint GET /reportes/{id}/estado" \
"🔴 Endpoint \`GET /reportes/{reporte_id}/estado\` en \`src/reportes/api/routes.py\`, protegido por auth (T013) — depende de T073.

**Feature**: $FEATURE | **User Story**: US4 | **TDD**: 🔴 orquestación" \
"phase:us4,tdd:orchestration"

create_issue "T075" "[US4] Persistir transiciones de estado en Redis" \
"Actualizar \`job_runner\` (T064) para persistir transición de estado en Redis en cada paso (\`pending → processing → ready|failed\`) para que T073 pueda leerla.

**Feature**: $FEATURE | **User Story**: US4

**Checkpoint**: Todas las user stories (US1–US4) funcionan de forma independiente" \
"phase:us4"

# ─────────────────────────────────────────────────────────────
# Phase 7: Polish & Cross-Cutting Concerns
# ─────────────────────────────────────────────────────────────

create_issue "T076" "[P] Métricas Prometheus de RabbitMQ" \
"Exponer métricas de RabbitMQ (colas, consumidores, mensajes en espera, tasa de DLQ) vía plugin de management + exporter Prometheus (FR-021).

**Feature**: $FEATURE | **Phase**: 7 - Polish
**Paralelizable**: Sí" \
"phase:polish,parallel"

create_issue "T077" "[P] Documentar README con setup local" \
"Documentar en \`README.md\` cómo correr cada módulo localmente (referenciar \`quickstart.md\`).

**Feature**: $FEATURE | **Phase**: 7 - Polish
**Paralelizable**: Sí" \
"phase:polish,parallel,documentation"

create_issue "T078" "[P] Limpieza de imports/lint" \
"Revisar y limpiar imports/lint en \`src/\` (usar T003).

**Feature**: $FEATURE | **Phase**: 7 - Polish
**Paralelizable**: Sí" \
"phase:polish,parallel"

create_issue "T079" "Validación end-to-end de quickstart.md" \
"Ejecutar validación completa de \`quickstart.md\` end-to-end (RabbitMQ + Redis + MinIO + mocks de api-general/FCM/SendGrid).

**Feature**: $FEATURE | **Phase**: 7 - Polish" \
"phase:polish"

create_issue "T080" "[P] Tests de seguridad: URLs firmadas" \
"Tests de seguridad: verificar que URLs no firmadas/expiradas de reportes son rechazadas (SC-004) en \`tests/integration/test_reporte_descarga_seguridad.py\`.

**Feature**: $FEATURE | **Phase**: 7 - Polish
**Paralelizable**: Sí" \
"phase:polish,parallel"

create_issue "T081" "[P] Test de verificación DLQ + alerta" \
"Test de verificación de cero pérdida silenciosa: 100% de mensajes que agotan reintentos terminan en su DLQ con alerta (SC-005) en \`tests/integration/test_dlq_alerting.py\`.

**Feature**: $FEATURE | **Phase**: 7 - Polish
**Paralelizable**: Sí" \
"phase:polish,parallel"

create_issue "T082" "Revisión final de Constitution Check" \
"Revisión final de Constitution Check (Principios I–VI) contra la implementación final antes de mergear.

**Feature**: $FEATURE | **Phase**: 7 - Polish" \
"phase:polish"

echo ""
echo "✅ 82 issues creados exitosamente en $REPO"
