# Checklist de Validación de Arquitectura

## Pre-Instalación

- [ ] Python 3.11+ instalado (`python --version`)
- [ ] pip funcionando (`pip --version`)
- [ ] Git configurado (opcional para versionado)

## Instalación

- [ ] Ambiente virtual creado (`python -m venv venv`)
- [ ] Ambiente virtual activado (`source venv/bin/activate`)
- [ ] Dependencias instaladas (`pip install -e ".[dev]"`)
- [ ] Importaciones funcionan:
  ```bash
  python -c "import fastapi; import sqlalchemy; import pydantic; print('✓ OK')"
  ```

## Estructura de Archivos

### Capa de Presentación (API)
- [ ] `app/api/__init__.py` existe
- [ ] `app/api/routers/__init__.py` existe
- [ ] `app/api/routers/document.py` existe
- [ ] Endpoints definidos en `document.py`:
  - [ ] `@router.post("")`
  - [ ] `@router.get("")`
  - [ ] `@router.get("/{document_id}")`
  - [ ] `@router.put("/{document_id}")`
  - [ ] `@router.delete("/{document_id}")`
  - [ ] `@router.post("/{document_id}/extract")`

### Capa de Lógica de Negocio (Services)
- [ ] `app/services/__init__.py` existe
- [ ] `app/services/document_service.py` existe
- [ ] Métodos en `DocumentService`:
  - [ ] `create_document()`
  - [ ] `get_document()`
  - [ ] `get_all_documents()`
  - [ ] `update_document()`
  - [ ] `delete_document()`
  - [ ] `extract_text()`

### Capa de Acceso a Datos (Repositories)
- [ ] `app/repositories/__init__.py` existe
- [ ] `app/repositories/document_repository.py` existe
- [ ] Métodos en `DocumentRepository`:
  - [ ] `create()`
  - [ ] `get_by_id()`
  - [ ] `get_all()`
  - [ ] `get_by_name()`
  - [ ] `update()`
  - [ ] `delete()`

### Modelos y Esquemas
- [ ] `app/models/document.py` existe con modelo SQLAlchemy
- [ ] `app/schemas/document.py` existe con esquemas Pydantic
- [ ] Modelo tiene todos los campos:
  - [ ] `id`
  - [ ] `name`
  - [ ] `file_path`
  - [ ] `file_size`
  - [ ] `extracted_text`
  - [ ] `is_processed`
  - [ ] `created_at`
  - [ ] `updated_at`

### Configuración
- [ ] `app/config/settings.py` existe
- [ ] `app/config/__init__.py` existe
- [ ] Variables de configuración definidas
- [ ] `.env.example` existe

### Utilidades
- [ ] `app/utils/database.py` existe
- [ ] `get_db()` generador funcionando
- [ ] `create_tables()` disponible
- [ ] `SessionLocal` configurado

### Tests
- [ ] `tests/__init__.py` existe
- [ ] `tests/conftest.py` existe con fixtures
- [ ] `tests/test_documents.py` existe
- [ ] Tests implementados:
  - [ ] `test_list_documents_empty()`
  - [ ] `test_create_document()`
  - [ ] `test_get_document()`
  - [ ] `test_get_nonexistent_document()`
  - [ ] `test_update_document()`
  - [ ] `test_delete_document()`

## Ejecución de la Aplicación

### Prueba de Inicio
```bash
# Ejecutar desde el directorio del proyecto
python main.py
```

- [ ] Aplicación inicia sin errores
- [ ] Mensaje: "✓ PDF Extract API started successfully"
- [ ] API disponible en http://localhost:8000

### Documentación API
- [ ] Swagger UI accesible: http://localhost:8000/docs
- [ ] ReDoc accesible: http://localhost:8000/redoc
- [ ] Endpoints listados en documentación

## Pruebas de Endpoints

### Crear Documento
```bash
curl -X POST "http://localhost:8000/api/v1/documents" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","file_path":"/tmp/test.pdf","file_size":100}'
```
- [ ] Retorna HTTP 201 Created
- [ ] Respuesta contiene `id`, `name`, `is_processed: false`
- [ ] `created_at` y `updated_at` están presentes

### Listar Documentos
```bash
curl "http://localhost:8000/api/v1/documents"
```
- [ ] Retorna HTTP 200
- [ ] Respuesta es un array JSON

### Obtener Documento
```bash
curl "http://localhost:8000/api/v1/documents/1"
```
- [ ] Retorna HTTP 200 si existe
- [ ] Retorna HTTP 404 si no existe

### Actualizar Documento
```bash
curl -X PUT "http://localhost:8000/api/v1/documents/1" \
  -H "Content-Type: application/json" \
  -d '{"name":"actualizado"}'
```
- [ ] Retorna HTTP 200
- [ ] Cambios se reflejan

### Eliminar Documento
```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/1"
```
- [ ] Retorna HTTP 204 No Content
- [ ] Documento se elimina de BD

## Validación de Arquitectura

### Separación de Capas
- [ ] API NO importa directamente Repository
- [ ] API solo usa Service
- [ ] Service solo usa Repository
- [ ] Repository solo usa SQLAlchemy
- [ ] Cada capa tiene responsabilidad clara

### Inyección de Dependencias
- [ ] `get_db()` se inyecta en Services
- [ ] `DocumentService` se inyecta en Routers
- [ ] No hay instancias globales (excepto settings)

### Validación Multinicapa
- [ ] Pydantic valida entrada en API
- [ ] Service valida lógica de negocio
- [ ] Repository maneja restricciones BD

### Manejo de Errores
- [ ] ValueError en Service → HTTPException en API
- [ ] Códigos HTTP apropiad (201, 200, 204, 400, 404)
- [ ] Mensajes de error útiles

## Pruebas

### Ejecutar Tests
```bash
pytest -v
```

- [ ] Todos los tests pasan
- [ ] No hay warnings críticos
- [ ] Cobertura > 70%

```bash
pytest --cov=app
```

- [ ] Cobertura de código se muestra

## Documentación

- [ ] `README.md` describe proyecto
- [ ] `QUICKSTART.md` tiene instrucciones
- [ ] `ARCHITECTURE.md` explica estructura
- [ ] `EJEMPLOS.md` muestra casos de uso
- [ ] Cada archivo tiene docstrings

## Configuración de Desarrollo

### Code Quality Tools
```bash
# Formateo
black app tests
```
- [ ] Código formateado sin errores

```bash
# Linting
flake8 app
```
- [ ] Sin errores de linting críticos

```bash
# Type checking
mypy app
```
- [ ] Sin errores de tipado críticos

```bash
# Import sorting
isort app tests
```
- [ ] Imports ordenados

## Base de Datos

- [ ] Archivo `pdf_extract.db` se crea al iniciar
- [ ] Tabla `documents` existe
- [ ] Tabla tiene columnas correctas
- [ ] Se pueden hacer queries sin error

```bash
# Verificar BD (SQLite)
sqlite3 pdf_extract.db ".tables"
```

## Integración con Git (Opcional)

- [ ] `.gitignore` está configurado
- [ ] `__pycache__` ignorado
- [ ] `.env` ignorado
- [ ] `.db` ignorado
- [ ] `venv/` ignorado

```bash
git add -A
git commit -m "Add 3-layer architecture"
git push
```

## Checklist de Características

### Implementadas
- [x] Arquitectura de 3 capas
- [x] CRUD de Documentos
- [x] Endpoint de extracción
- [x] Validación Pydantic
- [x] Base de datos SQLAlchemy
- [x] Tests con pytest
- [x] Documentación API (Swagger/ReDoc)
- [x] Manejo de errores
- [x] Configuración con variables de entorno
- [x] Documentación completa

### Por Implementar (Futuros)
- [ ] Autenticación JWT
- [ ] Extracción de PDF real (PyPDF2)
- [ ] Async/await completo
- [ ] Caché Redis
- [ ] Logging estructurado
- [ ] Alembic para migraciones
- [ ] WebSocket
- [ ] Rate limiting
- [ ] File upload
- [ ] Batch processing

## Validación Final

```bash
# 1. Instalar
pip install -e ".[dev]"

# 2. Ejecutar
python main.py

# 3. En otra terminal - Tests
pytest -v

# 4. Verificación de archivo
ls -la app/api/routers/document.py
ls -la app/services/document_service.py
ls -la app/repositories/document_repository.py

# 5. Import test
python -c "from app.main import create_app; app = create_app(); print('✓ App created successfully')"

# Checklist final
echo "✓ Estructura de 3 capas completada"
echo "✓ Documentación disponible"
echo "✓ Tests listos"
echo "✓ Proyecto listo para producción"
```

## Estado Final

Si todos los checks están marcados:

✅ **PROYECTO COMPLETADO EXITOSAMENTE**

Puedes:
- Ejecutar la aplicación en producción
- Agregar nuevas características siguiendo el patrón
- Escalar la aplicación
- Integrar con sistemas externos
- Implementar CI/CD
