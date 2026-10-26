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
RECOS_AUTO_PASSWORD=... ARCHIVOS_PASSWORD=... \
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
| `recos-auto` | `^recos-auto\.usuarios(\..*)?$` | `^(recos-auto\.usuarios(\..*)?\|amq\.default)$` | `^recos-auto\.usuarios(\..*)?$` |
| `archivos-worker` | `^reporte\.(generar\|listo)$` | `^amq\.default$` | `^reporte\.(generar\|listo)$` |

Notas:

- `recomendaciones-worker` necesita `amq.default` porque manda reintentos y DLQ por el
  exchange por defecto (RD-120).
- `api-general` publica los eventos de recomendaciones (`OutboxPublisher`) y, desde que fusionó
  el módulo de reportes a su `main` (26-oct-2026), también declara/consume `reporte.*` y publica
  `reporte.generar` y `notificaciones` por `amq.default`. El script le da esos permisos **por
  defecto** (`API_GENERAL_INCLUDE_REPORTES=1`); con `=0` queda solo con los de eventos.
- El exchange v2 `recomendacion.actualizar` **no se crea** ni se permite: está apagado
  (`RECOMMENDATIONS_OUTBOX_V2_ENABLED=false`) y no tiene consumidor.
- `recos-auto` y `archivos-worker` **no estaban en la tabla original de RD-120**; los definió
  notificaciones según lo que hace cada servicio en el broker (ver el script). Ambos publican
  por `amq.default`, que permite publicar en **cualquier** cola por nombre: los permisos de
  *write* no pueden restringirlo a `notificaciones` o `reporte.listo`. Es una limitación de
  RabbitMQ con el exchange por defecto, no del script.
- `Recome-Recos-Auto` solo **publica** en `notificaciones`: no la declara ni la lee.
- Sin los permisos de `reporte.*`, `api-general` no puede declarar ni publicar reportes
  (`ACCESS_REFUSED`): no usar `API_GENERAL_INCLUDE_REPORTES=0` en un entorno con reportes.

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
- `recos-auto` declara su topología con `declarar_topologia` de Recos-Auto, hace el *passive declare* del worker, consume y publica en `notificaciones` con `mandatory` y confirmación; no puede declarar ni leer `notificaciones` ni colas ajenas.
- `archivos-worker` declara/consume/publica `reporte.*`; no puede declarar ni leer `notificaciones`.
- `api-general` (con reportes) declara `reporte.*` y publica en `notificaciones`; no puede declararla ni leerla.

No prueba la topología desplegada en Dokploy: eso se verifica con la prueba de humo de
`migracion-v3.md` (repo de recomendaciones).

## Orden de activación (RD-120)

1. Aprovisionar el vhost y los usuarios (este documento).
2. Arrancar el **worker de recomendaciones**: declara y liga sus exchanges y colas.
3. Correr la **prueba de humo** de `migracion-v3.md` («Cómo lo verificamos»).
4. Recién entonces `api-general` activa `RECOMMENDATIONS_OUTBOX_ENABLED=true`.

## Pendientes con otros equipos

- Que los equipos de `Recome-Archivos` y `Recome-Recos-Auto` confirmen que usan los usuarios `archivos-worker` y `recos-auto` (hoy no sabemos con qué usuario se conectan en Dokploy).
- Que api-general nos pase el host/vhost/usuario con los que configurará `SPRING_RABBITMQ_*` (hoy su compose de Dokploy no configura RabbitMQ).
- Evidencia primaria de la aprobación (firmante y canal) para cerrar T006 en `api-general`.
