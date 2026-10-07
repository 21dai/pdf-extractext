"""Prometheus metrics of each replica, fed by the admission gate.

Grafana ya veia a Traefik (requests y latencias de afuera). Estas metricas
muestran lo de adentro de cada replica: cuanto hay en cola, por que se
rechaza y cuanto tarda cada extraccion. Se exponen en `GET /metrics`.

Cada app tiene su propio registro: los tests crean varias apps en el mismo
proceso y el registro global de prometheus_client no admite repetir nombres.
Con `WEB_CONCURRENCY` mayor a 1 cada proceso tendria sus propios numeros; el
stack del TP corre un proceso por replica.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Motivos de rechazo de la compuerta (etiqueta `motivo`).
REJECTION_REASONS = ("cola_llena", "tiempo_util", "cliente_desconectado")

# Cubre desde un PDF chico con la CPU libre hasta uno grande con la CPU
# saturada (de ~50 ms a varios segundos).
EXTRACTION_BUCKETS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2.5, 5, 10)


class PrometheusGateObserver:
    """Publish what the admission gate reports as Prometheus metrics."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self._pending = Gauge(
            "extract_queue_pending",
            "Requests admitidos en la cola de la replica (esperando o extrayendo)",
            registry=self.registry,
        )
        self._rejections = Counter(
            "extract_rejections",
            "Requests rechazados por la compuerta, por motivo",
            ["motivo"],
            registry=self.registry,
        )
        self._service = Histogram(
            "extract_service_seconds",
            "Duracion de cada extraccion (sin la espera en la cola)",
            buckets=EXTRACTION_BUCKETS,
            registry=self.registry,
        )
        for reason in REJECTION_REASONS:
            self._rejections.labels(reason)  # que aparezcan en 0 desde el inicio

    def queue_changed(self, pending: int) -> None:
        self._pending.set(pending)

    def rejected(self, reason: str) -> None:
        self._rejections.labels(reason).inc()

    def extracted(self, seconds: float) -> None:
        self._service.observe(seconds)

    def render(self) -> tuple[bytes, str]:
        """The metrics in the Prometheus text format, and its content type."""
        return generate_latest(self.registry), CONTENT_TYPE_LATEST
