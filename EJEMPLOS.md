"""
Ejemplos de uso de la estructura de 3 capas

Este archivo contiene ejemplos prácticos de cómo usar la arquitectura
en diferentes escenarios.
"""

# =============================================================================
# EJEMPLO 1: Crear un Documento
# =============================================================================

"""
Flujo completo de creación:

1. Cliente envía: POST /api/v1/documents
   {
       "name": "Mi PDF",
       "file_path": "/uploads/documento.pdf",
       "file_size": 1024
   }

2. Router (app/api/routers/document.py:create_document):
   - Recibe solicitud
   - Valida datos con DocumentCreate schema (Pydantic)
   - Inyecta DocumentService
   - Llama: service.create_document(document_data)

3. Service (app/services/document_service.py:create_document):
   - Valida que archivo existe: os.path.exists(file_path)
   - Aplica lógica de negocio
   - Crea objeto Document
   - Llama: self.repository.create(document)

4. Repository (app/repositories/document_repository.py:create):
   - Recibe objeto Document
   - Ejecuta: self.session.add(document)
   - Ejecuta: self.session.commit()
   - Retorna objeto Document guardado

5. Response viaja hacia arriba:
   Repository → Service → Router → Cliente
   
   Cliente recibe: HTTP 201 Created
   {
       "id": 1,
       "name": "Mi PDF",
       "file_path": "/uploads/documento.pdf",
       "file_size": 1024,
       "extracted_text": null,
       "is_processed": false,
       "created_at": "2024-01-15T10:30:00",
       "updated_at": "2024-01-15T10:30:00"
   }
"""

# =============================================================================
# EJEMPLO 2: Actualizar un Documento
# =============================================================================

"""
Cliente envía: PUT /api/v1/documents/1
{
    "name": "Mi PDF Actualizado"
}

1. Router valida con DocumentUpdate schema
   - Solo actualiza campos enviados (exclude_unset=True)

2. Service:
   - Obtiene documento actual
   - Aplica validaciones de negocio
   - Llama repository.update(id, data)

3. Repository:
   - Usa setattr para actualizar solo campos necesarios
   - Retorna documento actualizado

Ventaja: No necesitas enviar todos los campos
"""

# =============================================================================
# EJEMPLO 3: Extraer Texto (Lógica de Negocio Compleja)
# =============================================================================

"""
POST /api/v1/documents/1/extract

Service implementa:

def extract_text(self, document_id: int):
    # 1. Obtiene documento
    document = self.repository.get_by_id(document_id)
    
    # 2. Validaciones de negocio
    if not document:
        return None
    
    if document.is_processed:
        raise ValueError("Document already processed")
    
    # 3. Lógica de negocio (extracción)
    try:
        extracted_text = pdf_extract_library(document.file_path)
    except Exception as e:
        raise ValueError(f"Extraction failed: {e}")
    
    # 4. Persiste cambios
    update_data = {
        "extracted_text": extracted_text,
        "is_processed": True
    }
    return self.repository.update(document_id, update_data)

Key Points:
- La lógica de extracción está en Service, no en Router ni Repository
- Repository no sabe cómo extraer, solo persiste
- Router no sabe detalles, solo llama al service
"""

# =============================================================================
# EJEMPLO 4: Consultas Avanzadas (Extender Repository)
# =============================================================================

"""
Ejemplo: Buscar documentos procesados

# En repository/document_repository.py
def get_processed_documents(self):
    return self.session.query(Document).filter(
        Document.is_processed == True
    ).all()

# En service/document_service.py
def get_processed_documents(self):
    documents = self.repository.get_processed_documents()
    return [DocumentResponse.model_validate(doc) for doc in documents]

# En router/document.py
@router.get("/processed")
async def list_processed(service: DocumentService = Depends(get_document_service)):
    return service.get_processed_documents()

Patrón: Router → Service → Repository → Database
"""

# =============================================================================
# EJEMPLO 5: Testing (TDD)
# =============================================================================

"""
# Test unitario del servicio (no necesita BD real)
def test_create_document_validation():
    service = DocumentService(mock_db)
    
    with pytest.raises(ValueError):
        service.create_document(
            DocumentCreate(
                name="test",
                file_path="/nonexistent/file.pdf",  # No existe
                file_size=100
            )
        )

# Test de integración del endpoint
def test_create_document_api(client):
    response = client.post(
        "/api/v1/documents",
        json={
            "name": "test",
            "file_path": "/tmp/existing.pdf",
            "file_size": 100
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test"
    assert data["is_processed"] is False
"""

# =============================================================================
# EJEMPLO 6: Manejo de Errores en 3 Capas
# =============================================================================

"""
Escenario: Usuario intenta crear documento con archivo que no existe

1. Router:
   try:
       return service.create_document(document_data)
   except ValueError as e:
       raise HTTPException(400, detail=str(e))

2. Service:
   if not os.path.exists(document_data.file_path):
       raise ValueError(f"File not found: {document_data.file_path}")

3. Repository:
   # Si hay error de BD
   except SQLAlchemyError as e:
       # Log, retry, etc.
       raise

Cliente recibe:
{
    "detail": "File not found: /path/to/file.pdf"
}
HTTP 400 Bad Request
"""

# =============================================================================
# EJEMPLO 7: Agregar una Nueva Característica
# =============================================================================

"""
Requisito: "Permitir comentarios en documentos"

PASO 1: Crear Modelo (models/comment.py)
```python
class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    text = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
```

PASO 2: Crear Schemas (schemas/comment.py)
```python
class CommentCreate(BaseModel):
    text: str
    created_by: str

class CommentResponse(BaseModel):
    id: int
    text: str
    created_by: str
    created_at: datetime
```

PASO 3: Crear Repository (repositories/comment_repository.py)
```python
class CommentRepository:
    def create(self, comment: Comment):
        self.session.add(comment)
        self.session.commit()
        return comment
    
    def get_by_document(self, document_id: int):
        return self.session.query(Comment).filter(
            Comment.document_id == document_id
        ).all()
```

PASO 4: Crear Service (services/comment_service.py)
```python
class CommentService:
    def add_comment(self, document_id: int, data: CommentCreate):
        # Valida que documento existe
        doc = self.document_repo.get_by_id(document_id)
        if not doc:
            raise ValueError("Document not found")
        
        # Crea comentario
        comment = Comment(
            document_id=document_id,
            text=data.text,
            created_by=data.created_by
        )
        return self.comment_repo.create(comment)
    
    def get_comments(self, document_id: int):
        comments = self.comment_repo.get_by_document(document_id)
        return [CommentResponse.model_validate(c) for c in comments]
```

PASO 5: Crear Router (api/routers/comment.py)
```python
router = APIRouter(prefix="/comments", tags=["comments"])

@router.post("/documents/{document_id}/comments")
async def add_comment(document_id: int, data: CommentCreate, service: CommentService):
    return service.add_comment(document_id, data)

@router.get("/documents/{document_id}/comments")
async def get_comments(document_id: int, service: CommentService):
    return service.get_comments(document_id)
```

PASO 6: Registrar en main.py
```python
from app.api.routers import comment_router
app.include_router(comment_router, prefix=settings.api_v1_prefix)
```

PASO 7: Tests (tests/test_comments.py)
```python
def test_add_comment(client, db):
    # Crea documento
    doc_response = client.post(...)
    doc_id = doc_response.json()["id"]
    
    # Agrega comentario
    response = client.post(
        f"/api/v1/documents/{doc_id}/comments",
        json={"text": "Great document!", "created_by": "user@example.com"}
    )
    assert response.status_code == 201
    assert response.json()["text"] == "Great document!"
```

Beneficios:
- Cada capa tiene responsabilidad clara
- Fácil de mantener y extender
- Fácil de testear
- Cambios localizados
"""
