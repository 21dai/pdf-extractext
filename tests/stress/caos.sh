#!/usr/bin/env bash
# Prueba de caos del TP: corre el spike de k6 y, a mitad de la prueba, tira
# una replica. Mide cuantos requests fallan y cuanto tarda la replica en volver
# a estar healthy.
#
# Uso (desde la raiz del repo, con el stack del TP levantado):
#   tests/stress/caos.sh [caida|stop] [segundos]
#   tests/stress/caos.sh caida 15  # el proceso muere de golpe (SIGKILL)
#   tests/stress/caos.sh stop 15   # apagado ordenado (SIGTERM), como un deploy
set -euo pipefail

MODO="${1:-caida}"
ESPERA="${2:-15}"
case "$MODO" in caida|stop) ;; *) echo "modo invalido: $MODO (caida|stop)" >&2; exit 2 ;; esac

cd "$(dirname "$0")/../.."
STRESS="$PWD/tests/stress"
# En Git Bash, docker necesita la ruta de Windows para montar el volumen.
if command -v cygpath > /dev/null; then STRESS="$(cygpath -m "$STRESS")"; fi
export MSYS_NO_PATHCONV=1

VICTIMA="$(docker compose ps -q extract | head -1)"
NOMBRE="$(docker inspect -f '{{.Name}}' "$VICTIMA" | tr -d /)"
[ -n "$VICTIMA" ] || { echo "no hay replicas de extract corriendo" >&2; exit 1; }

caos() {
  sleep "$ESPERA"
  echo ">> t=${ESPERA}s: $MODO de $NOMBRE"
  local inicio=$SECONDS
  if [ "$MODO" = caida ]; then
    # docker kill cuenta como apagado manual y Docker no la reiniciaria. Una
    # caida real se simula matando el proceso desde fuera del contenedor:
    # la politica restart: unless-stopped la vuelve a levantar sola.
    local pid
    pid="$(docker inspect -f '{{.State.Pid}}' "$VICTIMA")"
    docker run --rm --pid=host alpine:3.22 kill -9 "$pid"
  else
    docker stop "$VICTIMA" > /dev/null
    echo ">> $NOMBRE termino su apagado en $((SECONDS - inicio)) s"
    docker start "$VICTIMA" > /dev/null
  fi
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$VICTIMA")" = healthy ]; do
    [ $((SECONDS - inicio)) -gt 120 ] && { echo ">> $NOMBRE no volvio en 120 s"; return; }
    sleep 1
  done
  echo ">> $NOMBRE healthy de nuevo a los $((SECONDS - inicio)) s"
}
caos &

docker run --rm --network pdf-extractext-tp_default -v "$STRESS:/scripts:ro" \
  grafana/k6 run -e BASE_URL=http://traefik /scripts/spike.js
wait
