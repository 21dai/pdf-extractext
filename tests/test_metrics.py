"""Own metrics of each replica: queue, rejections and extraction time.

Grafana solo veia a Traefik (requests y latencias de afuera). Con estas
metricas se ve adentro de cada replica: cuanto hay en cola, por que se
rechaza y cuanto tarda la extraccion.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ClientDisconnectedError, ServiceOverloadedError
from app.services.admission import AdmissionGate
from tests.support.pdf import MINIMAL_PDF_BYTES


class FakeObserver:
    def __init__(self) -> None:
        self.pending: list[int] = []
        self.rejections: list[str] = []
        self.extractions: list[float] = []

    def queue_changed(self, pending: int) -> None:
        self.pending.append(pending)

    def rejected(self, reason: str) -> None:
        self.rejections.append(reason)

    def extracted(self, seconds: float) -> None:
        self.extractions.append(seconds)


async def connected() -> bool:
    return False


async def disconnected() -> bool:
    return True


def make_gate(observer, **overrides) -> AdmissionGate:
    options = {"max_wait_seconds": 10.0, "max_pending": 1}
    options.update(overrides)
    return AdmissionGate(initial_service_seconds=0.3, observer=observer, **options)


class TestGateReportsToItsObserver:
    def test_reports_the_queue_size(self):
        observer = FakeObserver()
        gate = make_gate(observer)

        with gate.admit():
            pass

        assert observer.pending == [1, 0]

    def test_reports_a_full_queue(self):
        observer = FakeObserver()
        gate = make_gate(observer)

        with gate.admit():
            with pytest.raises(ServiceOverloadedError):
                gate.admit()

        assert observer.rejections == ["cola_llena"]

    def test_reports_a_request_past_its_useful_life(self):
        now = [0.0]
        observer = FakeObserver()
        gate = make_gate(observer, clock=lambda: now[0])

        async def work():
            return None

        async def scenario():
            with gate.admit() as ticket:
                now[0] += 11.0
                await ticket.run(work, connected)

        with pytest.raises(ServiceOverloadedError):
            asyncio.run(scenario())
        assert observer.rejections == ["tiempo_util"]

    def test_reports_a_client_that_left(self):
        observer = FakeObserver()
        gate = make_gate(observer)

        async def work():
            return None

        async def scenario():
            with gate.admit() as ticket:
                await ticket.run(work, disconnected)

        with pytest.raises(ClientDisconnectedError):
            asyncio.run(scenario())
        assert observer.rejections == ["cliente_desconectado"]

    def test_reports_how_long_each_extraction_took(self):
        now = [0.0]
        observer = FakeObserver()
        gate = make_gate(observer, clock=lambda: now[0])

        async def work():
            now[0] += 0.25

        async def scenario():
            with gate.admit() as ticket:
                await ticket.run(work, connected)

        asyncio.run(scenario())
        assert observer.extractions == [0.25]


class TestMetricsEndpoint:
    def test_exposes_the_metrics_in_prometheus_format(self, client: TestClient):
        client.post(
            "/extract",
            content=MINIMAL_PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        )

        response = client.get("/metrics")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "extract_queue_pending 0.0" in response.text
        assert "extract_service_seconds_count 1.0" in response.text
        assert "extract_rejections_total" in response.text
