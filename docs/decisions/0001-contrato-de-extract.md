# ADR 0001: contrato de `POST /extract`

- Estado: aceptada
- Fecha: 2026-10-02 (version 1.2.0)

## Contexto

La consigna del TP exige `POST /extract`, que recibe un PDF (multipart o
binario en el body) y responde `200` con `{"content": <Markdown>,
"page_count": N}`. El servicio ya tenia un CRUD de documentos
(`/api/v1/documents`) que guarda cada PDF en MongoDB con checksum y control de
duplicados: los scripts de carga mandan siempre los mismos 4 PDFs, asi que con
ese flujo responderian `409` desde el segundo request.

## Decision

- `/extract` es un endpoint **nuevo y sin estado**: valida, extrae y responde.
  No calcula checksum, no busca duplicados y no escribe en la base. El CRUD
  sigue igual.
- Acepta las dos formas de la consigna: body crudo (la firma `%PDF-` decide,
  no el `Content-Type`, porque curl manda `form-urlencoded` por defecto) y
  campo `file` de un multipart. En los dos casos el PDF se lee en memoria y se
  corta apenas supera el limite (con `Content-Length`, antes de leer).
- Va en la raiz (`/extract`), no bajo `/api/v1`, porque asi lo piden los
  scripts del profesor.
- Errores en RFC 9457 (problem details), como el resto del servicio: `400` no
  es PDF, `413` demasiado grande, `422` PDF ilegible, `503` saturado.
- Modo **solo extractor** (`DOCUMENTS_API_ENABLED=false`): las replicas del TP
  arrancan sin MongoDB y su `/health` no depende de la base.

## Alternativas descartadas

- Reusar `POST /api/v1/documents`: cambia el contrato existente (`201` y otro
  cuerpo) y persiste cada request, con duplicados y escrituras que no aportan
  nada a la carga.
- Endpoint aparte en otro servicio: mas codigo duplicado (validacion,
  extraccion) para el mismo motor.

## Consecuencias

- Las replicas son intercambiables (12-Factor VI): se escalan y se reintentan
  requests sin coordinacion (ver [0005](0005-tolerancia-a-fallos.md)).
- Agregar un endpoint sin romper nada es un cambio MINOR (1.1.0 -> 1.2.0).
- El mismo PDF se procesa todas las veces: no hay cache. Cachear por checksum
  daria miles de req/s en el benchmark (son siempre los mismos 4 PDFs), pero
  seria aprovechar la prueba y no mejorar el servicio.
