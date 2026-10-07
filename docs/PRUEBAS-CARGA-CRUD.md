# Pruebas de carga del CRUD

Pruebas de velocidad de los endpoints de documentos (`/api/v1/documents`).
Las del TP (`POST /extract`, spike y carga fija contra el profesor) estan en
[tests/stress](../tests/stress/README.md).

## Con k6

Miden la velocidad de respuesta de los endpoints con [k6](https://k6.io), que
se instala en la maquina (no es una dependencia del proyecto):

```powershell
winget install k6 --source winget
```

Con la API levantada en Docker (ver "Ejecucion con Docker"):

```powershell
k6 run tests/load/documents.js
```

Cada iteracion sube un PDF distinto (el service rechaza checksums repetidos),
lo lee por id y consulta `/health`. El script define umbrales (p95 de cada
endpoint y tasa de errores); si alguno no se cumple, `k6` termina con error.

Parametros opcionales por variable de entorno:

```powershell
k6 run -e BASE_URL=http://localhost:8000 -e VUS=20 -e DURATION=1m tests/load/documents.js
```

- `BASE_URL`: URL de la API (por defecto `http://localhost:8000`).
- `VUS`: usuarios virtuales concurrentes (por defecto 10).
- `DURATION`: duracion de la prueba (por defecto `30s`).

Linea base medida con la API en Docker, 10 usuarios durante 30 s:

| Endpoint | p50 | p95 |
|---|---|---|
| `POST /api/v1/documents` | 74 ms | 125 ms |
| `GET /api/v1/documents/{id}` | 62 ms | 101 ms |
| `GET /health` | 36 ms | 65 ms |

### Con Vegeta

`tests/load/vegeta/` replica el flujo de [Vegeta](https://github.com/tsenart/vegeta)
(`attack` → `report` → `report -type=json` → `plot`), con un PDF grande.
Vegeta se instala descomprimiendo el zip de sus releases y agregandolo al PATH.

```powershell
# 1. Generar los targets: 60 PDFs distintos de 279 paginas (67 MB) mas /health y GET
python tests/load/vegeta/make_targets.py tests/load/vegeta/results/targets --base-url http://127.0.0.1:8000 --pages 279 --variants 60 --document-id 1

# 2. Atacar: <targets> <nombre> [rate] [duracion]
.\tests\load\vegeta\run.ps1 tests\load\vegeta\results\targets\health.txt health 50 30s
.\tests\load\vegeta\run.ps1 tests\load\vegeta\results\targets\post_document.txt post_279p 1/2s 30s
```

`run.sh` es el equivalente para Git Bash o Linux, con los comandos de Vegeta
tal cual (`attack | tee | report`). Usar `127.0.0.1` y no `localhost`: Vegeta
en Windows no lo resuelve. Los resultados quedan en `tests/load/vegeta/results/`
(ignorado por git); el grafico `<nombre>.html` se abre con doble clic. La
evaluacion con los numeros medidos esta en
[tests/load/vegeta/EVALUACION.md](../tests/load/vegeta/EVALUACION.md).

### Limpieza

Los documentos creados por las pruebas quedan en la base con nombre
`carga vu<N> iter<M>` o `vegeta ...`. Se borran con un proceso de
administracion que usa el mismo codigo y la misma configuracion que la API
(12-Factor XII), asi no hace falta saber el nombre del contenedor de MongoDB
ni sus credenciales:

```powershell
# Dentro del contenedor de la API (stack de docker/)
docker compose -f docker/docker-compose.yml exec api python -m app.admin.clear_documents --name-regex "^(carga vu|vegeta)"

# Fuera de Docker, contra la base del .env
uv run python -m app.admin.clear_documents --name-regex "^(carga vu|vegeta)"
```

`--all` borra todos los documentos y `--dry-run` solo cuenta cuantos se
borrarian. Sin `--name-regex` ni `--all` el comando no hace nada: es
destructivo y hay que decir que borrar. Con `make`: `make limpiar-carga`.
