# ADR 0007: metricas propias de cada replica

- Estado: aceptada
- Fecha: 2026-10-07 (version 1.4.0)

## Contexto

Grafana solo mostraba las metricas de Traefik: requests por codigo y
latencias vistas desde afuera. No se veia cuanto habia en la cola de cada
replica, por que rechazaba la compuerta ni cuanto tardaba la extraccion sin
la espera. Para analizar una prueba de carga habia que leer los logs a mano.

## Decision

- Cada replica expone `GET /metrics` en formato Prometheus con
  `prometheus-client`: `extract_queue_pending` (requests en la cola),
  `extract_rejections_total{motivo}` (`cola_llena`, `tiempo_util`,
  `cliente_desconectado`) y el histograma `extract_service_seconds`.
- La compuerta no conoce Prometheus: avisa sus eventos a un observador
  (`GateObserver`, por defecto no hace nada) y la app conecta el que publica
  las metricas. Se prueba con un observador falso.
- Cada app tiene su propio registro de metricas (los tests crean varias apps
  en el mismo proceso).
- Prometheus descubre las replicas por el DNS de Docker (`dns_sd_configs`
  sobre el servicio `extract`) y Grafana suma tres paneles: cola por
  replica, rechazos por motivo y duracion de la extraccion.

## Alternativas

| Alternativa | Por que no |
|---|---|
| Solo logs JSON | sirven para un caso puntual, no para ver la evolucion durante una prueba |
| Llamar a Prometheus desde la compuerta | acopla la logica de admision a una libreria de metricas y complica los tests |
| OpenTelemetry | mas piezas (collector) para tres metricas |

## Consecuencias

- Durante el spike o Vegeta se ve en vivo que replica tiene cola y por que se
  rechaza.
- Con `WEB_CONCURRENCY` mayor a 1, cada proceso tiene sus propias metricas
  (haria falta el modo multiproceso de prometheus-client); el stack del TP
  corre un proceso por replica.
- `/metrics` queda publico detras de Traefik en el stack del TP. En un
  despliegue real habria que restringirlo.
