# Tasks: Worker de Notificaciones (Push/Mail)

**Input**: Design documents from `/specs/002-worker-notificaciones/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/,
quickstart.md — todos completos.

**Tests**: Se incluyen tareas de test. La Constitution (Principio VI) exige
Test-First obligatorio para las 4 user stories, con rigor clasificado por tarea
(🟢 TDD estricto / 🟡 test-first de integración / 🔴 test-first de contrato).

**Organization**: Tareas agrupadas por user story para permitir implementación y
validación independiente de cada una.

## Format: `[ID] [P?] [Story] [Rigor] Description`

- **[P]**: Puede ejecutarse en paralelo (archivos distintos, sin dependencias)
- **[Story]**: US1, US2, US3, US4 (según spec.md)
- **[Rigor]**: 🟢 estricto | 🟡 integración | 🔴 contrato/orquestación (Principio VI)

## Path Conventions

Proyecto único (single project), según `plan.md`:
`src/models/`, `src/services/`, `src/consumer/`, `src/config.py`, `tests/unit/`,
`tests/integration/`, `tests/contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización del proyecto Python y estructura base

- [ ] T001 Crear estructura de carpetas `src/{models,services/canales,consumer}` y
      `tests/{unit,integration,contract}` según `plan.md`
- [ ] T002 Inicializar proyecto Python 3.11 con `pyproject.toml`/`requirements.txt`:
      `pika`, `pydantic>=2`, `pytest`, `pytest-mock`
- [ ] T003 [P] Configurar linting/formatting (`ruff` o `flake8` + `black`)
- [ ] T004 [P] Crear `docker-compose.test.yml` con RabbitMQ (`rabbitmq:3-management`)
      para integration/contract tests, según `quickstart.md`
- [ ] T005 [P] Crear `.env.example` con `RABBITMQ_URL`, `RABBITMQ_QUEUE_NOTIFICACIONES`,
      `SQLITE_DEDUP_PATH` y placeholders de credenciales de proveedores

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura central que TODAS las user stories necesitan antes de
poder implementarse

**⚠️ CRITICAL**: Ninguna user story puede comenzar hasta completar esta fase

- [ ] T006 🟢 Crear modelo `MensajeNotificacion` (pydantic, `extra="forbid"`) en
      `src/models/mensaje.py` según `data-model.md` §1 y
      `contracts/mensaje-notificacion.schema.json`
- [ ] T007 [P] 🟢 Crear modelo `ResultadoEnvio` en `src/models/resultado.py` según
      `data-model.md` §2
- [ ] T008 Crear `src/config.py`: carga de variables de entorno (`RABBITMQ_URL`,
      `SQLITE_DEDUP_PATH`, etc.) (depende de T005)
- [ ] T009 Configurar logging estructurado base en `src/logging_config.py` (para
      cumplir FR-008: trazabilidad de mensajes rechazados/fallidos/duplicados)

**Checkpoint**: Fundación lista — las user stories pueden comenzar

---

## Phase 3: User Story 1 - Consumir mensaje y enviar notificación por el canal indicado (Priority: P1) 🎯 MVP

**Goal**: El worker consume un mensaje válido y dispara el envío por el canal
correcto (push o mail), confirmando (ack) al terminar exitosamente.

**Independent Test**: Publicar un mensaje válido (canal `push` o `mail`) en la cola y
verificar que se dispara el envío correcto y se hace `ack`.

### Tests for User Story 1 (escribir primero, deben fallar antes de implementar)

- [ ] T010 [P] [US1] 🟢 Unit test: validación exitosa de `MensajeNotificacion` con
      payload completo, en `tests/unit/test_mensaje_model.py`
- [ ] T011 [P] [US1] 🟢 Unit test: selección de canal (`push`→cliente push,
      `mail`→cliente mail) en `tests/unit/test_enrutamiento.py`
- [ ] T012 [P] [US1] 🟡 Integration test: cliente push envía correctamente (mock del
      SDK/proveedor) en `tests/integration/test_cliente_push.py`
- [ ] T013 [P] [US1] 🟡 Integration test: cliente mail envía correctamente (mock del
      SDK/proveedor) en `tests/integration/test_cliente_mail.py`
- [ ] T014 [US1] 🔴 Contract/integration test: consumer completo (mensaje válido en
      cola real de Docker → envío disparado → `ack`) en
      `tests/contract/test_consumer_flujo_feliz.py`

### Implementation for User Story 1

- [ ] T015 [P] [US1] Implementar `src/services/canales/push.py` (adaptador de envío
      push; interfaz simple `enviar(destinatario, contenido) -> ResultadoEnvio`)
- [ ] T016 [P] [US1] Implementar `src/services/canales/mail.py` (adaptador de envío
      mail; misma interfaz)
- [ ] T017 [US1] Implementar `src/services/enrutador.py`: dado un `MensajeNotificacion`,
      selecciona el cliente de canal correspondiente (depende de T015, T016)
- [ ] T018 [US1] Implementar `src/consumer/worker.py`: conexión `pika`
      `BlockingConnection`, `basic_consume` con `prefetch_count` bajo (configurable),
      callback que parsea+valida el mensaje, invoca `enrutador`, y hace `ack` si el
      envío fue exitoso (depende de T006, T008, T017)
- [ ] T019 [US1] Conectar logging de envíos exitosos en el consumer (depende de T009,
      T018)

**Checkpoint**: User Story 1 funcional y testeable de forma independiente (MVP)

---

## Phase 4: User Story 2 - Rechazar o encolar en dead-letter mensajes inválidos (Priority: P2)

**Goal**: Mensajes mal formados, incompletos o con canal no soportado se rechazan sin
intentar envío ni completar datos faltantes.

**Independent Test**: Publicar mensajes inválidos (campo faltante, canal desconocido,
tipo incorrecto) y verificar que no se dispara ningún envío y el mensaje termina en
dead-letter/rechazo.

### Tests for User Story 2

- [ ] T020 [P] [US2] 🟢 Unit test: `MensajeNotificacion` rechaza payload sin `canal`
      en `tests/unit/test_mensaje_model.py` (mismo archivo que T010, casos adicionales)
- [ ] T021 [P] [US2] 🟢 Unit test: `MensajeNotificacion` rechaza `canal` no soportado
      (ej. `"sms"`) en el mismo archivo
- [ ] T022 [P] [US2] 🟢 Unit test: `MensajeNotificacion` rechaza payload con campo
      extra no declarado (`extra="forbid"`) en el mismo archivo
- [ ] T023 [US2] 🔴 Contract/integration test: mensaje inválido publicado en cola real
      termina en dead-letter sin generar envío, en
      `tests/contract/test_consumer_mensaje_invalido.py` (depende de T014 como base)

### Implementation for User Story 2

- [ ] T024 [US2] Extender `src/consumer/worker.py`: capturar error de validación
      pydantic en el callback y hacer `nack(requeue=False)` (o publish a dead-letter
      exchange según configuración de la cola) (depende de T018)
- [ ] T025 [US2] Agregar logging de mensajes rechazados con motivo (FR-008) en
      `src/consumer/worker.py` (depende de T009, T024)
- [ ] T026 [US2] Documentar/configurar el dead-letter exchange en
      `docker-compose.test.yml` y en `quickstart.md` si falta detalle (depende de T004)

**Checkpoint**: User Stories 1 y 2 funcionan de forma independiente

---

## Phase 5: User Story 4 - Descartar mensajes duplicados (idempotencia) (Priority: P2)

> Nota: se implementa esta historia (US4 en spec.md) antes que US3 porque comparte
> prioridad P2 con US2 y es más simple de aislar que US3 (que depende del
> comportamiento de fallo transitorio). El orden no afecta independencia.

**Goal**: Mensajes con `id_mensaje` ya procesado exitosamente se descartan sin
generar un nuevo envío.

**Independent Test**: Publicar el mismo mensaje (mismo `id_mensaje`) dos veces y
verificar que solo se dispara un único envío.

### Tests for User Story 4

- [ ] T027 [P] [US4] 🟢 Unit test: `RegistroMensajeProcesado.existe()` devuelve
      `False` para un `id_mensaje` nuevo y `True` tras `registrar()`, en
      `tests/unit/test_dedup.py`
- [ ] T028 [US4] 🔴 Contract/integration test: mismo mensaje publicado dos veces en
      cola real genera un único envío, en
      `tests/contract/test_consumer_duplicado.py` (depende de T014)

### Implementation for User Story 4

- [ ] T029 [US4] Implementar `src/services/dedup.py`: `RegistroMensajeProcesado` sobre
      SQLite (tabla `processed_messages`, operaciones `existe`/`registrar`) según
      `data-model.md` §3
- [ ] T030 [US4] Integrar `dedup.py` en `src/consumer/worker.py`: verificar
      `existe(id_mensaje)` antes de enrutar; si existe, `ack` sin enviar; si no,
      procesar y `registrar()` tras envío exitoso (depende de T017, T018, T029)
- [ ] T031 [US4] Agregar logging de mensajes duplicados descartados (FR-008) (depende
      de T009, T030)

**Checkpoint**: User Stories 1, 2 y 4 funcionan de forma independiente

---

## Phase 6: User Story 3 - Reencolar mensaje ante fallo transitorio del proveedor de envío (Priority: P3)

**Goal**: Ante un fallo transitorio del proveedor, el worker hace `nack` sin
confirmar, dejando que RabbitMQ reencole según su configuración nativa (sin lógica de
reintento propia).

**Independent Test**: Simular una falla transitoria del proveedor (mock que falla las
primeras N veces) y verificar que el mensaje es reencolado por RabbitMQ y
eventualmente entregado, o agota el límite de entregas y termina en dead-letter.

### Tests for User Story 3

- [ ] T032 [P] [US3] 🟡 Integration test: cliente push/mail lanza una excepción
      "transitoria" simulada (ej. timeout mockeado) en
      `tests/integration/test_fallo_transitorio.py`
- [ ] T033 [US3] 🔴 Contract/integration test: mensaje reencolado por fallo
      transitorio se entrega en un intento posterior (usando `x-delivery-count` /
      límite de entregas configurado en RabbitMQ) en
      `tests/contract/test_consumer_reencolado.py` (depende de T014)
- [ ] T034 [US3] 🔴 Contract/integration test: mensaje que agota el límite de
      entregas configurado termina en la dead-letter exchange, en el mismo archivo
      que T033

### Implementation for User Story 3

- [ ] T035 [US3] Configurar la cola de notificaciones en `docker-compose.test.yml`
      (o script de setup) con `x-dead-letter-exchange` y límite de entregas
      (`x-delivery-limit` o patrón de conteo vía header), según `research.md` (depende
      de T004)
- [ ] T036 [US3] Extender `src/consumer/worker.py`: capturar excepción de envío del
      proveedor (distinta de error de validación) y hacer
      `nack(requeue=True)` sin lógica de reintento propia (depende de T018, T024)
- [ ] T037 [US3] Agregar logging de fallos transitorios y de mensajes que llegan a
      dead-letter tras agotar el límite de entregas (FR-008) (depende de T009, T036)

**Checkpoint**: Las 4 user stories funcionan de forma independiente y en conjunto

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras que afectan a todas las user stories

- [ ] T038 [P] Ejecutar y validar manualmente `quickstart.md` completo (levantar
      RabbitMQ, correr worker, publicar mensajes de prueba)
- [ ] T039 [P] Revisar cobertura de logging: todo mensaje termina en uno de los 4
      estados trazables de SC-004 (entregado, rechazado/dead-letter, duplicado
      descartado, fallido tras agotar entregas)
- [ ] T040 Configurar CI (GitHub Actions) para correr `tests/unit`,
      `tests/integration`, `tests/contract` (con RabbitMQ vía Docker) en cada PR,
      según Constitution § Development Workflow
- [ ] T041 [P] Documentar en `README.md` del repo cómo correr el worker y los tests

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — puede iniciar de inmediato
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA todas las user stories
- **User Stories (Phase 3-6)**: todas dependen de Foundational
  - US1 (P1) es el MVP y debe completarse primero en la práctica (las demás
    extienden el mismo `consumer/worker.py`)
  - US2, US4 (P2) pueden trabajarse en paralelo entre sí una vez completado US1
  - US3 (P3) depende de que exista el flujo de envío (US1) y el manejo de errores
    de validación (US2, para diferenciar error transitorio de error de payload)
- **Polish (Phase 7)**: depende de que las user stories deseadas estén completas

### Notas de dependencia específicas de este proyecto

A diferencia de un CRUD típico, aquí las 4 user stories **comparten el mismo archivo
central** `src/consumer/worker.py` (es el orquestador/wiring, clasificado 🔴 en la
Constitution). Esto significa que, en la práctica:

- US1 crea `worker.py` desde cero (T018)
- US2, US3, US4 lo **extienden** (T024, T030, T036) en vez de crear archivos nuevos
- Por lo tanto, aunque cada user story es independientemente testeable (cada una
  tiene su propio test de contrato), la implementación de US2/US3/US4 físicamente
  no puede paralelizarse entre sí sin coordinación, porque tocan el mismo archivo

### Within Each User Story

- Tests DEBEN escribirse y fallar antes de implementar (Principio VI)
- Modelos (T006, T007) antes que servicios
- Servicios de canal (T015, T016) antes que el enrutador (T017)
- Enrutador antes que el consumer (T018)
- Historia completa antes de pasar a la siguiente en integración física a
  `worker.py`

### Parallel Opportunities

- T003, T004, T005 (Setup) en paralelo
- T006, T007 (Foundational, modelos) en paralelo
- T010, T011, T012, T013 (tests US1) en paralelo entre sí
- T015, T016 (clientes de canal US1) en paralelo
- T020, T021, T022 (tests US2) en paralelo
- T027 (test US4) puede ir en paralelo con tests de US2
- T032 (test US3) puede ir en paralelo con otros tests de integración

---

## Parallel Example: User Story 1

```bash
# Tests de US1 en paralelo:
Task: "Unit test validación exitosa en tests/unit/test_mensaje_model.py"
Task: "Unit test selección de canal en tests/unit/test_enrutamiento.py"
Task: "Integration test cliente push en tests/integration/test_cliente_push.py"
Task: "Integration test cliente mail en tests/integration/test_cliente_mail.py"

# Clientes de canal en paralelo:
Task: "Implementar src/services/canales/push.py"
Task: "Implementar src/services/canales/mail.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 solamente)

1. Completar Phase 1: Setup
2. Completar Phase 2: Foundational (bloqueante)
3. Completar Phase 3: User Story 1
4. **DETENER y VALIDAR**: probar US1 de forma independiente vía `quickstart.md`
5. Este es el MVP: worker que consume, enruta y envía — sin dedup ni manejo fino de
   errores

### Incremental Delivery

1. Setup + Foundational → fundación lista
2. US1 → validar independientemente → MVP demo-able
3. US2 → validar independientemente (rechazo de inválidos)
4. US4 → validar independientemente (deduplicación)
5. US3 → validar independientemente (reencolado nativo de RabbitMQ)
6. Polish

### Aplicación del rigor TDD por tarea (Principio VI de la Constitution)

- 🟢 **TDD estricto** (T006, T007, T010, T011, T020, T021, T022, T027): ciclo
  red-green-refactor completo, sin mocks de infraestructura pesada.
- 🟡 **Test-first de integración** (T012, T013, T032): interfaz mock-first + test de
  integración contra el cliente del proveedor (real o sandbox).
- 🔴 **Test-first de contrato/orquestación** (T014, T023, T028, T033, T034):
  contract/integration test contra RabbitMQ real antes de extender el wiring en
  `worker.py`.

---

## Notes

- [P] = archivos distintos, sin dependencias entre sí
- [Story] mapea cada tarea a su user story para trazabilidad
- [Rigor] mapea cada tarea de test a su nivel exigido por la Constitution
- Verificar que los tests fallan antes de implementar
- Commitear después de cada tarea o grupo lógico
- US1 es el MVP; US2/US3/US4 son incrementales sobre el mismo `worker.py`
