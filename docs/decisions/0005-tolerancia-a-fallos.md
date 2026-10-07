# ADR 0005: tolerancia a fallos de las replicas

- Estado: aceptada
- Fecha: 2026-10-06

## Contexto

Una replica puede caerse (falla del proceso) o apagarse (deploy, `docker
stop`). La prueba de caos (`tests/stress/caos.sh`) mostro que, sin hacer
nada, una caida en medio del spike deja ~29 respuestas `502` y el exito baja
a ~93 %.

## Decision

- `restart: unless-stopped`: Docker levanta sola una replica caida (~15 s
  hasta healthy).
- Middleware **retry de Traefik** (3 intentos, 100 ms): si una replica no
  responde, reintenta en otra. Es seguro porque `/extract` no tiene estado
  (procesar dos veces el mismo PDF no cambia nada). En `infrastructure` se
  aplica solo a `/extract`, no al CRUD.
- **Apagado ordenado**: ante SIGTERM uvicorn deja de aceptar conexiones y
  termina su cola; `stop_grace_period: 35s` (25 s de tiempo util mas margen).
- Liveness (`/health`) separado de readiness (`/ready`): una caida de MongoDB
  no saca de servicio a las replicas de `/extract`.

## Resultados

| Escenario | Exito |
|---|---|
| Caida sin reintentos | 92,7 % / 94,1 % |
| Caida con reintentos | 95,6 % / 95,5 % |
| Apagado ordenado | 100 % / 99,6 % |

## Consecuencias

- En una caida se pierden los requests que ya estaban en la cola de esa
  replica (~18): ese trabajo muere con el proceso. Evitarlo pediria una cola
  externa (por ejemplo un broker), fuera del alcance del TP.
- Traefik sigue siendo el punto unico de falla: 4,3 s sin servicio si se cae,
  hasta que Docker lo reinicia.
