# Runbook del stack del TP

Que hacer en cada situacion con el stack de `docker-compose.yml` (Traefik + 5
replicas de `POST /extract`). Los comandos se corren desde la raiz del repo.

## Levantar, verificar y apagar

```powershell
docker compose up --build -d          # Traefik + 5 replicas
docker compose ps                      # las 5 replicas tienen que decir (healthy)
curl.exe http://127.0.0.1/health       # {"status":"ok"} a traves de Traefik
docker compose down                    # apaga y borra los contenedores
```

Antes de apagar la PC, cerrar Docker Desktop con **Quit**: si se apaga con
Docker abierto pueden quedar sockets viejos y Docker no vuelve a arrancar (ver
"Docker Desktop no arranca").

## Ver que pasa

| Que | Como |
|---|---|
| Logs de las replicas (JSON) | `docker compose logs -f extract` |
| Solo rechazos y errores | `docker compose logs extract \| Select-String "servicio_saturado\|pdf_rechazado\|cliente_desconectado"` |
| CPU y memoria por contenedor | `docker stats` |
| Rutas y replicas que ve Traefik | http://localhost:8080/dashboard/ |
| Metricas en el tiempo | `docker compose --profile monitoreo up -d` y abrir http://localhost:3000 |

Eventos de log utiles: `pdf_extraido` (bytes, paginas, duracion),
`servicio_saturado` (503), `pdf_rechazado` (400/413/422),
`cliente_desconectado` (el cliente se fue antes de su turno).

## Situaciones

### Muchos 503 con `Retry-After`

Es la contrapresion: la replica tiene su cola llena (`EXTRACT_MAX_PENDING`) o
el request espero mas que su tiempo util (`EXTRACT_MAX_WAIT_SECONDS`). No es
una falla: el servicio rechaza al instante lo que no puede terminar a tiempo.

- Si la carga es la esperada, falta capacidad: ver el plan de capacidad en
  `docs/INFORME-TP.md` (cada replica rinde ~5-6 req/s con un nucleo propio).
- No subir la cola por encima de ~30: con 100 la cola guarda mas trabajo del
  que entra en el tiempo util y los requests vencen esperando (Fase 2,
  experimento 2).

### Una replica se cae

Docker la vuelve a levantar sola (`restart: unless-stopped`, ~15 s hasta
healthy) y Traefik reintenta en otra los requests que no llegaron a
procesarse. Se pierden los que ya estaban en la cola de esa replica (~20 en el
spike). Si no vuelve:

```powershell
docker compose ps -a extract           # estado y codigo de salida
docker compose logs --tail 50 extract  # ultimo error
docker compose up -d                   # recrea las que falten
```

Un codigo de salida 137 con `OOMKilled: true` (`docker inspect`) es falta de
memoria: el limite es 1 GB y el pico medido con Vegeta es ~420 MiB.

### Traefik se cae

Es el punto unico de falla: mientras no esta, no responde nada. Docker lo
reinicia solo en ~4 s. Si no vuelve: `docker compose logs traefik` y
`docker compose up -d traefik`.

### Deploy o reinicio de una replica

`docker compose up -d` o `docker stop` mandan SIGTERM: la replica deja de
aceptar conexiones, termina su cola y sale (~10 s en el spike). Docker espera
hasta 35 s (`stop_grace_period`) antes de matarla. En la prueba de caos el
apagado ordenado no perdio ningun request.

### Volver a una version anterior

Cada version tiene su imagen (`pdf-extractext:X.Y.Z`) y su tag de git
(`vX.Y.Z`):

```powershell
$env:IMAGE_TAG = "1.2.0"; docker compose up -d   # imagen anterior, si existe
git checkout v1.2.0; docker compose up --build -d  # o reconstruirla
```

### Docker Desktop no arranca ("sailor-ingest.sock" o "engine.sock")

Quedaron sockets de un apagado sucio. Cerrar Docker Desktop del todo,
renombrar `%LOCALAPPDATA%\Docker\run` y `%LOCALAPPDATA%\docker-secrets-engine`
(por ejemplo con el sufijo `.viejo`) y abrir Docker Desktop una sola vez.

## Medir

| Prueba | Comando | Que mide |
|---|---|---|
| Spike (k6) | ver `tests/stress/README.md`, seccion A | throughput y latencias; termina con codigo 99 si no se cumple el SLO |
| Carga fija (Vegeta) | seccion B | exito y timeouts; termina con codigo 1 si algun request vence |
| Capacidad por replica | seccion C (`escala.js`) | req/s con N replicas |
| Caos | `bash tests/stress/caos.sh caida 15` o `stop 15` | requests perdidos y tiempo de recuperacion |

Medir siempre con el generador de carga dentro de la red de Docker (en
Windows el reenvio de puertos de Docker Desktop distorsiona los resultados) y
con el perfil `monitoreo` apagado.
