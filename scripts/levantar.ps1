# Levanta el stack del TP (Traefik + 5 replicas de POST /extract, el
# docker-compose.yml de la raiz) con un solo comando desde PowerShell, tanto
# con Docker Desktop como con Docker instalado dentro de WSL.
#
# Uso (desde cualquier carpeta):
#   .\scripts\levantar.ps1                  # detecta el Docker, construye y levanta
#   .\scripts\levantar.ps1 -SinBuild        # no reconstruye la imagen
#   .\scripts\levantar.ps1 -Apagar          # apaga el stack (tambien el perfil monitoreo)
#   .\scripts\levantar.ps1 -Docker wsl      # fuerza Docker de WSL (o windows)
#   .\scripts\levantar.ps1 -Distro Ubuntu   # distro de WSL a usar
#
# Si PowerShell no deja correr scripts:
#   powershell -ExecutionPolicy Bypass -File .\scripts\levantar.ps1
#
# Con Docker en WSL, la distro se apaga sola cuando no queda ningun proceso de
# WSL abierto, y Docker con ella. Por eso el script deja un "sleep infinity"
# oculto mientras el stack esta levantado; -Apagar lo termina.
#
# El stack completo de microservicios esta en el repo infrastructure
# (scripts\levantar.ps1 de ese repo). Los dos usan los puertos 80, 443 y 8080:
# no se pueden levantar a la vez.
param(
    [ValidateSet("auto", "windows", "wsl")]
    [string]$Docker = "auto",
    [switch]$Apagar,
    [switch]$SinBuild,
    [string]$Distro = ""
)

$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$proyecto = "pdf-extractext-tp"
$keepAlive = Join-Path $env:TEMP "$proyecto-wsl-keepalive.pid"
# wsl.exe escribe en UTF-16 salvo con esta variable.
$env:WSL_UTF8 = "1"

function Paso($texto) {
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host "  $texto" -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}

function Fallar($texto) {
    Write-Host ""
    Write-Host $texto -ForegroundColor Red
    exit 1
}

# --- Deteccion del Docker -----------------------------------------------------

function Probar-DockerWindows {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return "falta" }
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return "ok" }
    return "apagado"
}

function Distros-Wsl {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return @() }
    $lista = (wsl.exe -l -q 2>$null) -replace "`0", "" | ForEach-Object { $_.Trim() }
    # Las distros internas de Docker Desktop no sirven para correr comandos.
    return @($lista | Where-Object { $_ -and $_ -notlike "docker-desktop*" })
}

function Probar-DockerWsl($nombre) {
    wsl.exe -d $nombre --exec sh -c "command -v docker" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { return "falta" }
    # Si la distro estaba apagada, el daemon tarda unos segundos en arrancar.
    for ($i = 0; $i -lt 10; $i++) {
        wsl.exe -d $nombre --exec docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { return "ok" }
        Start-Sleep -Seconds 2
    }
    return "apagado"
}

function Elegir-Wsl {
    $candidatas = if ($Distro) { @($Distro) } else { Distros-Wsl }
    if ($candidatas.Count -eq 0) { return $null }
    foreach ($d in $candidatas) {
        $estado = Probar-DockerWsl $d
        if ($estado -eq "ok") { return $d }
        if ($estado -eq "apagado") {
            Fallar "Docker esta instalado en WSL ($d) pero el daemon no responde. Abri Ubuntu y corre: sudo service docker start"
        }
    }
    return $null
}

function Detectar-Docker {
    if ($Docker -ne "wsl") {
        $estado = Probar-DockerWindows
        if ($estado -eq "ok") { return @{ Modo = "windows"; Distro = "" } }
        if ($Docker -eq "windows") {
            if ($estado -eq "apagado") { Fallar "Docker Desktop esta instalado pero no responde: abrilo y espera a que diga 'Engine running'." }
            Fallar "No se encontro el comando docker en Windows. Instala Docker Desktop o usa -Docker wsl."
        }
        if ($estado -eq "apagado") {
            Fallar "Docker Desktop esta instalado pero no responde: abrilo y espera a que diga 'Engine running'."
        }
    }
    $d = Elegir-Wsl
    if ($d) { return @{ Modo = "wsl"; Distro = $d } }
    Fallar "No se encontro Docker ni en Windows (Docker Desktop) ni en ninguna distro de WSL."
}

# --- Comandos de Docker en el modo elegido -------------------------------------

# Corre "docker <argumentos>" en la carpeta del repo; el codigo de salida queda
# en $LASTEXITCODE. En WSL, --cd acepta la ruta de Windows y --exec evita que
# bash vuelva a interpretar los argumentos.
function Docker-Run([string[]]$argumentos) {
    if ($script:modo -eq "windows") {
        Push-Location $repo
        & docker @argumentos
        Pop-Location
    } else {
        & wsl.exe -d $script:distro --cd $repo --exec docker @argumentos
    }
}

function Compose([string[]]$argumentos) {
    Docker-Run (@("compose") + $argumentos)
}

# Contenedores de otro proyecto de compose que ya ocupan el puerto 443.
function Choque-De-Puertos {
    $filas = Docker-Run @("ps", "--filter", "publish=443", "--format", "{{.Names}};{{.Labels}}")
    foreach ($fila in @($filas)) {
        if (-not $fila) { continue }
        $nombre, $labels = $fila -split ";", 2
        $otro = ""
        if ($labels -match "com\.docker\.compose\.project=([^,]+)") { $otro = $Matches[1] }
        if ($otro -ne $proyecto) { return @{ Nombre = $nombre; Proyecto = $otro } }
    }
    return $null
}

function Iniciar-KeepAlive {
    if (Test-Path $keepAlive) {
        $id = Get-Content $keepAlive -ErrorAction SilentlyContinue
        if ($id -and (Get-Process -Id $id -ErrorAction SilentlyContinue)) { return }
    }
    $p = Start-Process wsl.exe -ArgumentList @("-d", $script:distro, "--exec", "sleep", "infinity") -WindowStyle Hidden -PassThru
    Set-Content -Path $keepAlive -Value $p.Id
}

function Detener-KeepAlive {
    if (-not (Test-Path $keepAlive)) { return }
    $id = Get-Content $keepAlive -ErrorAction SilentlyContinue
    $p = if ($id) { Get-Process -Id $id -ErrorAction SilentlyContinue }
    if ($p -and $p.ProcessName -eq "wsl") { Stop-Process -Id $id -Force }
    Remove-Item $keepAlive -ErrorAction SilentlyContinue
}

# --- Principal --------------------------------------------------------------------

Paso "Detectando Docker"
$elegido = Detectar-Docker
$script:modo = $elegido.Modo
$script:distro = $elegido.Distro
if ($script:modo -eq "wsl") {
    Write-Host "Docker de WSL, distro $($script:distro)"
} else {
    Write-Host "Docker Desktop"
}

if ($Apagar) {
    Paso "Apagando el stack del TP"
    Compose @("--profile", "monitoreo", "down")
    $codigo = $LASTEXITCODE
    if ($script:modo -eq "wsl") { Detener-KeepAlive }
    exit $codigo
}

$choque = Choque-De-Puertos
if ($choque) {
    $como = if ($choque.Proyecto -eq "infrastructure") {
        "Apagalo con: ..\infrastructure\scripts\levantar.ps1 -Apagar"
    } else {
        "Apagalo antes de seguir (docker stop $($choque.Nombre))."
    }
    Fallar "El puerto 443 ya lo usa '$($choque.Nombre)' (proyecto '$($choque.Proyecto)'). $como"
}

Paso "Levantando Traefik + 5 replicas (espera a que esten healthy)"
$up = @("up", "-d", "--wait", "--wait-timeout", "300")
if (-not $SinBuild) { $up += "--build" }
Compose $up
if ($LASTEXITCODE -ne 0) {
    Compose @("ps")
    Fallar "El stack no quedo healthy. Revisa los logs con: docker compose logs"
}
if ($script:modo -eq "wsl") { Iniciar-KeepAlive }

Compose @("ps")

Paso "Chequeo desde Windows"
$estado = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1/health
if ($estado -eq "200") {
    Write-Host "GET http://127.0.0.1/health -> 200" -ForegroundColor Green
} else {
    Write-Host "GET http://127.0.0.1/health -> $estado (esperaba 200)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "POST /extract (Vegeta):  http://127.0.0.1/extract"
Write-Host "POST /extract (k6):      https://extract.universidad.localhost/extract"
Write-Host "Dashboard de Traefik:    http://localhost:8080/dashboard/"
Write-Host "Para apagar:             .\scripts\levantar.ps1 -Apagar"
