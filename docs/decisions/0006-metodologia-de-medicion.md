# ADR 0006: como se mide

- Estado: aceptada
- Fecha: 2026-10-05

## Contexto

Las primeras mediciones daban numeros que no se podian comparar entre si ni
con los del profesor:

- Desde Windows, el reenvio de puertos de Docker Desktop hacia la VM de WSL2
  limitaba el throughput a la mitad (el tiempo crecia con el tamano del PDF,
  no con sus paginas).
- La notebook cambia de frecuencia con la temperatura: el mismo codigo dio de
  6 a 17 req/s en el spike en distintos momentos.
- La carga fija con k6 (`constant-arrival-rate`) descartaba iteraciones sin
  contarlas: con PDFs grandes no llega a crear los ~1.500 usuarios virtuales
  que hacen falta, y en algunas corridas mando 500-700 de los 1.500 requests.

## Decision

- El generador de carga corre **dentro de la red de Docker** (contenedores de
  k6 y Vegeta que apuntan a `http://traefik`).
- La carga fija se mide con **Vegeta 12.13.0**, la herramienta del profesor,
  en un contenedor (`tests/stress/docker/vegeta.Dockerfile`).
- Las configuraciones a comparar se miden **intercaladas** (A, B, A, B) y al
  menos dos veces; los cambios de CPU puro, en el **mismo proceso**,
  alternando 30 pares y comprobando que la salida sea identica.
- Un cambio que no mejora por fuera del ruido **no se commitea**.
- El SLO esta cargado en los scripts (`thresholds` de k6, control de timeouts
  en Vegeta): una corrida dice sola si se cumple.

## Consecuencias

- Las mediciones viejas con k6 de carga fija se descartaron y se dijo en el
  informe.
- Los numeros absolutos de la notebook no son comparables con los del
  profesor (otro hardware, que no se conoce): la comparacion mas justa es por
  replica con un nucleo propio (ver [0004](0004-workers-y-replicas.md)).
