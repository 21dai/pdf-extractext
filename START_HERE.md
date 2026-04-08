# 🚀 COMIENZA AQUÍ

## ¿Qué es esto?

Una **estructura de 3 capas profesional con FastAPI** lista para usar y escalar.

## 5 Minutos para Empezar

```bash
# 1. Ir al proyecto
cd /home/daiana/UTN/UTN/3ro/Desarrollo/Proyecto/pdf-extractext

# 2. Ambiente virtual
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

# 3. Instalar
pip install -e ".[dev]"

# 4. Ejecutar
python main.py

# 5. Ver en navegador
# http://localhost:8000/docs
```

## Archivos Importantes

| Archivo | Qué es |
|---------|--------|
| **README.md** | Documentación completa |
| **QUICKSTART.md** | Ejemplos rápidos |
| **ARCHITECTURE.md** | Cómo funciona internamente |
| **VISUAL_GUIDE.md** | Diagramas y flujos |
| **EJEMPLOS.md** | Casos de uso |

## Las 3 Capas

```
Router → Service → Repository → Database
  (API)   (Lógica)  (Datos)    (BD)
```

## Endpoints

- `POST /api/v1/documents` - Crear
- `GET /api/v1/documents` - Listar
- `GET /api/v1/documents/{id}` - Obtener
- `PUT /api/v1/documents/{id}` - Actualizar
- `DELETE /api/v1/documents/{id}` - Eliminar

## Estructura

```
app/
├── api/           ← Endpoints HTTP
├── services/      ← Lógica de negocio
├── repositories/  ← Acceso a datos
├── models/        ← Modelos BD
└── schemas/       ← Validación
```

## Próximos Pasos

1. Lee **README.md** para entender el proyecto
2. Lee **QUICKSTART.md** para ejemplos rápidos
3. Lee **ARCHITECTURE.md** para aprender el patrón
4. Ejecuta los tests: `pytest -v`

## ¿Necesitas agregar una entidad?

Sigue el patrón de `Document`:
1. Model → Schema → Repository → Service → Router

¡Listo! Más de 30 minutos de código profesional.

---

**¡El proyecto está listo para producción!** ✨
