# Data Model: Notificaciones Push/Mail y Reportes Exportables

Este repo no es dueño de bases de datos relacionales de negocio (Principio II). Las entidades
descritas abajo viven como estructuras en memoria/Redis (estado operativo de corto plazo) o
como metadatos junto al objeto en MinIO, no como fuente de verdad persistente para otros repos.

## Notificación (solicitud de envío)

Representa un pedido de envío a un usuario. No se persiste como historial canónico (eso vive
en `api-general`/Cassandra vía reporte de estado de entrega, FR-008).

| Campo | Tipo | Descripción |
|---|---|---|
| `event_id` | UUID | Identificador único del evento/solicitud, usado para dedup (FR-005) |
| `tipo_evento` | string | Clave que selecciona el template (FR-002) |
| `usuario_destino` | string (ID) | Identificador del usuario en `api-general` |
| `idioma` | string (opcional) | `es`/`en`; si ausente, se resuelve por preferencia (FR-009); si falta template para el idioma resuelto, hace fallback a `es` (FR-002) |
| `variables` | object | Variables de reemplazo del template, nunca texto libre |
| `canales_solicitados` | string[] | Subconjunto de `["push","mail"]` pedido por el publicador |
| `resultados_por_canal` | object | Mapa `canal → estado_canal`, cada canal se procesa y reintenta **independientemente** (Clarifications, sesión 2026-09-07) |
| `estado_entrega` | enum | Estado agregado del evento, derivado de `resultados_por_canal`: `enviado` \| `parcial` \| `fallido` \| `descartado_rate_limit` (FR-008) |

**Sub-entidad `estado_canal`** (uno por canal en `resultados_por_canal`):

| Campo | Tipo | Descripción |
|---|---|---|
| `canal` | enum | `push` \| `mail` |
| `estado` | enum | `enviado` \| `fallido` \| `descartado_rate_limit` |
| `intentos` | int | Cantidad de intentos realizados (máx. 5, FR-004) |
| `idioma_usado` | string | Idioma efectivamente usado para el template (puede diferir del solicitado si hubo fallback, FR-002) |

**Reglas de agregación de `estado_entrega`** (FR-008):
- `enviado`: todos los canales solicitados en `enviado`.
- `parcial`: al menos un canal `enviado` y al menos un canal en cualquier otro resultado.
- `fallido`: todos los canales solicitados en `fallido`.
- `descartado_rate_limit`: todos los canales solicitados en `descartado_rate_limit`.

**Validaciones**:
- `event_id` obligatorio y único por ventana de dedup (Redis TTL = ventana de reintento).
- `tipo_evento` debe existir en el registro de templates; si no, se rechaza (edge case de la
  spec) sin reintento.
- `variables` deben cumplir el schema DRAFT documentado para ese `tipo_evento`.
- Reintentos con backoff y paso a DLQ (FR-004) se gestionan por canal individual: un canal en
  DLQ no afecta el procesamiento ni el resultado de los demás canales solicitados.
- Rate limiting (FR-007) se controla con un contador independiente por canal (20/hora c/u por
  default), sin cupo compartido entre canales.

## Preferencia de notificación (opt-out)

Dato propiedad de `api-general`, consultado vía REST y cacheado en Redis (TTL 5 min). No se
persiste como fuente de verdad en este repo.

| Campo | Tipo | Descripción |
|---|---|---|
| `usuario_id` | string | Identificador del usuario |
| `tipo_evento` | string | Tipo de notificación al que aplica el opt-out |
| `opt_out` | boolean | Si es `true`, no se envía notificación de ese tipo |

## Reporte

Representa un job de generación de archivo exportable.

| Campo | Tipo | Descripción |
|---|---|---|
| `reporte_id` | UUID | Identificador único del reporte/job |
| `tipo` | enum | `ventas` \| `actividad_usuario` \| `catalogo_uso` \| `recomendaciones` |
| `filtros` | object | Filtros/IDs recibidos en `reporte.generar`, usados para consultar `api-general` |
| `formato` | enum | `pdf` \| `excel` |
| `estado` | enum | `pending` → `processing` → `ready` \| `failed` |
| `motivo` | string (opcional) | Presente solo si `estado == failed` (`timeout`, `dependencia_no_disponible`, `tipo_no_soportado`, `limite_tamano_excedido`) |
| `ubicacion_minio` | string (opcional) | Path/objeto en el bucket `recome-reportes`, presente solo si `estado == ready` |
| `fecha_creacion` | datetime | Timestamp de encolado |
| `fecha_expiracion` | datetime | `fecha_creacion` + retención configurada por `tipo` (default 30 días) |
| `usuario_solicitante` | string (ID) | Dueño del reporte, usado para el prefijo `tipo/fecha/usuario` |

**Transiciones de estado válidas**: `pending → processing`, `processing → ready`,
`processing → failed`. No hay transición desde `ready`/`failed` (estados terminales).

**Validaciones**:
- `tipo` debe existir en el registro de generadores; si no, `estado = failed`,
  `motivo = tipo_no_soportado`, sin reintento.
- El job debe respetar el timeout configurado por `tipo` (default 5 min); al excederse, el
  proceso de generación se cancela activamente (kill), `estado = failed`, `motivo = timeout`,
  de forma **definitiva** — nunca se reintenta automáticamente (FR-012).
- Antes de generar el archivo, se valida el volumen de datos a exportar contra el límite
  máximo configurado por `tipo` (FR-013a); si se excede, `estado = failed`,
  `motivo = limite_tamano_excedido`, de forma **definitiva** — igual que `timeout`, nunca se
  reintenta automáticamente ni se genera un archivo truncado/parcial.
- Fallos **transitorios** (ej. `motivo = dependencia_no_disponible`) SÍ se reintentan
  automáticamente con backoff antes de marcar el job como `failed` (FR-012a). El campo
  `intentos` (ver abajo) cuenta estos reintentos; ni el timeout ni el límite de tamaño
  incrementan `intentos` porque ninguno de los dos es un fallo reintentable.

| Campo adicional | Tipo | Descripción |
|---|---|---|
| `intentos` | int | Cantidad de reintentos automáticos realizados por fallos transitorios (FR-012a); no aplica a `motivo: timeout` ni `motivo: limite_tamano_excedido` |

## Registro de generadores de reporte

Mapeo en código (no en base de datos) `tipo → función/clase generadora`. Permite extender sin
modificar el flujo central (Principio VI).

| Campo | Tipo | Descripción |
|---|---|---|
| `tipo` | string | Clave única del tipo de reporte |
| `generador` | callable | Recibe `filtros`, `usuario_solicitante`, `formato`; devuelve bytes del archivo |
| `timeout_segundos` | int | Override opcional del timeout default (300s) |
| `retencion_dias` | int | Override opcional de la retención default (30 días) |
| `limite_registros` | int | Override opcional del límite máximo de filas/registros exportables por tipo (FR-013a); si se omite, se usa un default global a definir en el plan técnico |

## Registro de templates de notificación

Mapeo en código/archivos `tipo_evento + idioma → template`.

| Campo | Tipo | Descripción |
|---|---|---|
| `tipo_evento` | string | Clave del tipo de notificación |
| `idioma` | string | `es` \| `en` (mínimo soportado) |
| `canal` | enum | `push` \| `mail` |
| `template` | string/path | Plantilla Jinja2 con placeholders de `variables` |

## Relaciones entre entidades

- Un `Reporte` en estado `ready` o `failed` dispara la publicación del evento `reporte.listo`,
  que puede a su vez disparar una `Notificación` (consumida por el Módulo de Notificaciones)
  para avisar al usuario — pero esa notificación es una entidad independiente, generada por el
  publicador de `reporte.listo`, no por el módulo de Reportes directamente.
- Toda `Notificación` depende de una `Preferencia de notificación` (para resolver opt-out) y de
  un `Registro de templates` (para resolver el contenido).
- Todo `Reporte` depende de un `Registro de generadores` (para saber cómo producir el archivo)
  y de datos externos consultados a `api-general` según sus `filtros`.
