# Guion de Demo

## Objetivo

Mostrar en pocos minutos que la API:

- recibe un PDF real
- valida el archivo
- evita duplicados
- extrae texto en memoria
- persiste en MongoDB

## Preparacion previa

Antes de la clase o la demo:

1. Tener Docker Desktop iniciado.
2. Tener un PDF con texto seleccionable.
3. Tener un segundo PDF igual para mostrar duplicados, o volver a usar el mismo.
4. Opcional: tener un PDF escaneado o con imagenes para explicar la limitacion sin OCR.

## Arranque

### 1. Levantar MongoDB

```bash
docker compose up -d
docker compose ps
```

Esperado:

- el servicio `mongodb` aparece como `running` o `healthy`

### 2. Levantar la API

```bash
python main.py
```

### 3. Abrir Swagger

Abrir en el navegador:

- `http://localhost:8000/docs`

## Orden recomendado para mostrar

### 1. Verificacion de salud

Endpoint:

- `GET /health`

Que decir:

- "Este endpoint confirma que la API esta corriendo y que MongoDB esta conectado."

Esperado:

```json
{
  "status": "ok",
  "database": "mongodb",
  "database_name": "pdf_extract"
}
```

### 2. Alta de un PDF real

Endpoint:

- `POST /api/v1/documents`

Completar:

- `name`: cualquier nombre
- `file`: seleccionar un PDF real

Que decir:

- "La API recibe el archivo directamente por upload."
- "Valida que sea un PDF real, calcula checksum y extrae texto en memoria."

Esperado:

- codigo `201`
- `checksum`
- `original_filename`
- `extracted_text`
- `is_processed: true`

### 3. Listado de documentos

Endpoint:

- `GET /api/v1/documents`

Que decir:

- "Aca vemos que el documento quedo persistido en MongoDB."

### 4. Rechazo de duplicados

Volver a usar:

- `POST /api/v1/documents`

Subir exactamente el mismo PDF.

Que decir:

- "Aunque cambie el nombre, si el contenido es el mismo el checksum coincide y la API lo rechaza."

Esperado:

- codigo `400`
- detalle: `Ya existe un documento con el mismo checksum`

### 5. Actualizacion del nombre

Endpoint:

- `PUT /api/v1/documents/{document_id}`

Body:

```json
{
  "name": "Nombre actualizado"
}
```

Que decir:

- "La API permite actualizar el nombre, pero no campos internos como checksum o texto extraido."

### 6. Eliminacion

Endpoint:

- `DELETE /api/v1/documents/{document_id}`

Que decir:

- "El CRUD queda completo: alta, consulta, modificacion y baja."

## Caso especial para explicar

Si subis un PDF escaneado o compuesto por imagenes, `extracted_text` puede venir vacio.

Que decir:

- "Eso no significa que la API falle."
- "Significa que el PDF no tenia texto digital extraible."
- "La extraccion actual usa `pypdf` y no implementa OCR."

## Cierre sugerido

Frase corta para cerrar:

> La API ya cumple el flujo principal pedido por el trabajo: recibe PDFs reales, valida formato y tamano, evita duplicados por checksum, extrae texto en memoria y persiste los resultados en una base no relacional.
