# Revision Contra el Enunciado

## Resumen

Estado general del proyecto frente al enunciado del profesor:

- cumplimiento principal: `si`
- cumplimiento parcial o explicable en clase: `si`
- bloqueo tecnico actual: `no`

## Requisito por requisito

### 1. El cliente debe enviar un archivo PDF

Estado: `cumplido`

Como se resuelve:

- `POST /api/v1/documents`
- recibe `multipart/form-data`
- campos: `name` + `file`

## 2. Extraer el texto del PDF

Estado: `cumplido`

Como se resuelve:

- el service usa `pypdf`
- la extraccion se hace durante el alta
- el resultado se guarda en `extracted_text`

Nota:

- si el PDF es escaneado o solo tiene imagenes, el texto puede quedar vacio porque no hay OCR

## 3. Persistir el contenido en una base no relacional

Estado: `cumplido`

Como se resuelve:

- se usa MongoDB
- el repository trabaja con `pymongo`
- las colecciones principales son `documents` y `counters`

## 4. Guardar checksum del archivo

Estado: `cumplido`

Como se resuelve:

- se calcula SHA-256
- se guarda en el campo `checksum`

## 5. No permitir documentos duplicados

Estado: `cumplido`

Como se resuelve:

- antes de persistir, se busca por checksum
- si ya existe, la API responde `400`

## 6. CRUD de documentos persistidos

Estado: `cumplido`

Endpoints:

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `PUT /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`

## 7. Validar formato y tamano del PDF

Estado: `cumplido`

Como se resuelve:

- validacion de extension `.pdf`
- validacion de firma `%PDF-`
- validacion de tamano maximo con `MAX_PDF_SIZE_BYTES`

## 8. El PDF no debe persistirse temporalmente mientras se procesa

Estado: `cumplido`

Como se resuelve:

- la validacion
- el checksum
- y la extraccion

se realizan en memoria a partir de los bytes del upload.

## 9. Python como lenguaje

Estado: `cumplido`

## 10. FastAPI para la API

Estado: `cumplido`

## 11. uv como manejador de dependencias

Estado: `cumplido`

Como se resuelve:

- el proyecto puede instalarse con `uv sync --extra dev`
- tambien se dejo opcion con `pip` para facilitar pruebas del grupo

## 12. TDD

Estado: `cumplido de forma razonable`

Como se resuelve:

- hay suite automatizada con `pytest`
- los tests cubren alta, validaciones, duplicados, CRUD y salud de la API

Resultado esperado actual:

- `16 passed`

## 13. Uso de GitHub Project

Estado: `externo al codigo`

Como explicarlo:

- no es algo que se valide dentro del repositorio de la API
- depende de la organizacion del equipo en GitHub

## 14. Aplicacion de principios KISS, DRY, SOLID y 12 Factor

Estado: `cumplido de forma defendible`

Argumentos:

- `KISS`: flujo principal sencillo
- `DRY`: validacion y checksum centralizados en el service
- `SOLID`: separacion en router, service y repository
- `12 Factor`: configuracion por variables de entorno

## Conclusiones para defender en clase

Lo mas fuerte para remarcar:

1. El flujo principal pedido por el enunciado esta implementado.
2. La persistencia ya es no relacional con MongoDB.
3. La API recibe archivos reales y no depende de rutas manuales.
4. El procesamiento se hace en memoria.
5. El checksum permite evitar duplicados por contenido.

## Limitacion conocida

La API no implementa OCR.

Eso significa que:

- PDFs con texto digital: se procesan bien
- PDFs escaneados o con imagenes: pueden devolver `extracted_text` vacio

Eso no invalida el flujo principal del trabajo, pero conviene explicarlo si aparece en la demo.
