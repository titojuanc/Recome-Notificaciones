# Broker RabbitMQ: operación por notificaciones

`notificaciones` **opera el broker** de todo el sistema hasta que se despliegue en
Dokploy (RD-120, `prototipo_recomendaciones`, `data-model.md`; aprobación del
2026-10-06, ratificada el 2026-10-08).

Qué hace y qué NO hace este equipo:

| Lo hace notificaciones | Lo hace cada servicio, al arrancar |
|---|---|
| Crear el **vhost** de cada entorno (uno por entorno, **sin prefijos** en los nombres) | Declarar sus exchanges y colas |
| Crear los **usuarios** y sus **permisos** | Ligar las colas a los exchanges |
| Operar el broker (disponibilidad, acceso de red al puerto 5672) | Reintentos y DLQ propios |

## Aprovisionar un entorno

```bash
RABBIT_VHOST=dev \
RABBITMQCTL="docker exec recome-rabbitmq rabbitmqctl" \
NOTIFICACIONES_PASSWORD=... RECOMENDACIONES_PASSWORD=... API_GENERAL_PASSWORD=... \
./infra/rabbitmq/provision.sh
```

- Es **idempotente**: se puede repetir (también para rotar contraseñas).
- Un usuario sin su `*_PASSWORD` se omite.
- Las contraseñas se pasan por entorno y **no se guardan en el repo**.
- Los usuarios no tienen etiquetas: no acceden al panel de administración.
- `guest` no tiene acceso al vhost creado.

## Usuarios y permisos

| Usuario | configure | write | read |
|---|---|---|---|
| `notificaciones-worker` | `^notificaciones(\..*)?$` | `^notificaciones(\..*)?$` | `^notificaciones(\..*)?$` |
| `recomendaciones-worker` | `^(recomendacion\.actualizar\.v3\|usuario\.eliminado\|recomendaciones\..*)$` | `^(recomendaciones\..*\|amq\.default)$` | igual que configure |
| `api-general` (`main`) | `^$` | `^(recomendacion\.actualizar\.v3\|usuario\.eliminado)$` | `^$` |

Notas:

- `recomendaciones-worker` necesita `amq.default` porque manda reintentos y DLQ por el
  exchange por defecto (RD-120).
- `api-general` en su `main` **solo publica** (`OutboxPublisher`): no declara ni consume.
  Los permisos `reporte.*` y `amq.default` de la tabla original de RD-120 corresponden a su
  rama `notis`, aún sin fusionar. Con `API_GENERAL_INCLUDE_REPORTES=1` el script los agrega.
- El exchange v2 `recomendacion.actualizar` **no se crea** ni se permite: está apagado
  (`RECOMMENDATIONS_OUTBOX_V2_ENABLED=false`) y no tiene consumidor.
- **`Recome-Archivos` no está en la tabla**: su worker consume `reporte.generar` y publica
  `reporte.listo`, pero RD-120 no define su usuario. Pendiente de confirmar (ver abajo).

## Topología propia de notificaciones

Declarada por `src/consumer/worker.py`:

- cola quorum `notificaciones` (TTL 24 h, `x-delivery-limit=5`),
- exchange fanout `notificaciones.dlx` y cola `notificaciones.dead-letter`.

## Verificación

El script se probó contra un RabbitMQ real (dos corridas, para comprobar que es idempotente)
y con una conexión por cada usuario, comprobando lo permitido y lo denegado:

- `notificaciones-worker` declara su topología y no puede crear `usuario.eliminado`.
- `recomendaciones-worker` declara y liga los dos exchanges, usa `amq.default`, y no puede
  crear el exchange v2 ni leer la cola `notificaciones`.
- `api-general` publica en v3 (con `mandatory` y confirmación) y no puede declarar exchanges
  ni publicar en el v2.
- `guest` no accede al vhost.

No prueba la topología desplegada en Dokploy: eso se verifica con la prueba de humo de
`migracion-v3.md` (repo de recomendaciones).

## Orden de activación (RD-120)

1. Aprovisionar el vhost y los usuarios (este documento).
2. Arrancar el **worker de recomendaciones**: declara y liga sus exchanges y colas.
3. Correr la **prueba de humo** de `migracion-v3.md` («Cómo lo verificamos»).
4. Recién entonces `api-general` activa `RECOMMENDATIONS_OUTBOX_ENABLED=true`.

## Pendientes con otros equipos

- Permisos del usuario de `Recome-Archivos` (`reporte.*`).
- Cuál de los dos conjuntos de permisos de `api-general` aplica, y cuándo se fusiona `notis`.
- Evidencia primaria de la aprobación (firmante y canal) para cerrar T006 en `api-general`.
