# Quickstart: Notificaciones Push/Mail y Reportes Exportables

## Prerrequisitos

- Python 3.12
- Docker (para RabbitMQ, Redis y MinIO locales vía `docker-compose` o `testcontainers`)
- Variables de entorno (ver `.env.example`, a crear en la fase de implementación):
  - `RABBITMQ_URL`
  - `REDIS_URL`
  - `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
  - `API_GENERAL_BASE_URL`, `API_GENERAL_INTERNAL_API_KEY`
  - `FCM_CREDENTIALS_PATH` (o mock en `dev`)
  - `SENDGRID_API_KEY` (o mock en `dev`)
  - `ENVIRONMENT=dev|staging|prod` (controla mocks de FCM/SendGrid, FR-023)

## Levantar infraestructura local

1. Levantar RabbitMQ, Redis y MinIO con `docker-compose` (a definir en fase de tasks).
2. Cada worker declara sus propias colas/exchanges/DLQ de forma idempotente al arrancar
   (FR-020) — no requiere script de setup manual de colas.

## Correr el Módulo de Notificaciones

1. Arrancar el consumer de `notificacion.enviar` (valida contra
   `contracts/notificacion.enviar.draft.schema.json`).
2. Arrancar la API FastAPI (endpoint `/notificaciones/enviar` de `contracts/openapi.draft.yaml`).
3. En `dev`, los envíos de push/mail quedan logueados (mock), no llegan a FCM/SendGrid reales.

## Correr el Módulo de Reportes

1. Arrancar el consumer de `reporte.generar` (valida contra
   `contracts/reporte.generar.draft.schema.json`).
2. Arrancar la API FastAPI (`/reportes/{id}/estado`, `/reportes/{id}/descarga`).
3. Verificar que al completarse un job se publica `reporte.listo`
   (`contracts/reporte.listo.draft.schema.json`) y el archivo queda en el bucket
   `recome-reportes` de MinIO bajo `tipo/fecha/usuario`.

## Validación de contratos

Todo cambio a los `.draft.schema.json` o al `openapi.draft.yaml` en `contracts/` debe:
1. Estar acordado explícitamente con el equipo de `api-general`.
2. Referenciarse en el PR correspondiente (Principio III/IV de la constitution).
3. Pasar los contract tests (`tests/contract/`) antes de mergear.

## Pruebas

- `pytest tests/unit` — lógica de rate limiting, templates, generadores, dedup.
- `pytest tests/contract` — validación de payloads contra los schemas DRAFT/OpenAPI.
- `pytest tests/integration` — flujos completos contra RabbitMQ/MinIO reales
  (`testcontainers`) con mocks de `api-general`/FCM/SendGrid.
