# Guia de Arquitectura

## Vision general

El proyecto sigue una arquitectura de 3 capas con influencia parcial de Hexagonal:

```text
CRUD:            Router -> DocumentService   -> Repository -> MongoDB
POST /extract:   Router -> ExtractionService -> app/core (PDFium + Markdown)
```

El CRUD registra documentos y los guarda en MongoDB. `POST /extract` es el
endpoint del TP de carga: valida y extrae sin repositorio, sin checksum y sin
escribir nada, asi sus replicas no comparten estado.

> Clasificacion honesta: **no es Clean Architecture ni Onion Architecture**.
> Es una arquitectura en 3 capas clasica, con una influencia parcial del estilo
> Hexagonal (Ports & Adapters) reflejada en la existencia de `DocumentRepository`
> como unico punto de acceso a la persistencia. Sin embargo, no existe una
> separacion estricta entre dominio e infraestructura (ver la seccion
> "Decision de arquitectura: acoplamiento Modelo/Persistencia").

## 1. Capa de presentacion

Ubicacion: `app/api/routers/`

Responsabilidades:

- recibir requests HTTP
- validar parametros de entrada
- transformar errores de negocio en respuestas HTTP
- devolver respuestas JSON

Archivos principales:

- `app/api/routers/document.py`: CRUD de documentos
- `app/api/routers/extract.py`: `POST /extract`, PDF crudo o multipart
- `app/api/uploads.py`: lectura de uploads para los dos routers. El PDF queda
  en memoria (nunca en un archivo temporal) y un body demasiado grande se
  rechaza con 413 por `Content-Length` o apenas se pasa del limite
- `app/api/dependencies.py`: la compuerta de admision del proceso, que
  comparten `/extract` y el alta de documentos (los dos usan PDFium)
- `app/utils/problem_details.py`: traduce cada error de dominio a su respuesta
  RFC 9457 (400, 409, 413, 422, 503); los routers no atrapan errores
  genericos

## 2. Capa de logica de negocio

Ubicacion: `app/services/`

Responsabilidades:

- validar el nombre del documento
- validar que el archivo sea PDF
- controlar tamano maximo
- calcular checksum
- evitar duplicados
- pedir la extraccion al nucleo (`app/core/pdf_extraction.py`)
- definir el flujo de actualizacion y borrado

Archivos principales:

- `app/services/document_service.py`: alta, consulta, actualizacion y borrado
- `app/services/extraction_service.py`: valida y extrae para `POST /extract`, sin
  persistir; registra cada extraccion en el log (bytes, paginas, ms)
- `app/services/admission.py`: la compuerta de admision de cada proceso (cola
  acotada, una extraccion por vez, el PDF mas liviano primero con limite de
  espera, tiempo util con margen). Avisa lo que pasa a un observador
  (`GateObserver`) sin depender de Prometheus
- `app/utils/metrics.py`: el observador que publica las metricas de la
  compuerta en `GET /metrics` (formato Prometheus)

Los dos services reciben su motor por constructor: `ExtractionService` un
`PdfExtractor` (Markdown) y `DocumentService` una funcion de texto plano. Se
pueden probar con motores falsos y cambiar de motor sin tocar los routers.

## Nucleo

Ubicacion: `app/core/`

Reglas puras, sin FastAPI ni MongoDB, testeables sin levantar nada:

- `validators.py`: nombre, extension, firma `%PDF-` y tamano
- `exceptions.py`: errores de dominio; `/extract` los traduce a 400, 413 y 422
- `pdf_extraction.py`: texto y cantidad de paginas con `pypdfium2` (PDFium, el
  motor de Chrome). PDFium no es thread-safe: se serializa con un lock por
  proceso, y el paralelismo viene de los procesos de uvicorn y las replicas.
  El motor esta detras de la interfaz `PdfExtractor` (`PdfiumExtractor` por
  defecto): `ExtractionService` la recibe por constructor, asi otro motor se
  prueba y se mide sin tocar el servicio ni el router
- `markdown.py`: convierte las lineas de cada pagina a Markdown; los titulos
  salen de la altura de las letras comparada con la del cuerpo

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

## Decision de arquitectura: acoplamiento Modelo/Persistencia

### Estado actual

La clase `Document` (`app/models/document.py`) actua simultaneamente como:

- **entidad de dominio**: representa el concepto de negocio "documento PDF procesado" (nombre, checksum, texto extraido, tamano, etc.);
- **documento de base de datos**: su estructura es la que se persiste directamente en MongoDB a traves del repository.

Es decir, no existe una separacion entre un "modelo de dominio puro" y un "modelo de persistencia" propios de Clean Architecture o Onion Architecture.

### Esto es una decision consciente, no un descuido tecnico

Este acoplamiento es un **limite aceptado de forma deliberada** para el alcance actual del proyecto. Las razones son:

- **Simplicidad (KISS)**: para un CRUD con un solo agregado (`Document`), mantener dos modelos y un mapper entre ellos agregaria complejidad sin beneficio real.
- **Alcance acotado**: el dominio no tiene logica rica ni invariantes complejas que exijan aislar el modelo de la forma de persistencia.
- **Costo/beneficio**: el costo de desacoplar hoy supera el riesgo de migracion futura, dado que el seam ya esta previsto (ver abajo).

### Seam (punto de desacoplamiento futuro)

Aunque el modelo esta acoplado a la persistencia, **la frontera de desacoplamiento ya existe**: es `DocumentRepository` (`app/repositories/document_repository.py`).

Si en el futuro se necesita separar dominio de persistencia, el cambio es localizado:

1. Crear un modelo de dominio puro y un modelo de persistencia (o schema) independientes.
2. Modificar unicamente los metodos `_serialize` / `_deserialize` del repository para que actuen como mappers entre ambos modelos.

El resto de la aplicacion (routers, services) no deberia requerir cambios, porque ya consume al repository como unica via de acceso a datos. Este es el punto donde la influencia Hexagonal del diseno paga su deuda tecnica.

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

1. El cliente envia `name` y `file` (multipart).
2. El router pide lugar en la compuerta de admision (503 si la cola esta
   llena) y lee el archivo en memoria, con limite de tamano (413).
3. El service valida extension, firma y tamano.
4. El service calcula el checksum.
5. Si el checksum ya existe, rechaza el documento con 409 (tambien si dos
   uploads iguales llegan a la vez y los frena el indice unico de MongoDB).
6. Si el PDF es valido, extrae el texto en memoria.
7. El repository guarda el documento en MongoDB.
8. La API devuelve el documento ya procesado.

## Flujo de extraccion

Para documentos nuevos, la extraccion ya se realiza en el alta.

`POST /api/v1/documents/{id}/extract`:

- devuelve el texto ya almacenado si el documento ya fue procesado
- conserva compatibilidad con documentos viejos que pudieran requerir reprocesamiento

`POST /extract` (sin estado) es otro flujo: recibe el PDF, lo valida, devuelve
`{"content": <Markdown>, "page_count": N}` y no guarda nada.

```mermaid
flowchart LR
    C[Cliente: k6 / Vegeta] -->|POST /extract| T[Traefik<br/>round robin + reintentos]
    T --> R[5 replicas<br/>1 CPU, 1 GB y 1 proceso cada una]
    subgraph Replica [dentro de cada replica]
        G[AdmissionGate<br/>cola de 60, tiempo util 25 s] --> E[ExtractionService] --> P[PdfExtractor<br/>PDFium + Markdown]
    end
    R --> G
    T -.metricas.-> PR[Prometheus] --> GR[Grafana]
```

1. `AdmissionGate` admite el request si la cola de la replica tiene lugar; si
   no, 503 con `Retry-After` antes de leer el PDF.
2. Se lee el body en memoria (crudo o multipart) y se espera el turno: una
   extraccion por vez por proceso.
3. Si el cliente ya se fue o el request espero mas que su tiempo util, no se
   procesa. Si no, `ExtractionService` valida y el motor extrae.

## Modos de despliegue

- **Servicio completo** (`DOCUMENTS_API_ENABLED=true`, el default): CRUD +
  `POST /extract`, necesita MongoDB. Es el que usa el repo `infrastructure`.
- **Solo extractor** (`DOCUMENTS_API_ENABLED=false`): solo `POST /extract`, no
  crea indices ni se conecta a MongoDB. Es el de las 5 replicas del TP
  (`docker-compose.yml` de la raiz).

## Operacion

- `GET /health` (liveness): el proceso responde; no consulta dependencias. Lo
  usan los healthchecks de Docker, asi una caida de MongoDB no saca de servicio
  a las replicas de `POST /extract`.
- `GET /ready` (readiness): ademas verifica MongoDB (503 si no responde).
- Logs: una linea JSON por evento en stdout, incluidos los de uvicorn
  (`app/utils/structured_logging.py`, nivel por `LOG_LEVEL`).
- Administracion: `python -m app.admin.clear_documents` borra documentos con el
  mismo codigo y la misma configuracion que la API.
- Apagado ordenado: ante SIGTERM uvicorn deja de aceptar conexiones y termina
  lo que tiene en cola; Docker espera 35 s (`stop_grace_period`) antes de
  matarlo. Mientras tanto Traefik reintenta en otra replica.
- Caidas: `restart: unless-stopped` levanta la replica sola (~15 s hasta
  healthy) y Traefik reintenta en otra los requests que no llegaron a
  procesarse. Traefik es el punto unico de falla del stack del TP.
- Metricas: cada replica expone `GET /metrics` (cola, rechazos por motivo y
  tiempo de extraccion); el perfil `monitoreo` del compose las junta con las de
  Traefik en Prometheus y Grafana. Procedimientos en `docs/RUNBOOK.md`.
- Healthcheck: un socket con `python -S -I` cada 10 s (cada 1 s al arrancar).
  El anterior, con `urllib` cada 5 s, gastaba 12 % de un nucleo por replica.
- Conexiones: uvicorn mantiene las inactivas 120 s, mas que Traefik (90 s),
  para que Traefik nunca reuse una que se esta cerrando (502).

## Principios aplicados

- KISS: el flujo principal esta concentrado en un solo service
- DRY: el checksum y la validacion se centralizan
- SOLID: cada capa tiene una responsabilidad clara
- 12 Factor: configuracion por variables de entorno (III), procesos sin estado
  en `/extract` (VI), concurrencia por procesos y replicas (VIII), logs a stdout
  (XI) y procesos de administracion con el mismo codigo (XII)

## Dependencias relevantes

- FastAPI
- Pydantic
- PyMongo
- pypdfium2
- pytest
- mongomock

## Punto importante para clase

El proyecto ya no usa SQLite ni SQLAlchemy. Toda la persistencia actual se hace en MongoDB, que era uno de los requisitos del enunciado.

## Nota sobre `file_path`

El modelo interno todavia conserva un campo `file_path` por compatibilidad tecnica, pero en los documentos nuevos no representa una ruta real subida por el usuario.

Para los nuevos uploads se guarda solo una referencia logica interna tipo `memory://...`, ya que el procesamiento del PDF se realiza en memoria.

Se reviso si se puede quitar (2026-10-07): el orquestador no lo usa, pero
esta en la respuesta de la API, asi que quitarlo es un cambio incompatible
(version 2.0). Queda para decidirlo con el equipo.
