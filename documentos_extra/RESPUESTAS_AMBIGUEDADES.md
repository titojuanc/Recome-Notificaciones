# Respuestas — Ambigüedades del repo `Recome-Notificaciones`

## Módulo de Notificaciones Push/Mail

- **Canales reales:** solo Push y Mail. SMS e in-app quedan fuera de alcance (in-app se resuelve en el frontend, leyendo historial vía `api-general`).
- **Proveedor de Push:** FCM.
- **Proveedor de Mail:** SendGrid, detrás de una capa de abstracción propia (`MailProvider`).
- **Contenido del mensaje:** el módulo es dueño de los templates, versionados por `tipo_evento` + `idioma`. El publicador del evento manda solo `tipo`, `idioma` (opcional) y variables de reemplazo — nunca texto libre.
- **Preferencias de usuario (opt-out):** viven en DB General (`api-general`). Este módulo las consulta vía REST antes de enviar, con cache de 5 min en Redis.
- **Reintentos y fallos:** backoff exponencial, máximo 5 intentos. Agotados, va a la dead-letter queue y se reporta el fallo a `api-general` vía REST.
- **Idempotencia:** dedup por `event_id` (UUID del payload), guardado en Redis con TTL = ventana de reintento de RabbitMQ.
- **Endpoint REST expuesto:** canal adicional síncrono, no reemplaza al evento. Se usa solo cuando el llamador necesita confirmación inmediata (ej. recuperación de contraseña). El evento asíncrono es el camino por defecto para todo lo demás.
- **Rate limiting / anti-spam:** límite configurable por usuario/canal (default 20/hora), contador en Redis. Si se supera, se descarta y se loguea (no se reintenta).
- **Trazabilidad:** el módulo no duplica el log canónico (vive en Cassandra, propiedad de `api-general`). Reporta estado de entrega (`enviado`/`fallido`/`descartado_rate_limit`) vía REST a `api-general`. Redis guarda solo estado operativo de corto plazo para debugging.

## Módulo de Reportes Exportables

- **Tipos de reporte:** ventas, actividad de usuario, catálogo/uso, recomendaciones generadas. Implementado como registro extensible de generadores por `tipo`.
- **Origen de los datos:** el evento `reporte.generar` trae filtros/IDs, no datos completos. El worker consulta `api-general` vía REST (API key de servicio), paginando si hace falta.
- **Tamaño/tiempo esperado:** timeout default de 5 minutos por job, configurable por tipo. Si se excede: job pasa a `failed` con motivo `timeout`, se publica `reporte.listo` con `estado: "error"`.
- **Expiración de archivos:** retención default 30 días en MinIO, configurable por tipo. Job de limpieza periódico borra lo vencido.
- **Formato de nombre / URL de descarga:** URL firmada de MinIO, generada on-demand, no pública de forma permanente.
- **Autenticación de la descarga vía Nginx:** Nginx no queda expuesto directo al usuario. Flujo: frontend → `api-general` (valida dueño del reporte) → llamada interna a `GET /reportes/{id}/descarga` de este repo → este repo genera signed URL de MinIO con expiración de 15 minutos → `api-general` la redirige/proxea al frontend.
- **Estado del reporte:** estados `pending → processing → ready | failed`. Se publica `reporte.listo` en ambos casos (`ready` y `failed`, este último con `motivo`).

## Infraestructura de RabbitMQ

- **Dead-lettering:** cada cola tiene su propio Dead Letter Exchange. Tras agotar reintentos, el mensaje va a la DLQ y dispara alerta (log estructurado + hook opcional).
- **Durabilidad/persistencia:** todas las colas y exchanges son `durable=true`, mensajes con `delivery_mode=persistent`.
- **Multi-tenancy de colas por entorno:** instancia de broker separada por ambiente (dev/staging/prod), no compartida. Es responsabilidad de este repo.
- **Quién crea las colas:** cada worker las declara de forma idempotente en su propio arranque (sin script de IaC separado).
- **Monitoreo del broker:** obligatorio exponer métricas (colas, consumidores, mensajes en espera, tasa de DLQ) vía plugin de management de RabbitMQ + exporter de Prometheus.

## MinIO / Webserver de Archivos

- **Estructura de buckets:** un único bucket (`recome-reportes`) con prefijo por `tipo/fecha/usuario`.
- **Cuotas de almacenamiento:** sin cuota dura por ahora; la mitigación inicial es la expiración/limpieza de §reportes. Queda como deuda técnica a revisar si el volumen crece.
- **Backups:** best-effort, no crítico — los reportes son regenerables, no son fuente de verdad.

## Transversales

- **SLA de tiempo:** objetivo (no garantía dura) de <30s para notificaciones desde la publicación del evento; para reportes, el timeout de 5 min definido arriba. Se ajusta con métricas reales en producción.
- **Múltiples idiomas / localización:** sí. Se toma de la preferencia de usuario consultada a `api-general`; si el payload trae `idioma` explícito, ese tiene prioridad. Templates soportan mínimo `es` y `en`.
- **Diferencias por ambiente:** en `dev`, mail y push van contra mocks (mail catcher local, push logueado en vez de enviado a FCM real). `staging` y `prod` usan proveedores reales. Configuración por variables de entorno.
- **JSON Schema de `notificacion.enviar`, `reporte.generar`, `reporte.listo`:** mientras no exista el schema formal versionado en `api-general`, este repo trabaja contra un schema borrador (DRAFT) acordado explícitamente con el equipo de `api-general` y referenciado en cada PR de los workers. No se implementa nada contra campos "adivinados".
