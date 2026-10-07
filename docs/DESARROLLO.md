# Guia de desarrollo

Detalles para trabajar en el servicio: estructura de Docker y versionado,
persistencia, ejemplos con curl, calidad de codigo y comandos utiles. Lo
basico para levantarlo esta en el [README](../README.md).

## Persistencia

La base de datos usada es MongoDB.

Colecciones principales:

- `documents`
- `counters`

Campos principales guardados por documento:

- `id`
- `name`
- `original_filename`
- `file_path`
- `checksum`
- `file_size`
- `extracted_text`
- `is_processed`
- `created_at`
- `updated_at`

Nota importante: el PDF original no se guarda como binario en MongoDB. El texto se extrae desde los bytes recibidos en memoria y se persisten los metadatos junto con el texto extraido.

## Docker

### Estructura

Los archivos de infraestructura Docker se centralizaron en la carpeta `docker/` para mantener la raiz del proyecto limpia:

| Archivo original | Nueva ubicacion |
|------------------|-----------------|
| `Dockerfile` | `docker/Dockerfile` |
| `docker-compose.db.yml` | `docker/docker-compose.db.yml` |
| `docker-compose.yml` | `docker/docker-compose.yml` |

`.dockerignore` permanece en la raiz y ahora ignora el directorio `docker/` completo.

`docker-compose.yml` no hardcodea ningun host de backing service: `DATABASE_URL` se pasa tal cual viene de `.env` (factor de configuracion 12-factor). El host que va en `.env` depende de donde corra la API:

- API dentro de Docker (`make up` / `docker compose -f docker/docker-compose.yml up`): usar el nombre de servicio de la red Docker, `mongo:27017`.
- API corriendo localmente fuera de Docker (`python main.py`) contra el contenedor de Mongo expuesto: usar `localhost:27017`.

Cambiar de entorno es solo editar `.env`, sin tocar ningun archivo versionado.

### Versionado de la imagen (factor 5: build, release, run)

La imagen de la API se taguea con `IMAGE_TAG` (variable definida en `.env`), nunca con `latest` como release real:

```yaml
image: pdf-extractext-api:${IMAGE_TAG:-latest}
```

`latest` queda solo como valor por defecto de conveniencia si no se define `IMAGE_TAG` (por ejemplo, en una build local rapida). Para una release real:

- `IMAGE_TAG` debe coincidir con `APP_VERSION` (definida tambien en `pyproject.toml` y `app/config/settings.py`).
- Se sigue [Semantic Versioning](https://semver.org/lang/es/) (`MAJOR.MINOR.PATCH`):

  | Numero | Nombre | Cuando se incrementa |
  |--------|--------|----------------------|
  | **1**.0.0 | MAJOR | Cambios que rompen compatibilidad (ej. se modifica la forma de un endpoint existente). |
  | 1.**0**.0 | MINOR | Funcionalidad nueva sin romper lo existente (ej. un endpoint nuevo). |
  | 1.0.**0** | PATCH | Correccion de bugs, sin agregar funcionalidad ni romper nada. |

- La version actual es `1.3.4`. La `1.0.0` fue la primera release estable; la
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

Cada vez que se cierra una nueva release hay que subir `APP_VERSION` (en `pyproject.toml`, `app/config/settings.py` y `.env`) y reconstruir la imagen con ese mismo `IMAGE_TAG`, de forma que cada version del codigo quede asociada a una imagen Docker distinta e identificable, en vez de pisar siempre la misma imagen `latest`. Cada release tiene ademas su tag de git (`v1.0.0` ... `v1.3.0`): `git checkout vX.Y.Z` reconstruye exactamente esa version.

## Flujo principal

1. El cliente sube un PDF con `name` y `file`.
2. La API lee el archivo en memoria.
3. Se valida nombre, extension, firma y tamanio.
4. Se calcula el checksum SHA-256.
5. Si el checksum ya existe, el documento se rechaza.
6. Si es valido, se extrae el texto desde memoria usando `pypdfium2`.
7. Se guarda el documento en MongoDB con sus metadatos y texto extraido.
8. La API devuelve el documento creado.

## Ejemplo con curl

En PowerShell hay que escribir `curl.exe`: `curl` a secas es un alias de
`Invoke-WebRequest`, que no acepta estos parametros y ademas pide confirmacion.
El caracter de continuacion de linea en PowerShell es la comilla invertida.

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/documents" `
  -H "accept: application/json" `
  -F "name=Contrato de prueba" `
  -F "file=@C:/ruta/al/archivo.pdf;type=application/pdf"
```

> No hace falta pasar `Content-Type`: `curl` lo arma solo, con el `boundary`
> que necesita el `multipart/form-data`.

Tambien se puede probar sin la terminal, desde Swagger UI en
<http://localhost:8000/docs>, con el boton **Try it out**.

Respuesta esperada:

```json
{
  "name": "Contrato de prueba",
  "original_filename": "archivo.pdf",
  "file_size": 12345,
  "id": 1,
  "checksum": "sha256...",
  "extracted_text": "Texto extraido del PDF",
  "is_processed": true,
  "created_at": "2026-06-03T20:00:00.000000Z",
  "updated_at": "2026-06-03T20:00:00.000000Z"
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
- **Estado a preparar en un test**: siempre por una interfaz publica, nunca
  escribiendo documentos crudos en MongoDB.

## Comandos utiles

Comandos con `make`, si lo tenes instalado (desde la raiz del proyecto):

```bash
make up          # Levantar todo el stack
make down        # Apagar todo
make logs        # Ver logs de la API
make ps          # Ver estado de los contenedores
make api         # Levantar solo la API
make db          # Levantar solo MongoDB
```

Comandos manuales (por servicio):

Reconstruir la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build --force-recreate
```

Ver logs de MongoDB:

```bash
docker logs -f docker_mongo_1
```

Ver logs de la API:

```bash
docker logs -f docker_api_1
```

Apagar solo la API:

```bash
docker compose --env-file .env -f docker/docker-compose.yml down
```

Apagar solo MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml down
```

Borrar tambien el volumen de MongoDB:

```bash
docker compose --env-file .env -f docker/docker-compose.db.yml down -v
```
