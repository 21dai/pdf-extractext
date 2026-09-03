# Guia de Arquitectura

## Vision general

El proyecto sigue una arquitectura de 3 capas con influencia parcial de Hexagonal:

```text
Router -> Service -> Repository -> MongoDB
```

> Clasificacion honesta: **no es Clean Architecture ni Onion Architecture**.
> Es una arquitectura en 3 capas clasica, con una influencia parcial del estilo
> Hexagonal (Ports & Adapters) reflejada en la existencia de `DocumentRepository`
> como unico punto de acceso a la persistencia. Sin embargo, no existe una
> separacion estricta entre dominio e infraestructura (ver la seccion
> "Decision de arquitectura: acoplamiento Modelo/Persistencia").

## 1. Capa de presentacion

Ubicacion: `app/api/routers/`

Responsabilidades:

- recibir requests HTTP
- validar parametros de entrada
- transformar errores de negocio en respuestas HTTP
- devolver respuestas JSON

Archivo principal:

- `app/api/routers/document.py`

## 2. Capa de logica de negocio

Ubicacion: `app/services/`

Responsabilidades:

- validar el nombre del documento
- validar que el archivo sea PDF
- controlar tamano maximo
- calcular checksum
- evitar duplicados
- extraer texto con `pypdf`
- definir el flujo de actualizacion y borrado

Archivo principal:

- `app/services/document_service.py`

## 3. Capa de acceso a datos

Ubicacion: `app/repositories/`

Responsabilidades:

- crear documentos en MongoDB
- buscar por `id`, `name` y `checksum`
- actualizar documentos
- eliminar documentos
- manejar el contador secuencial de IDs

Archivo principal:

- `app/repositories/document_repository.py`

## Decision de arquitectura: acoplamiento Modelo/Persistencia

### Estado actual

La clase `Document` (`app/models/document.py`) actua simultaneamente como:

- **entidad de dominio**: representa el concepto de negocio "documento PDF procesado" (nombre, checksum, texto extraido, tamano, etc.);
- **documento de base de datos**: su estructura es la que se persiste directamente en MongoDB a traves del repository.

Es decir, no existe una separacion entre un "modelo de dominio puro" y un "modelo de persistencia" propios de Clean Architecture o Onion Architecture.

### Esto es una decision consciente, no un descuido tecnico

Este acoplamiento es un **limite aceptado de forma deliberada** para el alcance actual del proyecto. Las razones son:

- **Simplicidad (KISS)**: para un CRUD con un solo agregado (`Document`), mantener dos modelos y un mapper entre ellos agregaria complejidad sin beneficio real.
- **Alcance acotado**: el dominio no tiene logica rica ni invariantes complejas que exijan aislar el modelo de la forma de persistencia.
- **Costo/beneficio**: el costo de desacoplar hoy supera el riesgo de migracion futura, dado que el seam ya esta previsto (ver abajo).

### Seam (punto de desacoplamiento futuro)

Aunque el modelo esta acoplado a la persistencia, **la frontera de desacoplamiento ya existe**: es `DocumentRepository` (`app/repositories/document_repository.py`).

Si en el futuro se necesita separar dominio de persistencia, el cambio es localizado:

1. Crear un modelo de dominio puro y un modelo de persistencia (o schema) independientes.
2. Modificar unicamente los metodos `_serialize` / `_deserialize` del repository para que actuen como mappers entre ambos modelos.

El resto de la aplicacion (routers, services) no deberia requerir cambios, porque ya consume al repository como unica via de acceso a datos. Este es el punto donde la influencia Hexagonal del diseno paga su deuda tecnica.

## Persistencia

La aplicacion usa MongoDB.

Colecciones:

- `documents`
- `counters`

Indices principales:

- `id` unico
- `checksum` unico
- `name` no unico

## Flujo del alta

1. El cliente envia `name` y `file`.
2. El router lee los bytes del archivo.
3. El service valida extension, firma y tamano.
4. El service calcula el checksum.
5. Si el checksum ya existe, rechaza el documento.
6. Si el PDF es valido, extrae el texto en memoria.
7. El repository guarda el documento en MongoDB.
8. La API devuelve el documento ya procesado.

## Flujo de extraccion

Para documentos nuevos, la extraccion ya se realiza en el alta.

El endpoint `/extract`:

- devuelve el texto ya almacenado si el documento ya fue procesado
- conserva compatibilidad con documentos viejos que pudieran requerir reprocesamiento

## Principios aplicados

- KISS: el flujo principal esta concentrado en un solo service
- DRY: el checksum y la validacion se centralizan
- SOLID: cada capa tiene una responsabilidad clara
- 12 Factor: la configuracion se maneja por variables de entorno

## Dependencias relevantes

- FastAPI
- Pydantic
- PyMongo
- pypdf
- pytest
- mongomock

## Punto importante para clase

El proyecto ya no usa SQLite ni SQLAlchemy. Toda la persistencia actual se hace en MongoDB, que era uno de los requisitos del enunciado.

## Nota sobre `file_path`

El modelo interno todavia conserva un campo `file_path` por compatibilidad tecnica, pero en los documentos nuevos no representa una ruta real subida por el usuario.

Para los nuevos uploads se guarda solo una referencia logica interna tipo `memory://...`, ya que el procesamiento del PDF se realiza en memoria.
