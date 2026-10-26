#!/usr/bin/env bash
# Provisiona en RabbitMQ el vhost de un entorno y los usuarios con los permisos
# acordados en RD-120 (prototipo_recomendaciones, data-model.md; ratificación
# del 2026-10-08). Es idempotente: se puede correr de nuevo sin romper nada.
#
# notificaciones OPERA el broker, pero NO crea los exchanges/colas de otros
# equipos: solo el vhost, los usuarios y los permisos. Cada servicio declara su
# propia topología al arrancar.
#
# Uso:
#   RABBIT_VHOST=dev \
#   NOTIFICACIONES_PASSWORD=... RECOMENDACIONES_PASSWORD=... API_GENERAL_PASSWORD=... \
#   RECOS_AUTO_PASSWORD=... ARCHIVOS_PASSWORD=... \
#   ./infra/rabbitmq/provision.sh
#
# Variables:
#   RABBIT_VHOST              (obligatoria) vhost del entorno, p. ej. dev / prod.
#   RABBITMQCTL               comando a usar. Default: "rabbitmqctl".
#                             Con Docker: RABBITMQCTL="docker exec recome-rabbitmq rabbitmqctl"
#   *_PASSWORD                contraseña de cada usuario. Si falta, se omite ese usuario.
#   API_GENERAL_INCLUDE_REPORTES   (default 1)
#                             agrega los permisos reporte.* de api-general. El módulo de
#                             reportes ya está en su `main` (26-oct-2026) y sin estos
#                             permisos no puede declarar ni publicar (ACCESS_REFUSED).
#                             Poner 0 solo para un entorno sin reportes.
#
# Las contraseñas NUNCA se guardan en el repositorio: se pasan por entorno.
set -euo pipefail

: "${RABBIT_VHOST:?Definí RABBIT_VHOST (vhost del entorno, sin prefijos en los nombres)}"
# shellcheck disable=SC2206  # se necesita word-splitting a propósito
RMQ=(${RABBITMQCTL:-rabbitmqctl})
VH="$RABBIT_VHOST"

ctl() { "${RMQ[@]}" "$@"; }

crear_vhost() {
  if ctl list_vhosts -q | grep -qx "$VH"; then
    echo "vhost '$VH': ya existe"
  else
    ctl add_vhost "$VH"
    echo "vhost '$VH': creado"
  fi
}

# crear_usuario <usuario> <password> <configure> <write> <read>
crear_usuario() {
  local user="$1" pass="$2" conf="$3" write="$4" read="$5"
  if ctl list_users -q | cut -f1 | grep -qx "$user"; then
    ctl change_password "$user" "$pass" >/dev/null
    echo "usuario '$user': contraseña actualizada"
  else
    ctl add_user "$user" "$pass" >/dev/null
    echo "usuario '$user': creado"
  fi
  # Sin etiquetas: sin acceso al panel de administración.
  ctl set_user_tags "$user" >/dev/null
  ctl set_permissions -p "$VH" "$user" "$conf" "$write" "$read" >/dev/null
  echo "  permisos en '$VH': configure=$conf write=$write read=$read"
}

crear_vhost

# --- Worker de notificaciones (este repo) -------------------------------------
# Declara y consume `notificaciones`, `notificaciones.dlx` y
# `notificaciones.dead-letter` (src/consumer/worker.py). No publica a otros.
if [[ -n "${NOTIFICACIONES_PASSWORD:-}" ]]; then
  crear_usuario notificaciones-worker "$NOTIFICACIONES_PASSWORD" \
    '^notificaciones(\..*)?$' '^notificaciones(\..*)?$' '^notificaciones(\..*)?$'
else
  echo "notificaciones-worker: omitido (falta NOTIFICACIONES_PASSWORD)"
fi

# --- Worker de recomendaciones (RD-120, punto 5) ------------------------------
# Declara recomendacion.actualizar.v3 y usuario.eliminado y sus colas
# (recomendaciones.*). Necesita amq.default para los reintentos y la DLQ.
if [[ -n "${RECOMENDACIONES_PASSWORD:-}" ]]; then
  crear_usuario recomendaciones-worker "$RECOMENDACIONES_PASSWORD" \
    '^(recomendacion\.actualizar\.v3|usuario\.eliminado|recomendaciones\..*)$' \
    '^(recomendaciones\..*|amq\.default)$' \
    '^(recomendacion\.actualizar\.v3|usuario\.eliminado|recomendaciones\..*)$'
else
  echo "recomendaciones-worker: omitido (falta RECOMENDACIONES_PASSWORD)"
fi

# --- api-general (RD-120, ratificación 2026-10-08) ----------------------------
# Eventos de recomendaciones: solo PUBLICA en los dos exchanges.
# Reportes (en su `main` desde el 26-oct-2026): además declara/consume reporte.* y
# publica reporte.generar y notificaciones por el exchange por defecto.
if [[ -n "${API_GENERAL_PASSWORD:-}" ]]; then
  if [[ "${API_GENERAL_INCLUDE_REPORTES:-1}" == "1" ]]; then
    crear_usuario api-general "$API_GENERAL_PASSWORD" \
      '^reporte\.(generar|listo)$' \
      '^(recomendacion\.actualizar\.v3|usuario\.eliminado|amq\.default)$' \
      '^reporte\.(generar|listo)$'
  else
    crear_usuario api-general "$API_GENERAL_PASSWORD" \
      '^$' '^(recomendacion\.actualizar\.v3|usuario\.eliminado)$' '^$'
  fi
else
  echo "api-general: omitido (falta API_GENERAL_PASSWORD)"
fi

# --- Recome-Recos-Auto (cron + worker) -------------------------------------------
# Declara y consume `recos-auto.usuarios` (+ `.dlx` y `.dead-letter`, ver
# src/recos_auto/common/topology.py) y PUBLICA en `notificaciones` por el exchange
# por defecto (amq.default): NO declara ni consume esa cola. Si cambia
# RABBITMQ_USERS_QUEUE, ajustar este patrón.
if [[ -n "${RECOS_AUTO_PASSWORD:-}" ]]; then
  crear_usuario recos-auto "$RECOS_AUTO_PASSWORD" \
    '^recos-auto\.usuarios(\..*)?$' \
    '^(recos-auto\.usuarios(\..*)?|amq\.default)$' \
    '^recos-auto\.usuarios(\..*)?$'
else
  echo "recos-auto: omitido (falta RECOS_AUTO_PASSWORD)"
fi

# --- Recome-Archivos (worker de reportes) ----------------------------------------
# Declara y consume `reporte.generar`, declara `reporte.listo` y publica en ella por
# el exchange por defecto (src/worker/main.py, events/publisher.py).
if [[ -n "${ARCHIVOS_PASSWORD:-}" ]]; then
  crear_usuario archivos-worker "$ARCHIVOS_PASSWORD" \
    '^reporte\.(generar|listo)$' \
    '^amq\.default$' \
    '^reporte\.(generar|listo)$'
else
  echo "archivos-worker: omitido (falta ARCHIVOS_PASSWORD)"
fi

# Un usuario `guest` solo sirve en localhost; no se le da acceso al vhost nuevo.
echo
echo "Estado final de permisos en '$VH':"
ctl list_permissions -p "$VH"
