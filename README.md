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

## Estado actual

- Upload real de archivos PDF con `multipart/form-data`.
- Validacion de nombre, extension `.pdf`, firma `%PDF-` y tamanio maximo.
- Extraccion de texto con `pypdf` usando memoria, sin guardar temporalmente el PDF en disco.
- Calculo de checksum SHA-256.
- Rechazo de documentos duplicados por checksum.
- Persistencia en MongoDB.
- CRUD de documentos persistidos.
- Respuestas de error compatibles con Problem Details para casos especificos.
- Tests automatizados con `pytest` y `mongomock`.
- Imagen Docker propia para la API.
- Docker Compose separado para base de datos y aplicacion.

## Arquitectura

El proyecto sigue una arquitectura de 3 capas:

```text
Router -> Service -> Repository -> MongoDB
```

### 1. Capa de presentacion

Ubicacion:

- `app/api/routers/`

Responsabilidades:

- Recibir requests HTTP.
- Validar parametros basicos de entrada.
- Transformar errores de negocio en respuestas HTTP.
- Devolver respuestas JSON.

### 2. Capa de logica de negocio

Ubicacion:

- `app/services/`
- `app/core/validators.py`

Responsabilidades:

- Validar reglas del documento.
- Calcular checksum.
- Evitar duplicados.
- Extraer texto desde memoria.
- Coordinar el flujo de alta, consulta, actualizacion y eliminacion.

### 3. Capa de datos

Ubicacion:

- `app/repositories/`
- `app/utils/database.py`

Responsabilidades:

- Conectarse a MongoDB.
- Crear indices.
- Persistir documentos.
- Consultar, actualizar y eliminar registros.
- Manejar el contador secuencial de IDs.

## Persistencia

La base de datos usada es MongoDB.

Colecciones principales:

- `documents`
- `counters`

Campos principales guardados por documento:

- `id`
- `name`
- `original_filename`
- `file_path`
- `checksum`
- `file_size`
- `extracted_text`
- `is_processed`
- `created_at`
- `updated_at`

Nota importante: el PDF original no se guarda como binario en MongoDB. El texto se extrae desde los bytes recibidos en memoria y se persisten los metadatos junto con el texto extraido.

## Docker

### Estructura

Los archivos de infraestructura Docker se centralizaron en la carpeta `docker/` para mantener la raiz del proyecto limpia:

| Archivo original | Nueva ubicacion |
|------------------|-----------------|
| `Dockerfile` | `docker/Dockerfile` |
| `docker-compose.db.yml` | `docker/docker-compose.db.yml` |
| `docker-compose.yml` | `docker/docker-compose.yml` |

`.dockerignore` permanece en la raiz y ahora ignora el directorio `docker/` completo.

`docker-compose.yml` no hardcodea ningun host de backing service: `DATABASE_URL` se pasa tal cual viene de `.env` (factor de configuracion 12-factor). El host que va en `.env` depende de donde corra la API:

- API dentro de Docker (`make up` / `docker compose -f docker/docker-compose.yml up`): usar el nombre de servicio de la red Docker, `mongo:27017`.
- API corriendo localmente fuera de Docker (`python main.py`) contra el contenedor de Mongo expuesto: usar `localhost:27017`.

Cambiar de entorno es solo editar `.env`, sin tocar ningun archivo versionado.

## Requisitos

- Python 3.13+
- `uv`
- Docker Desktop
- Docker Compose (V1 o V2)
- `make` (instalar con `sudo apt install make` en WSL/Linux)

> **Nota sobre Docker Compose**: Si usas Docker Compose V1 (commando `docker-compose` con guion), usa la sintaxis manual con `--env-file .env`. Si usas V2 (commando `docker compose` sin guion), podés agregar el flag `--env-file` en cada comando o usar el `Makefile`.

## Variables de entorno

Crear el archivo `.env` a partir de `.env.example`:

```powershell
copy .env.example .env
```

Variables principales:

```env
APP_NAME=PDF Extract API
APP_VERSION=0.1.0
DEBUG=False

HOST=0.0.0.0
PORT=8000

DATABASE_URL=mongodb://admin:9009@mongo:27017/?authSource=admin
DATABASE_NAME=pdf_extract
DATABASE_TIMEOUT_MS=3000
MAX_PDF_SIZE_BYTES=10485760

API_V1_PREFIX=/api/v1
API_DOCS_URL=/docs
API_REDOC_URL=/redoc
API_OPENAPI_URL=/openapi.json

ROOT_USERNAME=admin
ROOT_PASSWORD=9009
```

## Ejecucion con Docker

### Opcion rapida (recomendada)

Desde la raiz del proyecto, usa `make` para levantar todo el stack:

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

### Opcion manual (por servicio)

Si preferis levantar los servicios uno por uno o necesitas mas control, ejecuta los comandos manualmente con `--env-file .env`:

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
docker logs -f docker_api_1
```

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
- Healthcheck: `http://localhost:8000/health`

Respuesta esperada del healthcheck:

```json
{
  "status": "ok",
  "database": "mongodb",
  "database_name": "pdf_extract"
}
```

## Endpoints principales

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `PUT /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/extract`
- `GET /health`

## Flujo principal

1. El cliente sube un PDF con `name` y `file`.
2. La API lee el archivo en memoria.
3. Se valida nombre, extension, firma y tamanio.
4. Se calcula el checksum SHA-256.
5. Si el checksum ya existe, el documento se rechaza.
6. Si es valido, se extrae el texto desde memoria usando `pypdf`.
7. Se guarda el documento en MongoDB con sus metadatos y texto extraido.
8. La API devuelve el documento creado.

## Ejemplo con curl

```powershell
curl -X POST "http://localhost:8000/api/v1/documents" ^
  -H "accept: application/json" ^
  -H "Content-Type: multipart/form-data" ^
  -F "name=Contrato de prueba" ^
  -F "file=@C:/ruta/al/archivo.pdf;type=application/pdf"
```

Respuesta esperada:

```json
{
  "name": "Contrato de prueba",
  "original_filename": "archivo.pdf",
  "file_size": 12345,
  "id": 1,
  "checksum": "sha256...",
  "extracted_text": "Texto extraido del PDF",
  "is_processed": true,
  "created_at": "2026-06-03T20:00:00.000000Z",
  "updated_at": "2026-06-03T20:00:00.000000Z"
}
```

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

## Documentacion util

- `START_HERE.md`: punto de entrada rapido.
- `QUICKSTART.md`: arranque en pocos minutos.
- `DEMO.md`: guion sugerido para mostrar en clase.
- `REVISION_ENUNCIADO.md`: chequeo punto por punto contra el TP.
- `ARCHITECTURE.md`: resumen de arquitectura actual.
- `EJEMPLOS.md`: ejemplos de requests y respuestas.
- `VISUAL_GUIDE.md`: vista visual del flujo principal.
- `TESTING_MANUAL.md`: guia de pruebas manuales.

## Limitacion conocida

La extraccion actual usa `pypdf`, por lo que obtiene texto digital embebido en el PDF.

Si el PDF es escaneado o contiene solo imagenes, `extracted_text` puede quedar vacio. Eso no significa que la API falle: significa que no se esta aplicando OCR.

## Comandos utiles

Comandos con `make` (desde la raiz del proyecto):

```bash
make up          # Levantar todo el stack
make down        # Apagar todo
make logs        # Ver logs de la API
make ps          # Ver estado de los contenedores
make api         # Levantar solo la API
make db          # Levantar solo MongoDB
```

Comandos manuales (por servicio):

Reconstruir la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --force-recreate
```

Ver logs de MongoDB:

```bash
docker logs -f docker_mongo_1
```

Ver logs de la API:

```bash
docker logs -f docker_api_1
```

Apagar solo la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
```

Apagar solo MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml down
```

Borrar tambien el volumen de MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml down -v
```
