# Benchmark completo del TP en un solo comando (PowerShell o la terminal de
# VS Code): limpia, levanta Traefik + 5 replicas, corre el spike de k6 y la
# carga fija de Vegeta dentro de la red de Docker y muestra el resumen contra
# el benchmark del profesor.
#
# Uso (desde cualquier carpeta):
#   .\tests\stress\benchmark.ps1           # deja el stack levantado al final
#   .\tests\stress\benchmark.ps1 -Apagar   # lo apaga al terminar
#   .\tests\stress\benchmark.ps1 -SinBuild # no reconstruye la imagen
#   .\tests\stress\benchmark.ps1 -Navegador # ademas, graficos en el navegador:
#        dashboard de k6 en vivo (http://localhost:5665), reporte HTML del spike
#        y Grafana con las metricas de Traefik (http://localhost:3000)
#   .\tests\stress\benchmark.ps1 -Orden fifo # cola por orden de llegada: lo mejor
#        en una maquina con menos nucleos que replicas (la notebook del grupo);
#        por defecto "size" (primero el PDF mas liviano, con un nucleo por replica)
#
# Solo necesita Docker Desktop abierto.
param(
    [switch]$Apagar,
    [switch]$SinBuild,
    [switch]$Navegador,
    [ValidateSet("size", "fifo")]
    [string]$Orden = ""
)

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo
$red = "pdf-extractext-tp_default"
$stress = Join-Path $repo "tests\stress"

function Paso($texto) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $texto" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

Paso "1/4  Limpiando contenedores anteriores"
docker compose --profile monitoreo down --remove-orphans

Paso "2/4  Levantando Traefik + 5 replicas"
if ($Orden) { $env:EXTRACT_QUEUE_ORDER = $Orden; Write-Host "  Orden de la cola: $Orden" }
if ($SinBuild) { docker compose up -d } else { docker compose up --build -d }
if ($Navegador) { docker compose --profile monitoreo up -d prometheus grafana }
if ($LASTEXITCODE -ne 0) { Write-Host "No se pudo levantar el stack. Esta abierto Docker Desktop?" -ForegroundColor Red; exit 1 }

$limite = (Get-Date).AddSeconds(180)
do {
    Start-Sleep -Seconds 2
    $sanas = @(docker compose ps extract --format "{{.Status}}" | Select-String "\(healthy\)").Count
    Write-Host "  replicas healthy: $sanas de 5"
} while ($sanas -lt 5 -and (Get-Date) -lt $limite)
if ($sanas -lt 5) { Write-Host "Las replicas no quedaron healthy en 3 minutos: docker compose logs extract" -ForegroundColor Red; exit 1 }
# Traefik tarda un instante en registrar las replicas.
$limite = (Get-Date).AddSeconds(60)
do { Start-Sleep -Seconds 1; $estado = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1/health } while ($estado -ne "200" -and (Get-Date) -lt $limite)

Paso "3/4  Spike con k6 (100 VUs, 10s / 20s / 10s)"
if ($Navegador) {
    Write-Host "  Dashboard de k6 en vivo: http://localhost:5665 (abrilo ahora)" -ForegroundColor Green
    Start-Process "http://localhost:3000/d/tp-extract"
    docker run --rm --network $red -p 5665:5665 -e K6_WEB_DASHBOARD=true -e K6_WEB_DASHBOARD_HOST=0.0.0.0 `
        -e K6_WEB_DASHBOARD_EXPORT=/resultados/spike.html -v "${stress}:/scripts:ro" -v "${stress}\results:/resultados" `
        grafana/k6 run --quiet -e BASE_URL=http://traefik /scripts/spike.js | Tee-Object -Variable spike
} else {
    docker run --rm --network $red -v "${stress}:/scripts:ro" grafana/k6 run --quiet -e BASE_URL=http://traefik /scripts/spike.js | Tee-Object -Variable spike
}
$spikeOk = ($LASTEXITCODE -eq 0)

Paso "4/4  Carga fija con Vegeta (50 req/s durante 30 s, timeout 30 s)"
if (-not (docker images -q vegeta:12.13.0)) {
    docker build -t vegeta:12.13.0 -f tests/stress/docker/vegeta.Dockerfile tests/stress/docker
}
docker run --rm --network $red --entrypoint bash -v "${stress}:/stress" vegeta:12.13.0 /stress/vegeta.sh http://traefik/extract
$vegetaOk = ($LASTEXITCODE -eq 0)

# ---------- Resumen ----------
$inv = [System.Globalization.CultureInfo]::InvariantCulture
function Num($texto) { [double]::Parse($texto, $inv) }
function Fila($nombre, $nuestro, $profesor, $formato, $mayorEsMejor) {
    $veredicto = if ([math]::Abs($nuestro - $profesor) -lt 1e-9) { "igual" }
        elseif (($nuestro -gt $profesor) -eq $mayorEsMejor) { "MEJOR" } else { "peor" }
    $color = @{ "MEJOR" = "Green"; "peor" = "Yellow"; "igual" = "Gray" }[$veredicto]
    $linea = "  {0,-28}{1,14}{2,14}   {3}" -f $nombre, [string]::Format($inv, $formato, $nuestro), [string]::Format($inv, $formato, $profesor), $veredicto
    Write-Host $linea -ForegroundColor $color
}

Paso "RESUMEN CONTRA EL PROFESOR"
Write-Host ("  {0,-28}{1,14}{2,14}" -f "", "nosotros", "profesor")

$total = ($spike | Select-String "^\s+TOTAL\s").Line
$rps = ($spike | Select-String "Throughput \(200 OK\):\s+([\d.]+)").Matches.Groups[1].Value
$exito = ($spike | Select-String "EXITO GLOBAL:\s+([\d.]+)").Matches.Groups[1].Value
if ($total -and $rps -and $exito) {
    $c = $total.Trim() -split "\s+"
    Write-Host "  Spike (k6)"
    Fila "Throughput" (Num $rps) 25.35 "{0:N2} req/s" $true
    Fila "Tasa de error" (100 - (Num $exito)) 0 "{0:N2} %" $false
    Fila "Latencia p50" (Num $c[5]) 1.88 "{0:N2} s" $false
    Fila "Latencia p90" (Num $c[7]) 7.83 "{0:N2} s" $false
    Fila "Latencia p95" (Num $c[9]) 8.80 "{0:N2} s" $false
    Fila "Latencia maxima" (Num $c[11]) 13.94 "{0:N2} s" $false
} else {
    Write-Host "  No se pudo leer el resultado del spike." -ForegroundColor Red
}

$json = Join-Path $stress "results\vegeta_50rps.json"
if (Test-Path $json) {
    $r = Get-Content $json -Raw | ConvertFrom-Json
    $codigos = $r.status_codes.PSObject.Properties
    $timeouts = 0; $ok = 0
    foreach ($p in $codigos) { if ($p.Name -eq "0") { $timeouts = [int]$p.Value }; if ($p.Name -eq "200") { $ok = [int]$p.Value } }
    Write-Host "  Vegeta"
    Fila "Throughput efectivo" $r.throughput 16.65 "{0:N2} req/s" $true
    Fila "Tasa de exito" ($r.success * 100) 66.53 "{0:N2} %" $true
    Fila "Peticiones exitosas" $ok 998 "{0:N0}" $true
    Fila "Timeouts" $timeouts 501 "{0:N0}" $false
    Fila "Latencia p50" ($r.latencies."50th" / 1e9) 14.89 "{0:N2} s" $false
}

Write-Host ""
Write-Host ("  SLO del spike:  " + $(if ($spikeOk) { "cumplido" } else { "NO cumplido" })) -ForegroundColor $(if ($spikeOk) { "Green" } else { "Red" })
Write-Host ("  SLO de Vegeta:  " + $(if ($vegetaOk) { "cumplido (ningun timeout)" } else { "NO cumplido" })) -ForegroundColor $(if ($vegetaOk) { "Green" } else { "Red" })
Write-Host ""
Write-Host "  Grafico de Vegeta:   tests\stress\results\vegeta_50rps.html"
if ($Navegador) {
    Write-Host "  Reporte del spike:   tests\stress\results\spike.html"
    Write-Host "  Grafana:             http://localhost:3000/d/tp-extract"
    Invoke-Item (Join-Path $stress "results\vegeta_50rps.html")
    $reporte = Join-Path $stress "results\spike.html"
    if (Test-Path $reporte) { Invoke-Item $reporte }
}
Write-Host "  Dashboard Traefik:   http://localhost:8080/dashboard/"

if ($Apagar) {
    Paso "Apagando el stack"
    docker compose --profile monitoreo down
} else {
    Write-Host "  El stack sigue levantado. Para apagarlo: docker compose down"
}
