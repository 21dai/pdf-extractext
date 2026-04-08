# Guía de Arquitectura de 3 Capas

## Visión General de la Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE PRESENTACIÓN                       │
│                    (API - Controllers)                       │
│              app/api/routers/document.py                     │
│                                                               │
│  - Endpoints HTTP (GET, POST, PUT, DELETE)                  │
│  - Validación de entrada con Pydantic                        │
│  - Manejo de excepciones HTTP                                │
│  - Respuestas formatadas en JSON                             │
└────────────────────────┬────────────────────────────────────┘
                         │ (Inyección de Dependencias)
                         │ def get_document_service(db)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   CAPA DE LÓGICA DE NEGOCIO                  │
│                    (Services)                                │
│              app/services/document_service.py                │
│                                                               │
│  - Reglas de negocio                                         │
│  - Validación de datos                                       │
│  - Orquestación de operaciones                               │
│  - Manejo de errores de negocio                              │
└────────────────────────┬────────────────────────────────────┘
                         │ (Repository Injection)
                         │ self.repository = DocumentRepository(db)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               CAPA DE ACCESO A DATOS                         │
│                   (Repositories)                             │
│          app/repositories/document_repository.py             │
│                                                               │
│  - Operaciones CRUD                                          │
│  - Consultas a base de datos                                 │
│  - Abstracción de la BD                                      │
│  - Transacciones                                             │
└────────────────────────┬────────────────────────────────────┘
                         │ (SQLAlchemy ORM)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               CAPA DE PERSISTENCIA                           │
│                  (Database)                                  │
│                                                               │
│  - SQLite / PostgreSQL / MySQL                               │
│  - Tablas relacionales                                       │
│  - Índices y restricciones                                   │
└─────────────────────────────────────────────────────────────┘
```

## Flujo de una Solicitud HTTP

```
1. Cliente (HTTP Request)
   │
   ▼
2. Router (app/api/routers/document.py)
   - Recibe solicitud en endpoint: GET /api/v1/documents/{id}
   - Valida con Pydantic schemas
   │
   ▼
3. Service (app/services/document_service.py)
   - Obtiene DocumentService via dependency injection
   - Ejecuta lógica de negocio: get_document(id)
   │
   ▼
4. Repository (app/repositories/document_repository.py)
   - Ejecuta: self.session.query(Document).filter(...)
   │
   ▼
5. Database (SQLAlchemy)
   - Ejecuta SQL: SELECT * FROM documents WHERE id = ?
   │
   ▼
6. Base de Datos (SQLite/PostgreSQL)
   - Retorna registro
   │
   ▼
7. Repository
   - Retorna Document objeto
   │
   ▼
8. Service
   - Retorna DocumentResponse (Pydantic model)
   │
   ▼
9. Router
   - Convierte a JSON y retorna HTTP 200
   │
   ▼
10. Cliente (HTTP Response)
```

## Principios de Diseño Implementados

### 1. Separación de Responsabilidades (Single Responsibility)

**API Layer:**
```python
@router.get("/documents/{document_id}")
async def get_document(document_id: int, service: DocumentService):
    # Solo maneja HTTP, validación y errores HTTP
    document = service.get_document(document_id)
    if not document:
        raise HTTPException(404, "Not found")
    return document
```

**Service Layer:**
```python
def get_document(self, document_id: int):
    # Solo contiene lógica de negocio
    document = self.repository.get_by_id(document_id)
    if document and document.is_archived:
        # Lógica de negocio específica
        pass
    return DocumentResponse.model_validate(document)
```

**Repository Layer:**
```python
def get_by_id(self, document_id: int):
    # Solo acceso a datos
    return self.session.query(Document).filter(
        Document.id == document_id
    ).first()
```

### 2. Inyección de Dependencias

```python
# FastAPI maneja inyección automática
def get_document_service(db: Session = Depends(get_db)):
    return DocumentService(db)

@router.get("/{document_id}")
async def get_document(
    document_id: int,
    service: DocumentService = Depends(get_document_service)
):
    return service.get_document(document_id)
```

### 3. No Acoplamiento Entre Capas

```python
# El Router NO importa Repository
# El Service NO importa Router
# Solo importan lo que necesitan

# Router solo conoce Service
from app.services import DocumentService

# Service solo conoce Repository
from app.repositories import DocumentRepository

# Repository solo conoce SQLAlchemy
from sqlalchemy.orm import Session
```

## Estructura de Archivos - Propósito de Cada Uno

### app/api/routers/document.py (Capa Presentación)
```
Responsabilidades:
✓ Definir endpoints HTTP
✓ Validar entrada con Pydantic schemas
✓ Llamar servicios
✓ Manejar excepciones HTTP
✓ Retornar respuestas JSON

NO debe:
✗ Contener lógica de negocio
✗ Acceder directamente a BD
✗ Conocer detalles de Repository
```

### app/services/document_service.py (Capa Lógica)
```
Responsabilidades:
✓ Implementar reglas de negocio
✓ Coordinar entre API y datos
✓ Validar datos de negocio
✓ Manejar excepciones de negocio
✓ Transformar modelos (DB → Response)

NO debe:
✗ Manejar HTTP directamente
✗ Escribir SQL
✗ Conocer Pydantic schemas (transformar es ok)
```

### app/repositories/document_repository.py (Capa Datos)
```
Responsabilidades:
✓ Operaciones CRUD
✓ Consultas a BD
✓ Manejo de sesiones
✓ Transacciones

NO debe:
✗ Contener lógica de negocio
✗ Validar datos
✗ Conocer HTTP
```

## Agregando Nuevas Entidades

### Ejemplo: Agregar entidad "User"

**1. Crear Modelo (app/models/user.py)**
```python
from sqlalchemy import Column, Integer, String

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    name = Column(String(255))
```

**2. Crear Schemas (app/schemas/user.py)**
```python
from pydantic import BaseModel

class UserCreate(BaseModel):
    email: str
    name: str

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
```

**3. Crear Repository (app/repositories/user_repository.py)**
```python
class UserRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        return user
    
    def get_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter(
            User.email == email
        ).first()
```

**4. Crear Service (app/services/user_service.py)**
```python
class UserService:
    def __init__(self, db: Session):
        self.repository = UserRepository(db)
    
    def create_user(self, user_data: UserCreate) -> UserResponse:
        # Validaciones de negocio
        if self.repository.get_by_email(user_data.email):
            raise ValueError("Email already exists")
        
        user = User(**user_data.model_dump())
        created = self.repository.create(user)
        return UserResponse.model_validate(created)
```

**5. Crear Router (app/api/routers/user.py)**
```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/users", tags=["users"])

def get_user_service(db = Depends(get_db)):
    return UserService(db)

@router.post("", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    service: UserService = Depends(get_user_service)
):
    return service.create_user(user_data)
```

**6. Registrar Router en (app/main.py)**
```python
from app.api.routers import user_router

app.include_router(
    user_router,
    prefix=settings.api_v1_prefix
)
```

## Testing en 3 Capas

```python
# tests/test_documents.py

# TEST DE UNIT (Service)
def test_create_document_service(db):
    service = DocumentService(db)
    result = service.create_document(
        DocumentCreate(name="test", file_path="/tmp/test", file_size=100)
    )
    assert result.name == "test"

# TEST DE INTEGRACIÓN (API)
def test_create_document_endpoint(client):
    response = client.post(
        "/api/v1/documents",
        json={"name": "test", "file_path": "/tmp/test", "file_size": 100}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "test"
```

## Beneficios de la Arquitectura de 3 Capas

1. **Mantenibilidad**: Cambios en BD no afectan API
2. **Testabilidad**: Cada capa se prueba independientemente
3. **Reusabilidad**: Services pueden usarse en múltiples contextos
4. **Escalabilidad**: Fácil agregar nuevas funcionalidades
5. **Seguridad**: Validación en múltiples niveles
6. **Claridad**: Cada capas tiene responsabilidad clara

## Consideraciones Importantes

### Validación Multinicapa
```
Entrada (API) → Validación Pydantic
     ↓
Negocio (Service) → Validación de Reglas
     ↓
Datos (Repository) → Validación de Restricciones BD
```

### Error Handling
```
Repository → ValueError
     ↓
Service → ValueError (captura y re-lanza si es necesario)
     ↓
Router → HTTPException (convierte a HTTP response)
```

### Transacciones
```
# Las transacciones se manejan en Repository
session.commit()  # Repository
# Service confía en que Repository maneja transacciones
# Router no conoce detalles de transacciones
```
