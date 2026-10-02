#!/usr/bin/env bash
# Prueba de carga fija del TP con Vegeta (modelo abierto): 50 req/s durante 30 s
# rotando los 4 PDFs de tests/stress/pdfs, con timeout de cliente de 30 s.
# Equivale a vegeta.ps1 para Git Bash o Linux, con los comandos del profesor.
#
# Uso (desde la raiz del repo):
#   tests/stress/vegeta.sh [url] [rate] [duration] [timeout]
#   tests/stress/vegeta.sh http://127.0.0.1/extract 50 30s 30s
set -euo pipefail

URL="${1:-http://127.0.0.1/extract}"
RATE="${2:-50}"
DURATION="${3:-30s}"
TIMEOUT="${4:-30s}"
NAME="vegeta_50rps"

DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS="$DIR/results"
mkdir -p "$RESULTS"
TARGETS="$RESULTS/targets.txt"

# Mismo formato que el test_carga.txt del profesor, con rutas absolutas locales.
: > "$TARGETS"
for pdf in "$DIR"/pdfs/*.pdf; do
  # En Git Bash, vegeta.exe no entiende rutas /d/...: pasarlas a D:/...
  if command -v cygpath > /dev/null; then pdf="$(cygpath -m "$pdf")"; fi
  printf 'POST %s\nContent-Type: application/pdf\n@%s\n\n' "$URL" "$pdf" >> "$TARGETS"
done

echo "== $NAME: $RATE req/s durante $DURATION, timeout $TIMEOUT, $URL"

# Ejecutar el ataque, almacenar binario y mostrar reporte en consola
vegeta attack -rate="$RATE" -duration="$DURATION" -timeout="$TIMEOUT" -targets="$TARGETS" \
  | tee "$RESULTS/$NAME.bin" | vegeta report

# Generar reporte JSON para analisis automatico
vegeta report -type=json "$RESULTS/$NAME.bin" > "$RESULTS/$NAME.json"

# Generar grafico interactivo HTML para visualizacion en navegador
vegeta plot "$RESULTS/$NAME.bin" > "$RESULTS/$NAME.html"

echo
echo "Profesor: 16.65 req/s efectivos, 998/1500 exitosas (66.53 %), 501 timeouts, p50 14.89 s"
echo "grafico: $RESULTS/$NAME.html"
