# ADR 0002: motor de extraccion y Markdown

- Estado: aceptada
- Fecha: 2026-09-19 (motor, version 1.1.0), 2026-10-02 (Markdown), revisada
  2026-10-06

## Contexto

El 85 % del CPU de cada request se va en extraer el texto (perfil con py-spy,
Fase 2). La consigna pide Markdown, no texto plano, y libertad de stack.

## Decision

- **PDFium** (el motor de Chrome) a traves de `pypdfium2`, licencia
  Apache/BSD, llamando a su API cruda en el bucle de paginas.
- **Markdown con una heuristica propia** (`app/core/markdown.py`): la altura
  de letra mas frecuente es el cuerpo; las lineas cortas con letra 1,15x,
  1,35x o 1,8x mas grande son titulos de nivel 3, 2 y 1; las vinetas pasan a
  `- `. La altura de cada linea se mide en una sola letra cerca del centro.
- El motor queda detras de la interfaz `PdfExtractor`: `ExtractionService` lo
  recibe por constructor y otro motor se prueba sin tocar el servicio ni el
  router.

## Alternativas medidas

| Alternativa | Resultado | Por que no |
|---|---|---|
| pypdf | 19x mas lento (version 1.1.0) | CPU |
| PyMuPDF (MuPDF) | 108-129 ms contra ~120 ms de PDFium | no gana y es AGPL |
| pdf_oxide (Rust) | 2 a 3 veces mas lento | CPU |
| PyMuPDF4LLM / librerias con modelos de ML | Markdown mas rico | AGPL o mucho mas lentas |
| Envoltorios de pypdfium2 por pagina | +5,8 % de CPU | se reemplazaron por la API cruda |
| Altura de 3 letras por linea (mediana) | +48 % sobre texto plano, contra +22 % con 1 letra | mismo Markdown en los 4 PDFs, mas caro |
| jemalloc / mimalloc | dentro del ruido | sin ganancia |

## Consecuencias

- PDFium no es thread-safe: un lock por proceso serializa la extraccion. El
  paralelismo viene de las replicas (ver [0004](0004-workers-y-replicas.md)).
- El CPU por request queda en el piso de PDFium (~160-200 ms por PDF con
  nucleo propio): lo que queda en Python no se puede bajar de forma medible.
- La heuristica no reconoce tablas ni columnas; para el benchmark alcanza con
  titulos, parrafos y listas.
