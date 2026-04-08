# PDF Extract API

A professional 3-layer architecture FastAPI application for PDF document extraction and management.

## Arquitectura de 3 Capas

La aplicación implementa un patrón de arquitectura de 3 capas:

### 1. **Capa de Presentación (API)**
- **Ubicación**: `app/api/routers/`
- Maneja solicitudes y respuestas HTTP
- Valida datos de entrada
- Retorna códigos HTTP apropiados
- Archivos: `document.py` - Endpoints de documentos

### 2. **Capa de Lógica de Negocio (Services)**
- **Ubicación**: `app/services/`
- Implementa reglas de negocio
- Valida datos
- Coordina entre API y capa de datos
- Archivos: `document_service.py` - Servicio de documentos

### 3. **Capa de Acceso a Datos (Repositories)**
- **Ubicación**: `app/repositories/`
- Gestiona operaciones con base de datos
- Abstrae implementación de base de datos
- Proporciona interfaz CRUD limpia
- Archivos: `document_repository.py` - Operaciones de base de datos

## Estructura del Proyecto

```
pdf-extractext/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Factory de app FastAPI
│   ├── api/
│   │   ├── __init__.py
│   │   └── routers/
│   │       ├── __init__.py
│   │       └── document.py     # Endpoints API (CAPA PRESENTACIÓN)
│   ├── services/
│   │   ├── __init__.py
│   │   └── document_service.py # Lógica de negocio (CAPA LÓGICA)
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── document_repository.py # Operaciones BD (CAPA DATOS)
│   ├── models/
│   │   ├── __init__.py
│   │   └── document.py         # Modelos SQLAlchemy
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── document.py         # Esquemas Pydantic
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # Configuración
│   └── utils/
│       ├── __init__.py
│       └── database.py         # Setup de base de datos
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Fixtures de Pytest
│   └── test_documents.py      # Tests de API
├── main.py                     # Punto de entrada
├── pyproject.toml             # Dependencias
├── .env.example               # Variables de entorno
└── README.md
```

## Tecnologías

- **Python** 3.11+
- **FastAPI** - Framework web moderno
- **SQLAlchemy** - ORM para base de datos
- **Pydantic** - Validación de datos
- **Pytest** - Testing
- **UV** - Gestor de dependencias (opcional)

## Metodologías

- **TDD** - Test-Driven Development
- **Proyecto dirigido en GitHub** - GitHub-driven development
- **12 Factor App** - Principios de aplicación cloud-native
- **SOLID** - Principios de diseño

## Principios de Programación

- **KISS** - Keep It Simple, Stupid
- **DRY** - Don't Repeat Yourself
- **YAGNI** - You Aren't Gonna Need It
- **SOLID** - Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion

## Instalación

### Requisitos Previos
- Python 3.11+
- pip o UV

### Configuración

1. Clonar repositorio:
```bash
cd pdf-extractext
```

2. Crear y activar ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -e ".[dev]"
```

4. Crear archivo `.env` desde plantilla:
```bash
cp .env.example .env
```

## Ejecutar la Aplicación

### Servidor de Desarrollo

```bash
python main.py
```

La API estará disponible en `http://localhost:8000`

### Documentación API

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Endpoints de API

### Documentos

- `GET /api/v1/documents` - Listar todos los documentos
- `POST /api/v1/documents` - Crear nuevo documento
- `GET /api/v1/documents/{document_id}` - Obtener documento por ID
- `PUT /api/v1/documents/{document_id}` - Actualizar documento
- `DELETE /api/v1/documents/{document_id}` - Eliminar documento
- `POST /api/v1/documents/{document_id}/extract` - Extraer texto de documento

## Testing

Ejecutar tests:
```bash
pytest
```

Ejecutar tests con cobertura:
```bash
pytest --cov=app
```

## Configuración

La configuración se gestiona a través de variables de entorno en archivo `.env`:

```env
# Aplicación
APP_NAME=PDF Extract API
DEBUG=False

# Servidor
HOST=0.0.0.0
PORT=8000

# Base de datos
DATABASE_URL=sqlite:///./pdf_extract.db

# API
API_V1_PREFIX=/api/v1
```

## Calidad de Código

### Formatear código
```bash
black app tests
```

### Verificar linting
```bash
flake8 app tests
```

### Ordenar imports
```bash
isort app tests
```

### Type checking
```bash
mypy app
```

## Modelo de Base de Datos

### Modelo Document
- `id`: Entero (Clave Primaria)
- `name`: Texto (255 caracteres)
- `file_path`: Texto (500 caracteres, único)
- `file_size`: Entero
- `extracted_text`: Texto (nullable)
- `is_processed`: Booleano (default: False)
- `created_at`: DateTime
- `updated_at`: DateTime

## Agregar Nuevas Características

Para agregar una nueva característica siguiendo la arquitectura de 3 capas:

1. **Crear Modelo de Base de Datos** (`app/models/`)
   - Definir modelo SQLAlchemy

2. **Crear Repository** (`app/repositories/`)
   - Implementar métodos de acceso a datos

3. **Crear Service** (`app/services/`)
   - Implementar lógica de negocio

4. **Crear Schema** (`app/schemas/`)
   - Definir modelos Pydantic de request/response

5. **Crear Router** (`app/api/routers/`)
   - Definir endpoints de API

6. **Escribir Tests** (`tests/`)
   - Testear todas las capas

## Mejores Prácticas

- **Una Responsabilidad**: Cada capa tiene una responsabilidad específica
- **Inyección de Dependencias**: Servicios y repositorios se inyectan vía dependencias
- **Manejo de Errores**: Códigos HTTP apropiados y mensajes de error claros
- **Validación**: Pydantic valida todas las entradas
- **Testing**: Tests unitarios para servicios y tests de integración para endpoints
- **Documentación**: Docstrings y documentación de API

## Mejoras Futuras

- [ ] Agregar autenticación JWT
- [ ] Implementar extracción de texto PDF (PyPDF2/pdfplumber)
- [ ] Implementar operaciones de BD asincrónicas
- [ ] Agregar capa de caché
- [ ] Implementar logging
- [ ] Migraciones de BD con Alembic
- [ ] Soporte WebSocket para tareas largas
- [ ] Rate limiting y throttling
- [ ] Manejo de carga de archivos
- [ ] Procesamiento en lote

## Licencia

MIT License
