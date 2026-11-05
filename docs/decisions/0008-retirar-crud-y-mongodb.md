# ADR 0008: retirar el CRUD y MongoDB

- Estado: aceptada
- Fecha: 2026-11-05 (version 2.0.0)
- Issue: #31

## Contexto

Hasta la 1.4.0 el servicio tenia dos responsabilidades:

- `POST /extract`: recibir un PDF y devolver su texto, sin estado (ADR 0001).
- Un CRUD en `/api/v1/documents` que extraia el texto **y** guardaba el
  documento en MongoDB, con checksum unico.

`DOCUMENTS_API_ENABLED` elegia el modo: con `true` (el default) se sumaban el
CRUD y una readiness que dependia de MongoDB; con `false` el servicio era solo
extractor, que es como corrian las 5 replicas del TP.

El equipo separo la persistencia en su propio microservicio, **document-store**,
y el orquestador coordina los dos (ADR-0003 de `orchestrator-service`): pide el
texto a `POST /extract`, calcula el checksum y guarda el documento en
document-store, que responde `409` si el checksum se repite. El flujo completo
quedo integrado en el stack de `infrastructure` (issue #1 de ese repo) y
probado punta a punta (issue #22 del orquestador). Desde entonces nadie llama
al CRUD de este servicio: el orquestador solo usa `/extract` y los scripts de
`tests/stress` tambien.

## Decision

pdf-extractext hace solamente **PDF -> texto extraido**:

- Se borran el router, el service, el repositorio, el modelo y los schemas del
  CRUD, la conexion a MongoDB (`app/utils/database.py`), el comando de limpieza
  (`app/admin/clear_documents.py`) y los validadores y excepciones que solo
  usaba el CRUD (nombre, filename, extension, paginacion, checksum, documento
  inexistente, duplicado, reproceso).
- Desaparece `DOCUMENTS_API_ENABLED`: el modo solo extractor es el unico. La
  readiness siempre responde sin consultar dependencias.
- Se quitan `pymongo` y `mongomock`, Mongo de los compose del repo y
  `docker/docker-compose.db.yml`.
- `POST /extract`, la contrapresion y el motor de extraccion no cambian.
- `Settings` ya ignoraba variables desconocidas (`extra="ignore"`): el stack de
  `infrastructure` todavia le pasa `DATABASE_URL`, `DATABASE_NAME` y
  `DATABASE_TIMEOUT_MS` y el servicio arranca igual. Lo prueba
  `tests/api/test_extraction_only_mode.py`.
- Version **2.0.0**: quitar endpoints publicos rompe a quien los usara
  (Semantic Versioning, MAJOR).

## Alternativas consideradas

| Alternativa | Por que no |
|---|---|
| Mantener el flag con `false` por defecto | El CRUD seguiria en el codigo sin uso: habria que mantener sus tests, su dependencia de MongoDB y sus vulnerabilidades, y cualquiera podria volver a activarlo y tener dos lugares donde se guardan documentos, con datos que no coinciden. |
| Deprecar sin borrar (responder `410 Gone` o avisar en los logs) | Sirve cuando hay clientes externos que necesitan tiempo para migrar. Aca el unico cliente era el orquestador y ya migro (issue #21 del orquestador): deprecar solo posterga el borrado. |
| Que pdf-extractext llame a document-store | Mezcla las responsabilidades que se quisieron separar y lo acopla a otro servicio. Coordinar es trabajo del orquestador. |

## Consecuencias

- Una sola responsabilidad y ningun backing service: el servicio arranca sin
  nada alrededor, `/ready` no depende de nada y una caida de MongoDB no lo
  afecta.
- Menos codigo y menos dependencias (`pymongo`, `dnspython`, `mongomock`) que
  mantener y auditar con `pip-audit`.
- Quien llamara a `/api/v1/documents` recibe `404`. Para guardar y consultar
  documentos se usa el orquestador.
- Volver a una 1.x en el stack del TP necesita `DOCUMENTS_API_ENABLED=false`
  (ver `docs/RUNBOOK.md`).
- Queda pendiente en `infrastructure` (no se toca en este issue): quitar
  `DATABASE_*` y `depends_on: mongo` del servicio `pdf-extractext` y subir
  `PDF_EXTRACTEXT_TAG` a `2.0.0`.
- Los informes y mediciones del CRUD (`docs/PRUEBAS-CARGA-CRUD.md`,
  `tests/load/vegeta/EVALUACION.md`) quedan como registro historico; sus
  scripts se borraron y siguen en el historial de git (tag `v1.4.0`).
