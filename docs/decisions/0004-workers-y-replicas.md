# ADR 0004: workers, replicas y balanceo

- Estado: aceptada
- Fecha: 2026-10-05

## Contexto

La consigna permite hasta 5 replicas con limites explicitos (~1 CPU y 512 MB
a 1 GB) detras de un reverse proxy, y sugiere separar el runtime HTTP de la
extraccion (pista 4). La extraccion es CPU pura y PDFium no es thread-safe.

## Decision

- **5 replicas de 1 CPU y 1 GB**, cada una con **1 proceso de uvicorn**
  (`WEB_CONCURRENCY=1`).
- Dentro del proceso, el endpoint es async: el event loop recibe los uploads y
  la extraccion corre en el threadpool, una por vez (ver
  [0003](0003-contrapresion.md)).
- **Traefik v3** con **round robin** (`wrr`), configurable con `LB_STRATEGY`.
- Memoria: 1 GB por replica (pico medido ~420 MiB bajo Vegeta; 512 MB quedaba
  al borde con el PDF de 9 MB).

## Alternativas medidas

| Alternativa | Resultado | Por que no |
|---|---|---|
| 2 procesos por replica | mismo throughput (11-11,6 req/s), p95 peor y el doble de memoria | se reparten el mismo nucleo |
| Pool de procesos para extraer | no agrega CPU con 1 CPU de limite | complejidad sin ganancia |
| `leasttime` | 1.172 rechazos en una corrida | manda mas trafico a la replica que responde rapido... con 503 |
| `p2c` | igual a `wrr` dentro del ruido | sin ventaja |
| HAProxy en lugar de Traefik | mismo CPU del proxy (~20 % de un nucleo), spike igual o peor y timeouts en Vegeta | sin ventaja |
| 3 o 4 replicas en el spike | 12-13 req/s contra 14,3-14,5 con 5 | 5 sigue siendo lo mejor |
| 1 a 5 replicas (escalado) | lineal hasta 2-3; despues el CPU por request sube de ~190 a 460 ms | la notebook tiene 4 nucleos para 5 replicas, Traefik y k6 |

## Consecuencias

- Capacidad = replicas x 1.000 / CPU por request (ms) mientras cada replica
  tenga su nucleo: ~5-6 req/s por replica, ~25-30 req/s con 5 nucleos libres.
- En la notebook del grupo las 5 replicas no tienen nucleo propio: el
  throughput medido (11-17 req/s) esta limitado por el hardware.
- Traefik es el punto unico de falla del stack (ver
  [0005](0005-tolerancia-a-fallos.md)).
