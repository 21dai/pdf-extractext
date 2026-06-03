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

El proyecto separa los servicios en archivos distintos:

- `Dockerfile`: define la imagen de la API FastAPI.
- `docker-compose.db.yml`: levanta MongoDB como servicio separado.
- `docker-compose.yml`: levanta la aplicacion usando la imagen construida desde el `Dockerfile`.
- `.dockerignore`: evita copiar archivos innecesarios dentro de la imagen.

Dentro de Docker, la API se conecta a MongoDB usando el nombre del servicio:

```text
mongo:27017
```

Desde la maquina local, la conexion a MongoDB se hace por:

```text
localhost:27017
```

## Requisitos

- Python 3.13+
- `uv`
- Docker Desktop
- Docker Compose

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

DATABASE_URL=mongodb://admin:9009@localhost:27017/?authSource=admin
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

Desde la raiz del proyecto:

```powershell
cd "h:\Mi unidad\Facultad\Facultad_2026\Desarrollo\Proyecto\pdf-extractext"
```

Levantar MongoDB:

```powershell
docker compose -f docker-compose.db.yml up -d
```

Construir y levantar la API:

```powershell
docker compose up -d --build
```

Verificar contenedores:

```powershell
docker compose -f docker-compose.db.yml ps
docker compose ps
```

Ver logs de la API:

```powershell
docker logs -f pdf-extractext-api-1
```

Apagar todo:

```powershell
docker compose -f docker-compose.db.yml -f docker-compose.yml down
```

## Ejecucion local

Tambien se puede correr la API localmente, usando MongoDB en Docker.

Instalar dependencias:

```powershell
uv sync --extra dev
```

Levantar MongoDB:

```powershell
docker compose -f docker-compose.db.yml up -d
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

Resultado esperado actual:

```text
72 passed
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

Reconstruir la API:

```powershell
docker compose up -d --build --force-recreate
```

Ver logs de MongoDB:

```powershell
docker logs -f pdf-extractext-mongo-1
```

Ver logs de la API:

```powershell
docker logs -f pdf-extractext-api-1
```

Apagar solo la API:

```powershell
docker compose down
```

Apagar solo MongoDB:

```powershell
docker compose -f docker-compose.db.yml down
```

Borrar tambien el volumen de MongoDB:

```powershell
docker compose -f docker-compose.db.yml down -v
```
