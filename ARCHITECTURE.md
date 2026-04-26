# Guia de Arquitectura

## Vision general

El proyecto sigue una arquitectura de 3 capas:

```text
Router -> Service -> Repository -> MongoDB
```

## 1. Capa de presentacion

Ubicacion: `app/api/routers/`

Responsabilidades:

- recibir requests HTTP
- validar parametros de entrada
- transformar errores de negocio en respuestas HTTP
- devolver respuestas JSON

Archivo principal:

- `app/api/routers/document.py`

## 2. Capa de logica de negocio

Ubicacion: `app/services/`

Responsabilidades:

- validar el nombre del documento
- validar que el archivo sea PDF
- controlar tamano maximo
- calcular checksum
- evitar duplicados
- extraer texto con `pypdf`
- definir el flujo de actualizacion y borrado

Archivo principal:

- `app/services/document_service.py`

## 3. Capa de acceso a datos

Ubicacion: `app/repositories/`

Responsabilidades:

- crear documentos en MongoDB
- buscar por `id`, `name` y `checksum`
- actualizar documentos
- eliminar documentos
- manejar el contador secuencial de IDs

Archivo principal:

- `app/repositories/document_repository.py`

## Persistencia

La aplicacion usa MongoDB.

Colecciones:

- `documents`
- `counters`

Indices principales:

- `id` unico
- `checksum` unico
- `name` no unico

## Flujo del alta

1. El cliente envia `name` y `file`.
2. El router lee los bytes del archivo.
3. El service valida extension, firma y tamano.
4. El service calcula el checksum.
5. Si el checksum ya existe, rechaza el documento.
6. Si el PDF es valido, extrae el texto en memoria.
7. El repository guarda el documento en MongoDB.
8. La API devuelve el documento ya procesado.

## Flujo de extraccion

Para documentos nuevos, la extraccion ya se realiza en el alta.

El endpoint `/extract`:

- devuelve el texto ya almacenado si el documento ya fue procesado
- conserva compatibilidad con documentos viejos que pudieran requerir reprocesamiento

## Principios aplicados

- KISS: el flujo principal esta concentrado en un solo service
- DRY: el checksum y la validacion se centralizan
- SOLID: cada capa tiene una responsabilidad clara
- 12 Factor: la configuracion se maneja por variables de entorno

## Dependencias relevantes

- FastAPI
- Pydantic
- PyMongo
- pypdf
- pytest
- mongomock

## Punto importante para clase

El proyecto ya no usa SQLite ni SQLAlchemy. Toda la persistencia actual se hace en MongoDB, que era uno de los requisitos del enunciado.

## Nota sobre `file_path`

El modelo interno todavia conserva un campo `file_path` por compatibilidad tecnica, pero en los documentos nuevos no representa una ruta real subida por el usuario.

Para los nuevos uploads se guarda solo una referencia logica interna tipo `memory://...`, ya que el procesamiento del PDF se realiza en memoria.
