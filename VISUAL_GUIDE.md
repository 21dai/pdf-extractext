# Resumen Visual

## Flujo principal

```text
POST /api/v1/documents
        |
        v
  Router de FastAPI
        |
        v
  DocumentService
    - valida nombre
    - valida PDF
    - calcula checksum
    - evita duplicados
    - extrae texto en memoria
        |
        v
  DocumentRepository
        |
        v
      MongoDB
```

## Que entra

```text
multipart/form-data
- name
- file
```

## Que sale

```json
{
  "name": "Contrato",
  "original_filename": "contrato.pdf",
  "file_size": 12345,
  "id": 1,
  "checksum": "sha256...",
  "extracted_text": "texto del pdf",
  "is_processed": true,
  "created_at": "...",
  "updated_at": "..."
}
```

## Validaciones

```text
Archivo subido
   |
   +-> extension .pdf
   +-> firma %PDF-
   +-> tamano maximo
   +-> checksum unico
```

## Colecciones en MongoDB

```text
documents
  - id
  - name
  - original_filename
  - file_path (referencia logica interna)
  - checksum
  - file_size
  - extracted_text
  - is_processed
  - created_at
  - updated_at

counters
  - _id: document_id
  - value
```

## Endpoints

```text
GET    /                     info general
GET    /health               estado de API + Mongo
POST   /api/v1/documents     crear documento
GET    /api/v1/documents     listar documentos
GET    /api/v1/documents/{id}
PUT    /api/v1/documents/{id}
DELETE /api/v1/documents/{id}
POST   /api/v1/documents/{id}/extract
```

## Limitacion actual

```text
PDF con texto digital  -> extrae texto
PDF escaneado/imagen   -> puede devolver extracted_text vacio
```

Eso no significa que falle la API: significa que no hay OCR implementado.
