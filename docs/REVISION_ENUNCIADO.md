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

- el service usa `pypdfium2` (PDFium, el motor de Chrome)
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

se realizan en memoria a partir de los bytes del upload. En `POST /extract`
tambien el multipart queda en memoria (Starlette guarda en disco las partes de
mas de 1 MB, y eso se desactivo), y un test falla si un upload pasa a disco.

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

Estado: `cumplido`

Como se resuelve:

- hay suite automatizada con `pytest` que corre en CI en cada push
- los tests cubren alta, validaciones, duplicados, CRUD, `/extract`, Markdown,
  liveness/readiness, logs y el proceso de administracion
- las funcionalidades nuevas muestran el ciclo en el historial: un commit con
  los tests en rojo (`test: ... (rojo)`) y despues el que los pone en verde

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
- `12 Factor`: configuracion por variables de entorno, procesos sin estado en
  `/extract`, logs a stdout y procesos de administracion con el mismo codigo

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

## Trabajo practico de carga y estres

El TP posterior (endpoint `POST /extract`, 5 replicas, pruebas con k6 y
Vegeta) se sigue en [PLAN-TP.md](PLAN-TP.md) y sus mediciones en
[INFORME-TP.md](INFORME-TP.md).

### Chequeo contra la consigna del TP

| Requisito | Donde se cumple |
|---|---|
| `POST /extract` con PDF en multipart o body crudo | `app/api/routers/extract.py`, tests en `tests/api/test_extract.py` |
| `200` con `{"content": <Markdown>, "page_count": N}` | `app/core/markdown.py`; los 4 PDFs oficiales en los tests |
| Imagen Docker y `docker compose up --build` | `docker/Dockerfile`, `docker-compose.yml` de la raiz |
| Hasta 5 replicas con limites explicitos | 5 replicas de 1 CPU y 1 GB; Traefik 1 CPU y 512 MB |
| PDFs oficiales en `tests/stress/pdfs` | los 4 PDFs, versionados como binarios |
| Script de k6 para el spike | `tests/stress/spike.js` (perfil del profesor, SLO como thresholds) |
| Script de Vegeta para la carga fija | `tests/stress/vegeta.sh` y `vegeta.ps1` |
| Pista 1: extraer sin disco ni buffers duplicados | body y multipart en memoria (test que falla si algo va a disco); PDFium lee de los bytes |
| Pista 2: backpressure con 429/503 | cola de 30 y tiempo util de 28 s, `503` con `Retry-After` ([ADR 0003](decisions/0003-contrapresion.md)) |
| Pista 3: replicas detras de un reverse proxy | Traefik con round robin y reintentos |
| Pista 4: separar HTTP de la extraccion | endpoint async; extraccion en el threadpool, una por vez |
| Twelve-Factor: config, port binding, sin estado, logs a stdout | informe, seccion 2 |
| Informe: arquitectura, cuello de botella, antes/despues, proceso de investigacion | [INFORME-TP.md](INFORME-TP.md), secciones 2 a 5 |
