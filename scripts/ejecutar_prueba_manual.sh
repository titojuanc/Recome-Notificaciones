#!/usr/bin/env bash
# Corre una prueba manual end-to-end del worker de notificaciones:
# 1. Verifica que RabbitMQ y Mailpit estén corriendo (los levanta si no).
# 2. Arranca el worker en background (si no está corriendo ya).
# 3. Publica un mensaje de cada tipo (mail, push, inválido, canal no
#    soportado, duplicado).
# 4. Muestra el resultado en el log del worker y en Mailpit.
#
# Uso:
#   ./scripts/ejecutar_prueba_manual.sh
#
# Ver docs/PRUEBAS_MANUALES.md para el detalle de qué se espera en cada caso.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

VENV_PY="$REPO_DIR/.venv/bin/python"
WORKER_LOG="$REPO_DIR/worker.log"
WORKER_PID_FILE="$REPO_DIR/worker.pid"

if [ ! -x "$VENV_PY" ]; then
  echo "No se encontró $VENV_PY. Corré primero:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"
  exit 1
fi

echo "== 1. Verificando infraestructura (RabbitMQ + Mailpit) =="
if ! docker ps --format '{{.Names}}' | grep -q '^recome-rabbitmq$'; then
  echo "RabbitMQ no está corriendo, levantando infraestructura con docker-compose..."
  docker compose -f docker-compose.test.yml up -d
  echo "Esperando a que RabbitMQ esté listo..."
  sleep 8
else
  echo "RabbitMQ ya está corriendo (recome-rabbitmq)."
fi

if ! docker ps --format '{{.Names}}' | grep -q '^recome-mailpit$'; then
  echo "Mailpit no está corriendo, levantando infraestructura con docker-compose..."
  docker compose -f docker-compose.test.yml up -d
  sleep 3
else
  echo "Mailpit ya está corriendo (recome-mailpit)."
fi

echo
echo "== 2. Verificando/arrancando el worker =="
if [ -f "$WORKER_PID_FILE" ] && kill -0 "$(cat "$WORKER_PID_FILE")" 2>/dev/null; then
  echo "El worker ya está corriendo (PID $(cat "$WORKER_PID_FILE"))."
else
  echo "Arrancando el worker en background (log en worker.log)..."
  nohup "$VENV_PY" -m src.consumer.worker > "$WORKER_LOG" 2>&1 < /dev/null &
  echo $! > "$WORKER_PID_FILE"
  disown
  sleep 2
  echo "Worker arrancado (PID $(cat "$WORKER_PID_FILE"))."
fi

echo
echo "== 3. Publicando mensajes de prueba =="

echo "--- mail ---"
"$VENV_PY" scripts/publicar_prueba.py mail
sleep 1

echo
echo "--- mensaje inválido (sin canal) ---"
"$VENV_PY" scripts/publicar_prueba.py invalido
sleep 1

echo
echo "--- canal no soportado ---"
"$VENV_PY" scripts/publicar_prueba.py canal-no-soportado
sleep 1

echo
echo "--- duplicado (mismo id_mensaje publicado dos veces) ---"
"$VENV_PY" scripts/publicar_prueba.py duplicado
sleep 2

echo
echo "--- push (sin VAPID real; falla, se reintenta hasta agotar RABBITMQ_DELIVERY_LIMIT y va a dead-letter) ---"
"$VENV_PY" scripts/publicar_prueba.py push
echo "Esperando a que se agoten los reintentos (x-delivery-limit) y el mensaje pase a dead-letter..."
sleep 6

echo
echo "== 4. Resultado (últimas líneas de worker.log) =="
tail -n 30 "$WORKER_LOG"

echo
echo "== Listo =="
echo "Revisá también:"
echo "  - Mailpit (http://localhost:8025) para ver el mail entregado."
echo "  - RabbitMQ (http://localhost:15672 -> Queues and Streams -> notificaciones.dead-letter)"
echo "    para ver el mensaje push que agotó sus reintentos."
echo "El worker sigue corriendo en background (PID $(cat "$WORKER_PID_FILE")). Para detenerlo:"
echo "  kill \$(cat worker.pid)"

