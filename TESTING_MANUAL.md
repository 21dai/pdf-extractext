# Testing Manual - Document Service

## Prueba 1 - Subir un PDF válido
**Endpoint:** POST /api/v1/documents
**Resultado:**  Texto extraído y guardado en MongoDB con checksum generado.

## Prueba 2 - Subir el mismo PDF dos veces
**Endpoint:** POST /api/v1/documents
**Resultado:**  Rechazado con error 400: "Ya existe un documento con el mismo checksum"

## Prueba 3 - Subir un archivo que no es PDF
**Endpoint:** POST /api/v1/documents
**Resultado:**  Rechazado con error 400: "Solo se permiten archivos PDF"

## Prueba 4 - Subir un PDF mayor a 10MB
**Endpoint:** POST /api/v1/documents
**Resultado:**  Rechazado con error 400: "El PDF supera el tamaño máximo permitido de 10485760 bytes"

## Prueba 5 - Update
**Endpoint:** PUT /api/v1/documents/1
**Resultado:**  Nombre actualizado correctamente, código 200.

## Prueba 6 - Delete
**Endpoint:** DELETE /api/v1/documents/1
**Resultado:**  Documento eliminado correctamente, código 204.