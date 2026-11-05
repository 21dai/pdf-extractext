# Guia de desarrollo

Detalles para trabajar en el servicio: estructura de Docker y versionado,
ejemplos con curl, calidad de codigo y comandos utiles. Lo basico para
levantarlo esta en el [README](../README.md).

## Sin persistencia

El servicio no tiene base de datos: recibe el PDF, extrae el texto en memoria
y lo devuelve. Guardar documentos (con su checksum, sin duplicados) es trabajo
de **document-store**, y el que los coordina es el orquestador: llama a
`POST /extract` de este servicio y despues a `POST /api/v1/documents` de
document-store.

Hasta la 1.4.0 este servicio guardaba los documentos en MongoDB (colecciones
`documents` y `counters`) y exponia un CRUD en `/api/v1/documents`. Se retiro
en la 2.0.0: ver [ADR-0008](decisions/0008-retirar-crud-y-mongodb.md).

## Docker

### Estructura

Los archivos de infraestructura Docker se centralizaron en la carpeta `docker/` para mantener la raiz del proyecto limpia:

| Archivo original | Nueva ubicacion |
|------------------|-----------------|
| `Dockerfile` | `docker/Dockerfile` |
| `docker-compose.yml` | `docker/docker-compose.yml` |

`.dockerignore` permanece en la raiz y ahora ignora el directorio `docker/` completo.

El servicio no tiene backing services: ni `docker/docker-compose.yml` ni el
`docker-compose.yml` de la raiz levantan una base de datos. La configuracion
sale de `.env` (factor III de 12-factor); cambiar de entorno es solo editar
`.env`, sin tocar ningun archivo versionado.

### Versionado de la imagen (factor 5: build, release, run)

La imagen de la API se taguea con `IMAGE_TAG` (variable definida en `.env`), nunca con `latest` como release real:

```yaml
image: pdf-extractext:${IMAGE_TAG:-latest}
```

`latest` queda solo como valor por defecto de conveniencia si no se define `IMAGE_TAG` (por ejemplo, en una build local rapida). Para una release real:

- `IMAGE_TAG` debe coincidir con `APP_VERSION` (definida tambien en `pyproject.toml` y `app/config/settings.py`).
- Se sigue [Semantic Versioning](https://semver.org/lang/es/) (`MAJOR.MINOR.PATCH`):

  | Numero | Nombre | Cuando se incrementa |
  |--------|--------|----------------------|
  | **1**.0.0 | MAJOR | Cambios que rompen compatibilidad (ej. se modifica la forma de un endpoint existente). |
  | 1.**0**.0 | MINOR | Funcionalidad nueva sin romper lo existente (ej. un endpoint nuevo). |
  | 1.0.**0** | PATCH | Correccion de bugs, sin agregar funcionalidad ni romper nada. |

- La version actual es `2.0.0`. La `1.0.0` fue la primera release estable; la
  `1.0.1` sumo el hardening del contenedor (issue #18), sin cambios de comportamiento;
  la `1.1.0` cambia la extraccion a `pypdfium2` (unas 15 veces mas rapida) y agrega
  `WEB_CONCURRENCY` para correr varios procesos. Es MINOR porque mejora sin romper
  nada: mismos endpoints, mismas respuestas.
- La `1.2.0` agrega `POST /extract` (Markdown + `page_count`, sin estado) y
  `DOCUMENTS_API_ENABLED` para correr el servicio solo como extractor. Tambien es
  MINOR: el CRUD responde exactamente igual.
- La `1.3.0` agrega la contrapresion de `/extract` (cola acotada con
  `EXTRACT_MAX_PENDING`, tiempo util con `EXTRACT_MAX_WAIT_SECONDS`, 503 con
  `Retry-After`), `/ready`, logs JSON y el comando de limpieza de documentos.
  MINOR: configuraciones nuevas con valores por defecto, sin romper nada.
- La `1.3.1` corrige el tiempo util: ademas de lo que espero, cuenta lo que va
  a tardar la extraccion, asi nada termina despues del timeout del cliente.
  PATCH: correccion de un bug, sin cambiar la API.
- La `1.3.2` hace pesimista el chequeo del tiempo util (promedio mas 4 desvios
  del tiempo de extraccion, como el temporizador de TCP) y sube la cola a 60
  por replica: en Vegeta, de ~22 % a ~30 % de exito sin timeouts. PATCH.
- La `1.3.3` baja el tiempo util a 25 s: mismo exito en Vegeta y ningun
  timeout en tres corridas (con 28 s quedaban algunos sueltos). PATCH.
- La `1.3.4` corrige el alta de documentos (el PDF ya no pasa a disco, limite
  de tamano sin leerlo entero, duplicados con `409`), CORS configurable y el
  keep-alive de uvicorn mayor que el de Traefik (sin `502` sueltos). PATCH.
- La `1.4.0` agrega `GET /metrics` (cola, rechazos y tiempo de extraccion de
  cada replica), atiende primero el PDF mas liviano (`EXTRACT_QUEUE_ORDER`),
  pasa el alta de documentos por la misma compuerta que `/extract`, hace mas
  liviano el healthcheck y actualiza dependencias con vulnerabilidades
  conocidas. MINOR: endpoint y configuraciones nuevas, sin romper nada.
- La `2.0.0` retira el CRUD `/api/v1/documents`, MongoDB y
  `DOCUMENTS_API_ENABLED`: el servicio solo expone `POST /extract`, que no
  cambia. **MAJOR**: quitar endpoints publicos rompe a quien los usara. La
  persistencia queda en document-store
  ([ADR-0008](decisions/0008-retirar-crud-y-mongodb.md)).

Cada vez que se cierra una nueva release hay que subir `APP_VERSION` (en `pyproject.toml`, `app/config/settings.py` y `.env`) y reconstruir la imagen con ese mismo `IMAGE_TAG`, de forma que cada version del codigo quede asociada a una imagen Docker distinta e identificable, en vez de pisar siempre la misma imagen `latest`. Cada release tiene ademas su tag de git (`v1.0.0`, `v1.3.0`, ...): `git checkout vX.Y.Z` reconstruye exactamente esa version.

## Flujo principal

1. El cliente (el orquestador, o k6 y Vegeta en el TP) manda el PDF a
   `POST /extract`, como body crudo o como campo `file` de un multipart.
2. La compuerta de admision lo acepta o responde `503` con `Retry-After`.
3. La API lee el archivo en memoria, con limite de tamanio (`413`).
4. Se valida que no este vacio y que empiece con `%PDF-` (`400`).
5. Se extrae el texto desde memoria con `pypdfium2` y se arma el Markdown
   (`422` si PDFium no puede leerlo).
6. La API devuelve `{"content", "page_count"}`. No se guarda nada.

## Ejemplo con curl

En PowerShell hay que escribir `curl.exe`: `curl` a secas es un alias de
`Invoke-WebRequest`, que no acepta estos parametros y ademas pide confirmacion.
El caracter de continuacion de linea en PowerShell es la comilla invertida.

Con el PDF como body crudo:

```powershell
curl.exe -X POST "http://localhost:8000/extract" `
  -H "Content-Type: application/pdf" `
  --data-binary "@C:/ruta/al/archivo.pdf"
```

O como multipart (`curl` arma solo el `Content-Type` con el `boundary`):

```powershell
curl.exe -X POST "http://localhost:8000/extract" `
  -F "file=@C:/ruta/al/archivo.pdf;type=application/pdf"
```

Tambien se puede probar sin la terminal, desde Swagger UI en
<http://localhost:8000/docs>, con el boton **Try it out**.

Respuesta esperada:

```json
{
  "content": "# Titulo\n\nTexto extraido del PDF",
  "page_count": 16
}
```

## Calidad de codigo

Las cuatro herramientas estan configuradas en el repo (`pyproject.toml` y
`.flake8`), asi que se corren **sin pasar ningun flag**. Las cuatro deben
quedar en cero antes de abrir un PR:

```powershell
black .          # formatea (88 caracteres)
isort .          # ordena imports (perfil black)
flake8           # estilo y errores comunes
mypy             # chequeo de tipos sobre app/
```

Para chequear sin modificar archivos:

```powershell
black --check .
isort --check-only .
```

Convenciones vigentes:

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/es/) con el
  numero de issue como alcance, y `Closes #N` para cerrarlo al hacer push.
  Ejemplo: `fix(#30): corregir los errores de tipos de mypy. Closes #30`.
- **Tests**: nombres que se leen como especificacion (`test_<que_hace_el_sistema>`),
  organizados por capa (ver seccion Tests).
- **Estado a preparar en un test**: siempre por una interfaz publica.

## Comandos utiles

Comandos con `make`, si lo tenes instalado (desde la raiz del proyecto):

```bash
make up          # Levantar la API (igual que make api)
make down        # Apagarla
make logs        # Ver logs de la API
make ps          # Ver estado del contenedor
make tp-up       # Stack del TP: Traefik + 5 replicas
make tp-down     # Apagar el stack del TP
```

Comandos manuales:

Reconstruir la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --force-recreate
```

Ver logs de la API:

```bash
docker logs -f docker_api_1
```

Apagar la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
```
