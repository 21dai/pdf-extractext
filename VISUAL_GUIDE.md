# Resumen Visual de la Estructura de 3 Capas

## Diagrama de Flujo de Datos

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLIENTE HTTP                               │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         │ HTTP Request
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│              🔴 CAPA DE PRESENTACIÓN (API)                          │
│                   app/api/routers/                                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  @router.post("/documents")                                         │
│  async def create_document(data: DocumentCreate,                   │
│                            service: DocumentService):              │
│      try:                                                           │
│          return service.create_document(data)                      │
│      except ValueError as e:                                       │
│          raise HTTPException(400, detail=str(e))                   │
│                                                                     │
│  Responsabilidades:                                                 │
│  ✓ Recibir solicitud HTTP                                         │
│  ✓ Validar con Pydantic                                           │
│  ✓ Llamar al servicio                                             │
│  ✓ Retornar respuesta HTTP                                        │
│                                                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │ Inyección de Dependencias
                         │ service: DocumentService
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│          🟡 CAPA DE LÓGICA DE NEGOCIO (SERVICES)                   │
│                   app/services/                                     │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  class DocumentService:                                             │
│      def create_document(self, data: DocumentCreate):              │
│          # Validar archivo existe                                  │
│          if not os.path.exists(data.file_path):                   │
│              raise ValueError("File not found")                    │
│                                                                     │
│          # Crear documento                                         │
│          doc = Document(**data.dict())                             │
│                                                                     │
│          # Persistir                                               │
│          created = self.repository.create(doc)                     │
│          return DocumentResponse.model_validate(created)           │
│                                                                     │
│  Responsabilidades:                                                 │
│  ✓ Implementar reglas de negocio                                  │
│  ✓ Validar datos importantes                                      │
│  ✓ Coordinar operaciones                                          │
│  ✓ Transformar modelos (DB → Response)                            │
│                                                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │ Repository Injection
                         │ self.repository = DocumentRepository(db)
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│          🟢 CAPA DE ACCESO A DATOS (REPOSITORIES)                  │
│                   app/repositories/                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  class DocumentRepository:                                          │
│      def create(self, document: Document):                         │
│          self.session.add(document)                                │
│          self.session.commit()                                     │
│          self.session.refresh(document)                            │
│          return document                                           │
│                                                                     │
│  Responsabilidades:                                                 │
│  ✓ Operaciones CRUD                                               │
│  ✓ Consultas a base de datos                                      │
│  ✓ Manejo de sesiones                                             │
│  ✓ Transacciones                                                  │
│                                                                     │
└────────────────────────┬─────────────────────────────────────────┘
                         │ SQLAlchemy ORM
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                    BASE DE DATOS                                    │
│                   (SQLite/PostgreSQL)                              │
│                                                                     │
│  CREATE TABLE documents (                                           │
│      id INTEGER PRIMARY KEY,                                        │
│      name VARCHAR(255),                                             │
│      file_path VARCHAR(500),                                        │
│      file_size INTEGER,                                             │
│      extracted_text TEXT,                                           │
│      is_processed BOOLEAN,                                          │
│      created_at DATETIME,                                           │
│      updated_at DATETIME                                            │
│  );                                                                 │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

## Ejemplo: Crear un Documento

```
SOLICITUD HTTP
┌─────────────────────────────┐
│ POST /api/v1/documents      │
│ Content-Type: application/  │
│   json                      │
│                             │
│ {                           │
│   "name": "Mi PDF",        │
│   "file_path": "/tmp/...", │
│   "file_size": 1024        │
│ }                           │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 1. ROUTER RECIBE Y VALIDA                       │
│    ✓ Valida datos con DocumentCreate schema    │
│    ✓ Inyecta DocumentService                   │
│    ✓ Llama: service.create_document(data)      │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 2. SERVICE IMPLEMENTA LÓGICA                    │
│    ✓ Valida: os.path.exists(file_path)        │
│    ✓ Crea: Document(...)                      │
│    ✓ Llama: repository.create(document)        │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 3. REPOSITORY PERSISTE                         │
│    ✓ session.add(document)                     │
│    ✓ session.commit()                          │
│    ✓ Retorna: documento guardado               │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 4. RESPUESTA SUBE A TRAVÉS DE CAPAS            │
│    Repository → Service → Router → Cliente     │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌──────────────────────────────────────────────────┐
│ RESPUESTA HTTP                                   │
│                                                  │
│ HTTP/1.1 201 Created                            │
│ Content-Type: application/json                  │
│                                                  │
│ {                                               │
│   "id": 1,                                      │
│   "name": "Mi PDF",                            │
│   "file_path": "/tmp/...",                     │
│   "file_size": 1024,                           │
│   "extracted_text": null,                      │
│   "is_processed": false,                       │
│   "created_at": "2024-01-15T10:30:00",        │
│   "updated_at": "2024-01-15T10:30:00"         │
│ }                                               │
└──────────────────────────────────────────────────┘
```

## Comparación: Sin vs Con 3 Capas

### ❌ Sin Arquitectura (Monolítico)

```python
# main.py - TODO EN UN ARCHIVO

from fastapi import FastAPI
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# Modelo, validación, lógica, BD todo aquí
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    name = Column(String)

@app.post("/documents")
async def create_document(name: str, file_path: str, file_size: int):
    # Validación
    if not name or not file_path:
        return {"error": "Invalid"}
    
    # Lógica
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    
    # BD
    db = SessionLocal()
    doc = Document(name=name, file_path=file_path)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    db.close()
    
    return doc

PROBLEMAS:
❌ Difícil de mantener (todo junto)
❌ Difícil de testear (interdependencias)
❌ Difícil de escalar (cambios en BD afectan todo)
❌ Duplicación de código
❌ Mezcla de responsabilidades
```

### ✅ Con 3 Capas (Arquitectura Profesional)

```
app/
├── api/routers/
│   └── document.py (SOLO HTTP)
├── services/
│   └── document_service.py (LÓGICA)
├── repositories/
│   └── document_repository.py (BD)

BENEFICIOS:
✅ Separación clara de responsabilidades
✅ Fácil de mantener (cambios localizados)
✅ Fácil de testear (mockear cada capa)
✅ Reutilizable (service en múltiples contextos)
✅ Escalable (agregar features sin romper código)
✅ Sin duplicación (reutilización de código)
```

## Tabla de Responsabilidades

| Capa | Archivo | Responsabilidad | No Debe |
|------|---------|-----------------|--------|
| **Presentación** | `api/routers/` | HTTP, Validación, Errores | Lógica, BD, SQL |
| **Lógica** | `services/` | Reglas, Validación, Orquestación | HTTP, SQL, Detalles BD |
| **Datos** | `repositories/` | CRUD, Queries, Transacciones | HTTP, Lógica, Validación |

## Flujo de Control (Unidireccional)

```
        ┌─────────────┐
        │   Router    │ (API)
        └──────┬──────┘
               │
               │ (Inyecta)
               │
        ┌──────▼──────┐
        │   Service   │ (Lógica)
        └──────┬──────┘
               │
               │ (Usa)
               │
        ┌──────▼──────────┐
        │   Repository    │ (Datos)
        └──────┬──────────┘
               │
               │ (SQLAlchemy)
               │
        ┌──────▼──────────┐
        │   Database      │ (BD)
        └─────────────────┘

✓ Siempre hacia abajo
✓ Nunca hacia arriba
✓ Cada capa solo conoce la siguiente
```

## Instalación de Dependencias por Capa

```
CAPA DE PRESENTACIÓN
├─ fastapi         (servidor web)
├─ uvicorn         (ASGI server)
└─ pydantic        (validación)

CAPA DE LÓGICA
└─ (solo usa servicios de otras capas)

CAPA DE DATOS
├─ sqlalchemy      (ORM)
└─ psycopg2        (driver BD, opcional)

TESTING
├─ pytest
├─ pytest-asyncio
├─ httpx           (client HTTP)
└─ sqlalchemy      (test engine)
```

## Extensibilidad: Agregar Nueva Entidad

```
Patrón a Seguir:

1. Crear Model      → app/models/{entity}.py
2. Crear Schema     → app/schemas/{entity}.py
3. Crear Repository → app/repositories/{entity}_repository.py
4. Crear Service    → app/services/{entity}_service.py
5. Crear Router     → app/api/routers/{entity}.py
6. Registrar Router → app/main.py
7. Escribir Tests   → tests/test_{entity}.py

Tiempo por capa: 5-10 minutos
Riesgo de romper código: MÍNIMO
Testabilidad: MÁXIMA
```

## Métrica de Calidad

```
ANTES (Monolítico)
├─ Complejidad: ████████████████ 16/10 (Muy Alta)
├─ Mantenibilidad: ███ 3/10 (Baja)
├─ Testabilidad: ████ 4/10 (Baja)
└─ Escalabilidad: ██ 2/10 (Muy Baja)

DESPUÉS (3 Capas)
├─ Complejidad: ██████ 6/10 (Normal)
├─ Mantenibilidad: █████████ 9/10 (Excelente)
├─ Testabilidad: ██████████ 10/10 (Excelente)
└─ Escalabilidad: █████████ 9/10 (Excelente)
```

## Integración con Frontend

```
Frontend (React/Vue/Angular)
         │
         │ HTTP/JSON
         ▼
    /api/v1/
         │
         ├─ /documents
         ├─ /users
         ├─ /comments
         └─ /...
         │
         ▼
    Router (FastAPI)
         │
         ▼
    Service (Lógica)
         │
         ▼
    Repository (BD)
         │
         ▼
    Database

El frontend NO necesita conocer detalles de:
✓ Lógica de negocio (Service)
✓ Estructura de BD (Repository)
✓ Detalles técnicos

Solo consume API REST
```

## Seguridad por Capas

```
ENTRADA (API)
└─ Valida input con Pydantic
   ✓ Tipo correcto
   ✓ Formato válido
   ✓ Longitud correcta

NEGOCIO (Service)
└─ Valida reglas
   ✓ Permiso
   ✓ Datos consistentes
   ✓ Lógica válida

DATOS (Repository)
└─ Valida constrains
   ✓ Integridad referencial
   ✓ Restricciones únicas
   ✓ Transacciones seguras

RESULTADO:
✅ Defensa en profundidad
✅ Múltiples puntos de validación
✅ Robusto contra ataques
```

## Conclusión

```
┌────────────────────────────────────────────────┐
│  ARQUITECTURA DE 3 CAPAS = ÉXITO EN EQUIPOS  │
│                                                │
│  ✅ Código limpio y mantenible                │
│  ✅ Fácil colaboración                        │
│  ✅ Escalable a largo plazo                   │
│  ✅ Profesional y estándar                    │
│  ✅ Probado en la industria                   │
│  ✅ Preparado para producción                 │
└────────────────────────────────────────────────┘
```
