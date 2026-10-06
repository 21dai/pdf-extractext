# ADR 0003: contrapresion (backpressure) en la app

- Estado: aceptada
- Fecha: 2026-10-05 (version 1.3.0)

## Contexto

En la prueba de Vegeta (modelo abierto, 50 req/s, timeout de 30 s) entra mas
trabajo del que el servicio puede hacer. Sin control, cada replica encola todo
y sigue procesando requests cuyo cliente ya se fue: el profesor tiene 501
timeouts y p50 de 14,89 s, y nuestra linea base colapsaba a 2,93 req/s
efectivos. La consigna (pista 2) pide rechazar de forma controlada si la cola
excede el tiempo util de vida.

## Decision

`AdmissionGate` (`app/services/admission.py`), una por proceso:

1. **Cola acotada por cantidad**: hasta `EXTRACT_MAX_PENDING` = 30 requests
   admitidos. Llena, el siguiente recibe `503` con `Retry-After` al instante,
   sin leer el PDF.
2. **Una extraccion por vez** en un semaforo de asyncio: los admitidos esperan
   sin ocupar un hilo, y el event loop sigue atendiendo HTTP (pista 4).
3. **Tiempo util**: cuando le toca el turno, si el cliente ya se desconecto
   no se procesa; si lo que espero mas una extraccion promedio supera
   `EXTRACT_MAX_WAIT_SECONDS` = 28 s (menos que el timeout de 30 s), recibe
   `503` sin procesarse. Hasta la 1.3.0 solo contaba la espera: con la
   maquina lenta, requests que empezaban cerca de los 28 s terminaban despues
   de los 30 s (1 y 19 timeouts en dos corridas). Desde la 1.3.1 cuenta
   tambien la extraccion (0 timeouts).

## Alternativas medidas

| Alternativa | Resultado en Vegeta | Por que no |
|---|---|---|
| Sin limite (linea base) | colapso, cientos de timeouts | trabajo desperdiciado |
| Estimar la espera al llegar (EWMA) | 57-141 timeouts | estima mal durante el ataque; llego a rechazar 1 request en el spike |
| Cola de 100 | 7,7 % de exito en una corrida, 985 timeouts | guarda mas trabajo del que entra en el tiempo util |
| Cola de 30 | 0 timeouts, p50 ~0,1 s, ~390 MiB | elegida |
| `inFlightReq` de Traefik (150, responde 429) | empate en exito, 0 timeouts | numero fijo sin tiempo util, 429 sin `Retry-After`, limite global y no por replica |

## Consecuencias

- Ningun request vence por timeout: lo que no se puede atender a tiempo se
  rechaza en milisegundos, con `Retry-After`, y no se gasta CPU en respuestas
  que nadie va a leer.
- La memoria por replica queda acotada (PDFs en espera).
- El porcentaje de exito de Vegeta lo pone la capacidad (req/s), no la cola:
  con mas nucleos sube solo.
- 30 depende del costo por PDF de este set: si cambian los PDFs hay que
  revisarlo (el tiempo util protege igual, pero una cola demasiado larga
  vuelve a desperdiciar trabajo).
