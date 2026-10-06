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

## Fase 2: experimentos

### Como se mide

La notebook cambia de frecuencia segun temperatura y energia (de 2,1 a 3,5 GHz):
la misma imagen dio de 160 a 290 ms de CPU por request en distintos momentos,
y el throughput del spike vario entre 6 y 12 req/s con el mismo codigo. Para
que una comparacion valga:

- Las configuraciones se miden **intercaladas** (A, B, C, A, B, C...) y cada
  una al menos dos veces, asi el ruido afecta a todas por igual.
- Los cambios de CPU puro se comparan **en el mismo proceso**: la version vieja
  (sacada de git) y la nueva, alternadas 30 veces con los 4 PDFs.
- El spike (modelo cerrado) se mide con k6 y la carga fija (modelo abierto) con
  **Vegeta**, los dos dentro de la red de Docker (ver hallazgo 1).

### Error de medicion corregido: la carga fija con k6

Las primeras mediciones de la carga fija se hicieron con `carga_fija.js` (k6,
executor de tasa constante). Daban porcentajes de exito inflados: cada usuario
virtual de k6 carga los 4 PDFs (13,7 MB) y, con requests que esperan ~30 s,
hacen falta ~1.500 a la vez. k6 no llega a crearlos y **descarta iteraciones
sin contarlas**: en varias corridas mando entre 500 y 700 de los 1.500
requests, y el porcentaje se calculaba sobre esos. Esas mediciones se
descartaron. Desde entonces la carga fija se mide con Vegeta 12.13.0 en un
contenedor (`tests/stress/docker/vegeta.Dockerfile`), y `carga_fija.js` cuenta
las iteraciones descartadas como fallas y avisa.

### Experimento 1: API cruda de PDFium (F2-8)

El perfil mostraba ~10 % del CPU en los envoltorios de pypdfium2 (cada pagina
y cada pagina de texto es un objeto Python con finalizadores). El bucle de
paginas paso a usar los handles crudos (`FPDF_LoadPage`, `FPDFText_LoadPage`,
`FPDFText_GetText`) y a cerrarlos a mano.

| Version | CPU por PDF (mediana de 30) |
|---|---|
| pypdfium2 | 117,8 ms |
| API cruda | 111,0 ms (**-5,8 %**, gana en 24 de 30 pares) |

Salida identica byte a byte (texto y Markdown de los 4 PDFs). Menos que el 10 %
del perfil: abrir y cerrar cada pagina hay que hacerlo igual; se ahorra solo
el envoltorio.

### Experimento 2: compuerta de admision (F2-1 y F2-3)

`app/services/admission.py`, una por proceso:

1. **Cola acotada**: admite hasta `EXTRACT_MAX_PENDING` requests; llena, 503
   con `Retry-After` al instante, sin leer el PDF.
2. **Una extraccion por vez** en un semaforo de asyncio: antes cada request
   bloqueaba un hilo contra el lock de PDFium; ahora el event loop atiende HTTP
   y la extraccion va aparte (pista 4 de la consigna).
3. **Tiempo util**: si cuando le toca el turno el cliente ya se fue, o si
   espero mas de `EXTRACT_MAX_WAIT_SECONDS` (28 s), no se procesa (pista 2).

**Spike** (k6, 100 VUs, intercalado, 2 rondas):

| Version | Throughput | p50 | p95 |
|---|---|---|---|
| Fase 1 | 10,09 / 10,52 req/s | 8,49 / 7,45 s | 10,83 / 11,21 s |
| Compuerta | **11,80 / 12,25 req/s** | **6,82 / 6,66 s** | **9,39 / 9,06 s** |

+16 % de throughput con 100 % de exito. En el spike la compuerta nunca rechaza
(unos 20 requests por replica): la mejora viene de no tener 20 hilos peleando
por el lock de PDFium en cada replica.

#### Como se eligio el criterio de admision

La primera version estimaba la espera al llegar (pendientes x tiempo de
servicio promedio) y rechazaba si superaba el maximo. Problemas encontrados:

- Con un promedio que pesaba ~5 extracciones, un par de PDFs grandes seguidos
  lo inflaba y llego a rechazar **1 request en el spike** (que tiene que dar
  0 % de error).
- Con Vegeta, la prueba terminaba a los ~45 s cuando el timeout permite
  trabajar hasta los ~60 s: durante el ataque la CPU esta saturada (Vegeta y
  Traefik mueven ~167 MB/s de PDFs) y cada extraccion tarda mas, pero esa cola
  se vacia mucho mas rapido cuando el ataque termina. Una estimacion hecha en
  el momento admite de menos.

Por eso la cola paso a acotarse **por cantidad**, y el tiempo util lo controla
el chequeo exacto en el turno. **Carga fija con Vegeta** (50 req/s, 30 s,
timeout 30 s, 1.500 requests enviados), tres rondas intercaladas:

| Criterio | Exito | Timeouts | p50 | Pico de memoria |
|---|---|---|---|---|
| Estimacion de espera | 20,7 / 23,1 / 25,5 % | 141 / 57 / 26 | 0,1-3,1 s | ~540 MiB |
| **Cola de 30** | **21,5 / 25,8 / 24,0 %** | **0 / 0 / 0** | **~0,1 s** | **~390 MiB** |
| Cola de 100 | 26,1 / 32,7 / **7,7 %** | 117 / 4 / **985** | hasta 30 s | ~600 MiB |

Con 30, todo lo admitido se atiende antes de los 28 s. Con 100 la cola guarda
mas trabajo del que entra en el tiempo util: en una corrida todo vencio
esperando (colapso de una cola FIFO sobrecargada). El spike con cola de 30 sigue
en 100 % de exito sin ningun 503.

### Experimento 3: estrategia de balanceo de Traefik (F2-5)

Spike con k6, dos rondas intercaladas:

| Estrategia | Throughput | Errores |
|---|---|---|
| `wrr` (round robin) | 11,59 / 8,37 req/s | 0 / 1 (el 503 de la estimacion) |
| `p2c` (de dos al azar, la de menos en vuelo) | 11,08 / 11,55 req/s | 0 / 0 |
| `leasttime` (la que responde mas rapido) | 11,91 / 5,75 req/s | 0 / **1.172 rechazos** |

`leasttime` se descarto: cuando hay rechazos, la replica que "responde mas
rapido" es la que esta devolviendo 503, y le manda todavia mas trafico.
Entre `wrr` y `p2c` la diferencia queda dentro del ruido; se mantiene `wrr`
(configurable con `LB_STRATEGY`).

### Experimento 4: dos procesos por replica (F2-2)

Spike con `WEB_CONCURRENCY=2`: 11,02 / 11,32 / 11,61 req/s, igual que con 1
proceso, y p95 peor (~12,2 s contra ~10 s). Con 1 CPU de limite, dos procesos
se reparten el mismo nucleo; ademas cada uno tiene su cola, asi que duplica la
memoria de PDFs en espera. Se mantiene 1 proceso por replica.

### Descartados por medicion (F2-7)

Serializar la respuesta cuesta 0,3-1,5 ms contra 150-300 ms de extraccion
(menos del 1 %): orjson no justifica una dependencia nueva.

### Experimento 5: cuanto rinde cada replica (2026-10-06)

Carga cerrada constante (`tests/stress/escala.js`, 3 usuarios por replica,
60 s), variando la cantidad de replicas. El CPU por request sale del cgroup de
las replicas (`usage_usec` antes y despues).

| Replicas | req/s (ronda 1) | CPU por request | req/s (ronda 2) | CPU por request |
|---|---|---|---|---|
| 1 | 5,05 | 202 ms | 3,27 | 307 ms |
| 2 | 9,48 | 189 ms | 5,33 | 393 ms |
| 3 | 12,68 | 237 ms | - | - |
| 4 | 12,38 | 320 ms | - | - |
| 5 | 10,98 | 460 ms | 17,10 | 285 ms |

- En la ronda 1 escala casi lineal hasta 2 replicas y se estanca desde 3: el
  CPU por request **sube** con las replicas (de ~190 a 460 ms) aunque el codigo
  es el mismo. Con 4 nucleos fisicos para 5 replicas, Traefik y k6, los
  procesos comparten nucleo (hyperthreading) y la frecuencia baja.
- La ronda 2, con el mismo codigo, da otra forma (1 y 2 replicas mas lentas,
  5 mas rapidas): la frecuencia de la notebook cambio durante la medicion.
  Los numeros absolutos de esta maquina varian hasta 2 veces entre corridas.

Con una sola replica y 2 usuarios, en 5 corridas de 40 s: **5,5-6,4 req/s**,
con **159-186 ms de CPU por request**. El benchmark del profesor equivale a
25,35 / 5 = **5,07 req/s por replica**. Si cada una de las 5 replicas tuviera
su nucleo a esta velocidad, serian ~28-32 req/s. Es una **proyeccion**, no una
medicion: supone que el resto de la maquina (proxy y generador de carga) no le
quita CPU a las replicas, cosa que en esta notebook no pasa.

### Experimento 6: bajar el CPU por request (2026-10-06)

Desglose en el mismo proceso (los 4 PDFs, 8 repeticiones):

| Etapa | Costo | Parte |
|---|---|---|
| `FPDF_LoadPage` (PDFium interpreta la pagina) | 68 ms | 46 % |
| `FPDFText_LoadPage` (PDFium arma el texto) | 55 ms | 37 % |
| Medir la altura de las lineas (Python + PDFium) | 9 ms | 6 % |
| Armar el Markdown (Python) | 5 ms | 3 % |
| Copiar el texto, abrir y cerrar el documento | 5 ms | 4 % |

Por pagina, PDFium cuesta ~1 ms parejo: ningun PDF ni pagina en particular
dispara el costo. Con py-spy dentro del contenedor y bajo carga, el 92,5 % de
las muestras estan en la extraccion (79 % dentro de las llamadas a PDFium) y
~7 % en la capa HTTP. Lo que se probo para bajarlo:

| Intento | Resultado | Decision |
|---|---|---|
| PyMuPDF (MuPDF) | texto plano 108 ms, con tamanos de letra 129 ms, contra ~120 ms de PDFium | Descartado: no gana y es AGPL |
| pdf_oxide (Rust, MIT/Apache) | 356-467 ms por PDF, 2 a 3 veces mas lento | Descartado |
| jemalloc / mimalloc / umbral de mmap de glibc | dentro del ruido (+-10 % entre corridas) | Descartado |
| Abrir el documento y medir las letras sin envoltorios de pypdfium2 | -1,2 % y +1,8 % en dos A/B de 30 pares, salida identica | Descartado (no se commitea) |

Conclusion: ~85 % del CPU por request esta dentro de PDFium, el motor mas
rapido de los tres probados, y lo que queda en Python no se puede bajar de
forma medible. Para esta carga, el CPU por request esta en su piso.

### Experimento 7: limite en la app o en Traefik (F2-4, 2026-10-06)

Traefik trae el middleware `inFlightReq`: limita los requests en vuelo y
responde 429 al resto. Se comparo con Vegeta (50 req/s, 30 s), dos rondas
intercaladas:

- **app**: la compuerta de la app (cola de 30 por replica, tiempo util de
  28 s), sin limite en Traefik.
- **traefik**: `inFlightReq` con 150 en vuelo (5 x 30, comun a todos los
  clientes) y la compuerta de la app sin limite.
- **ambos**: las dos cosas.

| Configuracion | Exito | Rechazos | Timeouts | p50 | Pico de memoria |
|---|---|---|---|---|---|
| app | 32,7 / 20,7 % | 1.009 / 1.190 (503) | 0 / 0 | 0,07 / 0,13 s | ~420 MiB |
| traefik | 26,2 / 25,3 % | 1.107 / 1.120 (429) | 0 / 0 | 0,01 / 0,01 s | ~340 MiB |
| ambos | 22,5 / 25,1 % | ~1.130 (429 + 503) | 0 / 0 | 0,02 / 0,02 s | ~330 MiB |

El exito queda dentro del ruido de esta maquina: ninguna gana. Traefik usa
menos memoria en las replicas porque rechaza antes de reenviarles el PDF.
**Se mantiene el limite en la app**, sin el de Traefik:

- Con 150 en vuelo no hubo timeouts porque el numero coincide con lo que las
  5 replicas terminan en 28 s **en esta maquina y con estos PDFs**. Es un
  numero fijo: con PDFs mas pesados o una CPU mas lenta, los admitidos vencen
  esperando. La app corta por tiempo util en el momento del turno, asi que
  nunca procesa algo que ya vencio.
- La app responde 503 con `Retry-After`; `inFlightReq` responde 429 sin
  decirle al cliente cuando reintentar, y 429 significa "este cliente pide
  demasiado", no "el servicio esta saturado".
- El limite de Traefik es comun a todas las replicas; el de la app es por
  replica, y la protege tambien cuando se la usa sin este proxy (por ejemplo,
  desde `infrastructure`).

### Estado al cierre de los experimentos

| Prueba | Nosotros | Profesor |
|---|---|---|
| Spike, throughput | ~11-12 req/s | 25,35 req/s |
| Spike, p50 / p95 | ~7 s / ~9,5 s | 1,88 s / 8,80 s |
| Spike, errores | 0 % | 0 % |
| Vegeta, exito | ~24 % | 66,53 % |
| Vegeta, timeouts | **0** | 501 |
| Vegeta, p50 | **~0,1 s** | 14,89 s |

La capacidad bruta (req/s) sigue siendo la mitad. Lo que se gano es
comportamiento bajo sobrecarga: ningun request vence por timeout, los rechazos
son instantaneos y con `Retry-After`, la memoria esta acotada y no se gasta CPU
en respuestas que nadie va a leer.

**La comparacion absoluta no es justa**: esta PC es una notebook de 15 W con 4
nucleos para 5 replicas, Traefik y el generador de carga, y el benchmark del
profesor no dice en que hardware se midio (ni su microservicio de referencia
esta disponible para correrlo aca). La comparacion por replica del
experimento 5 es la mas justa que se puede hacer: con su nucleo propio, una
replica rinde 5,5-6,4 req/s contra 5,07 del profesor.

## Como reproducir

```powershell
docker compose up --build -d
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik /scripts/spike.js
docker build -t vegeta:12.13.0 -f tests/stress/docker/vegeta.Dockerfile tests/stress/docker
docker run --rm --network pdf-extractext-tp_default --entrypoint bash -v "${PWD}/tests/stress:/stress" vegeta:12.13.0 /stress/vegeta.sh http://traefik/extract
# Experimento 5: capacidad con N replicas (3 usuarios por replica)
docker compose up -d --scale extract=1
docker run --rm --network pdf-extractext-tp_default -v "${PWD}/tests/stress:/scripts:ro" grafana/k6 run -e BASE_URL=http://traefik -e VUS=3 /scripts/escala.js
```
