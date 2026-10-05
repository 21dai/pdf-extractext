# Plan del TP: Test de Carga, Estres y Optimizacion de Microservicio

Hoja de ruta para la entrega del TP de Desarrollo de Software (UTN FRSR) y
para dejar `pdf-extractext` alineado con la teoria de la catedra: los 8
principios de *production-readiness* de Susan Fowler, 12-Factor App, Codigo
Limpio, TDD y los patrones de microservicios.

Alcance: todo ocurre dentro de `pdf-extractext` e `infrastructure`. No se
agregan microservicios nuevos (document-store, colas, auth): eso queda para
el resto del equipo y nada de este plan lo bloquea.

## Lo que pide la consigna

- Endpoint obligatorio **`POST /extract`**. Entrada: PDF binario, por
  `multipart/form-data` o directo en el body. Salida: **`200 OK`** con
  `application/json`:

  ```json
  { "content": "<texto en Markdown>", "page_count": 292 }
  ```

- Imagen Docker y despliegue con `docker compose`, reproducible con un unico
  `docker compose up --build`.
- Hasta **5 replicas** detras de un reverse proxy con balanceo.
- **Limite explicito de recursos** por contenedor (orden de 1.0 CPU y
  512 MB a 1 GB de RAM).
- PDFs de prueba en **`tests/stress/pdfs`**.
- Entregables: repo, script de k6 (spike), script de Vegeta (carga fija) e
  informe con arquitectura, cuello de botella, metricas antes vs. despues y el
  proceso de investigacion.

## Benchmark a superar

| Prueba | Metrica del profesor |
|---|---|
| k6 spike: 100 VUs (10 s subida, 20 s meseta, 10 s bajada) | 1.037 peticiones, **25,35 req/s**, 0,00 % error, p50 **1,88 s**, p90 7,83 s, p95 8,80 s, max 13,94 s |
| Vegeta: 50 req/s durante 30 s, timeout 30 s | 16,65 req/s, 998/1500 exitosas (**66,53 %**), 501 timeouts, p50 **14,89 s** |

Superarlo suma +1,5 puntos en el 2do parcial; el mejor grupo suma +1,0 extra.

Punto de partida medido (2026-09-19, camino Traefik -> orquestador ->
pdf-extractext -> MongoDB, 8 workers): 100 % de exito y ~4,5 docs/s con
10 VUs; con 100 VUs, 99,6 % de exito y mediana de 11 a 18 s. La diferencia
con el profesor es de arquitectura: ese camino calcula checksum, consulta
duplicados y escribe el texto en Mongo en cada request.

---

## Fase 0: requisitos de la consigna

- [x] **F0-1** `POST /extract` que acepte el PDF crudo en el body
  (`Content-Type: application/pdf`, como el `spike_tests.js` del profesor) y
  tambien multipart.
- [x] **F0-2** Respuesta `200` con `{"content", "page_count"}` en un schema
  propio, separado de `DocumentResponse`.
- [x] **F0-3** Conversion a Markdown (hoy se devuelve texto plano).
- [x] **F0-4** `/extract` sin estado: sin MongoDB, sin checksum, sin
  duplicados (12-Factor VI). El CRUD de `/api/v1/documents` no cambia.
- [x] **F0-5** Quitar `container_name` del servicio en el compose: impide
  escalar.
- [x] **F0-6** 5 replicas con `deploy.replicas`.
- [x] **F0-7** Limites de CPU y memoria por replica con
  `deploy.resources.limits`, ajustados midiendo el pico de RAM.
- [x] **F0-8** Ruta directa de Traefik a `/extract`, sin pasar por el
  orquestador, en el host `extract.universidad.localhost` que usa el script
  del profesor.
- [x] **F0-9** PDFs de prueba en `tests/stress/pdfs/`.
- [x] **F0-10** Scripts de k6 (spike) y Vegeta (50 req/s) dentro del repo, en
  `tests/stress/`.
- [x] **F0-11** `docker compose up --build` autocontenido en este repo
  (Traefik + extract x5 con limites), sin depender de los repos hermanos.

## Fase 1: problemas del proyecto actual

- [x] **F1-1** Los uploads de mas de 1 MB se escriben a disco: `UploadFile` de
  Starlette usa un archivo temporal a partir de 1 MB. En `/extract`, leer el
  body en memoria y rechazar por `Content-Length` antes de leerlo.
- [ ] **F1-2** Agregar CI (GitHub Actions: black, isort, flake8, mypy, pytest
  y build de la imagen). El orquestador ya lo tiene.
- [ ] **F1-3** Sacar las credenciales de MongoDB del compose de
  `infrastructure` a un `.env` (12-Factor III).
- [ ] **F1-4** Consolidar la documentacion: hay 9 `.md` en la raiz y cuatro
  todavia mencionan `pypdf` (ARCHITECTURE, DEMO, EJEMPLOS,
  REVISION_ENUNCIADO). Dejar `README.md`, `ARCHITECTURE.md` y `docs/`.
- [x] **F1-5** Logs estructurados propios a stdout: tamano, paginas, ms de
  extraccion y errores (Fowler: Monitoring; 12-Factor XI).
- [x] **F1-6** Separar liveness (`/health`) de readiness (base de datos): las
  replicas de `/extract` no deben caer porque cae MongoDB.
- [ ] **F1-7** Dockerfile multi-stage, sin `pip install uv` en la imagen final.
- [ ] **F1-8** Unificar la version de Python con el orquestador (3.13 vs 3.14).
- [ ] **F1-9** Imagenes con tag versionado en `infrastructure`
  (`image: pdf-extractext:${IMAGE_TAG}`, 12-Factor V).
- [x] **F1-10** La limpieza de MongoDB como target del `Makefile` o script
  (12-Factor XII).

## Fase 2: optimizacion (proceso de investigacion)

Cada item es un experimento: se mide antes y despues con el spike de k6
(100 VUs) y con Vegeta (50 req/s x 30 s), con los mismos 4 PDFs, anotando
throughput, % de exito, p50/p90/p95/max y CPU/RAM (`docker stats`).

- [ ] **F2-1** Pool de procesos separado del runtime HTTP
  (`ProcessPoolExecutor`): pista 4 de la consigna.
- [ ] **F2-2** Cantidad de procesos por replica con 1 CPU de limite (1, 2, 3).
- [ ] **F2-3** Backpressure con fecha limite: cola acotada y `503` con
  `Retry-After` cuando la espera estimada supera el tiempo util (< 30 s del
  timeout de Vegeta), en vez de dejar expirar el request.
- [ ] **F2-4** Comparar ese limite en la app contra el middleware
  `inFlightReq` de Traefik (responde `429`).
- [ ] **F2-5** Estrategia de balanceo de Traefik frente a PDFs de costo muy
  distinto (0,3 MB vs 9 MB).
- [ ] **F2-6** Motor de Markdown: heuristica propia sobre pypdfium2 (tamano de
  fuente -> titulos) vs. librerias existentes, con su licencia y su costo.
- [ ] **F2-7** Serializacion JSON con orjson (~700 KB de `content` en el PDF
  mas grande).
- [ ] **F2-8** Pasar los bytes del body directo a pdfium, sin copias.
- [ ] **F2-9** Pico de memoria por replica con el PDF mas pesado, para
  justificar el limite de F0-7.

## Fase 3: principios

### Fowler, production-readiness

| Principio | Accion |
|---|---|
| Stability | F1-2 y un tag de git por version. Agregar `/extract` es MINOR. |
| Reliability | F1-6 y apagado ordenado (terminar lo que se esta procesando ante SIGTERM). |
| Scalability | Plan de capacidad escrito: req/s por CPU, por replica y con 5 replicas. |
| Fault tolerance | Chaos test: `docker kill` de una replica durante el k6. Listar los puntos unicos de falla (Traefik, MongoDB). |
| Performance | SLO escrito (p95, req/s, % de error) y cargado como `thresholds` de k6. |
| Monitoring | F1-5. Opcional: Prometheus + Grafana con las metricas de Traefik. |
| Documentation | F1-4, diagrama de arquitectura, runbook y ADRs. |

### 12-Factor

| Factor | Estado |
|---|---|
| I, II, IV, VII, VIII | Cumplen |
| III Config | F1-3 |
| V Build/release/run | F1-9 |
| VI Procesos sin estado | F0-4 |
| IX Disposability | F1-7, apagado ordenado, tiempo de arranque |
| X Paridad dev/prod | F1-8 |
| XI Logs | F1-5 |
| XII Procesos de administracion | F1-10 |

### TDD y Codigo Limpio

- [x] **F3-1** `/extract` con el ciclo visible en el historial: commit del test
  en rojo, despues el verde, despues el refactor.
- [ ] **F3-2** Tests de `/extract`: `200`, `400` no es PDF, `413` demasiado
  grande, `422` PDF ilegible, `503` saturado, body crudo y multipart.
- [x] **F3-3** Tests del conversor a Markdown con archivos de referencia
  (PDF de fixture y su `.md` esperado).
- [ ] **F3-4** Motor de extraccion detras de una interfaz, para poder cambiarlo
  y medir sin tocar el router.
- [x] **F3-5** Errores de `/extract` en RFC 9457 (sucesor de 7807), como el resto del servicio.

## Fase 4: entregables

- [ ] **F4-1** Informe: arquitectura y decisiones, cuello de botella, tabla
  antes/despues de cada experimento, proceso de investigacion y comparacion
  con el benchmark del profesor.
- [ ] **F4-2** ADRs en `docs/decisions/`: contrato de `/extract`, motor de
  Markdown, backpressure, workers y replicas.
- [ ] **F4-3** README con "como reproducir el benchmark" en pocos comandos.

## Orden de trabajo

```
F0-9, F0-10                 PDFs y scripts dentro del repo
   |
F3-1 -> F0-1, F0-2, F0-4    /extract con TDD, todavia sin Markdown
   |
F0-5..F0-8, F0-11           5 replicas, limites, ruta directa -> linea base
   |
F0-3 + F2-6                 Markdown
   |
F2-1..F2-9                  experimentos, de a uno, midiendo cada uno
   |
F1-x, F3-x                  en paralelo
   |
F4                          el informe se escribe con cada medicion
```
