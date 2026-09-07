# Phase 0 Research: Notificaciones Push/Mail y Reportes Exportables

## Decisiones y justificación

### 1. Framework REST: FastAPI
**Decisión**: FastAPI para ambos endpoints (solicitud de envío, estado/descarga de reportes).
**Razón**: Ya fijado en la constitution como stack tecnológico del repo; integra bien
validación de schemas (Pydantic) y es liviano para servicios internos.
**Alternativas consideradas**: Flask (descartado, la constitution ya fija el stack y no hay
justificación fuerte para reabrir la decisión).

### 2. Cliente de RabbitMQ: pika
**Decisión**: `pika` síncrono con reconexión y declaración idempotente de exchanges/colas/DLQ
en el arranque de cada worker.
**Razón**: Fijado en constitution. Cada worker declara sus propias colas (FR-020), sin IaC
separado.
**Alternativas consideradas**: `aio-pika` (async) — descartado por ahora para mantener
consistencia con el stack decidido; se puede reevaluar si el volumen de mensajes lo exige,
con coordinación cross-repo.

### 3. Validación de contratos: JSON Schema DRAFT + jsonschema
**Decisión**: Mientras `api-general` no publique el schema formal versionado, este repo usa un
schema DRAFT acordado explícitamente, versionado en `src/broker/schemas/` y referenciado en
cada PR que lo use (Principio III/IV, FR-022). Se valida con la librería `jsonschema` antes de
procesar cualquier evento, y con Pydantic/OpenAPI para los endpoints REST.
**Razón**: Evita implementar contra campos "adivinados"; deja rastro explícito de qué versión
DRAFT se usó en cada momento.

### 4. Idempotencia y rate limiting: Redis
**Decisión**: Redis para: dedup por `event_id` (TTL = ventana de reintento de RabbitMQ), cache
de preferencias de opt-out (TTL 5 min), contadores de rate limit por usuario/canal (ventana
deslizante de 1 hora), y estado transitorio de jobs de reporte (`pending`/`processing`).
**Razón**: Necesidad de baja latencia y TTLs nativos; evita levantar una base relacional propia
para datos que son, por diseño, efímeros u operativos (no fuente de verdad).
**Alternativas consideradas**: Base relacional propia — descartada porque el estado que se
necesita persistir es de corto plazo y el historial canónico ya vive en `api-general`
(Cassandra), evitando duplicar responsabilidad de "dueño de datos".

### 5. Almacenamiento de archivos: MinIO + signed URLs
**Decisión**: Bucket único `recome-reportes` con prefijo `tipo/fecha/usuario`; signed URLs
on-demand con expiración de 15 minutos, generadas solo ante solicitud autenticada desde
`api-general`. Nginx no se expone directo al usuario final.
**Razón**: Cumple FR-014 y evita exposición pública permanente de reportes de usuarios,
consistente con Principio II (otros repos no acceden directo a MinIO salvo vía REST de este
repo).

### 6. Generación de reportes: registro extensible por tipo
**Decisión**: Cada tipo de reporte (ventas, actividad, catálogo/uso, recomendaciones) se
implementa como un generador independiente registrado por clave `tipo`, que:
1. Recibe filtros/IDs del evento `reporte.generar`.
2. Pagina llamadas REST a `api-general` para traer los datos (nunca hay datos completos en el
   payload del evento, FR-011).
3. Renderiza PDF (`WeasyPrint`/`reportlab`) o Excel (`openpyxl`) según formato solicitado.
**Razón**: Permite agregar nuevos tipos de reporte sin tocar el flujo central del worker
(Principio VI, simplicidad).

### 7. Proveedores de notificación: FCM + SendGrid detrás de abstracciones
**Decisión**: `PushProvider` (implementación FCM vía `firebase-admin`) y `MailProvider`
(implementación SendGrid vía su SDK oficial), ambos con implementación mock intercambiable
por configuración de entorno para `dev` (FR-023).
**Razón**: Aísla el código de negocio (templates, rate limit, dedup) del proveedor concreto,
facilitando tests y futuros cambios de proveedor sin afectar contratos externos.

### 8. Testing de integración: testcontainers
**Decisión**: Usar `testcontainers-python` para levantar RabbitMQ y MinIO reales en CI, y
mocks HTTP (`respx`) para las llamadas salientes a `api-general`, FCM y SendGrid.
**Razón**: Cumple Principio V (integration testing contra RabbitMQ/MinIO reales) sin depender
de infraestructura compartida de otros equipos durante CI.

## Puntos que quedan fuera del alcance de este research (dependen de otro repo)

- El schema JSON formal y versionado de `notificacion.enviar`, `reporte.generar`,
  `reporte.listo`, y las specs OpenAPI de los endpoints consumidos de `api-general` (consulta
  de opt-out, consulta de datos para reportes) — se coordina directamente con el equipo de
  `api-general`; este repo trabaja con DRAFT hasta que se publique la versión formal.
