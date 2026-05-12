# Checklist de Validacion

## Instalacion

- [ ] Python 3.13+ instalado
- [ ] Docker Desktop funcionando
- [ ] Dependencias instaladas con `uv sync --extra dev` o `python -m pip install -e ".[dev]"`
- [ ] Archivo `.env` creado a partir de `.env.example`

## MongoDB

- [ ] `docker compose up -d` ejecutado
- [ ] `docker compose ps` muestra `mongodb` levantado
- [ ] `GET /health` responde `200`

## API

- [ ] `python main.py` inicia sin errores
- [ ] Swagger disponible en `http://localhost:8000/docs`
- [ ] `GET /` devuelve informacion basica
- [ ] `GET /health` devuelve estado `ok`

## Flujo principal

- [ ] `POST /api/v1/documents` acepta `name` + `file`
- [ ] El alta rechaza archivos que no son PDF
- [ ] El alta rechaza duplicados por checksum
- [ ] El alta devuelve `is_processed: true`
- [ ] El alta devuelve `original_filename`
- [ ] El alta devuelve `extracted_text`

## CRUD

- [ ] `GET /api/v1/documents` lista documentos
- [ ] `GET /api/v1/documents/{id}` trae un documento por ID
- [ ] `PUT /api/v1/documents/{id}` actualiza el nombre
- [ ] `PUT /api/v1/documents/{id}` rechaza nombre vacio
- [ ] `DELETE /api/v1/documents/{id}` elimina el documento
- [ ] `POST /api/v1/documents/{id}/extract` devuelve el texto almacenado

## Tests

- [ ] `python -m pytest -q` ejecuta correctamente
- [ ] Resultado esperado: `16 passed`

## Demo de clase

- [ ] Mongo levantado con Docker
- [ ] API levantada con `python main.py`
- [ ] Swagger abierto
- [ ] Un PDF con texto seleccionable listo para subir
- [ ] Un PDF repetido listo para demostrar rechazo por checksum
