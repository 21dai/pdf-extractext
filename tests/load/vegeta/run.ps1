# Ataque de carga con Vegeta (https://github.com/tsenart/vegeta), version PowerShell.
# Equivale a run.sh: mismo flujo attack -> report -> report -type=json -> plot.
#
# Uso:
#   .\tests\load\vegeta\run.ps1 <targets.txt> <nombre> [rate] [duration]
#   .\tests\load\vegeta\run.ps1 tests\load\vegeta\results\targets\health.txt health 50 30s
#
# Deja en tests/load/vegeta/results/ (ignorado por git):
#   <nombre>.bin   resultados binarios de Vegeta
#   <nombre>.json  reporte para analisis automatico
#   <nombre>.html  grafico interactivo de latencias
#
# Se usa -output en vez de "| tee" y "> archivo" porque en PowerShell ambos
# reescriben los bytes (Tee-Object y la redireccion trabajan con texto).
param(
    [Parameter(Mandatory = $true)] [string] $Targets,
    [Parameter(Mandatory = $true)] [string] $Name,
    [string] $Rate = "50",
    [string] $Duration = "30s"
)

$ErrorActionPreference = "Stop"

# Si vegeta no esta en el PATH de esta terminal (por ejemplo, VS Code abierto
# antes de instalarlo), buscarlo en la carpeta de instalacion por usuario.
if (-not (Get-Command vegeta -ErrorAction SilentlyContinue)) {
    $instalado = Join-Path $env:LOCALAPPDATA "Programs\vegeta"
    if (Test-Path (Join-Path $instalado "vegeta.exe")) {
        $env:Path = "$env:Path;$instalado"
    } else {
        throw "No se encontro vegeta. Instalarlo (ver README, seccion Pruebas de carga) o agregarlo al PATH."
    }
}

$results = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Force $results | Out-Null
$binOutput = Join-Path $results "$Name.bin"
$jsonOutput = Join-Path $results "$Name.json"
$plotOutput = Join-Path $results "$Name.html"

Write-Host "== ${Name}: rate=$Rate/s duration=$Duration targets=$Targets"

# Ejecutar el ataque, almacenar binario y mostrar reporte en consola
vegeta attack -rate="$Rate" -duration="$Duration" -targets="$Targets" -output="$binOutput"
vegeta report "$binOutput"

# Generar reporte JSON para analisis automatico
vegeta report -type=json -output="$jsonOutput" "$binOutput"

# Generar grafico interactivo HTML para visualizacion en navegador
vegeta plot -output="$plotOutput" "$binOutput"

Write-Host "grafico: $plotOutput"
