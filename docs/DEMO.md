# Guion de Demo

## Objetivo

Mostrar en pocos minutos que el servicio:

- recibe un PDF real
- valida el archivo
- extrae texto en memoria y lo devuelve en Markdown
- no guarda nada: es un extractor sin estado

Guardar el documento y rechazar duplicados ya no es trabajo de este servicio:
lo hace document-store, coordinado por el orquestador (ver "Demo del sistema
completo" al final y el [ADR-0008](decisions/0008-retirar-crud-y-mongodb.md)).

## Preparacion previa

Antes de la clase o la demo:

1. Tener Docker Desktop iniciado (solo para la demo del TP o del sistema
   completo; la API sola corre sin Docker).
2. Tener un PDF con texto seleccionable (sirven los de `tests/stress/pdfs/`).
3. Opcional: tener un PDF escaneado o con imagenes para explicar la limitacion sin OCR.

## Arranque

### 1. Levantar la API

```powershell
uv run python main.py
```

O en Docker, con `make up` (o
`docker compose --env-file .env -f docker/docker-compose.yml up -d --build`).
No hace falta levantar ninguna base de datos.

### 2. Abrir Swagger

Abrir en el navegador:

- `http://localhost:8000/docs`

## Orden recomendado para mostrar

### 1. Verificacion de salud

Endpoints:

- `GET /health` y `GET /ready`

Que decir:

- "Los dos responden `{"status": "ok"}`: el servicio no depende de ninguna base
  ni de otros servicios, asi que no hay nada mas que chequear."

### 2. Extraccion de un PDF real

Endpoint:

- `POST /extract` (en Swagger, el campo `file`)

```powershell
curl.exe -X POST http://localhost:8000/extract -H "Content-Type: application/pdf" --data-binary "@tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf"
```

Que decir:

- "Valida que sea un PDF real y extrae el texto en memoria: el archivo nunca
  se escribe a disco."
- "Los titulos salen de la altura de las letras."

Esperado:

- codigo `200`
- `content` con el Markdown
- `page_count: 16`

### 3. Sin estado

Mandar exactamente el mismo PDF otra vez.

Que decir:

- "Responde lo mismo: no guarda nada, no calcula checksum ni rechaza duplicados.
  Por eso se puede escalar en replicas sin estado compartido."

### 4. Errores claros

Mandar un archivo que no es PDF, por ejemplo un `.txt`.

Esperado:

- codigo `400` con `application/problem+json` (RFC 9457)

## Caso especial para explicar

Si subis un PDF escaneado o compuesto por imagenes, `content` puede venir vacio.

Que decir:

- "Eso no significa que la API falle."
- "Significa que el PDF no tenia texto digital extraible."
- "La extraccion usa `pypdfium2` y no implementa OCR."

## Cierre sugerido

Frase corta para cerrar:

> El servicio hace una sola cosa: recibe PDFs reales, valida formato y tamano y
> devuelve el texto en Markdown, en memoria y sin estado. Guardar los documentos
> es trabajo de document-store.

## Demo del TP de carga

1. `docker compose up --build -d` en la raiz: Traefik + 5 replicas de
   `POST /extract`. Mostrar el dashboard de Traefik en
   `http://localhost:8080/dashboard/` con las 5 replicas.
2. Mandar un PDF y mostrar el Markdown y el `page_count`:

```powershell
curl.exe -X POST http://127.0.0.1/extract -H "Content-Type: application/pdf" --data-binary "@tests/stress/pdfs/2020-Scrum-Guide-Spanish-Latin-South-American.pdf"
```

3. Correr el spike del profesor y mostrar la tabla por PDF y la comparacion
   con su benchmark (ver [tests/stress](../tests/stress/README.md)).

## Demo del sistema completo

El alta, la consulta y el rechazo de duplicados se muestran con el stack del
repo `infrastructure` (Traefik + orquestador + este servicio + document-store +
MongoDB), contra el orquestador:

```powershell
curl.exe -k -F "file=@documento.pdf" https://orchestrator.proyecto.localhost/api/v1/documents
```

- La primera vez responde `201` con el documento guardado.
- La segunda, con el mismo PDF, `409`: document-store ya tiene ese checksum.

Que decir:

- "El orquestador le pide el texto a pdf-extractext y lo guarda en
  document-store: cada servicio tiene una sola responsabilidad."
