# Evaluacion de carga con Vegeta

Fecha: 2026-09-16. API `pdf-extractext` 1.0.1 corriendo en Docker
(`docker compose -f docker/docker-compose.yml`), un solo proceso de uvicorn,
MongoDB en Docker, Vegeta v12.13.0 desde Windows contra `127.0.0.1:8000`.

Documento de prueba: PDF de **279 paginas**, 40 lineas de texto por pagina,
1,1 MB, generado con `build_pdf.py`. Los reportes completos (`.json` y los
graficos `.html`) quedan en `results/` al correr los ataques.

## Resultados

| Ataque | Rate | Requests | Exito | p50 | p95 | p99 | Codigos |
|---|---|---|---|---|---|---|---|
| `GET /health` | 50/s, 30 s | 1500 | 100 % | 5 ms | 9 ms | 21 ms | 200: 1500 |
| `GET /documents/{id}` (279 p.) | 10/s, 30 s | 300 | 100 % | 24 ms | 33 ms | 42 ms | 200: 300 |
| `POST /documents` (279 p.) | 0,5/s, 30 s | 15 | 93 % | 1,7 s | 2,5 s | 2,5 s | 201: 14, 400: 1 (*) |
| `GET /health` durante el POST a 0,5/s | 10/s, 35 s | 350 | 100 % | 491 ms | 1,7 s | 2,2 s | 200: 350 |
| `POST /documents` (279 p.) | 2/s, 30 s | 60 | **27 %** | **30 s** | 30 s | 30 s | 201: 16, 400: 2 (*), timeout: 42 |
| `GET /health` durante el POST a 2/s | 10/s, 35 s | 350 | **77 %** | 5,2 s | 30 s | 30 s | 200: 270, timeout: 80 |

(*) Los 400 son duplicados intencionales: el mismo PDF ya estaba cargado y el
service rechaza checksums repetidos. Es el comportamiento esperado.

Un solo `POST` de 279 paginas, sin carga, tarda **1,6 s** y devuelve 886 000
caracteres de texto extraido (todas las paginas, verificado).

## Que funciona

- Los endpoints de lectura son rapidos y estables: `/health` responde en
  5 ms a 50 req/s y el `GET` de un documento de 279 paginas en 24 ms a 10 req/s,
  sin un solo error.
- La extraccion del PDF de 279 paginas es correcta y completa.
- La deduplicacion por checksum funciona bajo carga (400 consistente).
- El servidor no pierde trabajo: los 42 uploads que Vegeta dio por perdidos a
  los 30 s igual terminaron procesados y guardados en Mongo. Cuando la cola
  se vacio, la API volvio a responder `/health` en 10 ms sin reiniciar.

## Que no funciona

1. **El `POST` bloquea toda la API mientras procesa.** Con uploads a 0,5/s,
   `/health` pasa de 5 ms a 491 ms de mediana y 2,2 s de p99. Con uploads a
   2/s, el 23 % de los `/health` no responde en 30 s. Causa: los endpoints
   son `async def` y llaman al service sincronico (`pypdf` es CPU) dentro
   del event loop de uvicorn, asi que ningun otro request avanza hasta que
   termina la extraccion (`app/api/routers/document.py:40-52`).

2. **Capacidad de ~0,6 uploads/s de 279 paginas.** Cada extraccion ocupa
   1,7 s del unico proceso. A 2/s la cola crece sin limite, la latencia sube
   de 1,7 s a 30 s en 9 segundos y el 70 % de los clientes recibe timeout.
   No hay ningun mecanismo que rechace carga (429) ni que limite la cola.

3. **Las respuestas del `GET` pesan lo que pesa el texto.** El documento de
   279 paginas devuelve 900 KB por request porque `extracted_text` viaja
   entero. A 10 req/s son 9 MB/s. El listado (`GET /documents`) devuelve
   hasta 100 documentos completos.

## Recomendaciones, en orden

1. Sacar la extraccion del event loop. La opcion minima es declarar los
   endpoints con `def` en vez de `async def`: FastAPI los corre en un pool
   de hilos y `/health` deja de esperar. La opcion completa es
   `await run_in_threadpool(service.create_document, ...)` solo en el `POST`.
2. Correr mas de un proceso de uvicorn (`--workers N`) para usar mas de un
   nucleo; hoy la API usa uno.
3. Limitar la concurrencia del `POST` con un semaforo y responder 429 o 503
   cuando la cola supere un umbral, en vez de aceptar todo y colgar.
4. No devolver `extracted_text` en el listado, y evaluar un endpoint aparte
   (o paginado) para el texto de un documento.

Con esto los patrones que pide el orquestador (Retry, Circuit Breaker,
Bulkhead) tendrian sentido: hoy un reintento contra este servicio bajo carga
solo empeora la cola.

## Resultado despues de los cambios (version 1.1.0, 2026-09-19)

Se aplicaron las recomendaciones 1 y 2, y ademas se cambio la libreria de
extraccion: `pypdf` -> `pypdfium2` (PDFium). En el PDF de 90 paginas y 8,9 MB
la extraccion pura paso de 3,7 s a 0,2 s. PDFium no es thread-safe, asi que la
extraccion se serializa con un lock por proceso y el paralelismo viene de los
workers de uvicorn (`WEB_CONCURRENCY`).

Medido de punta a punta a traves de Traefik y el orquestador, con los 4 PDFs
reales de la catedra (16 a 90 paginas, 0,3 a 8,9 MB), spike de k6 con 10
usuarios concurrentes durante 40 s:

| Version | Exito | Mediana | Documentos/s |
|---|---|---|---|
| 1.0.1 (pypdf, 1 proceso, `async def`) | 23 % | 8,6 s | 0,7 |
| 1.0.1 + 4 workers + endpoints `def` | 100 % | 13,3 s | 0,6 |
| 1.1.0 (pypdfium2 + lock + 8 workers) | **100 %** | **0,5 s** | **4,5** |

Con 100 usuarios concurrentes (el spike original de la catedra) el exito se
mantiene en 99-100 %, pero la mediana sube a 11-18 s: con ~4,5 documentos/s de
capacidad y 100 pedidos en vuelo, cada uno espera en promedio 100 / 4,5 = 22 s
(ley de Little). Para que 100 concurrentes sean rapidos hace falta escalar
`pdf-extractext` horizontalmente, no mas codigo.
