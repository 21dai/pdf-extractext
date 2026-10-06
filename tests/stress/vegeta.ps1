# Prueba de carga fija del TP con Vegeta (modelo abierto): 50 req/s durante 30 s
# rotando los 4 PDFs de tests/stress/pdfs, con timeout de cliente de 30 s, y
# comparacion contra el benchmark del profesor.
#
# Uso (desde la raiz del repo):
#   .\tests\stress\vegeta.ps1
#   .\tests\stress\vegeta.ps1 -Url http://127.0.0.1/extract -Rate 50 -Duration 30s
#
# Usar 127.0.0.1 y no localhost: Vegeta en Windows no resuelve localhost.
# Deja en tests/stress/results/ (ignorado por git): <Name>.bin, <Name>.json,
# <Name>.html (grafico) y targets.txt.
#
# Se usa -output en vez de "| tee" y "> archivo" porque en PowerShell ambos
# reescriben los bytes (Tee-Object y la redireccion trabajan con texto).
param(
    [string] $Url = "http://127.0.0.1/extract",
    [string] $Rate = "50",
    [string] $Duration = "30s",
    [string] $Timeout = "30s",
    [string] $Name = "vegeta_50rps"
)

$ErrorActionPreference = "Stop"

# Si vegeta no esta en el PATH de esta terminal (por ejemplo, VS Code abierto
# antes de instalarlo), buscarlo en la carpeta de instalacion por usuario.
if (-not (Get-Command vegeta -ErrorAction SilentlyContinue)) {
    $instalado = Join-Path $env:LOCALAPPDATA "Programs\vegeta"
    if (Test-Path (Join-Path $instalado "vegeta.exe")) {
        $env:Path = "$env:Path;$instalado"
    } else {
        throw "No se encontro vegeta. Instalarlo (ver tests/stress/README.md) o agregarlo al PATH."
    }
}

$pdfs = Join-Path $PSScriptRoot "pdfs"
$results = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Force $results | Out-Null
$targets = Join-Path $results "targets.txt"
$binOutput = Join-Path $results "$Name.bin"
$jsonOutput = Join-Path $results "$Name.json"
$plotOutput = Join-Path $results "$Name.html"

# Mismo formato que el test_carga.txt del profesor, con rutas absolutas locales.
$bloques = Get-ChildItem $pdfs -Filter *.pdf | Sort-Object Name | ForEach-Object {
    "POST $Url`nContent-Type: application/pdf`n@$($_.FullName)`n"
}
[System.IO.File]::WriteAllText($targets, ($bloques -join "`n"))

Write-Host "== ${Name}: $Rate req/s durante $Duration, timeout $Timeout, $Url"

# Ejecutar el ataque, almacenar binario y mostrar reporte en consola
vegeta attack -rate="$Rate" -duration="$Duration" -timeout="$Timeout" -targets="$targets" -output="$binOutput"
vegeta report "$binOutput"

# Generar reporte JSON para analisis automatico
vegeta report -type=json -output="$jsonOutput" "$binOutput"

# Generar grafico interactivo HTML para visualizacion en navegador
vegeta plot -output="$plotOutput" "$binOutput"

# ---------- Comparacion con el benchmark del profesor (consigna, seccion B) ----------
$r = Get-Content $jsonOutput -Raw | ConvertFrom-Json
$timeouts = 0
if ($r.status_codes.PSObject.Properties.Name -contains "0") { $timeouts = [int]$r.status_codes."0" }
$exitosas = [int][math]::Round($r.success * $r.requests)

function Fila([string] $nombre, [double] $nuestro, [double] $profesor, [string] $formato, [bool] $mayorEsMejor) {
    if ([math]::Abs($nuestro - $profesor) -lt 1e-9) { $veredicto = "igual" }
    elseif (($nuestro -gt $profesor) -eq $mayorEsMejor) { $veredicto = "MEJOR" }
    else { $veredicto = "peor" }
    # Cultura invariante: punto decimal, igual que la salida de k6 y de Vegeta.
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    "  {0,-26}{1,14}{2,14}   {3}" -f $nombre, [string]::Format($inv, $formato, $nuestro), [string]::Format($inv, $formato, $profesor), $veredicto
}

$ns = 1e9
Write-Host ""
Write-Host ("=" * 70)
Write-Host ("  {0,-26}{1,14}{2,14}" -f "COMPARACION CON EL PROFESOR", "nosotros", "profesor")
Write-Host ("  " + "-" * 66)
Write-Host (Fila "Throughput efectivo" $r.throughput 16.65 "{0:N2} req/s" $true)
Write-Host (Fila "Peticiones exitosas" $exitosas 998 "{0:N0}" $true)
Write-Host (Fila "Tasa de exito" ($r.success * 100) 66.53 "{0:N2} %" $true)
Write-Host (Fila "Timeouts (codigo 0)" $timeouts 501 "{0:N0}" $false)
Write-Host (Fila "Latencia p50" ($r.latencies."50th" / $ns) 14.89 "{0:N2} s" $false)
if ($Rate -ne "50" -or $Duration -ne "30s" -or $Timeout -ne "30s") {
    Write-Host ""
    Write-Host "  Aviso: el perfil no es el del profesor (50 req/s, 30 s, timeout 30 s); la comparacion no es valida."
}
Write-Host ("=" * 70)
Write-Host "grafico: $plotOutput"

# SLO bajo sobrecarga: ningun request vence por timeout (codigo 0 en Vegeta).
# Lo que el servicio no puede atender a tiempo se rechaza al instante con 503.
if ($timeouts -gt 0) {
    Write-Host "SLO INCUMPLIDO: $timeouts requests vencieron por timeout"
    exit 1
}
Write-Host "SLO cumplido: ningun request vencio por timeout"
