# Ejemplos de Uso

## 1. Crear un documento

### Swagger

En `POST /api/v1/documents` completar:

- `name`: nombre del documento
- `file`: seleccionar un PDF real

### curl

```bash
curl -X POST "http://localhost:8000/api/v1/documents" ^
  -H "accept: application/json" ^
  -H "Content-Type: multipart/form-data" ^
  -F "name=Contrato ejemplo" ^
  -F "file=@C:/ruta/contrato.pdf;type=application/pdf"
```

## 2. Respuesta esperada

```json
{
  "name": "Contrato ejemplo",
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

## 3. Documento duplicado

Si se vuelve a subir exactamente el mismo PDF, la API responde `400`.

Ejemplo de detalle:

```json
{
  "detail": "Ya existe un documento con el mismo checksum"
}
```

## 4. Listar documentos

```bash
curl "http://localhost:8000/api/v1/documents"
```

## 5. Obtener documento por ID

```bash
curl "http://localhost:8000/api/v1/documents/1"
```

## 6. Actualizar nombre

```bash
curl -X PUT "http://localhost:8000/api/v1/documents/1" ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Contrato actualizado\"}"
```

## 7. Eliminar documento

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/1"
```

## 8. Verificar salud del sistema

```bash
curl "http://localhost:8000/health"
```

Respuesta esperada:

```json
{
  "status": "ok",
  "database": "mongodb",
  "database_name": "pdf_extract"
}
```

## 9. Caso importante para explicar en clase

Si el PDF contiene solo imagenes o escaneos, `extracted_text` puede venir vacio.

Eso no implica un error del sistema:

- el upload funciona
- la validacion funciona
- el checksum se calcula
- MongoDB persiste el documento

La limitacion es que `pypdf` no hace OCR.
