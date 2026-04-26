# API de Extraccion de PDF

API construida con FastAPI y arquitectura de 3 capas para registrar PDFs, validar su contenido, evitar duplicados por checksum y extraer texto real. El proyecto procesa el PDF en memoria y persiste los metadatos y el texto extraido en MongoDB.

## Integrantes
- Gabriel Flores
- Lucas Martinez
- Daiana Galdeano
- Solange Parada
- Joaquin Antequeda
- Nicolas Santivañez

## Estado actual

- Upload real de archivos PDF con `multipart/form-data`
- Validacion de extension, firma PDF y tamano maximo
- Checksum SHA-256 para evitar duplicados
- Extraccion de texto con `pypdf`
- Persistencia en MongoDB
- Tests automatizados con `mongomock`
- Documentacion interactiva en `Swagger UI`

## Arquitectura

### 1. Capa de presentacion
- Ubicacion: `app/api/routers/`
- Responsabilidad: recibir requests HTTP y devolver responses

### 2. Capa de logica
- Ubicacion: `app/services/`
- Responsabilidad: validaciones, reglas de negocio y extraccion

### 3. Capa de datos
- Ubicacion: `app/repositories/`
- Responsabilidad: persistencia en MongoDB

## Documentacion util

- `START_HERE.md`: punto de entrada rapido
- `QUICKSTART.md`: arranque en pocos minutos
- `DEMO.md`: guion sugerido para mostrar en clase
- `REVISION_ENUNCIADO.md`: chequeo punto por punto contra el TP
- `ARCHITECTURE.md`: resumen de arquitectura actual
- `EJEMPLOS.md`: ejemplos de requests y respuestas
- `VISUAL_GUIDE.md`: vista visual del flujo principal

## Requisitos

- Python 3.13+
- `uv` disponible
- Docker Desktop con Docker Compose

## Instalacion

### Opcion recomendada con uv

```bash
cd pdf-extractext
uv sync --extra dev
copy .env.example .env
```

### Opcion alternativa con pip

```bash
cd pdf-extractext
python -m venv venv
venv\Scripts\activate
python -m pip install -e ".[dev]"
copy .env.example .env
```

## Arranque rapido con Mongo real

1. Levantar MongoDB con Docker:

```bash
docker compose up -d
```

2. Verificar que el contenedor este sano:

```bash
docker compose ps
```

3. Levantar la API:

```bash
python main.py
```

## URLs utiles

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health: `http://localhost:8000/health`

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
2. La API valida que sea un PDF real.
3. Se calcula el checksum.
4. Si el checksum ya existe, el documento se rechaza.
5. Si es valido, se extrae el texto en memoria.
6. Se guarda el documento en MongoDB.

## Limitacion conocida

Si el PDF contiene solo imagenes o escaneos, `extracted_text` puede venir vacio.

Eso no implica un error de la API. La extraccion actual usa `pypdf`, que obtiene texto digital, pero no realiza OCR.

## Ejemplo de uso con curl

```bash
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
  "created_at": "2026-04-25T23:56:47.157530Z",
  "updated_at": "2026-04-25T23:56:47.157530Z"
}
```

## Tests

```bash
python -m pytest -q
```

Resultado esperado:

```text
16 passed
```

## Variables de entorno

```env
APP_NAME=API de Extraccion de PDF
APP_VERSION=0.1.0
DEBUG=False
HOST=0.0.0.0
PORT=8000
DATABASE_URL=mongodb://localhost:27017
DATABASE_NAME=pdf_extract
DATABASE_TIMEOUT_MS=3000
MAX_PDF_SIZE_BYTES=10485760
API_V1_PREFIX=/api/v1
API_DOCS_URL=/docs
API_REDOC_URL=/redoc
API_OPENAPI_URL=/openapi.json
```

## Apagar Mongo

```bash
docker compose down
```

Para borrar tambien los datos locales:

```bash
docker compose down -v
```
