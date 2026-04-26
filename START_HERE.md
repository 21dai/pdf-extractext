# Comienza Aqui

## Que tenes en este repo

Una API en FastAPI para:

- subir archivos PDF reales
- validar formato y tamano
- calcular checksum SHA-256
- evitar duplicados
- extraer texto en memoria
- persistir documentos en MongoDB

## El flujo actual

```text
Cliente -> Router -> Service -> Repository -> MongoDB
```

## Arranque recomendado para clase

### 1. Levantar MongoDB

```bash
docker compose up -d
```

### 2. Verificar que Mongo este bien

```bash
docker compose ps
```

### 3. Ejecutar la API

```bash
python main.py
```

### 4. Abrir Swagger

```text
http://localhost:8000/docs
```

### 5. Verificar salud

```text
http://localhost:8000/health
```

## Archivos mas importantes

- `README.md`: vista general del proyecto
- `QUICKSTART.md`: arranque rapido
- `DEMO.md`: guion de demo para clase
- `REVISION_ENUNCIADO.md`: chequeo contra lo pedido por el profesor
- `app/api/routers/document.py`: endpoints
- `app/services/document_service.py`: reglas de negocio
- `app/repositories/document_repository.py`: persistencia en MongoDB

## Si queres recorrer el codigo

1. `tests/test_documents.py`
2. `app/api/routers/document.py`
3. `app/services/document_service.py`
4. `app/repositories/document_repository.py`

## Comando rapido de verificacion

```bash
python -m pytest -q
```

Resultado esperado:

```text
16 passed
```
