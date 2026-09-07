# Recome-Notificaciones Constitution

## Contexto del sistema

Este repositorio (`Recome-Notificaciones`) es **uno de cuatro repos** que componen RecoMe,
un hub de recomendaciones de películas y videojuegos con arquitectura híbrida (núcleo síncrono
REST + workers asíncronos vía RabbitMQ). Los otros tres repos son `api-general` (puerta de
entrada única, dueño de la documentación de contratos compartidos), `recomendaciones` (motor
de recomendación híbrido) y `frontend` (PWAs de usuario/vendedor + Analytics). Ninguna decisión
tomada en este repo puede contradecir los límites de responsabilidad frente a esos otros tres.

## Core Principles

### I. Responsabilidad acotada del repo (NON-NEGOTIABLE)

Este repo es dueño exclusivamente de: la infraestructura de RabbitMQ (broker compartido por
todo el sistema: deploy y definición base de exchanges/colas), el Módulo de Notificaciones
Push/Mail (Python worker + pika), el Módulo de Reportes Exportables (Python worker + pika),
la DB Archivos (MinIO) y el Webserver de Archivos (Nginx). No implementa lógica de negocio de
recomendación, catálogo, usuarios ni autenticación de usuarios finales — eso pertenece a
`api-general` y `recomendaciones`. No es accesible directamente por los frontends: solo
`api-general` puede orquestar hacia este repo.

### II. Cero acceso directo a bases de datos ajenas (NON-NEGOTIABLE)

Ningún componente de este repo lee ni escribe directamente sobre la DB General (PostgreSQL),
DB Logs (Cassandra), ni DB Recomendaciones (PostgreSQL+pgvector) de los otros repos, bajo
ninguna circunstancia, incluso si parece más simple o performante hacerlo. Toda interacción
con datos que no son propios (MinIO/Archivos) se hace vía REST contra el repo dueño, o vía
evento de RabbitMQ. A la inversa, otros repos no acceden directo a MinIO: deben pasar por los
endpoints REST expuestos por los módulos de este repo.

### III. Contratos de eventos y endpoints como fuente externa de verdad

Este repo hostea la infraestructura del broker, pero **no es dueño unilateral** del
schema/contrato de ningún evento de RabbitMQ ni de ningún endpoint REST expuesto o consumido.
Esos contratos (JSON Schema de eventos, specs OpenAPI de endpoints) viven documentados en
`api-general`. Ningún cambio a un contrato compartido (`notificacion.enviar`,
`reporte.generar`, `reporte.listo`, o los endpoints REST de notificaciones/reportes) se
implementa sin antes actualizar esa documentación y avisar a los repos consumidores/
publicadores. Un cambio de contrato NUNCA se considera "interno" a este repo.

### IV. Eventos y endpoints: implementación fiel al contrato documentado

- Consumo de eventos: los workers de este repo (`notificacion.enviar`, `reporte.generar`)
  deben validar el payload recibido contra el JSON Schema documentado en `api-general` antes
  de procesarlo; payloads inválidos se rechazan/deadletter, nunca se "adivinan" campos.
- Publicación de eventos: este repo publica `reporte.listo` (Reportes → Notificaciones)
  siguiendo exactamente el schema documentado, sin campos ad-hoc no acordados.
- Endpoints REST expuestos (envío de notificaciones, estado/descarga de reportes) deben estar
  documentados con OpenAPI y linkeados/documentados desde `api-general` antes de considerarse
  disponibles para otros repos. Cambios breaking requieren versión explícita y coordinación
  previa con los repos consumidores.
- Todas las llamadas REST internas entre repos (entrantes a este repo) se autentican con la
  API key interna de servicio-a-servicio del entorno correspondiente; ningún endpoint interno
  queda expuesto públicamente sin ese control.

### V. Test-First e Integration/Contract Testing (NON-NEGOTIABLE)

TDD obligatorio para lógica de negocio propia (armado de notificaciones, generación de
reportes, manejo de archivos): tests escritos → aprobados → fallando → luego implementación.
Además, son obligatorios:
- **Contract tests** contra los JSON Schema / OpenAPI documentados en `api-general` para cada
  evento consumido/publicado y cada endpoint expuesto, ejecutados en CI antes de cualquier
  deploy, para detectar rupturas de compatibilidad tempranamente.
- **Pruebas de integración** contra RabbitMQ (colas/exchanges reales o equivalentes de test)
  y contra MinIO, cubriendo los flujos completos: evento recibido → notificación enviada /
  reporte generado → archivo persistido → evento de salida (si aplica).
- Ningún PR que modifique el manejo de un evento o endpoint compartido se mergea sin que sus
  contract tests pasen.

#### Rigor de TDD por tipo de tarea

No toda tarea de implementación exige el mismo nivel de rigor TDD. Toda feature de este repo
DEBE clasificar sus tareas de implementación en uno de estos tres niveles antes de comenzar a
codear (documentado explícitamente en el `tasks.md` de la feature):

- **🟢 TDD estricto**: lógica pura/determinística, fácil de aislar sin mocks de
  infraestructura pesada (ej. rate limiting, deduplicación, agregación de estados,
  resolución de reglas condicionales, validación de contratos). Exige ciclo
  red-green-refactor completo: test unitario específico → falla → implementación mínima →
  refactor.
- **🟡 Test-first de integración**: lógica que envuelve un SDK/proveedor externo (clientes de
  terceros, generadores de archivos, storage). Se define primero la interfaz/contrato
  (mock-first) con su test, pero el detalle fino se valida con un test de integración en
  lugar de exigir TDD unitario puro sobre cada línea.
- **🔴 Test-first de contrato/orquestación**: consumers de eventos y endpoints que coordinan
  servicios ya testeados por separado (wiring). Se escribe primero el contract test y/o
  integration test correspondiente, pero no se exige TDD unitario línea a línea sobre la
  orquestación en sí.

En los tres niveles el test se escribe **antes** que el código de implementación — lo que
cambia es la granularidad exigida, nunca si se hace test-first o no. Esta clasificación debe
mantenerse y aplicarse consistentemente en todas las features futuras de este repo, no solo
en la primera donde se definió.

### VI. Simplicidad y aislamiento operativo

Cada módulo (Notificaciones Push/Mail, Reportes Exportables) es desplegable e independiente;
comparten el broker pero no código de negocio entre sí más allá de utilidades comunes
explícitas. Se prefiere la solución más simple que respete los principios I–IV; "por
simplicidad" nunca es justificación válida para romper el aislamiento de datos o contratos.

## Stack tecnológico (no reabrir sin justificación fuerte + coordinación cross-repo)

- **Broker**: RabbitMQ, un exchange/cola por tipo de evento. Deploy y definición base de
  exchanges/colas son responsabilidad de este repo.
- **Módulo de Notificaciones Push/Mail**: Python + pika (consumidor de eventos) y framework
  REST liviano (p. ej. FastAPI) para el endpoint de solicitud de envío.
- **Módulo de Reportes Exportables**: Python + pika (consumidor de eventos), generación de
  PDF/Excel, y framework REST liviano para consulta de estado/descarga.
- **DB Archivos**: MinIO (almacenamiento de objetos para reportes generados).
- **Webserver de Archivos**: Nginx, exponiendo los archivos de MinIO con acceso restringido
  (no acceso anónimo/público a reportes de usuarios).
- Cambios de stack (ej. cambiar de pika, de MinIO, o de motor de reportes) requieren
  justificación técnica documentada y coordinación con los equipos de los otros 3 repos, dado
  que pueden afectar contratos o SLAs compartidos.

## Reglas cross-repo heredadas (recordatorio vinculante)

1. Ningún repo accede directo a la base de datos de otro repo (incluye este repo respecto a
   los demás, y los demás respecto a MinIO de este repo salvo vía REST).
2. `api-general` es la única puerta de entrada para los frontends; este repo nunca es
   accesible directamente desde Frontend Usuario o Frontend Vendedor/Admin.
3. Comunicación asíncrona vía RabbitMQ, un exchange/cola por tipo de evento; contratos vivos
   en `api-general`.
4. Comunicación síncrona vía REST con contratos versionados, documentados en OpenAPI y
   linkeados desde `api-general`.
5. Autenticación servicio-a-servicio con API key interna por entorno para toda llamada REST
   interna.
6. Este repo es responsable exclusivo de sus propias migraciones/esquema (MinIO, config de
   colas); ningún otro repo puede asumir su estructura interna más allá del contrato expuesto.
7. Eventos y convenciones de API nuevos que afecten a otros repos se definen primero en la
   documentación de contratos de `api-general`, antes de implementarse acá.

## Development Workflow

- Todo PR que toque consumo/publicación de eventos o endpoints REST expuestos debe enlazar la
  sección correspondiente de la documentación de contratos en `api-general` y confirmar que
  sigue vigente (o incluir el PR de actualización de esa documentación como prerequisito).
- Se requiere revisión de al menos un miembro del equipo de este repo antes de mergear cambios
  a exchanges/colas de RabbitMQ, dado que afectan a los demás repos consumidores/publicadores.
- CI debe correr: tests unitarios, contract tests contra los schemas/specs de `api-general`, y
  pruebas de integración contra RabbitMQ/MinIO, antes de permitir merge a la rama principal.
- Acceso a reportes/archivos vía Nginx debe validarse en cada cambio de configuración para
  evitar exposición pública no intencional.

## Governance

Esta constitution prevalece sobre cualquier práctica o atajo ad-hoc dentro de este repo. Toda
enmienda debe documentarse explícitamente, indicar impacto sobre los otros 3 repos si lo
hubiera, y ser coordinada con sus equipos cuando afecte contratos compartidos. Ningún PR se
aprueba si introduce una violación a los principios I–IV (acceso directo a datos ajenos,
redefinición unilateral de contratos, exposición no autenticada de endpoints internos, o
acceso directo de frontends a este repo). La complejidad adicional debe justificarse por
escrito en el PR correspondiente.

**Version**: 1.1.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-09-07
