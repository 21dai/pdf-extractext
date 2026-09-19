#!/usr/bin/env bash
# Ataque de carga con Vegeta (https://github.com/tsenart/vegeta).
#
# Uso:
#   tests/load/vegeta/run.sh <targets.txt> <nombre> [rate] [duration]
#   tests/load/vegeta/run.sh targets/health.txt health 50 30s
#
# Deja en tests/load/vegeta/results/ (ignorado por git):
#   <nombre>.bin   resultados binarios de Vegeta
#   <nombre>.json  reporte para analisis automatico
#   <nombre>.html  grafico interactivo de latencias
set -euo pipefail

TARGETS="${1:?falta el archivo de targets}"
NAME="${2:?falta el nombre del ataque}"
RATE="${3:-50}"
DURATION="${4:-30s}"

RESULTS="$(dirname "$0")/results"
mkdir -p "${RESULTS}"
BIN_OUTPUT="${RESULTS}/${NAME}.bin"
JSON_OUTPUT="${RESULTS}/${NAME}.json"
PLOT_OUTPUT="${RESULTS}/${NAME}.html"

echo "== ${NAME}: rate=${RATE}/s duration=${DURATION} targets=${TARGETS}"

# Ejecutar el ataque, almacenar binario y mostrar reporte en consola
vegeta attack -rate="${RATE}" -duration="${DURATION}" -targets="${TARGETS}" | tee "${BIN_OUTPUT}" | vegeta report

# Generar reporte JSON para analisis automatico
vegeta report -type=json < "${BIN_OUTPUT}" > "${JSON_OUTPUT}"

# Generar grafico interactivo HTML para visualizacion en navegador
vegeta plot < "${BIN_OUTPUT}" > "${PLOT_OUTPUT}"
