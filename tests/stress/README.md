# Pruebas de estres del TP

Reproducen las dos pruebas de la consigna del TP contra `POST /extract`, con
los PDFs oficiales de [`pdfs/`](pdfs/), y comparan el resultado contra el
benchmark del profesor. El plan completo esta en
[`docs/PLAN-TP.md`](../../docs/PLAN-TP.md).

| PDF | Paginas | Tamano |
|---|---|---|
| `2020-Scrum-Guide-Spanish-Latin-South-American.pdf` | 16 | 0,3 MB |
| `Essential-Kanban-Condensed-Spanish.pdf` | 90 | 8,9 MB |
| `Filosofia Lean.pdf` | 42 | 0,7 MB |
| `scrum_manager_historias_usuario.pdf` | 62 | 3,8 MB |

## Instalacion de las herramientas

```powershell
winget install k6 --source winget
```

Vegeta: descomprimir el zip de
[sus releases](https://github.com/tsenart/vegeta/releases) en
`%LOCALAPPDATA%\Programs\vegeta` (el script lo busca ahi si no esta en el
PATH).

## Levantar el servicio

Desde la raiz del repo, el stack del TP (Traefik + 5 replicas de `/extract`):

```powershell
docker compose up --build -d
docker compose ps
```

Esperar a que las 5 replicas digan `healthy` antes de medir: mientras
arrancan, Traefik no tiene a donde mandar el trafico y responde 404.

## Medir desde dentro de la red de Docker (recomendado en Windows)

En Windows, el trafico de la PC a los contenedores pasa por el reenvio de
puertos de Docker Desktop, que con uploads grandes y concurrentes se vuelve el
cuello de botella y esconde el rendimiento real del servicio (ver
[el informe](../../docs/INFORME-TP.md#hallazgo-1-el-reenvio-de-puertos-de-docker-desktop-distorsiona-la-medicion)).
Para medir como en Linux, correr k6 en un contenedor dentro de la red del
stack:

```powershell
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik /scripts/spike.js
```

## A. Spike con k6 (modelo cerrado)

Perfil del profesor: 100 VUs, 10 s de subida, 20 s sostenidos, 10 s de
bajada. Cada VU manda un PDF al azar como body crudo
(`Content-Type: application/pdf`), igual que el `spike_tests.js` original.

```powershell
k6 run tests/stress/spike.js
```

Al terminar imprime una tabla por PDF (enviados, % OK, mediana, p90, p95,
maximo), las respuestas por codigo HTTP, el throughput y la comparacion con el
profesor.

| Variable | Default | Uso |
|---|---|---|
| `BASE_URL` | `https://extract.universidad.localhost` | URL del servicio |
| `VUS` | `100` | usuarios concurrentes |
| `SUBIDA` / `MESETA` / `BAJADA` | `10s` / `20s` / `10s` | etapas |
| `MODO` | `crudo` | `multipart` manda el PDF como campo `file` |
| `LOG` | `0` | `1` imprime una linea por request |

Dashboard en vivo en http://127.0.0.1:5665 mientras corre, y reporte HTML que
queda al terminar:

```powershell
k6 run --out "web-dashboard=export=tests/stress/results/spike.html" tests/stress/spike.js
```

### Carga fija con k6 (el perfil de Vegeta, dentro de la red de Docker)

`carga_fija.js` reproduce el perfil de Vegeta con el executor
`constant-arrival-rate` de k6: 50 req/s durante 30 s, rotando los 4 PDFs en
orden, timeout de 30 s, y latencias de todos los requests (un timeout cuenta
30 s), como las calcula Vegeta. Sirve para medir el modelo abierto desde la red
de Docker, porque Vegeta no tiene imagen oficial:

```powershell
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik /scripts/carga_fija.js
```

Variables: `BASE_URL`, `RATE` (50), `DURACION` (`30s`), `TIMEOUT` (`30s`),
`MODO`. La parte comun de los dos scripts (PDFs, metricas y resumen) esta en
`comun.js`.

## B. Carga fija con Vegeta (modelo abierto)

Perfil del profesor: 50 req/s durante 30 s (1.500 solicitudes) rotando los 4
PDFs, con timeout de cliente de 30 s.

```powershell
.\tests\stress\vegeta.ps1
```

```bash
tests/stress/vegeta.sh
```

Parametros: `-Url` (default `http://127.0.0.1/extract`), `-Rate`, `-Duration`,
`-Timeout` y `-Name` en PowerShell; los mismos en orden en Bash. Usar
`127.0.0.1` y no `localhost`: Vegeta en Windows no resuelve `localhost`.

Los resultados quedan en `tests/stress/results/` (ignorado por git): `.bin`,
`.json`, el grafico `.html` y el `targets.txt` generado.

## Benchmark del profesor

| Prueba | Resultado |
|---|---|
| k6 spike | 1.037 peticiones, 25,35 req/s, 0,00 % error, p50 1,88 s, p90 7,83 s, p95 8,80 s, max 13,94 s |
| Vegeta 50 req/s | 16,65 req/s efectivos, 998/1500 exitosas (66,53 %), 501 timeouts, p50 14,89 s |

La diferencia entre las dos pruebas es el modelo de carga: en k6 cada VU
espera su respuesta antes de mandar la siguiente (modelo cerrado), asi que la
carga se autorregula; Vegeta inyecta a tasa constante sin importar si el
servicio responde (modelo abierto), y si la tasa supera la capacidad la cola
crece hasta que los requests expiran.
