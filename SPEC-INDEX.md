# 📚 Documentación de Especificación — Notificaciones Push/Mail y Reportes Exportables

Bienvenido al repositorio **Recome-Notificaciones**. Este documento es tu puerta de entrada a la especificación completa y el roadmap de implementación.

---

## 🎯 ¿Por dónde empezar?

### Si eres **nuevo en el proyecto:**
1. Lee [`README.md`](./README.md) para entender qué es Recome-Notificaciones
2. Consulta [`specs/001-notificaciones-reportes/spec.md`](#specmd) para entender qué se va a construir
3. Revisa [`specs/001-notificaciones-reportes/TASKS-SUMMARY.md`](#tasks-summarymd) para una panorámica rápida del roadmap

### Si eres **desarrollador iniciando implementación:**
1. Lee [`specs/001-notificaciones-reportes/TASKS-SUMMARY.md`](#tasks-summarymd) (este documento)
2. Consulta [`specs/001-notificaciones-reportes/tasks.md`](#tasksmd) para ver tu task específica
3. Abre [`specs/001-notificaciones-reportes/plan.md`](#planmd) para referencia técnica
4. Ejecuta [`specs/001-notificaciones-reportes/quickstart.md`](#quickstartmd) para setup local

### Si eres **product owner o stakeholder:**
1. Lee [`specs/001-notificaciones-reportes/spec.md`](#specmd) (Historias de Usuario y criterios de aceptación)
2. Consulta [`specs/001-notificaciones-reportes/TASKS-SUMMARY.md`](#tasks-summarymd) para timelines y checkpoints
3. Revisa [`specs/001-notificaciones-reportes/plan.md`](#planmd) sección "Success Criteria"

---

## 📄 Documentos de Especificación

### **spec.md**
**Archivo:** `specs/001-notificaciones-reportes/spec.md`

Especificación completa del proyecto: 4 historias de usuario (US1–US4), 23 requisitos funcionales, 5 criterios de éxito, 9 casos edge.

**Contiene:**
- ✅ Historias de usuario con escenarios de aceptación
- ✅ Requisitos funcionales detallados (FR-001 a FR-023)
- ✅ Criterios de éxito medibles (SC-001 a SC-005)
- ✅ Casos edge y clarificaciones (2 rondas de Q&A)
- ✅ Suposiciones y limitaciones

**Cuándo leerlo:**
- Antes de cualquier implementación
- Para entender el "por qué" detrás de cada feature
- Como fuente de verdad en discusiones de diseño

---

### **plan.md**
**Archivo:** `specs/001-notificaciones-reportes/plan.md`

Plan técnico y roadmap: stack de tecnología, estructura del proyecto, Constitution check, constraints.

**Contiene:**
- ✅ Stack Python 3.12 con todas las dependencias
- ✅ Estructura de directorios (`src/`, `tests/`)
- ✅ Constitution Check (Principios I–VI, todos ✅)
- ✅ Constraints técnicas (rate limiting, idioma, tamaño)
- ✅ Métricas de éxito (95% notif <30s, 100% reports dentro de timeout)

**Cuándo leerlo:**
- Para entender la arquitectura general
- Cuando necesites consultar versiones de dependencias
- Para validar que el código sigue la estructura definida

---

### **data-model.md**
**Archivo:** `specs/001-notificaciones-reportes/data-model.md`

Modelo de datos: entidades, campos, enumeraciones, relaciones, máquinas de estado.

**Contiene:**
- ✅ Entidad `Notificacion` (con estado por canal + agregado)
- ✅ Entidad `Reporte` (con máquina de estados: pending→processing→ready|failed)
- ✅ Entidad `Preferencia` (opt-out)
- ✅ Registro de templates (tipo_evento + idioma + canal)
- ✅ Registro de generadores (ventas, actividad_usuario, etc.)

**Cuándo leerlo:**
- Al implementar modelos (T027, T057)
- Para entender campos requeridos, tipos, validaciones
- Como referencia al diseñar tests

---

### **research.md**
**Archivo:** `specs/001-notificaciones-reportes/research.md`

Fase 0: decisiones técnicas justificadas antes de la implementación.

**Contiene:**
- ✅ 8 decisiones técnicas con justificación
- ✅ Alternativas consideradas y rechazadas
- ✅ Scope boundaries explícitas

**Cuándo leerlo:**
- Si cuestionas por qué se eligió X tecnología en lugar de Y
- Para entender el contexto histórico de decisiones

---

### **TASKS-SUMMARY.md** ⭐ **EMPEZAR AQUÍ**
**Archivo:** `specs/001-notificaciones-reportes/TASKS-SUMMARY.md`

Resumen ejecutivo de los 82 tasks: phases, dependencies, effort estimates, TDD classification.

**Contiene:**
- ✅ Visión general de 7 phases (Setup → Foundational → 4 User Stories → Polish)
- ✅ Tasks agrupados por phase + description + duración
- ✅ Clasificación TDD (🟢 estricto / 🟡 integración / 🔴 orquestación)
- ✅ Matriz de dependencias
- ✅ Esfuerzo estimado por phase
- ✅ Estrategia de entrega incremental (MVP checkpoints)
- ✅ Estructura final del proyecto

**Cuándo leerlo:**
- **Primero**, si eres desarrollador nuevo
- Para planning del sprint
- Para entender qué puede correr en paralelo
- Para validar que no hay dependencias circulares

---

### **tasks.md**
**Archivo:** `specs/001-notificaciones-reportes/tasks.md`

Decomposición detallada de los 82 tasks con paths exactos de archivo, TDD rigor, y dependencias.

**Contiene:**
- ✅ T001–T082 en orden de ejecución recomendado
- ✅ Cada task con [P] (parallelizable), [Story], 🟢/🟡/🔴 (TDD tier)
- ✅ Descripción detallada incluyendo paths de archivo
- ✅ Sugerencias de cómo escribir tests primero
- ✅ Checkpoints de entrega entre phases

**Cuándo leerlo:**
- Cuando necesitas implementar un task específico
- Para ver exactamente dónde va el archivo/clase
- Para entender qué otros tasks dependen de este

---

### **contracts/** (DRAFT Schemas & OpenAPI)
**Ubicación:** `specs/001-notificaciones-reportes/contracts/`

Especificaciones de contrato: JSON Schema para eventos, OpenAPI para endpoints.

**Archivos:**
- `notificacion.enviar.draft.schema.json` — Validación de evento de notificación
- `reporte.generar.draft.schema.json` — Validación de evento de generación de reporte
- `reporte.listo.draft.schema.json` — Validación de evento de reporte listo (motivo enum: timeout/dependencia/tipo_no_soportado/limite_tamano_excedido)
- `openapi.draft.yaml` — Especificación OpenAPI de 3 endpoints REST

**Cuándo leerlo:**
- Antes de implementar consumidor/proveedor de eventos
- Antes de implementar endpoints FastAPI
- Para validar estructura de payloads

**Nota:** Son DRAFT porque esperan ratificación formal de `api-general`. Consultar spec.md Clarifications para cambios en uso.

---

### **quickstart.md**
**Archivo:** `specs/001-notificaciones-reportes/quickstart.md`

Guía rápida de configuración local: docker-compose, variables de entorno, cómo lanzar módulos.

**Contiene:**
- ✅ Comandos docker-compose (RabbitMQ, Redis, MinIO)
- ✅ Variables de entorno (.env.example)
- ✅ Cómo lanzar notificaciones + reportes módulos
- ✅ Workflow de validación de contratos

**Cuándo leerlo:**
- Antes de T001 (Setup)
- Cuando necesites entender qué servicio externo usar
- Para troubleshooting del ambiente local

---

## 🔗 Relación Entre Documentos

```
spec.md (requisitos, historias, criterios)
    ↓
plan.md (stack, estructura, constraints)
    ↓
data-model.md (entidades, campos, máquinas de estado)
    ↓
contracts/ (JSON Schema, OpenAPI — validación)
    ↓
tasks.md (descomposición detallada)
    ↓
TASKS-SUMMARY.md (panorámica ejecutiva) ← EMPIEZA AQUÍ
    ↓
quickstart.md (setup local)
```

---

## 📊 Resumen de Contenido

| Documento | Tamaño | Audience | Tiempo Lectura |
|---|---|---|---|
| spec.md | 322 líneas | POs, Devs, Tech Leads | 20 min |
| plan.md | 146 líneas | Tech Leads, Architects | 10 min |
| data-model.md | 132 líneas | Backend Devs | 15 min |
| research.md | 8 decisiones | Architects, Decision-makers | 10 min |
| tasks.md | 415 líneas | Devs, Project Managers | 30 min |
| **TASKS-SUMMARY.md** | 511 líneas | **Devs (PRIMERO)**, Planners | **25 min** |
| contracts/ | 4 archivos | Backend Devs | 10 min |
| quickstart.md | Setup guide | Devs | 5 min |
| **TOTAL** | ~1700 líneas | — | ~125 min = ~2 horas |

**Tiempo mínimo recomendado antes de iniciar dev:** 1 hora (spec.md + TASKS-SUMMARY.md + quickstart.md)

---

## 🚀 Roadmap de Implementación (Resumen)

### MVP (Fases 1–5)
- **Setup (T001–T005):** 2–4 horas
- **Foundational (T006–T014):** 4–6 horas [BLOQUEA]
- **US1 Notificaciones (T015–T040):** 20–30 horas [P1]
- **US3 Reportes (T046–T084):** 30–40 horas [P1, parallelizable con US1]

**Total MVP:** 60–80 horas (con ambas stories en paralelo)

### Enhancements (Fases 4, 6)
- **US2 REST síncrono (T041–T045):** 3–5 horas [depende US1]
- **US4 Consulta estado (T071–T075):** 4–6 horas [depende US3]

### Polish (Fase 7)
- **Métricas, docs, seguridad (T076–T082):** 10–15 horas

**Total Proyecto:** 100–130 horas

---

## ✅ Constitution & Principios

Este proyecto se adhiere a **6 Principios** documentados en `.specify/memory/constitution.md`:

1. **Spec-Driven Development:** Especificación completa, unambigua, antes de código
2. **Zero Direct DB Access:** Solo REST a `api-general`, jamás acceso directo a DBs
3. **Contract-First:** Eventos validados con JSON Schema DRAFT, contracts como fuente de verdad
4. **Security by Design:** Auth middleware obligatorio, URLs firmadas MinIO, no secrets en logs
5. **Test-First & TDD:** Todos los tests antes de implementación, con 3-tier rigor (🟢/🟡/🔴)
6. **Integration & Contract Testing:** Contract tests obligatorios, integration tests en testcontainers, cero builtins

**Nuevo en v1.1.0:** TDD rigor classification (🟢/🟡/🔴) es **formal y binding** para TODAS las futuras features

---

## 🤝 Cómo Contribuir

1. **Lee la especificación:** `spec.md` (historias + criterios) + `plan.md` (arquitectura)
2. **Entiende tu task:** Consulta `tasks.md` para tu T0XX específico
3. **Valida dependencias:** Usa matriz en `TASKS-SUMMARY.md` para ver bloqueos
4. **Escribe tests primero:** Aplica TDD rigor según clasificación (🟢/🟡/🔴)
5. **Abre PR:** Referencia spec.md y tasks.md en la descripción del PR
6. **Valida Constitution:** T082 debe pasar antes de mergear

---

## 📞 Preguntas Frecuentes

**P: ¿Por dónde empiezo si soy nuevo?**  
R: Lee `TASKS-SUMMARY.md` (25 min) + `spec.md` (20 min). Luego ejecuta `quickstart.md`.

**P: ¿Cuál es la dependencia crítica?**  
R: Phase 2 (Foundational, T006–T014) bloquea TODO. Complétalo primero.

**P: ¿Puedo trabajar en US1 y US3 al mismo tiempo?**  
R: Sí, son independientes. Ambas dependen solo de Phase 2. Coordina evitando conflictos en `src/shared/`.

**P: ¿Qué es TDD 🟢/🟡/🔴?**  
R: Niveles de rigor TDD. Lee "Clasificación de Rigor TDD" en `TASKS-SUMMARY.md` y sección "Rigor de TDD por tipo de tarea" en `tasks.md`.

**P: ¿Qué pasa si la especificación cambia?**  
R: Actualizar `spec.md` → propagar a `plan.md` → `data-model.md` → `contracts/` → `tasks.md`. Ver `constitution.md` Principio I.

**P: ¿Cómo valido que mi código sigue la especificación?**  
R: T082 (Constitution Check final) cubre Principios I–VI. Además, todos los contract tests en `tests/contract/` validan conformidad con `contracts/`.

---

## 📋 Checklist Pre-Dev

- [ ] Leí `spec.md` y entiendo las 4 historias de usuario
- [ ] Leí `TASKS-SUMMARY.md` y sé qué task es mío
- [ ] Leí `tasks.md` y tengo la descripción detallada
- [ ] Entiendo mi clasificación TDD (🟢/🟡/🔴)
- [ ] He ejecutado `quickstart.md` y puedo levantar docker-compose
- [ ] Mis variables de entorno en `.env.local` están OK
- [ ] Entiendo Constitution v1.1.0 (especialmente Principio V: TDD rigor)
- [ ] Tengo claridad sobre dependencias (¿qué task bloquea el mío?)

---

## 📌 Última Actualización

- **Especificación completa:** 8 de septiembre de 2026
- **Clarificaciones:** 2 rondas resueltas (8 ambigüedades)
- **Constitution:** v1.1.0 con TDD rigor classification
- **Total tasks:** 82
- **Estado:** Listo para implementación

---

**¿Listo para empezar?** → Abre `TASKS-SUMMARY.md` o tu task específico en `tasks.md`.

¡Bienvenido al equipo! 🚀
