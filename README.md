# API de Extraccion de PDF

API construida con FastAPI para registrar documentos PDF, validar su formato y tamanio, extraer texto en memoria, calcular checksum y persistir la informacion en MongoDB.

El proyecto corresponde a la Etapa 1 de Desarrollo de Software. La aplicacion trabaja con arquitectura de 3 capas y usa Docker para separar la base de datos de la aplicacion.

## Integrantes

- Gabriel Flores
- Lucas Martinez
- Daiana Galdeano
- Solange Parada
- Joaquin Antequeda
- Nicolas Santivanez

## TP de carga y estres: reproducir el benchmark

Solo hace falta Docker. Todo en un comando (PowerShell o la terminal de VS
Code, en la raiz del repo): limpia, levanta el stack, corre el spike y Vegeta
y muestra la tabla contra el profesor.

```powershell
.\tests\stress\benchmark.ps1
```

`-Apagar` baja el stack al terminar y `-SinBuild` no reconstruye la imagen.
Los mismos pasos, uno por uno:

```powershell
# 1. Traefik + 5 replicas de POST /extract (1 CPU y 1 GB cada una)
docker compose up --build -d

# 2. Spike del profesor con k6 (100 VUs, 10s/20s/10s)
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik /scripts/spike.js

# 3. Carga fija del profesor con Vegeta (50 req/s, 30 s, timeout 30 s)
docker build -t vegeta:12.13.0 -f tests/stress/docker/vegeta.Dockerfile tests/stress/docker
docker run --rm --network pdf-extractext-tp_default --entrypoint bash -v "${PWD}/tests/stress:/stress" vegeta:12.13.0 /stress/vegeta.sh http://traefik/extract

# 4. Apagar
docker compose down
```

Cada script imprime la comparacion con el benchmark del profesor y si se
cumplio el SLO. Los generadores de carga corren dentro de la red de Docker: en
Windows, el reenvio de puertos de Docker Desktop distorsiona los resultados.

| Prueba | Nosotros (v1.3.3) | Profesor |
|---|---|---|
| Spike: throughput / errores | 11-14,5 req/s / 0 % | 25,35 req/s / 0 % |
| Spike: p95 / maximo | 7,8-11,3 s / 8,7-12,8 s | 8,80 s / 13,94 s |
| Vegeta: exito | 25-30 % | 66,53 % |
| Vegeta: timeouts / p50 | **0-1 / 0,1-2,5 s** | 501 / 14,89 s |

Medido en una notebook con 4 nucleos fisicos para 5 replicas, Traefik y el
generador de carga. El analisis completo (arquitectura, cuello de botella,
antes y despues, proceso de investigacion) esta en
[docs/INFORME-TP.md](docs/INFORME-TP.md) y las decisiones en
[docs/decisions](docs/decisions/README.md).

## Estado actual

- `POST /extract` sin estado, el endpoint del TP: recibe un PDF (body crudo o
  multipart) y devuelve su contenido en Markdown y su cantidad de paginas.
- Upload real de archivos PDF con `multipart/form-data`.
- Validacion de nombre, extension `.pdf`, firma `%PDF-` y tamanio maximo.
- Extraccion de texto con `pypdfium2` (PDFium, el motor de PDF de Chrome) en memoria, sin guardar temporalmente el PDF en disco.
- Calculo de checksum SHA-256.
- Metricas propias de cada replica en `GET /metrics` (cola, rechazos por motivo,
  tiempo de extraccion) y dashboard de Grafana (`--profile monitoreo`).
- Rechazo de documentos duplicados por checksum (`409`, tambien si dos uploads
  iguales llegan a la vez y los frena el indice unico de MongoDB).
- Persistencia en MongoDB.
- CRUD de documentos persistidos.
- Respuestas de error compatibles con Problem Details para casos especificos.
- Tests automatizados con `pytest` y `mongomock`.
- Imagen Docker propia para la API.
- Docker Compose separado para base de datos y aplicacion.

## Arquitectura

Tres capas con influencia de arquitectura hexagonal:

```text
Router (app/api) -> Service (app/services) -> Repository (app/repositories) -> MongoDB
```

El detalle de capas, nucleo, flujos y decisiones esta en
[ARCHITECTURE.md](ARCHITECTURE.md) y en los ADRs de
[docs/decisions](docs/decisions/README.md). Persistencia, estructura de Docker,
versionado, ejemplos con curl y comandos utiles: [docs/DESARROLLO.md](docs/DESARROLLO.md).

## Requisitos

- Python 3.14+
- `uv`
- Docker Desktop
- Docker Compose (V1 o V2)
- `make` **opcional**: solo para los atajos del `Makefile`. No viene en Windows;
  en WSL/Linux se instala con `sudo apt install make`. Sin `make` se usan los
  comandos de `docker compose`, que funcionan en cualquier sistema.

> **Nota sobre Docker Compose**: Si usas Docker Compose V1 (commando `docker-compose` con guion), usa la sintaxis manual con `--env-file .env`. Si usas V2 (commando `docker compose` sin guion), podés agregar el flag `--env-file` en cada comando o usar el `Makefile`.

## Variables de entorno

Crear el archivo `.env` a partir de `.env.example`:

```powershell
copy .env.example .env
```

Variables principales:

```env
APP_NAME=PDF Extract API
APP_VERSION=1.3.4
IMAGE_TAG=1.3.4
DEBUG=False
# Nivel de los logs JSON en stdout: DEBUG, INFO, WARNING, ERROR.
LOG_LEVEL=INFO

HOST=0.0.0.0
PORT=8000
# Procesos de uvicorn: PDFs que se extraen en paralelo. 1 en desarrollo;
# en Docker, tantos como nucleos quieras dedicar (la extraccion es CPU).
WEB_CONCURRENCY=1
# Segundos que uvicorn mantiene una conexion inactiva: mas que Traefik (90 s).
HTTP_KEEP_ALIVE_SECONDS=120

DATABASE_URL=mongodb://admin:9009@mongo:27017/?authSource=admin
DATABASE_NAME=pdf_extract
DATABASE_TIMEOUT_MS=3000
MAX_PDF_SIZE_BYTES=10485760
# false: solo POST /extract, sin MongoDB ni CRUD (las replicas del TP).
DOCUMENTS_API_ENABLED=true
# Backpressure de POST /extract: tiempo util de un request (espera + extraccion);
# si no llega a terminar a tiempo, 503 sin procesarlo. Menor que el timeout de los clientes.
EXTRACT_MAX_WAIT_SECONDS=25
# Requests de /extract admitidos a la vez por proceso (la cola); llena, 503.
EXTRACT_MAX_PENDING=60
# Origenes permitidos por CORS, separados por coma. "*" = cualquiera, sin credenciales.
CORS_ALLOW_ORIGINS=*

API_V1_PREFIX=/api/v1
API_DOCS_URL=/docs
API_REDOC_URL=/redoc
API_OPENAPI_URL=/openapi.json

ROOT_USERNAME=admin
ROOT_PASSWORD=9009
```

## Ejecucion con Docker

### Atajo con `make` (opcional)

Si tenes `make` instalado, desde la raiz del proyecto:

```bash
make up
```

Esto levanta automaticamente: MongoDB → API

Otros comandos disponibles:

```bash
make down   # Apagar todo
make logs   # Ver logs de la API
make ps     # Ver estado de los contenedores
make api    # Levantar solo la API
make db     # Levantar solo MongoDB
```

### Con docker compose (recomendado, funciona en cualquier sistema)

No necesita `make`. Desde la raiz del proyecto:

Levantar MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml up -d
```

Construir y levantar la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
```

Verificar contenedores:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml ps
docker compose --env-file .env -f docker/docker-compose.yml ps
```

Ver logs de la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml logs -f api
```

> Nota: el nombre del contenedor puede variar (`docker-api-1`, `docker_api_1`, etc.) según la versión/configuración de Docker Compose.

Apagar todo:

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
docker compose --env-file .env -f docker/docker-compose.db.yml down
```

## Ejecucion local

Tambien se puede correr la API localmente, usando MongoDB en Docker.

Instalar dependencias:

```powershell
uv sync --extra dev
```

Levantar MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml up -d
```

Correr la API:

```powershell
uv run python main.py
```

Alternativa si el entorno ya tiene dependencias instaladas:

```powershell
python main.py
```

## URLs utiles

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Liveness: `http://localhost:8000/health`
- Readiness: `http://localhost:8000/ready`
- Metricas (Prometheus): `http://localhost:8000/metrics`

`/health` (liveness) solo dice que el proceso responde y no consulta MongoDB:
es el que usa el healthcheck de Docker, para que una caida de la base no saque
de servicio a las replicas de `POST /extract`, que no la usan. `/ready`
(readiness) tambien verifica MongoDB y responde `503` si no esta disponible:

```json
{
  "status": "ok",
  "database": "mongodb",
  "database_name": "pdf_extract"
}
```

## Endpoints principales

- `POST /extract` (sin estado, ver la seccion siguiente)
- `POST /api/v1/documents` (multipart con `name` y `file`; el PDF se lee en
  memoria con limite: `400` invalido, `409` duplicado, `413` demasiado grande,
  `422` ilegible o falta un campo)
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `PUT /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/extract`
- `GET /health` (liveness)
- `GET /ready` (readiness)

## POST /extract (TP de carga y estres)

Endpoint que pide la consigna del TP. Recibe el PDF como body crudo
(`Content-Type: application/pdf`) o como campo `file` de un multipart, y
responde `200`:

```json
{ "content": "# Titulo\n\nTexto...", "page_count": 16 }
```

- No guarda nada: no calcula checksum ni rechaza duplicados; el mismo PDF se
  puede mandar las veces que haga falta.
- `content` es Markdown: los titulos salen de la altura de las letras
  (`app/core/markdown.py`) y las vinetas como items de lista.
- Errores en formato RFC 9457: `400` si no es un PDF o esta vacio, `413` si
  supera `MAX_PDF_SIZE_BYTES`, `422` si PDFium no puede leerlo.
- Backpressure: cada proceso admite hasta `EXTRACT_MAX_PENDING` (60) requests a
  la vez; con la cola llena responde `503` con `Retry-After` al instante, sin leer
  el PDF. Un request que no llegaria a terminar dentro de `EXTRACT_MAX_WAIT_SECONDS`
  (25 s, contando lo que espero mas una extraccion pesimista) tambien recibe `503`
  sin procesarse: nunca se gasta CPU en algo que va a vencer.

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract -H "Content-Type: application/pdf" --data-binary "@tests/stress/pdfs/Filosofia Lean.pdf"
```

### Stack del TP: 5 replicas detras de Traefik

El `docker-compose.yml` de la raiz levanta Traefik y 5 replicas de
`/extract` (1 CPU y 1 GB cada una, sin MongoDB), con un solo comando:

```powershell
docker compose up --build
```

Queda en `http://127.0.0.1/extract` y en
`https://extract.universidad.localhost/extract`; el dashboard de Traefik en
`http://localhost:8080/dashboard/`. Si una replica se cae o se apaga, Traefik
reintenta en otra; con `docker compose --profile monitoreo up -d` se agregan
Prometheus y Grafana (`http://localhost:3000`). Usa los mismos puertos que el stack
completo del repo `infrastructure`: no levantar los dos a la vez. Las pruebas
de carga del TP estan en [tests/stress](tests/stress/README.md), el plan en
[docs/PLAN-TP.md](docs/PLAN-TP.md) y las mediciones en
[docs/INFORME-TP.md](docs/INFORME-TP.md).

## Tests

Ejecutar la suite:

```powershell
python -m pytest -q
```

Los tests cubren:

- Healthcheck.
- Alta de documentos.
- Lectura/listado.
- Actualizacion.
- Eliminacion.
- Extraccion de texto.
- Validaciones de nombre, PDF, tamanio, checksum y paginacion.
- Errores controlados.

Los tests estan organizados por capa:

- `tests/test_validators.py`: reglas de dominio puras, sin I/O.
- `tests/service/`: la capa de negocio (`DocumentService`) probada por su propia interfaz, sin HTTP.
- `tests/api/`: el flujo completo por HTTP con `TestClient` y `mongomock`.
- `tests/load/`: pruebas de carga con k6 (ver la seccion siguiente). No corren con `pytest`.

## Calidad de codigo

```powershell
uv run pre-commit install          # una vez: black, isort y flake8 antes de cada commit
uv run black --check app tests main.py
uv run isort --check-only app tests main.py
uv run flake8 app tests main.py
uv run mypy app main.py
uv run pytest -q --cov=app --cov-fail-under=95
```

El CI corre lo mismo en cada push, mas el build de la imagen con un smoke test,
el escaneo de secretos y la auditoria de dependencias (`pip-audit`). Detalle en
[docs/DESARROLLO.md](docs/DESARROLLO.md).

## Documentacion util

- `ARCHITECTURE.md`: capas, nucleo, modos de despliegue y operacion.
- `docs/PLAN-TP.md`: plan del TP de carga y estres.
- `docs/INFORME-TP.md`: informe del TP (arquitectura, cuello de botella, antes y despues, proceso de investigacion) y bitacora de mediciones.
- `docs/decisions/`: ADRs con cada decision y las alternativas medidas.
- `docs/REVISION_ENUNCIADO.md`: chequeo punto por punto contra el enunciado.
- `docs/DEMO.md`: guion para mostrar la API y el TP en clase.
- `docs/RUNBOOK.md`: que hacer ante saturacion, caidas, deploys y rollback.
- `docs/MEJORAS-RENDIMIENTO.md`: que mas se puede hacer para superar al profesor, con tiempos estimados.
- `docs/PLAN-MEJORAS.md`: plan por fases para mejorar el proyecto completo y el TP.
- `docs/DESARROLLO.md`: Docker y versionado, persistencia, ejemplos con curl, calidad de codigo y comandos utiles.
- `docs/PRUEBAS-CARGA-CRUD.md`: pruebas de carga de los endpoints de documentos.
- `tests/stress/README.md`: como correr las pruebas de carga del TP.

## Limitacion conocida

La extraccion actual usa `pypdfium2`, por lo que obtiene texto digital embebido en el PDF.

Si el PDF es escaneado o contiene solo imagenes, `extracted_text` puede quedar vacio. Eso no significa que la API falle: significa que no se esta aplicando OCR.
