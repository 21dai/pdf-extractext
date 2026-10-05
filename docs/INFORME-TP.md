# Informe del TP: Test de Carga, Estres y Optimizacion

Informe tecnico de la entrega. Se completa con cada medicion; el plan de
trabajo esta en [PLAN-TP.md](PLAN-TP.md) y los scripts en
[tests/stress](../tests/stress/README.md).

## Arquitectura

```
cliente (k6 / Vegeta)
   |  POST /extract  (PDF crudo o multipart)
   v
Traefik v3.7  ---- round robin ---->  extract x5  (1 CPU, 1 GB c/u)
 (1 CPU, 512 MB)                       FastAPI + uvicorn + pypdfium2
                                       sin estado, sin base de datos
```

- **Sin estado (12-Factor VI).** `/extract` valida y extrae; no calcula
  checksum, no busca duplicados y no escribe en MongoDB. Las replicas corren
  con `DOCUMENTS_API_ENABLED=false`: arrancan sin base de datos y su
  `/health` no depende de ella.
- **Motor de extraccion: pypdfium2** (PDFium, el motor de Chrome; licencia
  Apache/BSD). Ya lo habiamos elegido contra pypdf (19x mas lento) y PyMuPDF
  (licencia AGPL) en la version 1.1.0.
- **Lectura del body en memoria**, cortada apenas supera el limite; si el
  cliente manda `Content-Length`, se rechaza con 413 antes de leer.

## Linea base (2026-10-02)

Stack del TP (`docker compose up --build`): 5 replicas con 1 proceso de
uvicorn cada una. PC con 8 nucleos, Docker Desktop sobre WSL2 (la VM de
Docker tiene 8 CPUs y 10,6 GB). Spike de k6 con el perfil del profesor
(100 VUs, 10s/20s/10s), PDF como body crudo.

| Corrida | Exito | Throughput (200) | p50 | p90 | p95 | Max |
|---|---|---|---|---|---|---|
| **Profesor** | 100 % | **25,35 req/s** | 1,88 s | 7,83 s | 8,80 s | 13,94 s |
| k6 desde Windows, por HTTPS | 100 % | 3,41 req/s | 11,05 s | 41,54 s | 43,70 s | 54,34 s |
| k6 dentro de la red de Docker, por HTTP | 100 % | 7,75 req/s | 11,06 s | 15,75 s | 16,94 s | 18,68 s |
| k6 dentro de la red, **1 solo VU** | 100 % | 3,71 req/s | 0,21 s | 0,46 s | 0,69 s | 1,24 s |

### Hallazgo 1: el reenvio de puertos de Docker Desktop distorsiona la medicion

Corriendo k6 desde Windows, el Kanban (8,9 MB) tenia una mediana de 41 s y
el Scrum Guide (0,3 MB) de 3 s: el tiempo crecia con el **tamano** del
archivo, no con su cantidad de paginas. Durante la prueba, varias replicas
estaban al 16-24 % de CPU y Traefik al 55 %: nadie estaba saturado.

El trafico de Windows a los contenedores pasa por el reenvio de puertos de
Docker Desktop hacia la VM de WSL2, que tenia que mover ~12 MB/s de uploads
concurrentes. Corriendo el mismo script en un contenedor de k6 dentro de la
red de Docker, el throughput se duplico y todos los PDFs pasaron a tardar lo
mismo (~12 s). El cuello de botella era del entorno de medicion, no del
servicio. El profesor mide en Linux, donde ese reenvio no existe, asi que
**las mediciones comparables se hacen desde dentro de la red de Docker**.

### Hallazgo 2: con 20 requests concurrentes por replica, cada request cuesta 3 veces mas CPU

> **Corregido en la Fase 2** (ver "Diagnostico"): midiendo el tiempo de CPU
> del proceso, el costo por request es el mismo con 1, 5 o 20 requests
> concurrentes. La estimacion de abajo salia de `docker stats` con 5 replicas,
> Traefik y k6 compitiendo por los mismos nucleos.

Tiempo de CPU de la extraccion sola, en un contenedor con 1 CPU:

| PDF | Paginas | Extraccion | JSON |
|---|---|---|---|
| Scrum Guide | 16 | 53 ms | 0,3 ms |
| Essential Kanban | 90 | 214 ms | 1,5 ms |
| Filosofia Lean | 42 | 178 ms | 0,5 ms |
| Scrum Manager | 62 | 352 ms | 0,8 ms |
| **Promedio** | | **~200 ms** | |

Con ~200 ms por PDF, 5 replicas de 1 CPU tienen un techo teorico de
**~25 req/s**, el mismo numero que el profesor. Con un solo usuario la
mediana es 0,21 s, coherente con ese costo. Pero con 100 VUs (20 requests en
vuelo por replica) las 5 replicas estan al 100 % de CPU y procesan 1,55
req/s cada una: **~0,65 s de CPU por request**, el triple.

El costo extra aparece solo con concurrencia: dentro de cada proceso compiten
el event loop (recibiendo 20 uploads a la vez) y el hilo que extrae, por el
mismo GIL y por la misma cuota de 1 CPU. Es exactamente lo que apuntan las
pistas 2 y 4 de la consigna (control de concurrencia y pool de workers
separado del runtime HTTP), y es lo primero a atacar en la Fase 2 del plan.

## Fin de la Fase 0 (2026-10-02, version 1.2.0)

Con todos los requisitos de la consigna cumplidos: `/extract` devuelve
Markdown, 5 replicas sin estado con limites de recursos y ruta directa en
Traefik. Spike del profesor con k6 dentro de la red de Docker:

| Corrida | Exito | Throughput (200) | p50 | p90 | p95 | Max |
|---|---|---|---|---|---|---|
| **Profesor** | 100 % | **25,35 req/s** | 1,88 s | 7,83 s | 8,80 s | 13,94 s |
| Linea base (texto plano) | 100 % | 7,75 req/s | 11,06 s | 15,75 s | 16,94 s | 18,68 s |
| **Fase 0 (Markdown)** | 100 % | 5,80 req/s | 13,99 s | 17,82 s | 18,90 s | 20,88 s |

### Costo del Markdown

El Markdown se arma con una heuristica propia (`app/core/markdown.py`): la
altura de letra mas frecuente es el cuerpo, y las lineas cortas con letra
1,15x / 1,35x / 1,8x mas grande son titulos de nivel 3, 2 y 1. No se uso una
libreria porque las que generan Markdown de PDF son AGPL (PyMuPDF4LLM) o
cargan modelos de ML, mucho mas lentos.

Tiempo de CPU promedio de los 4 PDFs en un contenedor con 1 CPU:

| Version | Extraccion | Sobre el texto plano |
|---|---|---|
| Texto plano | 124 ms | - |
| Markdown, mediana de 3 letras por linea | 178 ms | +48 % |
| **Markdown, 1 letra cerca del centro** | **151 ms** | **+22 %** |

Medir una sola letra da exactamente el mismo Markdown en los 4 PDFs. La caida
de throughput entre la linea base y la Fase 0 (7,75 -> 5,80 req/s) es mayor
que ese +22 %: las corridas en Docker Desktop tienen bastante variacion entre
si, algo a controlar en la Fase 2 repitiendo cada medicion.

### Memoria

Pico de memoria por replica durante el spike: entre 363 y 440 MiB. El limite
de 1 GB deja margen; uno de 512 MB quedaria al borde de que Docker mate el
contenedor por falta de memoria.

## Fase 2: diagnostico (2026-10-05)

### Hardware

AMD Ryzen 5 3450U de notebook: **4 nucleos fisicos con SMT (8 hilos)**, 2,1 GHz
base, 22 GB de RAM. Docker Desktop le da 8 CPUs a su VM, pero son 8 hilos de 4
nucleos: las 5 replicas de "1 CPU", Traefik y el generador de carga compiten
por 4 nucleos reales. El benchmark del profesor no dice en que hardware se
midio.

### Linea base de la Fase 2 (version 1.2.0 + Fase 1, k6 dentro de la red)

| Prueba | Exito | Throughput (200) | p50 | p90 | p95 | Max |
|---|---|---|---|---|---|---|
| Spike, corrida 1 | 100 % | 9,30 req/s | 8,80 s | 11,94 s | 12,48 s | 13,30 s |
| Spike, corrida 2 | 100 % | 9,25 req/s | 8,56 s | 11,17 s | 12,91 s | 14,09 s |
| Carga fija 50 req/s (`carga_fija.js`) | **37,1 %** | **2,93 req/s** | 29,99 s | 30,00 s | 30,00 s | 30,09 s |

El spike subio de 5,80 a 9,3 req/s respecto del cierre de la Fase 0; el cambio
mas probable es la imagen en Python 3.14 (antes 3.13), queda para verificar.

**La carga fija colapsa:** con ~9 req/s de capacidad, el servicio completa solo
2,93 req/s efectivos y 298 requests vencen por timeout. Es el colapso por
congestion: las replicas siguen procesando requests cuyo cliente ya se fue a
los 30 s, y ese trabajo se tira mientras los requests nuevos esperan en cola.

### CPU por request segun la concurrencia

Una replica sola (1 CPU), 200 requests con k6, tiempo de CPU del proceso leido
de `/proc`:

| Requests concurrentes | CPU por request | Throughput | p50 |
|---|---|---|---|
| 1 | 291 ms | 3,07 req/s | 0,27 s |
| 5 | 288 ms | 3,20 req/s | 1,39 s |
| 20 | 314 ms | 2,85 req/s | 5,59 s |

El costo por request **no depende de la concurrencia**: el hallazgo 2 de la
Fase 0 estaba mal. Una replica procesa ~3 req/s; 5 replicas, ~15 req/s si
tuvieran 5 nucleos libres, que esta PC no tiene.

### Donde se va el CPU

- Logs del servidor (`pdf_extraido`), un usuario: la extraccion dura 133 ms
  (Scrum Guide), 191 ms (Lean), 240 ms (Scrum Manager) y 339 ms (Kanban),
  **~226 ms en promedio de ~290 ms totales: el 78 %**.
- Perfil con py-spy de una replica bajo carga (4.333 muestras en 30 s):

| Donde | Muestras |
|---|---|
| PDFium cargando cada pagina (`get_page`) | 44 % |
| PDFium armando el texto de la pagina (`get_textpage`) | 28 % |
| Envoltorios de pypdfium2 (cerrar objetos, finalizadores con weakref) | ~10 % |
| Nuestro Markdown y la medicion de alturas | ~10 % |
| HTTP: recibir el body, FastAPI, JSON | ~5 % |

**Conclusiones para los experimentos:**

1. El costo esta en la extraccion misma, no en la infraestructura HTTP: no hay
   que buscar el problema en uvicorn ni en Traefik.
2. ~10 % se va en los objetos de pypdfium2 (cada pagina y cada pagina de texto
   se envuelven en objetos Python con finalizadores). Usar la API cruda de
   PDFium en el bucle de paginas puede ahorrarlo.
3. En el modelo abierto el problema es el trabajo desperdiciado: hace falta
   backpressure (rechazar rapido lo que no se va a poder atender a tiempo) y
   dejar de procesar requests cuyo cliente ya se desconecto.
4. Con 1 CPU por replica, mas procesos por replica (`WEB_CONCURRENCY`) o un
   pool de procesos no agregan capacidad: a lo sumo separan el HTTP de la
   extraccion. Hay que medirlo, pero no es donde esta la ganancia.

## Como reproducir

```powershell
docker compose up --build -d
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik /scripts/spike.js
```
