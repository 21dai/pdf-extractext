# Guía de Inicio Rápido

## Instalación y Ejecución en 5 Minutos

### 1. Preparar Ambiente

```bash
# Entrar al directorio del proyecto
cd /home/daiana/UTN/UTN/3ro/Desarrollo/Proyecto/pdf-extractext

# Crear ambiente virtual
python -m venv venv

# Activar ambiente (Linux/Mac)
source venv/bin/activate

# Activar ambiente (Windows)
venv\Scripts\activate

# Instalar dependencias
pip install -e ".[dev]"
```

### 2. Ejecutar la Aplicación

```bash
python main.py
```

Verás:
```
✓ PDF Extract API started successfully
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 3. Acceder a Documentación Interactiva

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Primeras Llamadas API

### Crear un Documento

```bash
curl -X POST "http://localhost:8000/api/v1/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Mi Primer PDF",
    "file_path": "/tmp/documento.pdf",
    "file_size": 1024
  }'
```

Respuesta:
```json
{
  "id": 1,
  "name": "Mi Primer PDF",
  "file_path": "/tmp/documento.pdf",
  "file_size": 1024,
  "extracted_text": null,
  "is_processed": false,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

### Listar Documentos

```bash
curl "http://localhost:8000/api/v1/documents"
```

### Obtener Documento por ID

```bash
curl "http://localhost:8000/api/v1/documents/1"
```

### Actualizar Documento

```bash
curl -X PUT "http://localhost:8000/api/v1/documents/1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Documento Actualizado"
  }'
```

### Eliminar Documento

```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/1"
```

## Estructura de 3 Capas Explicada Simply

### Capa 1: API (Routers)
**¿Dónde?**: `app/api/routers/document.py`

```python
@router.post("/documents")
async def create_document(data: DocumentCreate, service: DocumentService):
    # Solo recibe datos y los pasa al servicio
    return service.create_document(data)
```

**Responsabilidades:**
- Recibir solicitudes HTTP
- Validar con Pydantic
- Llamar al servicio
- Retornar respuesta JSON

### Capa 2: Lógica de Negocio (Services)
**¿Dónde?**: `app/services/document_service.py`

```python
def create_document(self, data: DocumentCreate):
    # Validar que archivo existe
    if not os.path.exists(data.file_path):
        raise ValueError("File not found")
    
    # Crear documento y guardarlo
    document = Document(**data.dict())
    return self.repository.create(document)
```

**Responsabilidades:**
- Implementar reglas de negocio
- Validar datos importantes
- Coordinar operaciones
- Llamar al repositorio

### Capa 3: Acceso a Datos (Repositories)
**¿Dónde?**: `app/repositories/document_repository.py`

```python
def create(self, document: Document):
    self.session.add(document)
    self.session.commit()
    return document
```

**Responsabilidades:**
- Guardar/obtener datos
- Ejecutar queries
- Manejar transacciones

## Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests con output verbose
pytest -v

# Tests con cobertura
pytest --cov=app

# Un test específico
pytest tests/test_documents.py::test_create_document
```

## Archivos Importantes

| Archivo | Propósito |
|---------|----------|
| `main.py` | Punto de entrada |
| `app/main.py` | Factory de FastAPI |
| `app/api/routers/document.py` | Endpoints HTTP |
| `app/services/document_service.py` | Lógica de negocio |
| `app/repositories/document_repository.py` | Acceso a datos |
| `app/models/document.py` | Modelo de BD |
| `app/schemas/document.py` | Esquemas Pydantic |
| `app/config/settings.py` | Configuración |
| `app/utils/database.py` | Conexión BD |

## Variables de Entorno

Crear `.env`:

```env
DEBUG=True
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./pdf_extract.db
```

## Comandos Útiles

```bash
# Ver estructura del proyecto
find app -type f -name "*.py" | head -20

# Formatear código
black app tests

# Verificar linting
flake8 app

# Type checking
mypy app

# Instalar en modo desarrollo
pip install -e "."

# Instalar con extras (dev, pdf)
pip install -e ".[dev,pdf]"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"

Solución:
```bash
pip install fastapi uvicorn sqlalchemy pydantic
```

### "Database locked"

Solución (SQLite):
```bash
rm pdf_extract.db
# La BD se recreará automáticamente
```

### "Port 8000 already in use"

Solución:
```bash
# Usar puerto diferente
python main.py --port 8001

# O modificar .env
PORT=8001
```

## Próximos Pasos

1. **Entender la arquitectura**: Leer `ARCHITECTURE.md`
2. **Ver ejemplos**: Consultar `EJEMPLOS.md`
3. **Escribir tests**: Leer `tests/test_documents.py`
4. **Agregar nueva entidad**: Seguir patrón de 3 capas

## Validación Rápida

¿La estructura está funcionando correctamente?

```bash
# 1. Iniciar servidor
python main.py

# 2. En otra terminal:

# Crear documento
curl -X POST "http://localhost:8000/api/v1/documents" \
  -H "Content-Type: application/json" \
  -d '{"name": "test", "file_path": "/tmp/test.pdf", "file_size": 100}'

# Debería retornar algo como:
# {"id": 1, "name": "test", ...}

# Listar
curl "http://localhost:8000/api/v1/documents"

# Si ves respuestas JSON, ¡todo está funcionando!
```

## Más Información

- **FastAPI Docs**: https://fastapi.tiangolo.com
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org
- **Pydantic Docs**: https://docs.pydantic.dev
- **Pytest Docs**: https://docs.pytest.org
