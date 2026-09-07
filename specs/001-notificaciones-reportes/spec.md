# Feature Specification: Notificaciones Push/Mail y Reportes Exportables

**Feature Branch**: `001-notificaciones-reportes`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "Módulo de Notificaciones Push/Mail y Módulo de Reportes Exportables,
sobre infraestructura RabbitMQ compartida, con almacenamiento de archivos en MinIO expuesto vía
Nginx" — ambigüedades resueltas por el equipo en `RESPUESTAS_AMBIGUEDADES.md`.

## Clarifications

### Session 2026-09-07

- Q: Cuando una notificación se solicita por ambos canales (push + mail) y uno tiene éxito y
  el otro falla, ¿cómo se modela el estado de entrega? → A: Se agrega el estado `parcial`;
  se reintenta **solo el canal que falló** (backoff/DLQ aplican por canal), el canal ya
  exitoso no se reenvía.
- Q: ¿El contador de rate limit (FR-007) es único compartido entre canales o independiente
  por canal? → A: Independiente por canal — push y mail cada uno con su propio contador de
  20/hora por usuario (no se comparte cupo entre canales).
- Q: Al cumplirse el timeout de generación de un reporte (FR-012), ¿qué pasa con el proceso
  de generación en curso? → A: Se cancela activamente (kill) el proceso de generación al
  cumplirse el timeout, liberando recursos de inmediato; no se deja continuar en background.
- Q: ¿Los jobs de reporte se reintentan automáticamente antes de marcarse `failed`? → B:
  Reintento automático con backoff para fallos transitorios (ej.
  `dependencia_no_disponible`), pero NO para `timeout`, que es siempre definitivo (el
  timeout ya implica que se agotó el tiempo disponible, incluyendo el de reintentos).
- Q: Si un `tipo_evento` no tiene template cargado en el idioma solicitado/resuelto (ej. falta
  `en`, solo existe `es`), ¿qué hace el sistema? → A: Fallback automático al idioma default
  del sistema (`es`) cuando falta el template del idioma solicitado; se envía igual, sin
  tratarlo como error, y se loguea que se usó fallback de idioma.
- Q: Si `api-general` responde que el usuario no tiene ninguna preferencia de idioma
  registrada (nunca la configuró), ¿qué idioma se usa? → A: Se usa `es` como idioma default
  del sistema (mismo default que el fallback de template faltante, FR-002).
- Q: ¿Hay un límite máximo de tamaño (filas/páginas) para el archivo de un reporte? → B: Sí,
  se define un límite máximo configurable por tipo de reporte; si los datos a exportar lo
  exceden, el job falla con `motivo: limite_tamano_excedido` (sin truncar el archivo).
- Q: Si se reciben dos eventos `reporte.generar` con `reporte_id` distintos pero filtros
  idénticos (mismo usuario, mismo tipo, mismo rango), ¿se deduplica por contenido? → A: No;
  cada `reporte_id` es completamente independiente y se genera su propio archivo. La única
  deduplicación existente es por `reporte_id` repetido (ver edge case ya definido); no hay
  deduplicación por combinación de filtros/contenido en esta iteración.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recibir una notificación relevante (Push/Mail) (Priority: P1)

Como usuario final de RecoMe, cuando ocurre un evento relevante para mí (ej. mi reporte está
listo, o `api-general`/otro módulo solicita avisarme algo), quiero recibir una notificación por
push y/o mail, en mi idioma preferido, sin duplicados y sin ser spameado.

**Why this priority**: Es la función central del módulo; sin esto no hay valor entregado.

**Independent Test**: Publicar un evento `notificacion.enviar` válido contra el broker y
verificar que el usuario objetivo recibe el push (mock FCM en test) y/o el mail (mock SendGrid)
correspondiente, respetando su preferencia de opt-out y su idioma.

**Acceptance Scenarios**:

1. **Given** un usuario sin opt-out para el tipo de evento, **When** se publica
   `notificacion.enviar` con `tipo`, `idioma` y variables, **Then** el worker consulta la
   preferencia en `api-general`, renderiza el template correspondiente y envía por el/los
   canal(es) indicados.
2. **Given** un usuario con opt-out activo para ese tipo, **When** se publica el mismo evento,
   **Then** el worker no envía la notificación y registra el resultado como no enviado por
   preferencia.
3. **Given** el mismo `event_id` recibido dos veces (redelivery de RabbitMQ), **When** el
   worker lo procesa la segunda vez, **Then** no se envía una notificación duplicada.
4. **Given** el usuario superó el límite de notificaciones por hora en ese canal, **When**
   llega un nuevo evento, **Then** se descarta, se loguea y NO se reintenta.
5. **Given** un fallo transitorio del proveedor (FCM/SendGrid), **When** el envío falla,
   **Then** se reintenta con backoff exponencial hasta 5 intentos antes de ir a la DLQ.

---

### User Story 2 - Solicitar envío inmediato vía REST (ej. recuperación de contraseña) (Priority: P2)

Como servicio interno (ej. `api-general`) que necesita confirmación inmediata de que una
notificación fue disparada (no solo encolada), quiero invocar un endpoint REST síncrono del
módulo de Notificaciones para casos donde la vía asíncrona por evento no es suficiente.

**Why this priority**: Es un canal complementario para casos puntuales críticos de UX
(recuperación de contraseña, confirmaciones inmediatas), pero el camino por defecto es el
evento asíncrono.

**Independent Test**: Invocar el endpoint REST con API key de servicio válida y payload
correcto; verificar respuesta síncrona de éxito/fallo y que la notificación se dispara con la
misma lógica de templates/preferencias/rate-limit que la vía asíncrona.

**Acceptance Scenarios**:

1. **Given** una llamada autenticada con API key interna válida, **When** se solicita el envío
   inmediato, **Then** el módulo responde de forma síncrona con el resultado del intento de
   envío.
2. **Given** una llamada sin API key o con API key inválida, **When** se invoca el endpoint,
   **Then** se rechaza con error de autenticación y no se procesa el envío.

---

### User Story 3 - Generar un reporte exportable y descargarlo (Priority: P1)

Como usuario (vendedor/admin) que solicita un reporte (ventas, actividad, catálogo/uso o
recomendaciones generadas), quiero que el sistema lo genere en PDF/Excel de forma asíncrona,
me avise cuando esté listo, y pueda descargarlo de forma segura sin exponer los archivos
públicamente.

**Why this priority**: Es la segunda función central del módulo, con impacto directo en
usuarios de negocio (vendedor/admin).

**Independent Test**: Publicar `reporte.generar` con `tipo` y filtros, verificar que el worker
consulta los datos vía REST a `api-general`, genera el archivo, lo sube a MinIO, publica
`reporte.listo` con estado `ready`, y que la descarga solo es posible a través del flujo
autenticado vía `api-general`.

**Acceptance Scenarios**:

1. **Given** un evento `reporte.generar` válido con `tipo` soportado y filtros, **When** el
   worker lo procesa dentro del timeout configurado, **Then** genera el archivo, lo persiste
   en MinIO bajo el prefijo `tipo/fecha/usuario`, y publica `reporte.listo` con `estado: ready`
   y la referencia al reporte.
2. **Given** un job que excede el timeout configurado para su tipo, **When** se cumple el
   límite de tiempo, **Then** el job pasa a `failed` con `motivo: timeout` y se publica
   `reporte.listo` con `estado: error`.
3. **Given** un reporte en estado `ready`, **When** `api-general` solicita la descarga en
   nombre del usuario dueño, **Then** este módulo valida la solicitud (API key de servicio) y
   devuelve una signed URL de MinIO con expiración de 15 minutos.
4. **Given** un usuario que NO es el dueño del reporte intenta descargarlo, **When** llega la
   solicitud a `api-general`, **Then** `api-general` la rechaza antes de siquiera consultar a
   este módulo (control de propiedad fuera de este repo, pero el contrato debe soportarlo).
5. **Given** un reporte con más de 30 días de antigüedad (o el período configurado para su
   tipo), **When** corre el job de limpieza periódico, **Then** el archivo se borra de MinIO.

---

### User Story 4 - Consultar el estado de un reporte (Priority: P2)

Como usuario que pidió un reporte, quiero poder consultar en qué estado está (`pending`,
`processing`, `ready`, `failed`) antes de que esté listo, sin tener que esperar la
notificación.

**Why this priority**: Mejora de UX sobre la funcionalidad ya cubierta por P1 (User Story 3);
no bloquea el valor central pero se espera junto con el mismo release.

**Independent Test**: Consultar el endpoint de estado para un `reporte_id` en cada una de sus
fases y verificar que el estado devuelto coincide con la fase real del job.

**Acceptance Scenarios**:

1. **Given** un reporte recién encolado, **When** se consulta su estado, **Then** se devuelve
   `pending`.
2. **Given** un reporte en generación, **When** se consulta su estado, **Then** se devuelve
   `processing`.
3. **Given** un reporte terminado con éxito o con error, **When** se consulta su estado,
   **Then** se devuelve `ready` o `failed` (con `motivo` si aplica), de forma consistente con
   lo publicado en `reporte.listo`.

---

### Edge Cases

- ¿Qué pasa si `api-general` no responde (timeout/caído) cuando el módulo de Notificaciones
  necesita consultar preferencias de opt-out? → Se trata como fallo transitorio: reintento con
  backoff igual que un fallo de proveedor; si se agotan los intentos, va a DLQ.
- ¿Qué pasa si `api-general` no responde cuando el Módulo de Reportes necesita traer los datos
  a exportar? → Se trata como fallo transitorio (FR-012a): se reintenta con backoff antes de
  marcar el job; si se agotan los reintentos, el job pasa a `failed` con
  `motivo: dependencia_no_disponible`, y se publica `reporte.listo` con `estado: error`.
- ¿Qué pasa si el mismo `reporte_id` recibe dos eventos `reporte.generar`? → Debe tratarse con
  la misma lógica de idempotencia por `event_id` que las notificaciones, para evitar generación
  duplicada. Nótese que esto es distinto de recibir dos `reporte_id` diferentes con filtros
  idénticos: en ese caso NO hay deduplicación por contenido/filtros — cada `reporte_id` genera
  su propio archivo de forma independiente (Clarifications, sesión 2026-09-07).
- ¿Qué pasa si el tipo de reporte o el tipo de notificación solicitado no existe en el
  registro de generadores/templates? → Se rechaza el evento/solicitud sin reintentos, se loguea
  y (para notificaciones) se reporta como no enviado por tipo inválido; (para reportes) se
  publica `reporte.listo` con `estado: error`, `motivo: tipo_no_soportado`.
- ¿Qué pasa si el broker de RabbitMQ está caído al momento de publicar `reporte.listo` o al
  reportar estado a `api-general`? → Debe reintentarse con backoff antes de darlo por perdido;
  este comportamiento se detalla en el plan técnico, no en esta spec.

## Requirements *(mandatory)*

### Functional Requirements — Notificaciones Push/Mail

- **FR-001**: El sistema DEBE soportar únicamente los canales Push (vía FCM) y Mail (vía
  SendGrid, detrás de una abstracción `MailProvider`). SMS e in-app quedan fuera de alcance.
- **FR-002**: El sistema DEBE ser dueño de los templates de notificación, versionados por
  `tipo_evento` + `idioma` (mínimo `es` y `en`). El publicador del evento NUNCA envía texto
  libre, solo `tipo`, `idioma` (opcional) y variables de reemplazo. Si el `tipo_evento` no
  tiene template cargado para el idioma resuelto (FR-009), el sistema DEBE hacer fallback
  automático al template en `es` (idioma default del sistema) y registrar en el log que se
  usó fallback de idioma, sin tratarlo como error ni bloquear el envío.
- **FR-003**: El sistema DEBE consultar la preferencia de opt-out del usuario en `api-general`
  vía REST antes de enviar, cacheando el resultado por 5 minutos.
- **FR-004**: El sistema DEBE reintentar envíos fallidos por causas transitorias con backoff
  exponencial, hasta un máximo de 5 intentos, antes de enviar el mensaje a la dead-letter
  queue correspondiente. El reintento se aplica **por canal individual**: si una notificación
  se solicitó por push y mail y solo uno de los dos falla, únicamente el canal fallido
  reintenta/agota su DLQ; el canal exitoso no se reenvía.
- **FR-005**: El sistema DEBE garantizar idempotencia de envío usando `event_id` (UUID del
  payload) como clave de deduplicación, con TTL igual a la ventana de reintento de RabbitMQ.
- **FR-006**: El sistema DEBE exponer un endpoint REST síncrono adicional para solicitudes que
  requieren confirmación inmediata de envío, autenticado con API key interna de servicio.
- **FR-007**: El sistema DEBE aplicar rate limiting configurable por usuario y canal, con
  contador **independiente por canal** (default 20/hora por canal; ej. hasta 20 push/hora Y
  hasta 20 mail/hora para el mismo usuario, sin cupo compartido entre canales); al superarse
  el límite de un canal, el envío por ese canal se descarta y se loguea, sin reintento (los
  demás canales solicitados no se ven afectados).
- **FR-008**: El sistema DEBE reportar a `api-general` vía REST el estado de entrega de cada
  notificación, evaluado a nivel de evento como agregación de sus canales, donde cada canal
  solicitado resuelve independientemente en `enviado` / `fallido` (agotó reintentos) /
  `descartado_rate_limit`, y el estado agregado del evento es:
  - `enviado`: todos los canales solicitados resultaron `enviado`.
  - `parcial`: al menos un canal `enviado` y al menos un canal en cualquier otro resultado
    (`fallido` o `descartado_rate_limit`).
  - `fallido`: todos los canales solicitados resultaron `fallido`.
  - `descartado_rate_limit`: todos los canales solicitados resultaron `descartado_rate_limit`.
  Sin duplicar el log canónico de eventos (que vive en Cassandra, propiedad de `api-general`).
- **FR-009**: El sistema DEBE resolver el idioma de la notificación priorizando el `idioma`
  explícito del payload por sobre la preferencia consultada a `api-general`; si ninguno de
  los dos está disponible (el payload no trae `idioma` y `api-general` no tiene preferencia
  registrada para el usuario), el sistema DEBE usar `es` como idioma default del sistema
  (mismo default usado en el fallback de template faltante, FR-002).

### Functional Requirements — Reportes Exportables

- **FR-010**: El sistema DEBE soportar, como mínimo, reportes de tipo: ventas, actividad de
  usuario, catálogo/uso y recomendaciones generadas, implementados como un registro extensible
  de generadores por `tipo`.
- **FR-011**: El sistema DEBE obtener los datos a exportar consultando a `api-general` vía REST
  (con API key de servicio, paginando si es necesario) a partir de los filtros/IDs recibidos en
  el evento `reporte.generar`; el evento NUNCA trae los datos completos embebidos.
- **FR-012**: El sistema DEBE aplicar un timeout configurable por tipo de reporte (default 5
  minutos); al excederse, DEBE cancelar activamente el proceso de generación en curso
  (liberando sus recursos de inmediato, sin dejarlo continuar en background), el job pasa a
  `failed` con `motivo: timeout` de forma **definitiva** (sin reintento automático), y se
  publica `reporte.listo` con `estado: error`.
- **FR-012a**: El sistema DEBE reintentar automáticamente, con backoff, los fallos
  **transitorios** de generación de reporte (ej. `motivo: dependencia_no_disponible`) antes
  de marcar el job como `failed`. El timeout (FR-012) no es un fallo transitorio y por lo
  tanto nunca se reintenta automáticamente; requiere que el solicitante encole un nuevo
  evento `reporte.generar` si desea reintentarlo.
- **FR-013**: El sistema DEBE aplicar una política de retención configurable por tipo (default
  30 días) sobre los archivos en MinIO, con un job de limpieza periódico que borre lo vencido.
- **FR-013a**: El sistema DEBE aplicar un límite máximo configurable por tipo de reporte sobre
  el volumen de datos exportables (ej. cantidad de filas/registros). Si los datos a exportar,
  según los filtros recibidos, exceden ese límite, el job DEBE fallar de forma **definitiva**
  (sin reintento automático, igual que `timeout`) con `motivo: limite_tamano_excedido`, sin
  truncar ni generar un archivo parcial.
- **FR-014**: El sistema DEBE generar URLs de descarga firmadas de MinIO, on-demand, sin exponer
  URLs públicas permanentes. Nginx no debe quedar expuesto directamente al usuario final; la
  descarga se sirve exclusivamente a través de: frontend → `api-general` (valida propiedad del
  reporte) → llamada interna autenticada a este módulo → signed URL con expiración de 15
  minutos, devuelta/proxeada por `api-general`.
- **FR-015**: El sistema DEBE modelar el estado del reporte como
  `pending → processing → ready | failed`, exponiéndolo vía endpoint REST de consulta y
  publicando `reporte.listo` en ambos casos terminales (`ready` y `failed`, este último con
  `motivo`).
- **FR-016**: El sistema DEBE almacenar los reportes en un único bucket de MinIO
  (`recome-reportes`), organizados con prefijo `tipo/fecha/usuario`.

### Functional Requirements — Infraestructura RabbitMQ

- **FR-017**: El sistema DEBE declarar todas sus colas y exchanges como `durable=true`, con
  mensajes publicados en `delivery_mode=persistent`.
- **FR-018**: El sistema DEBE definir un Dead Letter Exchange por cada cola; al agotar los
  reintentos de un mensaje, éste DEBE moverse a su DLQ correspondiente y disparar una alerta
  (log estructurado + hook opcional).
- **FR-019**: El sistema DEBE ejecutarse contra una instancia de broker separada por ambiente
  (dev/staging/prod), sin compartir colas entre ambientes.
- **FR-020**: Cada worker DEBE declarar sus propias colas/exchanges de forma idempotente en su
  arranque, sin depender de un script de infraestructura (IaC) separado para el provisioning
  base.
- **FR-021**: El sistema DEBE exponer métricas del broker (colas, consumidores, mensajes en
  espera, tasa de mensajes en DLQ) vía el plugin de management de RabbitMQ y un exporter
  compatible con Prometheus.

### Functional Requirements — Contratos compartidos y ambientes

- **FR-022**: El sistema DEBE validar todo payload de evento (`notificacion.enviar`,
  `reporte.generar`) y todo payload de request REST contra el JSON Schema / spec OpenAPI
  vigente antes de procesarlo; en ausencia de un schema formal versionado en `api-general`, DEBE
  trabajar contra un schema borrador (DRAFT) acordado explícitamente y referenciado en cada PR,
  nunca contra campos asumidos sin acuerdo.
- **FR-023**: El sistema DEBE operar en modo mock para Push y Mail en el ambiente `dev` (mail
  catcher local, push logueado en vez de enviado a FCM real), y contra proveedores reales en
  `staging` y `prod`, controlado por configuración de variables de entorno.

### Key Entities *(include if feature involves data)*

- **Notificación (solicitud de envío)**: representa un pedido de envío a un usuario; atributos
  clave: `event_id`, `tipo_evento`, `usuario_destino`, `idioma`, `variables`, `canal(es)`
  resultantes, y `estado de entrega` agregado (`enviado`/`parcial`/`fallido`/
  `descartado_rate_limit`). El reintento y el paso a DLQ se gestionan por canal individual
  (push y mail son independientes entre sí). No persiste historial canónico (eso vive en
  `api-general`); mantiene solo estado operativo de corto plazo.
- **Preferencia de notificación (opt-out)**: dato propiedad de `api-general`, consumido vía
  REST y cacheado brevemente por este módulo; no se persiste como fuente de verdad acá.
- **Reporte**: representa un job de generación de archivo exportable; atributos clave:
  `reporte_id`, `tipo`, `filtros`, `estado` (`pending/processing/ready/failed`), `motivo` (si
  falla), `ubicación en MinIO`, `fecha de expiración`.
- **Registro de generadores de reporte**: mapeo extensible `tipo → lógica de generación`,
  permite agregar nuevos tipos de reporte sin modificar el flujo central.
- **Registro de templates de notificación**: mapeo `tipo_evento + idioma → template`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 95% de las notificaciones válidas (sin opt-out, sin rate-limit excedido) se
  envían dentro de los 30 segundos posteriores a la publicación del evento (objetivo, no SLA
  duro).
- **SC-002**: El 100% de los reportes procesados dentro del timeout configurado quedan en
  estado `ready` con archivo descargable; el resto queda en `failed` con `motivo` explícito,
  sin jobs que queden colgados indefinidamente en `processing`.
- **SC-003**: Cero notificaciones duplicadas enviadas ante redelivery del mismo `event_id`,
  verificable en pruebas de integración con reenvío forzado de mensajes.
- **SC-004**: Cero accesos exitosos a un reporte vía URL no firmada o expirada, verificable en
  pruebas de seguridad sobre el flujo de descarga.
- **SC-005**: 100% de los mensajes que agotan sus reintentos terminan en su DLQ correspondiente
  y generan una alerta visible (log estructurado), sin pérdida silenciosa de mensajes.

## Assumptions

- El JSON Schema formal de `notificacion.enviar`, `reporte.generar` y `reporte.listo` en
  `api-general` aún no existe al momento de esta spec; se trabaja con un schema DRAFT acordado
  explícitamente con ese equipo y referenciado en cada PR (ver FR-022). Esto se resuelve fuera
  de este repo y no bloquea el resto de la spec.
- La validación de que el usuario que solicita la descarga de un reporte es su dueño ocurre en
  `api-general`, antes de llegar a este módulo (este módulo confía en la autenticación
  servicio-a-servicio, no reimplementa esa autorización de usuario final).
- No hay cuota dura de almacenamiento en MinIO por usuario/tenant en esta iteración; se
  mitiga solo con la política de retención/expiración (FR-013), y queda registrado como deuda
  técnica a revisar si el volumen de reportes crece significativamente.
- Los backups de MinIO son best-effort (no críticos), dado que los reportes son regenerables a
  partir de los datos de `api-general` y no son fuente de verdad del sistema.
- Los reportes son regenerables porque los datos de origen siempre están disponibles vía REST
  en `api-general`; no se asume que el reporte en sí deba sobrevivir a una pérdida de MinIO.
- Este módulo depende de que `api-general` exponga los endpoints REST necesarios (consulta de
  opt-out, consulta de datos paginados para reportes) con autenticación servicio-a-servicio
  ya operativa; su ausencia bloquea US1 y US3 respectivamente, pero es responsabilidad de
  coordinación cross-repo, no de esta spec.
