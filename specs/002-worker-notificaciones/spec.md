# Feature Specification: Worker de Notificaciones (Push/Mail)

**Feature Branch**: `002-worker-notificaciones`

**Created**: 2026-09-10

**Status**: Draft

**Input**: User description: "feature 001: worker. El broker al ser un setup simple, vamos a dejarlo para después, empezamos con el worker primero. Su trabajo es simple, recibe un mensaje del broker con ciertas especificaciones que luego definiremos, y después envía la notificación por el canal que sea indicado (push o mail)."

## Clarifications

### Session 2026-09-10

- Q: Si el broker reentrega el mismo mensaje dos veces (ej. el worker procesó y envió
  pero se cayó antes del ack), ¿qué comportamiento esperás? → A: El worker debe detectar
  duplicados (por `id_mensaje`) y descartar el reenvío sin volver a notificar.
- Q: Si el destinatario no tiene el canal habilitado (sin mail registrado o sin
  suscripción push), ¿quién valida eso? → A: El worker asume que el emisor del mensaje
  ya validó que el destinatario tiene el canal habilitado; el worker solo intenta enviar
  y trata fallos técnicos como fallo del proveedor.
- Q: ¿Qué política de reintentos ante fallo transitorio del proveedor? → B: Delegar el
  reintento al mecanismo nativo de RabbitMQ (requeue con límite de entregas/TTL +
  dead-letter exchange), sin lógica de reintento explícita en el código del worker.
- Q: ¿Qué nivel de detalle del schema del mensaje fijar para esta spec? → B: Fijar un
  esquema mínimo de trabajo (`canal`, `destinatario`, `contenido`, `id_mensaje`) que sirva
  de base para el plan técnico; el contrato final se validará contra el repo puerta de
  entrada.
- Q: US3 describía "reintento" del worker, contradiciendo FR-007 (que delega todo a
  RabbitMQ). → A: Reescribir US3 para reflejar el comportamiento real: el worker hace
  `nack` ante fallo transitorio y deja que RabbitMQ reencole, sin lógica de reintento
  propia.

### Session 2026-09-14

- Q: `id_mensaje` y `destinatario` ¿qué tipo de dato tienen? → Numéricos (no strings).
  `destinatario` es el id numérico del usuario en el sistema, usado solo para
  trazabilidad/logging.
- Q: ¿La notificación lleva un tipo de evento (para alimentar el algoritmo de
  recomendación)? → No. Ese dominio (eventos para el algoritmo) es ajeno a
  notificaciones y no forma parte de este mensaje ni de este repo.
- Q: ¿Cómo obtiene el worker el mail o la subscription push para enviar, sin acceder
  a una BDD ajena (Principio II)? → El mensaje llega con los datos de contacto ya
  resueltos: campo `mail` (si `canal = "mail"`) o campo `push_sub` (si
  `canal = "push"`), provistos por el emisor del mensaje. El worker nunca consulta
  ninguna base de datos para resolverlos.
- Q: ¿`push_sub` es un string simple o una estructura? → Objeto con el formato
  estándar de Web Push Subscription del navegador: `endpoint` (string) + `keys`
  (`p256dh` y `auth`, ambos string).
- Q: ¿`mail` y `push_sub` son mutuamente excluyentes según `canal`, o pueden venir
  ambos siempre? → Son condicionales y estrictos: si `canal = "mail"`, `mail` es
  obligatorio y `push_sub` debe estar ausente; si `canal = "push"`, `push_sub` es
  obligatorio y `mail` debe estar ausente. Un mensaje con el campo "equivocado"
  presente para su canal, o sin el campo requerido, se considera inválido (rechazo,
  ver US2/FR-005).

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Consumir mensaje y enviar notificación por el canal indicado (Priority: P1)

Como sistema, cuando llega un mensaje de notificación ya validado desde el broker,
el worker debe interpretar el canal indicado en el mensaje (push o mail) y disparar el
envío correspondiente sin decidir nada sobre si corresponde notificar o no — esa decisión
ya viene tomada en el mensaje.

**Why this priority**: Es la razón de existir del worker; sin esto no hay funcionalidad
entregable. Es el flujo mínimo que constituye el MVP de esta feature.

**Independent Test**: Se puede probar publicando un mensaje válido (canal = "push" o
"mail") en la cola que consume el worker y verificando que se dispara el envío por el
canal correcto (usando un proveedor real o un mock/stub del proveedor).

**Acceptance Scenarios**:

1. **Given** un mensaje válido con canal `push` y los datos necesarios para armar la
   notificación, **When** el worker lo consume, **Then** se dispara un envío de
   notificación push con el contenido indicado en el mensaje.
2. **Given** un mensaje válido con canal `mail` y los datos necesarios, **When** el
   worker lo consume, **Then** se dispara un envío de mail con el contenido indicado en
   el mensaje.
3. **Given** un mensaje válido que fue procesado exitosamente, **When** el envío se
   confirma, **Then** el mensaje se acusa recibo (ack) en la cola y no se reprocesa.
4. **Given** un mensaje con un `id_mensaje` que ya fue procesado exitosamente
   anteriormente, **When** el worker lo recibe de nuevo (reentrega del broker), **Then**
   el worker descarta el reenvío sin disparar una nueva notificación y hace ack.

---

### User Story 2 - Rechazar o encolar en dead-letter mensajes inválidos (Priority: P2)

Como sistema, cuando llega un mensaje mal formado, incompleto, o con un canal no
soportado, el worker debe rechazarlo (o enviarlo a dead-letter) sin intentar adivinar
valores faltantes ni enviar una notificación parcial o incorrecta.

**Why this priority**: Es crítico para la confiabilidad del sistema y está directamente
mandado por el Principio IV de la Constitution (validación estricta de payloads), pero
depende de que el flujo feliz (US1) ya exista para tener sentido evolutivo.

**Independent Test**: Se puede probar publicando mensajes deliberadamente inválidos
(campo faltante, canal desconocido, tipo de dato incorrecto) y verificando que el worker
no intenta enviar ninguna notificación y que el mensaje termina en dead-letter o es
rechazado de forma visible/loggeada.

**Acceptance Scenarios**:

1. **Given** un mensaje sin el campo de canal, **When** el worker lo recibe, **Then** el
   mensaje se rechaza/envía a dead-letter y no se dispara ningún envío.
2. **Given** un mensaje con un canal no soportado (ni "push" ni "mail"), **When** el
   worker lo recibe, **Then** el mensaje se rechaza/envía a dead-letter.
3. **Given** un mensaje con el contenido de notificación incompleto (ej. falta el
   destinatario), **When** el worker lo recibe, **Then** el mensaje se rechaza/envía a
   dead-letter, sin intentar completar el dato faltante.

---

### User Story 3 - Reencolar mensaje ante fallo transitorio del proveedor de envío (Priority: P3)

Como sistema, cuando el envío de la notificación falla por un problema transitorio del
proveedor (push o mail), el worker debe rechazar el mensaje sin confirmarlo (`nack`),
dejando que sea RabbitMQ quien lo reencole según la configuración nativa de la cola
(límite de entregas, TTL, dead-letter exchange) — el worker no implementa lógica de
reintento propia.

**Why this priority**: Mejora la confiabilidad y reduce notificaciones perdidas por
fallas temporales de terceros, pero el sistema es funcional (aunque menos robusto) sin
esto — puede entregarse en una iteración posterior.

**Independent Test**: Se puede probar simulando una falla transitoria del proveedor (mock
que falla las primeras N veces) y verificando que el mensaje es reencolado por RabbitMQ y
finalmente entregado, o que agota el límite de entregas de la cola y termina en
dead-letter.

**Acceptance Scenarios**:

1. **Given** un mensaje válido cuyo primer intento de envío falla por un error
   transitorio, **When** el worker detecta el fallo, **Then** hace `nack` sin confirmar
   el mensaje, y RabbitMQ lo reencola según la configuración de la cola.
2. **Given** un mensaje reencolado que en un intento posterior se envía exitosamente,
   **When** el envío se confirma, **Then** el worker hace `ack` y el mensaje no se
   vuelve a reencolar.
3. **Given** un mensaje cuyo envío falla repetidamente hasta agotar el límite de
   entregas configurado en la cola, **When** se agota ese límite, **Then** RabbitMQ lo
   envía automáticamente a la dead-letter exchange, de forma trazable.

---

### User Story 4 - Descartar mensajes duplicados (idempotencia) (Priority: P2)

Como sistema, cuando el broker reentrega un mensaje que ya fue procesado exitosamente
(identificado por `id_mensaje`), el worker debe reconocerlo y descartarlo sin volver a
enviar la notificación.

**Why this priority**: Evita notificaciones duplicadas al usuario final, un problema de
confiabilidad tan importante como el rechazo de mensajes inválidos (US2). Depende de que
exista el flujo feliz (US1).

**Independent Test**: Se puede probar publicando el mismo mensaje (mismo `id_mensaje`) dos
veces y verificando que solo se dispara un único envío de notificación.

**Acceptance Scenarios**:

1. **Given** un mensaje con `id_mensaje` ya procesado exitosamente, **When** el worker lo
   recibe nuevamente, **Then** no dispara un nuevo envío y confirma (ack) el mensaje.
2. **Given** un mensaje con `id_mensaje` nuevo (nunca visto), **When** el worker lo
   recibe, **Then** lo procesa normalmente (US1).

---

### Edge Cases

- ¿Qué pasa si el canal indicado es válido pero el proveedor de ese canal está caído por
  completo (no es un fallo transitorio sino una interrupción prolongada)? El worker no
  implementa lógica especial para esto: cada intento fallido se trata como fallo
  transitorio y se apoya en el requeue/dead-letter nativo de RabbitMQ (ver FR-007); si la
  interrupción es prolongada, el mensaje terminará en dead-letter tras agotar el límite
  de entregas configurado en la cola.
- ¿Qué pasa si el mensaje indica un canal soportado pero le faltan campos específicos de
  ese canal (ej. mail sin asunto, push sin título)? Se trata como mensaje inválido (US2)
  y se rechaza/dead-letter.
- El worker NO valida si el destinatario tiene el canal habilitado (ver Clarifications):
  esa responsabilidad es del emisor del mensaje. Si el envío falla porque el destinatario
  no tiene el canal habilitado, el worker lo trata como un fallo del proveedor (fallo
  técnico de envío), no como un mensaje inválido.
- ¿Qué pasa si un mensaje con `canal = "mail"` trae también `push_sub`, o con
  `canal = "push"` trae también `mail`? Se trata como mensaje inválido (FR-013): la
  presencia del campo de contacto "equivocado" para el canal indicado es motivo de
  rechazo, igual que la ausencia del campo requerido.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El worker DEBE consumir mensajes desde una cola del broker de mensajes
  (RabbitMQ) dedicada a eventos de notificación.
- **FR-002**: El worker DEBE validar cada mensaje contra el esquema mínimo de trabajo
  definido en Key Entities (`id_mensaje`, `canal`, `destinatario`, `mail`, `push_sub`,
  `contenido`) antes de procesarlo (Principio III y IV de la Constitution). El
  contrato final y completo se validará contra la documentación externa del repo
  "puerta de entrada" cuando esté disponible.
- **FR-003**: El worker DEBE interpretar el campo `canal` del mensaje y enrutar el envío
  exclusivamente a: notificación push, o notificación por mail, según ese campo.
- **FR-004**: El worker NO DEBE decidir por sí mismo si corresponde notificar o no, ni
  cuándo hacerlo — solo ejecuta lo que el mensaje ya indica.
- **FR-005**: El worker DEBE rechazar o enviar a dead-letter cualquier mensaje inválido
  (campo faltante, tipo incorrecto, canal no soportado) sin intentar completar valores
  faltantes.
- **FR-006**: El worker DEBE confirmar (ack) un mensaje solo después de que el envío por
  el canal correspondiente se haya completado exitosamente, o después de determinar que
  el mensaje es un duplicado ya procesado (FR-011).
- **FR-007**: Ante un fallo transitorio del proveedor de envío, el worker DEBE dejar que
  el mensaje sea reencolado (nack/requeue) y delegar la política de reintentos (límite de
  entregas, TTL, dead-letter) a la configuración nativa de la cola de RabbitMQ; el worker
  NO implementa lógica de reintento propia (backoff, contadores) en su código.
- **FR-008**: El worker DEBE registrar (log) de forma trazable todo mensaje rechazado,
  fallido, duplicado descartado, o enviado a dead-letter, incluyendo el motivo.
- **FR-009**: El worker NO DEBE acceder directamente a ninguna base de datos de otro
  repo del sistema; toda la información necesaria para notificar DEBE venir en el
  payload del mensaje o, si no es posible, vía llamada REST al repo dueño del dato
  (Principio II de la Constitution).
- **FR-010**: El worker NO DEBE ser accesible directamente por ningún frontend; solo
  consume mensajes publicados por el repo "puerta de entrada" del sistema (Principio V).
- **FR-011**: El worker DEBE identificar mensajes duplicados mediante el campo
  `id_mensaje` y descartarlos (sin reenviar la notificación) si ese `id_mensaje` ya fue
  procesado exitosamente anteriormente.
- **FR-012**: El worker NO DEBE validar si el destinatario tiene el canal habilitado
  (ej. mail registrado, push suscripto); asume que el emisor del mensaje ya lo validó. Un
  fallo de envío por esta causa se trata como fallo técnico del proveedor.
- **FR-013**: El worker DEBE validar de forma cruzada `canal` contra los campos de
  contacto: si `canal = "mail"`, el campo `mail` DEBE estar presente y el campo
  `push_sub` DEBE estar ausente; si `canal = "push"`, el campo `push_sub` DEBE estar
  presente y el campo `mail` DEBE estar ausente. Cualquier combinación distinta se
  trata como mensaje inválido (rechazo/dead-letter, ver FR-005).
- **FR-014**: El worker NO DEBE incluir ni depender de ningún campo de "tipo de
  evento" en el mensaje; ese concepto pertenece al dominio del algoritmo de
  recomendación y es explícitamente ajeno a este repo (Principio I).

### Key Entities

- **Mensaje de notificación**: Representa un pedido de envío ya decidido por otro
  componente del sistema. Esquema mínimo de trabajo para esta feature (sujeto a
  confirmación en el contrato externo — ver Principio III de la Constitution):
  - `id_mensaje`: identificador único numérico del mensaje, usado para detectar
    duplicados.
  - `canal`: `"push"` | `"mail"`.
  - `destinatario`: identificador numérico del usuario, usado solo para
    trazabilidad/logging (no es el dato de contacto en sí).
  - `mail`: dirección de correo ya resuelta por el emisor; obligatoria si y solo si
    `canal = "mail"` (FR-013).
  - `push_sub`: Web Push Subscription ya resuelta por el emisor (objeto con
    `endpoint`, `keys.p256dh`, `keys.auth`); obligatoria si y solo si
    `canal = "push"` (FR-013).
  - `contenido`: datos necesarios para armar la notificación (se asume ya resuelto; el
    mecanismo de plantillas queda fuera de esta spec, ver Assumptions).
- **Resultado de envío**: Representa el resultado de intentar entregar una notificación
  por un canal dado: éxito, fallo transitorio (se reencola vía RabbitMQ), o fallo
  definitivo (dead-letter tras agotar el límite de entregas de la cola).
- **Registro de mensajes procesados**: Mecanismo de idempotencia que permite al worker
  saber si un `id_mensaje` ya fue procesado exitosamente, para poder descartar reentregas
  duplicadas (FR-011). Su implementación concreta se define en la fase de planificación.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de los mensajes válidos publicados en la cola resultan en un
  intento de envío por el canal correcto (push o mail, según el mensaje).
- **SC-002**: El 100% de los mensajes inválidos (campo faltante, canal no soportado) son
  rechazados o enviados a dead-letter sin generar ningún envío de notificación.
- **SC-003**: Ante una falla transitoria simulada del proveedor, el mensaje es
  reencolado y reprocesado por RabbitMQ hasta agotar el límite de entregas configurado,
  sin intervención manual.
- **SC-004**: Ningún mensaje se pierde silenciosamente: todo mensaje termina en uno de
  estos cuatro estados trazables — entregado, rechazado/dead-letter, descartado por
  duplicado, o fallido tras agotar el límite de entregas.
- **SC-005**: El 100% de los mensajes con un `id_mensaje` ya procesado exitosamente se
  descartan sin generar un envío duplicado de notificación.

## Assumptions

- El broker (RabbitMQ) ya existe o se asume disponible con una cola de notificaciones
  definida, incluyendo configuración de dead-letter exchange y límite de entregas; el
  setup/infraestructura del broker en sí queda fuera de esta feature (se aborda en una
  feature posterior, según lo indicado por el usuario).
- El esquema mínimo de trabajo (`id_mensaje`, `canal`, `destinatario`, `mail`,
  `push_sub`, `contenido`) es una base para el plan técnico de esta feature; el
  contrato final y completo se validará contra la documentación externa del repo
  "puerta de entrada" cuando esté disponible (Principio III de la Constitution).
- El worker confía en que el emisor del mensaje ya resolvió y validó el dato de
  contacto correspondiente al canal (dirección de mail real, o Web Push Subscription
  real del usuario); el worker no consulta ninguna base de datos para obtenerlos ni
  para validar que el destinatario tenga el canal habilitado (Principio II).
- El campo `destinatario` es el id numérico de usuario, usado exclusivamente para
  trazabilidad/logging — no es el dato usado para efectuar el envío en sí (eso lo
  hacen `mail` o `push_sub`, según corresponda).
- Este mensaje no incluye ni depende de un "tipo de evento": ese concepto pertenece
  al dominio del algoritmo de recomendación, ajeno a este repo (FR-014).
- La política de reintentos ante fallo transitorio se apoya completamente en las
  capacidades nativas de RabbitMQ (requeue, TTL, dead-letter exchange); no hay lógica de
  reintento propia en el código del worker.
- El mecanismo de deduplicación (registro de mensajes procesados) requiere algún tipo de
  almacenamiento de estado por parte del worker (ej. cache o tabla de IDs ya procesados);
  su implementación concreta (in-memory, Redis, DB liviana propia, etc.) se decide en la
  fase de planificación (`/speckit.plan`), respetando que no sea una base de datos de
  dominio ajena (Principio II).
- Los proveedores concretos de envío push y mail (SDK/servicio externo) no están
  definidos en esta spec; se asume que existe o existirá una integración con al menos
  un proveedor de cada canal.
- El mecanismo de plantillas de contenido queda expresamente fuera de esta spec (ver
  Constitution: "Decisión de diseño pendiente: mecanismo de plantillas"); se asume que
  el contenido a enviar llega ya resuelto en el mensaje, o esa decisión se toma en un
  documento de contrato posterior.
- No hay frontend ni usuario final interactuando directamente con este worker; el único
  disparador válido es el mensaje del broker.

