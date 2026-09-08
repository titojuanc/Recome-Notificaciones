# 📋 Resumen de Tasks Preparados para Implementar

**Documento de referencia rápida para el roadmap de implementación**

Versión: 1.0  
Fecha: 8 de septiembre de 2026  
Base: `tasks.md` (82 tasks totales)

---

## 📌 Panorámica General

- **Total Tasks:** 82
- **Phases:** 7 (Setup → Foundational → 4 User Stories → Polish)
- **MVP Stories:** US1 (Notificaciones), US3 (Reportes) — P1, parallelizable
- **Enhancement Stories:** US2 (REST síncrono), US4 (Consulta estado) — P2, con dependencias internas
- **Esfuerzo Total Estimado:** 100–130 horas (spec-driven, test-first, TDD clasificado)

---

## 🔄 Fases de Implementación

### **Phase 1: Setup (T001–T005) — 6 tasks**

**Duración:** 2–4 horas  
**Bloqueos:** Ninguno  
**Parallelizable:** Sí [P]

Inicializa la estructura del proyecto Python 3.12:

- **T001**: Crear directorios (`src/broker`, `src/notificaciones`, `src/reportes`, `src/shared`, `tests/`)
- **T002**: Configurar `pyproject.toml`, `requirements.txt` con todas las dependencias
  - FastAPI, pika, httpx, jsonschema, redis, minio, jinja2, firebase-admin, sendgrid
  - WeasyPrint/openpyxl/reportlab, pytest, pytest-asyncio, testcontainers, respx
- **T003** [P]: Linting/formatting (`ruff`/`black`) + pre-commit hooks
- **T004** [P]: `docker-compose.yml` con RabbitMQ, Redis, MinIO
- **T005** [P]: `.env.example` con todas las variables de entorno

**✅ Estado:** Listo para iniciar inmediatamente

---

### **Phase 2: Foundational (T006–T014) — 9 tasks**

**Duración:** 4–6 horas  
**Bloqueos:** Depende de Phase 1  
**⚠️ CRÍTICO:** Bloquea todas las user stories

Infraestructura núcleo compartida:

- **T006–T007**: RabbitMQ connection con reconexión idempotente + Dead Letter Exchanges
- **T008** [P]: Copiar DRAFT schemas a `src/broker/schemas/`, crear `schema_validator.py`
- **T009–T013** [P]: Config compartida (`config.py`, `logging.py`, `api_general_client.py`, `redis_client.py`, `auth.py`)
- **T014**: App FastAPI base con middleware de auth

**Deliverable:** Todos los módulos pueden conectarse al broker, validar eventos, autenticarse

**✅ Estado:** Listo tras Phase 1. **NO AVANZAR A USER STORIES SIN ESTO.**

---

### **Phase 3: User Story 1 — Recibir Notificación Push/Mail (P1 MVP) — 26 tasks**

**Duración:** 20–30 horas  
**Bloqueos:** Depende de Phase 2  
**Parallelizable:** Sí (tests y algunos servicios [P])  
**Dependencias Externas:** US1 servicios necesarios para US2

**Objetivo:** Consumir evento `notificacion.enviar`, resolver template/idioma, respetar opt-out, rate limit, dedup, enviar por push+mail con retry y agregación de estado.

#### Tests (T015–T026) — 12 tests

**Unit Tests** 🟢 [P]:
- **T015**: Contract test schema `notificacion.enviar`
- **T016**: Contract test `NotificacionEnviarResponse`
- **T017**: Idioma resolve: payload > preferencia > default `es` + template fallback
- **T018**: Estado_entrega aggregation (enviado/parcial/fallido/descartado_rate_limit)
- **T019**: Rate limiting independiente por canal (20/hora cada uno)
- **T020**: Dedup por `event_id` con TTL en Redis

**Integration Tests** (testcontainers):
- **T021**: Evento válido sin opt-out → push+mail enviados
- **T022**: Usuario con opt-out → descartado (sin envío)
- **T023**: Mismo `event_id` dos veces → sin duplicados
- **T024**: Rate limit excedido → descartado, otro canal no afectado
- **T025**: Fallo transitorio → backoff 5 intentos → DLQ
- **T026**: Push OK + Mail falla → `estado_entrega = parcial`

#### Implementación (T027–T040) — 14 servicios

**Modelos** [P]:
- **T027**: `Notificacion` + `EstadoCanal`
- **T028**: `Preferencia` (opt-out)
- **T029**: Registro de templates (tipo_evento + idioma + canal → Jinja2)

**Servicios Lógica Pura** 🟢:
- **T030**: Template resolver (idioma + fallback)
- **T032**: Rate limiter (independiente por canal)
- **T033**: Dedup service (event_id + TTL)
- **T037**: Estado_entrega aggregator

**Servicios SDK** 🟡:
- **T031**: Opt-out service (cache Redis 5 min)
- **T034**: PushProvider (FCM real + mock)
- **T035**: MailProvider (SendGrid real + mock)
- **T036**: Canal sender (backoff exponencial, 5 intentos)

**Orquestación** 🔴:
- **T038**: Consumer `notificacion.enviar` (valida → dedup → opt-out → rate-limit → envío → agregación)
- **T039**: Delivery reporter (publica resultado a api-general)
- **T040**: Logging estructurado (fallback idioma, rate-limit, DLQ)

**✅ Deliverable:** Notificaciones asíncronas completas (evento → envío por ambos canales + retry + estado)

**✅ Estado:** Listo tras Phase 2

---

### **Phase 4: User Story 2 — Solicitar Envío vía REST Síncrono (P2) — 5 tasks**

**Duración:** 3–5 horas  
**Bloqueos:** Depende de US1 servicios (T030–T037 completados)  
**Parallelizable:** No (depende internamente de US1)

**Objetivo:** Endpoint REST síncrono reutilizando lógica de US1 (template/opt-out/rate-limit).

#### Tests (T041–T043) — 3 tests

- **T041**: Contract test OpenAPI `/notificaciones/enviar` POST
- **T042**: Integration test llamada autenticada → respuesta síncrona
- **T043**: Integration test sin API key / inválida → 401

#### Implementación (T044–T045) — 2 componentes

- **T044** 🔴: Endpoint `POST /notificaciones/enviar` (protegido auth, síncrono)
- **T045**: Registrar router en `src/notificaciones/api/app.py`

**✅ Deliverable:** Endpoint REST síncrono para envío inmediato, misma validación que vía evento

**✅ Estado:** Listo tras US1

---

### **Phase 5: User Story 3 — Generar & Descargar Reportes Exportables (P1 MVP) — 35 tasks**

**Duración:** 30–40 horas  
**Bloqueos:** Depende de Phase 2  
**Parallelizable:** Sí (tests, generadores [P], servicios [P])  
**Notas:** Parallelizable con US1 si hay capacidad de equipo

**Objetivo:** Consumir `reporte.generar`, obtener datos de api-general, generar PDF/Excel, subir a MinIO, publicar `reporte.listo`, exponer descarga vía signed URL.

#### Tests (T046–T056, T051a, T084) — 11 tests

**Contract Tests**:
- **T046**: Schema `reporte.generar`
- **T047**: Schema `reporte.listo` (motivo enum: timeout/dependencia/tipo_no_soportado/limite_tamano_excedido)
- **T048**: Endpoint GET `/reportes/{id}/descarga`

**Unit Tests** 🟢 [P]:
- **T049**: Generadores (ventas, actividad_usuario, catalogo_uso, recomendaciones)
- **T050**: Timeout con cancelación activa
- **T051**: Retry automático solo para transitorios (no timeout)
- **T051a**: Rechazo definitivo por límite de tamaño (sine truncate, sin retry) — **NEW Clarif#2**

**Integration Tests** (testcontainers):
- **T052**: Reporte válido → archivo en MinIO → `reporte.listo ready`
- **T053**: Job excede timeout → `failed/motivo: timeout`, sin retry
- **T054**: Descarga autenticada → signed URL 15 min
- **T055**: Limpieza por retención (>30 días)
- **T056**: api-general no disponible → retry transitorio → `failed/dependencia_no_disponible`
- **T084**: Datos exceden límite → `failed/limite_tamano_excedido`, sin archivo, sin retry — **NEW Clarif#2**

#### Implementación (T057–T070, T083) — 20 componentes

**Modelos** [P]:
- **T057**: `Reporte` (con intentos, motivo, fecha_expiracion)

**Storage** [P]:
- **T058**: MinIO client (upload, signed URLs 15 min, listado por prefijo)

**Generadores** [P] 🟡:
- **T059**: Registro extensible de generadores
- **T060**: Generador `ventas`
- **T061**: Generador `actividad_usuario`
- **T062**: Generador `catalogo_uso`
- **T063**: Generador `recomendaciones`

**Servicios Lógica Pura** 🟢:
- **T064**: Job runner (timeout configurable con cancelación activa + size_limit_validator)
- **T065**: Retry service (backoff solo para transitorios, NO timeout/size-limit)
- **T083**: Size limit validator (conteo vs limite_registros) — **NEW Clarif#2**

**Servicios SDK** 🟡:
- **T066**: Data fetcher (paginación vía api_general_client)
- **T069**: Retention cleanup (default 30 días, override por tipo)

**Orquestación** 🔴:
- **T067**: Consumer `reporte.generar` (valida → fetch datos → validate size → generar → upload MinIO → publica `reporte.listo`)
- **T068**: Endpoint GET `/reportes/{id}/descarga` (signed URL si `estado == ready`)

**Wiring**:
- **T070**: Registrar router en `src/reportes/api/app.py`

**✅ Deliverable:** Reportes PDF/Excel generados bajo demanda, con 4 tipos de generadores, timeout activo, retry transitorio, límite de tamaño, limpieza automática

**✅ Estado:** Listo tras Phase 2, **PARALLELIZABLE CON US1**

---

### **Phase 6: User Story 4 — Consultar Estado Reporte (P2) — 5 tasks**

**Duración:** 4–6 horas  
**Bloqueos:** Depende de US3 modelos + job_runner (T057, T064)  
**Parallelizable:** No (depende internamente de US3)

**Objetivo:** Endpoint REST para consultar estado sin esperar notificación.

#### Tests (T071–T072) — 2 tests

- **T071**: Contract test GET `/reportes/{id}/estado`
- **T072**: Integration test estado consistency (pending → processing → ready|failed)

#### Implementación (T073–T075) — 3 componentes

- **T073** 🟡: Estado reader (Redis transitorio + MinIO terminal)
- **T074** 🔴: Endpoint GET `/reportes/{id}/estado`
- **T075**: Persist transiciones en Redis (modifica T064 job_runner)

**✅ Deliverable:** Endpoint de estado sincronizado con job_runner, lectura desde Redis/MinIO

**✅ Estado:** Listo tras US3

---

### **Phase 7: Polish & Cross-Cutting Concerns (T076–T082) — 7 tasks**

**Duración:** 10–15 horas  
**Bloqueos:** Ninguno (ejecuta después de features)  
**Parallelizable:** Sí [P]

Mejoras transversales a todas las stories:

- **T076** [P]: Métricas Prometheus (RabbitMQ: colas, consumidores, tasa DLQ)
- **T077** [P]: Documentación README (cómo correr cada módulo, referenciar quickstart.md)
- **T078** [P]: Linting cleanup (`ruff` check)
- **T079**: End-to-end quickstart validation (RabbitMQ + Redis + MinIO + mocks)
- **T080** [P]: Tests seguridad (URLs no-firmadas/expiradas rechazadas)
- **T081** [P]: Verificación DLQ (100% de mensajes agotados → DLQ + alerta)
- **T082**: Constitution Check final (Principios I–VI vs implementación)

**✅ Estado:** Listo tras features principales

---

## 🎯 Clasificación de Rigor TDD (Constitution v1.1.0)

No todas las tareas benefician igual de TDD unitario estricto. Cada task tiene un tier:

### 🟢 **TDD Estricto** (~14 tasks)

**Criterio:** Lógica pura/determinística, fácil de aislar sin infraestructura pesada

**Aplica a:**
- Rate limiting (T019, T032)
- Dedup (T020, T033)
- Template resolver + idioma fallback (T017, T030)
- Estado_entrega aggregation (T018, T037)
- Timeout + cancelación (T050, T064 parcial)
- Retry diferenciado (T051, T065)
- Size limit validator (T051a, T083)

**Disciplina Requerida:** Red-Green-Refactor obligatorio
- Escribir test unitario específico
- Verlo fallar
- Recién implementar
- Refactorizar

### 🟡 **Test-First de Integración** (~15 tasks)

**Criterio:** Lógica envuelve SDK/proveedor externo (FCM, SendGrid, MinIO, generadores)

**Aplica a:**
- Opt-out service con cache (T031)
- PushProvider, MailProvider (T034, T035)
- Canal sender con backoff (T036)
- Todos los 4 generadores (T060–T063)
- MinIO client (T058)
- Retention cleanup (T069)
- Estado reader (T073)

**Disciplina Requerida:** Define interfaz/contrato primero (mock-first)
- Escribir test de integración/contrato
- Definir interfaz esperada
- Mockear SDK/externo
- Implementar interface
- Validar con integration test real

### 🔴 **Test-First de Contrato/Orquestación** (~5 tasks)

**Criterio:** Consumers + endpoints que coordinan servicios ya testeados

**Aplica a:**
- Consumer `notificacion.enviar` (T038)
- Endpoint REST síncrono (T044)
- Consumer `reporte.generar` (T067)
- Endpoint GET descarga (T068)
- Endpoint GET estado (T074)

**Disciplina Requerida:** Contract test + integration test pre-escritos
- Tests ya están en "Tests for User Story N" (ejecutan primero, fallan)
- Implementar orquestación para pasar los tests
- No se exige TDD unitario línea a línea

**En todos los casos:** Test **siempre** se escribe antes que la implementación — la diferencia es granularidad

---

## 📊 Estrategia de Entrega Incremental

### Dependencias de Fases

```
Phase 1: Setup
    ↓
Phase 2: Foundational ← BLOQUEA TODAS LAS STORIES
    ↓ ↓
    ├─→ Phase 3: US1 (P1) ║ Phase 5: US3 (P1)
    │       ↓                    ↓
    │   Phase 4: US2 (P2)    Phase 6: US4 (P2)
    │       ↓                    ↓
    └──────────────────────────────
            ↓
        Phase 7: Polish
```

### Checkpoints de Entrega MVP

| Checkpoint | Tasks Completadas | Valor Entregado |
|---|---|---|
| Base lista | Phase 1–2 (T001–T014) | Proyecto scaffold, infraestructura, broker operativo |
| Notificaciones MVP | Phase 1–3 (T001–T040) | Notificaciones asíncronas push/mail con retry, opt-out, rate-limit, dedup |
| Reportes MVP | Phase 1–2 + 5 (T001–T014 + T046–T070, T083–T084) | Reportes PDF/Excel generados, descargables, timeout, retry transitorio |
| **Full MVP** | Phases 1–5 (T001–T070, T083–T084) | **Notificaciones + Reportes completamente funcionales** |
| Enhancements | Phase 4 + 6 (T041–T045, T071–T075) | REST síncrono + consulta estado |
| Production | Phase 7 (T076–T082) | Métricas, seguridad, documentación, alertas |

### Paralelismo Dentro de Fases

- **Phase 1:** Todas las tareas [P] pueden correr en paralelo (3 equipos)
- **Phase 2:** Todas las tareas [P] pueden correr en paralelo (5 tareas simultáneas)
- **Phase 3 + 5:** Pueden correr en paralelo si hay capacidad (US1 y US3 independientes tras Phase 2)
- **US1 Tests:** T015–T020 [P] pueden ser paralelas
- **US3 Tests:** T049–T051a [P] pueden ser paralelas
- **US3 Generadores:** T060–T063 [P] pueden ser paralelas
- **Phase 7:** Todas las tareas [P] pueden correr en paralelo

---

## ⏱️ Esfuerzo Estimado por Phase

| Phase | Tasks | Duración | Parallelizable |
|---|---|---|---|
| Setup | 6 | 2–4 h | Sí (3 tasks) |
| Foundational | 9 | 4–6 h | Sí (5 tasks) |
| US1 (Notif) | 26 | 20–30 h | Parcial (tests/services [P]) |
| US2 (REST) | 5 | 3–5 h | No (depende US1) |
| US3 (Reports) | 35 | 30–40 h | Parcial (generadores [P]) |
| US4 (Estado) | 5 | 4–6 h | No (depende US3) |
| Polish | 7 | 10–15 h | Sí (5 tasks) |
| **TOTAL** | **82** | **100–130 h** | Ambas P1 en paralelo |

**Con ejecución óptima** (US1 y US3 paralelas, máximo paralelismo dentro de fases):
- Setup + Foundational: 6–10 h (serie)
- US1 ║ US3: 30–40 h (paralelo con mínima coordinación)
- US2 + US4: 7–11 h (serie después de sus dependencias)
- Polish: 10–15 h (paralelo a refinement final)
- **Mínimo teórico: ~60–75 h** (equipo de 2, máxima coordinación)

---

## 🔗 Dependencias Internas por Story

### US1 → US2

- **T030–T037** (servicios de notificación) DEBEN estar completos antes de iniciar US2
- T044 (endpoint) reutiliza: `template_resolver`, `opt_out_service`, `rate_limiter`, `canal_sender`, `estado_aggregator`

### US3 → US4

- **T057** (modelo Reporte) + **T058** (MinIO) + **T064** (job_runner) DEBEN estar completos antes de iniciar US4
- T074 (endpoint estado) reutiliza: `estado_reader` (T073)

### Dentro de US3

- **T083** (size_limit_validator) es consumido por **T064** (job_runner) antes de invocar generadores
- **T084** (integration test) valida flujo de T083 + T067

---

## 📋 Checklist Antes de Iniciar Implementación

- [ ] Phase 1–2 completadas y validadas (no hay errores de import/config)
- [ ] Docker-compose funcionando (RabbitMQ + Redis + MinIO accesibles)
- [ ] Linting pasa sin warnings (`ruff check src/`)
- [ ] Todos los tests de Phase 2 pasan
- [ ] Variables de entorno `.env.local` cargadas correctamente
- [ ] Decisión tomada: ¿Equipo ejecuta US1+US3 en paralelo o secuencial?
- [ ] TDD rigor entendido (🟢/🟡/🔴) — cada developer lee "Nivel de rigor TDD" en `tasks.md`

---

## 📚 Referencia Rápida: Estructura del Proyecto Final

```
src/
├── broker/
│   ├── connection.py       # RabbitMQ + DLX (T006–T007)
│   └── schemas/            # DRAFT JSON schemas (T008)
│
├── notificaciones/
│   ├── api/
│   │   ├── app.py         # FastAPI app (T014)
│   │   └── routes.py      # POST /notificaciones/enviar (T044)
│   ├── consumers/
│   │   └── notificacion_consumer.py  # Event consumer (T038)
│   ├── providers/
│   │   ├── push_provider.py    # FCM (T034)
│   │   └── mail_provider.py    # SendGrid (T035)
│   ├── services/
│   │   ├── template_resolver.py       # Idioma + fallback (T030)
│   │   ├── opt_out_service.py         # Cache opt-out (T031)
│   │   ├── rate_limiter.py            # Per-channel (T032)
│   │   ├── dedup_service.py           # Event_id TTL (T033)
│   │   ├── canal_sender.py            # Backoff retry (T036)
│   │   ├── estado_aggregator.py       # Aggregation (T037)
│   │   └── delivery_reporter.py       # Report result (T039)
│   ├── models/
│   │   ├── notificacion.py    # Notificacion + EstadoCanal (T027)
│   │   └── preferencia.py     # Opt-out (T028)
│   └── templates/
│       ├── registry.py         # Template registry (T029)
│       ├── es/                 # Spanish templates
│       └── en/                 # English templates
│
├── reportes/
│   ├── api/
│   │   ├── app.py         # FastAPI app (T014)
│   │   └── routes.py      # GET /reportes/{id}/descarga, estado (T068, T074)
│   ├── consumers/
│   │   └── reporte_consumer.py        # Event consumer (T067)
│   ├── generators/
│   │   ├── registry.py               # Generator registry (T059)
│   │   ├── ventas.py                 # Sales reports (T060)
│   │   ├── actividad_usuario.py      # User activity (T061)
│   │   ├── catalogo_uso.py           # Catalog usage (T062)
│   │   └── recomendaciones.py        # Recommendations (T063)
│   ├── storage/
│   │   └── minio_client.py    # Upload + signed URLs (T058)
│   ├── services/
│   │   ├── job_runner.py              # Timeout + execution (T064)
│   │   ├── retry_service.py           # Transitorio backoff (T065)
│   │   ├── data_fetcher.py            # Pagination (T066)
│   │   ├── size_limit_validator.py    # Size check (T083)
│   │   ├── retention_cleanup.py       # Cleanup (T069)
│   │   └── estado_reader.py           # Read status (T073)
│   └── models/
│       └── reporte.py         # Reporte model (T057)
│
└── shared/
    ├── config.py                  # Environment config (T009)
    ├── logging.py                 # Structured logging (T010)
    ├── api_general_client.py      # HTTP client + auth (T011)
    ├── redis_client.py            # Redis wrapper (T012)
    └── auth.py                    # Auth middleware (T013)

tests/
├── unit/
│   ├── test_template_resolver.py       # T017
│   ├── test_estado_entrega_aggregation.py
│   ├── test_rate_limiter.py
│   ├── test_dedup.py
│   └── [... otros tests 🟢 ...]
├── contract/
│   ├── test_notificacion_enviar_schema.py
│   ├── test_reporte_generar_schema.py
│   └── [... otros contract tests ...]
└── integration/
    ├── test_notificacion_enviar_flow.py
    ├── test_reporte_generar_ready.py
    └── [... otros integration tests ...]
```

---

## 🚀 Primeros Pasos Recomendados

1. **Validar setup:** Correr quickstart.md end-to-end (docker-compose, env variables)
2. **Phase 1–2:** Ejecutar en serie. Validar que todos los imports funcionan
3. **Decision:** ¿US1 y US3 en paralelo o secuencial?
4. **US1 (si paralelo):** Iniciar con tests 🟢 (T015–T020) en paralelo
5. **US3 (si paralelo):** Iniciar con tests 🟢 + generadores [P] en paralelo
6. **Checkpoint US1:** Todos los tests de T015–T026 pasan
7. **Checkpoint US3:** Todos los tests de T046–T056, T051a, T084 pasan
8. **Validate:** Correr linting, Constitution Check (T082 temprano)

---

**Última actualización:** 8 de septiembre de 2026  
**Basado en:** `spec.md`, `plan.md`, `data-model.md`, `tasks.md`, Constitution v1.1.0  
**Para dudas:** Consultar `tasks.md` para descripción completa de cada task
