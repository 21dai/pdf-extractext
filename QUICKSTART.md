# Guia de Inicio Rapido

## Demo en menos de 5 minutos

### 1. Instalar dependencias

Opcion recomendada con `uv`:

```bash
cd pdf-extractext
uv sync --extra dev
copy .env.example .env
```

Opcion alternativa con `pip`:

```bash
cd pdf-extractext
python -m venv venv
venv\Scripts\activate
python -m pip install -e ".[dev]"
copy .env.example .env
```

### 2. Levantar MongoDB real

```bash
docker compose up -d
docker compose ps
```

Cuando el servicio `mongodb` figure como `running` o `healthy`, segui con el siguiente paso.

### 3. Ejecutar la API

```bash
python main.py
```

Vas a ver algo asi:

```text
[OK] API de Extraccion de PDF started successfully
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Abrir la documentacion

- Swagger: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

### 5. Probar el alta de un PDF

En `POST /api/v1/documents`:

- `name`: un nombre cualquiera
- `file`: un PDF real desde tu PC

Si el alta sale bien, la respuesta viene con:

- `original_filename`
- `checksum`
- `extracted_text`
- `is_processed: true`

## Comandos utiles

### Correr tests

```bash
python -m pytest -q
```

### Verificar salud de la API

```bash
curl http://localhost:8000/health
```

### Apagar Mongo

```bash
docker compose down
```

### Borrar volumen de Mongo

```bash
docker compose down -v
```

## Si no queres usar Mongo real por un momento

Solo para pruebas rapidas locales:

```powershell
$env:DATABASE_URL='mongomock://localhost'
python main.py
```

Eso no reemplaza la demo final, pero sirve para seguir trabajando aunque Mongo no este levantado.
