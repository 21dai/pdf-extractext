# Que mas se puede hacer para superar al profesor

Hoja de ruta despues de la version 1.3.3. Cada propuesta sale de una medicion
del [informe](INFORME-TP.md); los tiempos son estimaciones para una persona
del grupo que ya conoce el proyecto.

## Donde estamos y que hace falta

| Metrica | Nosotros (notebook) | Profesor | Que la mueve |
|---|---|---|---|
| Spike: throughput | 11-14,5 req/s | 25,35 req/s | CPU disponible y CPU por request |
| Spike: p50 / p95 | ~6-7 s / ~7,8-11,3 s | 1,88 s / 8,80 s | el throughput (ley de Little) |
| Vegeta: exito | ~25-30 % (1.3.3) | 66,53 % | el throughput |
| Vegeta: timeouts / p50 | **0-1 / 0,1-2,5 s** | 501 / 14,89 s | ya ganamos |

Dos numeros explican casi todo:

- **CPU por request: 160-200 ms** con un nucleo propio (el 85 % dentro de
  PDFium). Para igualar 25,35 req/s con 5 replicas de 1 CPU hace falta
  5.000 ms / 25,35 = **197 ms por request**: con nucleo propio ya estamos ahi
  o un poco mejor (5,5-6,4 req/s por replica contra 5,07).
- **CPU disponible**: la notebook tiene 4 nucleos fisicos para 5 replicas,
  Traefik y el generador de carga. Con 5 replicas el CPU por request sube a
  ~460 ms porque se comparten nucleos.

En el spike, con 100 usuarios fijos, la latencia promedio es la cantidad de
usuarios en vuelo dividida por el throughput (ley de Little): no se puede
bajar la latencia sin subir el throughput. Por eso **casi todo pasa por tener
mas CPU real o gastar menos CPU por request**.

## Propuestas, de mayor a menor impacto por hora de trabajo

### 1. Medir en una maquina con mas nucleos (1-2 horas, sin tocar codigo)

La consigna fija los limites por contenedor (1 CPU por replica), no la
maquina. Con 8 nucleos fisicos o mas, cada replica tiene su nucleo y el
generador de carga no les quita CPU.

- Que hacer: correr `tests/stress/benchmark.ps1` en la PC de escritorio mas
  potente del grupo o en una del laboratorio, o correr k6 y Vegeta desde otra
  maquina en la misma red apuntando a la IP de la que tiene el stack.
- Ganancia esperada: de 9-15 a **~25-30 req/s** en el spike (proyeccion del
  experimento 5), p95 por debajo de 8,80 s y bastante mas exito en Vegeta.
- Riesgo: ninguno. Es la unica forma de comparar contra el profesor en
  condiciones parecidas a las suyas.

### 2. Preparar la notebook para medir (15-30 minutos)

La variacion entre corridas es de hasta 2 veces con el mismo codigo.

- Enchufada, plan de energia "Maximo rendimiento", sin otros programas
  abiertos, y Docker Desktop recien iniciado.
- Repetir cada prueba 3 veces y reportar la mediana.
- Ganancia: no sube el techo, pero evita corridas malas (de 9 a 13-15 req/s
  en el spike segun el momento).

### 3. Volver a medir una cola mas larga, ahora que el tiempo util es exacto (1 hora) - HECHO

Hasta la 1.3.0, una cola de 60 o 100 producia timeouts porque el chequeo no
contaba la extraccion. La 1.3.1 lo corrige: una cola mas larga ya no deberia
producir timeouts, y en Vegeta podria completar mas requests en la ventana de
30 s.

- Resultado (informe, experimento 9): con 90 y 120 volvieron los timeouts,
  porque el chequeo usaba el tiempo promedio. Con un margen de 4 desvios
  (como el temporizador de TCP) la cola de 60 sube Vegeta de ~22 % a ~30 %
  de exito sin timeouts. Adoptado en la 1.3.2.

### 4. Proxy mas liviano: HAProxy o nginx en lugar de Traefik (medio dia) - PROBADO, NO SIRVE

En Vegeta el proxy mueve ~167 MB/s de PDFs y compite por los mismos nucleos
que las replicas. HAProxy y nginx estan escritos en C y gastan menos CPU por
byte que Traefik (Go).

- Que cambiar: el servicio `traefik` del `docker-compose.yml` por
  `haproxy:3` con un `haproxy.cfg` (round robin, `retries 3`, chequeo de
  `/health`) o por `nginx` con `upstream` (tambien hay que resolver las
  replicas por DNS del servicio). Se pierden el dashboard y las metricas de
  Traefik (HAProxy tiene su propia pagina de estadisticas y exporter de
  Prometheus).
- Ganancia esperada: 5-15 % en la notebook (CPU que se le devuelve a las
  replicas). En una maquina con nucleos de sobra, casi nada.
- Riesgo: bajo; hay que repetir la prueba de caos y el monitoreo.
- Resultado (informe, experimento 11): Traefik usa solo ~20 % de un nucleo
  en el spike, HAProxy casi lo mismo, y con HAProxy aparecieron timeouts en
  Vegeta. Se mantiene Traefik.

### 5. Linux nativo en lugar de Docker Desktop (2-4 horas)

Docker Desktop corre en una VM de WSL2 con su propia capa de red. En Linux
nativo (Ubuntu desde un USB o en dual boot) los contenedores corren directo
sobre el kernel.

- Ganancia esperada: 5-15 % (menos virtualizacion y red mas directa), y
  resultados mas estables.
- Riesgo: bajo; el `docker compose` es el mismo.

### 6. Compilar las partes en Python (1-2 dias)

Nuestro Python (medir las alturas, armar el Markdown, la capa HTTP) es ~12-15 %
del CPU por request.

- Que cambiar: compilar `app/core/markdown.py` y el armado de lineas
  (`_page_lines`) con mypyc o Cython. El JSON no vale la pena: pesa menos del
  1 % (por eso se descarto orjson).
- Ganancia esperada: 5-8 % del CPU por request (no todo ese 12-15 % se
  elimina).
- Riesgo: medio; mas complejidad en el build de la imagen.

### 7. Reescribir el servicio en Rust o Go sobre PDFium (1-3 semanas)

Libertad de stack lo permite: la consigna acepta Go, Rust, C++, etc.

- Que cambiar: un servicio nuevo con el mismo contrato (`POST /extract`,
  `{"content", "page_count"}`), por ejemplo Rust con `axum` y
  `pdfium-render`, o Go con `net/http` y `go-pdfium`. Hay que portar la
  heuristica de Markdown, la compuerta (cola acotada + tiempo util), los
  tests, el Dockerfile y los healthchecks.
- Ganancia esperada: **~10-15 %** del CPU por request. Solo sale lo que hoy
  hace Python: el 85 % que esta dentro de PDFium queda igual, porque el
  motor es el mismo.
- Riesgo: alto. Es mucho trabajo para poca ganancia, y el proyecto de la
  materia exige Python y FastAPI: tendria que ser un servicio aparte solo
  para el TP.

### 8. Un extractor propio que lea solo el texto del PDF (3-6 semanas)

PDFium arma la pagina completa (imagenes, trazos, layout) antes de dar el
texto. Un extractor que lea solo los operadores de texto del content stream y
decodifique las fuentes (CMaps `ToUnicode`) podria ser varias veces mas
rapido.

- Que cambiar: un parser en Rust (por ejemplo sobre `lopdf`) con decodificacion
  de fuentes, orden de lectura y deteccion de titulos.
- Ganancia esperada: potencialmente 2-5 veces menos CPU, pero sin medir.
- Riesgo: muy alto. La extraccion de texto de PDF tiene muchisimos casos
  (fuentes embebidas, codificaciones, columnas). pdf_oxide, que es justamente
  eso en Rust, resulto 2-3 veces **mas lento** que PDFium (experimento 6). No
  es viable para esta entrega.

## Lo que ya se probo y no sirve

| Idea | Resultado |
|---|---|
| PyMuPDF, pdf_oxide | no ganan a PDFium (y PyMuPDF es AGPL) |
| jemalloc, mimalloc | dentro del ruido |
| 2 procesos por replica | mismo throughput, peor p95 |
| `leasttime` / `p2c` en Traefik | peor / igual |
| Cola por tamano (el PDF mas liviano primero) | peor throughput y p95 |
| `inFlightReq` de Traefik en vez de la cola de la app | empate |

## Lo que no hay que hacer

- **Cachear la respuesta por checksum del PDF.** Las pruebas repiten siempre
  los mismos 4 PDFs: daria miles de req/s, pero es aprovechar el benchmark,
  no mejorar el servicio.
- Saltear paginas o devolver menos texto: rompe el contrato.
- Pasar de 5 replicas o de 1 CPU por replica: rompe las reglas de la consigna.

## Plan recomendado

| Orden | Que | Tiempo | Ganancia esperada |
|---|---|---|---|
| 1 | Medir en una PC con 8+ nucleos o con el generador en otra maquina | 1-2 h | de 9-15 a ~25-30 req/s |
| 2 | Preparar la maquina y reportar la mediana de 3 corridas | 30 min | menos variacion |
| 3 | Cola de 60 con margen pesimista (hecho, 1.3.2) | 1 h | Vegeta de ~22 % a ~30 % |
| 4 | HAProxy en lugar de Traefik (probado: no sirve) | - | - |
| 5 | Linux nativo | 2-4 h | 5-15 % |
| 6 | mypyc / Cython en el Markdown | 1-2 dias | 5-8 % |

Con 1 y 2 (un dia) el throughput y el p95 del spike deberian superar al
profesor. El p50 de 1,88 s es el mas dificil: con 100 usuarios fijos haria
falta mas del doble de su throughput, o un orden de cola que favorezca a los
PDFs chicos sin perjudicar al resto (el que se probo no funciono). Las
propuestas 7 y 8 no convienen antes de la entrega: mucho trabajo para una
ganancia chica o incierta.
