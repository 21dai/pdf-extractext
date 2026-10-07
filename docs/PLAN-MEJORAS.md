# Plan de mejoras del proyecto y del TP

Plan para dejar el servicio `pdf-extractext` mejorado en conjunto (el CRUD
del proyecto, la arquitectura, el codigo, las herramientas y la
documentacion) y, sobre esa base, seguir mejorando los numeros del TP. Sigue
al [plan del TP](PLAN-TP.md), que ya esta completo.

Cada tarea sale de algo verificado el 2026-10-07: un test que falla, una
medicion o una lectura del codigo. Se trabaja igual que hasta ahora: TDD
(test en rojo y despues verde), un commit por cambio, medir antes de adoptar
cualquier cambio de rendimiento y documentar lo que se descarta.

## Estado de partida

- 161 tests, **97 % de cobertura** del paquete `app`, CI con black, isort,
  flake8, mypy, tests, build de la imagen, smoke test y trufflehog.
- `/extract` (el TP) esta medido y documentado en 13 experimentos.
- El CRUD (`/api/v1/documents`) quedo atras de `/extract`: se le aplicaron
  menos cuidados y tiene los problemas de la fase A.

## Fase A: correcciones (el proyecto tiene que cumplir lo que dice) - HECHA (1.3.4)

| # | Problema verificado | Que hacer | Como se comprueba |
|---|---|---|---|
| A1 | **Requisito 8 incumplido en el CRUD**: un PDF de 3,8 MB subido a `POST /api/v1/documents` se escribe en un archivo temporal (Starlette pasa a disco las partes de mas de 1 MB). `REVISION_ENUNCIADO.md` lo da por cumplido. | Leer el multipart del CRUD en memoria, como ya hace `/extract`, con el mismo helper. Corregir la revision. | Test que falla si un upload pasa a disco (ya existe para `/extract`). |
| A2 | El CRUD lee todo el archivo antes de validar el tamano: un upload enorme ocupa memoria antes de rechazarse. | Rechazar por `Content-Length` y cortar la lectura al pasar el limite (como `/extract`). | Test con un body mas grande que el limite: `413` sin leerlo entero. |
| A3 | Un PDF duplicado responde `400` (el service lanza `ValueError`), y si dos uploads iguales llegan juntos el indice unico de MongoDB lanza `DuplicateKeyError` y la API responde `500`. | Excepcion de dominio `DuplicateDocumentError` -> `409 Conflict` en RFC 9457, tambien cuando la detecta el indice. | Tests del duplicado y de la carrera (repositorio que lanza `DuplicateKeyError`). |
| A4 | CORS con `allow_origins=["*"]` y `allow_credentials=True`: combinacion que los navegadores rechazan y que no es segura. | Origenes por variable de entorno (`CORS_ALLOW_ORIGINS`, 12-Factor III); sin credenciales con `*`. | Test de la configuracion de CORS. |
| A5 | Errores sueltos `502` en el spike (0,2 % en una corrida, 1 en la emulacion): uvicorn cierra las conexiones inactivas a los 5 s y Traefik las reusa hasta 90 s. | `timeout_keep_alive` de uvicorn mayor que el de Traefik, configurable. | Test de la configuracion y spikes sin errores. |

Tiempo estimado: **3-4 horas**. Version resultante: 1.3.4 (correcciones).

Hecho con TDD el 2026-10-07 (cada uno con su commit en rojo y en verde):
A1 y A2 (`9612959`), A3 (`e3f80c6`), A4 (`640816e`) y A5 (`6d57a28`). La
lectura de uploads quedo en `app/api/uploads.py`, compartida por los dos
routers: eso adelanta la tarea B1.

Verificacion: CPU por request de una replica sola, 1.3.3 contra 1.3.4
alternadas (3 rondas): mediana 214 contra 206 ms. Las correcciones no le
agregan costo a `/extract`.

## Fase B: arquitectura y codigo

| # | Que mejorar | Por que |
|---|---|---|
| B1 | (Hecho en la fase A) Un modulo `app/api/uploads.py` con la lectura de uploads (crudo y multipart, en memoria, con limite) para los dos routers. | Hoy esa logica esta solo en el router de `/extract` (DRY; la fase A la necesita en el CRUD). |
| B2 | `DocumentService` recibe el motor por la interfaz `PdfExtractor` en vez de llamar a `extract_pdf_text`. | Inversion de dependencias: hoy hay dos caminos al motor. |
| B3 | Los uploads del CRUD pasan por la misma `AdmissionGate` que `/extract`. | Comparten el lock de PDFium por proceso: hoy un pico de uploads del CRUD bloquea hilos sin limite y le quita turnos a `/extract` (Bulkhead). |
| B4 | Sacar los `try/except ValueError` del router del CRUD: errores de dominio con sus handlers RFC 9457, como en `/extract`. | Respuestas de error uniformes y routers mas finos. |
| B5 | Metricas propias en `/metrics` (Prometheus): requests en cola, rechazos por motivo, duracion de la extraccion por PDF. | Hoy Grafana solo ve a Traefik; la cola y los rechazos de cada replica no se ven (Fowler: monitoring). |
| B6 | Evaluar el campo heredado `file_path` (`memory://...`) y su indice unico. | Solo existe por compatibilidad (`ARCHITECTURE.md`); hay que confirmar con el equipo si el orquestador lo usa antes de tocarlo. |

Tiempo estimado: **4-5 horas**. Version resultante: 1.4.0 (B5 agrega un
endpoint).

## Fase C: estructura, herramientas y CI

| # | Que mejorar | Por que |
|---|---|---|
| C1 | Cobertura en el CI con umbral (`pytest-cov`, minimo 95 %). | Hoy es 97 %, pero nadie la mide: puede bajar sin que se note. |
| C2 | `pre-commit` con black, isort y flake8 para todo el equipo. | Los errores de formato se ven recien en el CI. |
| C3 | Auditoria de dependencias (`pip-audit`) en el CI. | Seguridad de la cadena de dependencias. |
| C4 | Ordenar los tres `docker-compose`: `docker/` (desarrollo con MongoDB), la raiz (stack del TP) e `infrastructure` (todo el sistema). Arreglar el `Makefile` (`make logs` apunta a un contenedor con nombre viejo) y agregar `make benchmark`. | Hoy no es obvio cual usar para que. |
| C5 | README mas corto: pasar las guias largas a `docs/` (desarrollo, API, pruebas de carga del CRUD y del TP). | El README tiene mas de 600 lineas. |
| C6 | Healthcheck cada 10 s en lugar de 5 s. | Cada chequeo arranca un `python` nuevo en cada replica: CPU que se le quita a las extracciones. Medirlo antes de adoptarlo. |

Tiempo estimado: **3-4 horas**.

## Fase D: rendimiento del TP

| # | Que hacer | Evidencia |
|---|---|---|
| D1 | Volver a activar la cola "mas chico primero" con limite de espera de **7,5 s**, configurable (`EXTRACT_QUEUE_ORDER`, `EXTRACT_PRIORITY_AGE_SECONDS`). | Emulacion con un nucleo por replica (2 replicas, 20 usuarios por replica, 3 rondas): +13 % de throughput y p50 de ~4 s a ~2,1 s; p90 y p95 suben ~1 s. La simulacion del spike predice lo mismo. |
| D2 | Decidir el valor por defecto de D1. | Ayuda con un nucleo por replica (la maquina del profesor); en la notebook del grupo, con 5 replicas, no (la espera tipica ya supera el limite). |
| D3 | Opcion `-Navegador` en `benchmark.ps1`: dashboard de k6 en vivo y reporte HTML del spike. | Ya probado a mano: `K6_WEB_DASHBOARD` funciona dentro del contenedor. |
| D4 | Medir en una PC con 8 nucleos o mas (de un integrante o del laboratorio). | Es lo unico que puede confirmar el throughput: con la velocidad por nucleo de la notebook la proyeccion es ~21 req/s. |
| D6 | Que el tiempo util no dependa del estado de la maquina. | Con la notebook muy lenta (spike de 6-9 req/s) volvieron los timeouts en Vegeta con la 1.3.3 y la 1.3.4: 2, 7, 13 y 55 por corrida. El margen de 4 desvios se adapta a la extraccion, pero no a lo que pasa fuera de la compuerta (subir el PDF y devolver la respuesta con la CPU saturada). Medir ese tramo y sumarlo, o achicar la cola cuando la maquina va lenta. |
| D5 | Informe y ADRs con los experimentos 14 en adelante (emulacion a escala, keep-alive, cola por tamano con limite corto). | El proceso de investigacion es lo que la consigna pide para el puntaje extra. |

Tiempo estimado: **3 horas** sin D4.

## Fase E: cierre

- Version final (1.4.0), tags, imagen y `infrastructure` actualizado.
- `REVISION_ENUNCIADO.md`, `ARCHITECTURE.md`, ADRs y README al dia.
- Corrida final de `benchmark.ps1` (3 veces) y resumen del informe.
- Mensaje para el equipo con los cambios.

Tiempo estimado: **1-2 horas**.

## Orden recomendado

```
Fase A (correcciones) ──> Fase D (rendimiento del TP) ──> Fase B (arquitectura)
                                                           │
                                     Fase C (herramientas) ┴──> Fase E (cierre)
```

A primero porque son errores reales (uno incumple un requisito de la
materia). D despues porque es lo que mas impacta en la nota del TP. B y C
mejoran el proyecto en si y se pueden hacer en otra sesion. Total estimado:
**15-18 horas** de trabajo.

## Fuera de alcance

- Microservicios nuevos y el orquestador: los hacen los companeros.
- Reescribir en otro lenguaje: el 85 % del CPU esta en PDFium y la materia
  pide Python y FastAPI (ver [MEJORAS-RENDIMIENTO.md](MEJORAS-RENDIMIENTO.md)).
- Cachear respuestas por checksum: seria aprovechar el benchmark.
