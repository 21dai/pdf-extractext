"""Unit tests for the admission gate of POST /extract (backpressure).

The gate admits a request only if its estimated wait (pending requests times
the average service time) stays under the limit, runs one extraction at a
time, and skips the work of clients that already disconnected.
"""

import asyncio

import pytest

from app.core.exceptions import ClientDisconnectedError, ServiceOverloadedError
from app.services.admission import AdmissionGate


async def connected() -> bool:
    return False


async def disconnected() -> bool:
    return True


def run(coro):
    return asyncio.run(coro)


class TestAdmission:
    def test_admits_while_the_estimated_wait_is_under_the_limit(self):
        gate = AdmissionGate(max_wait_seconds=1.0, initial_service_seconds=0.3)

        tickets = [gate.admit() for _ in range(3)]  # espera estimada: 0,9 s

        assert gate.pending == 3
        for ticket in tickets:
            ticket.release()

    def test_rejects_with_retry_after_when_the_wait_would_exceed_the_limit(self):
        gate = AdmissionGate(max_wait_seconds=1.0, initial_service_seconds=0.3)
        tickets = [gate.admit() for _ in range(4)]  # el siguiente esperaria 1,2 s

        with pytest.raises(ServiceOverloadedError) as error:
            gate.admit()

        assert error.value.retry_after_seconds == 2  # 1,2 s redondeado hacia arriba
        assert gate.pending == 4
        for ticket in tickets:
            ticket.release()

    def test_releasing_a_ticket_frees_its_place(self):
        gate = AdmissionGate(max_wait_seconds=0.5, initial_service_seconds=0.3)
        ticket = gate.admit()
        ticket.release()
        ticket.release()  # liberar dos veces no descuenta de mas

        assert gate.pending == 0

    def test_ticket_is_released_when_used_as_context_manager(self):
        gate = AdmissionGate(max_wait_seconds=1.0, initial_service_seconds=0.3)

        with gate.admit():
            assert gate.pending == 1

        assert gate.pending == 0


class TestTurns:
    def test_runs_the_work_and_returns_its_result(self):
        gate = AdmissionGate(max_wait_seconds=1.0, initial_service_seconds=0.3)

        async def work():
            return "markdown"

        async def scenario():
            with gate.admit() as ticket:
                return await ticket.run(work, connected)

        assert run(scenario()) == "markdown"

    def test_runs_one_extraction_at_a_time(self):
        gate = AdmissionGate(max_wait_seconds=10.0, initial_service_seconds=0.3)
        running = 0
        max_running = 0

        async def work():
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.01)
            running -= 1

        async def one():
            with gate.admit() as ticket:
                await ticket.run(work, connected)

        async def scenario():
            await asyncio.gather(*(one() for _ in range(5)))

        run(scenario())
        assert max_running == 1

    def test_skips_the_work_if_the_client_already_left(self):
        gate = AdmissionGate(max_wait_seconds=1.0, initial_service_seconds=0.3)
        calls = 0

        async def work():
            nonlocal calls
            calls += 1

        async def scenario():
            with gate.admit() as ticket:
                await ticket.run(work, disconnected)

        with pytest.raises(ClientDisconnectedError):
            run(scenario())
        assert calls == 0

    def test_learns_the_service_time_from_the_work_it_runs(self):
        now = [0.0]
        gate = AdmissionGate(
            max_wait_seconds=10.0,
            initial_service_seconds=1.0,
            smoothing=0.5,
            clock=lambda: now[0],
        )

        async def work():
            now[0] += 3.0  # la extraccion tarda 3 s

        async def scenario():
            with gate.admit() as ticket:
                await ticket.run(work, connected)

        run(scenario())
        assert gate.service_seconds == pytest.approx(2.0)  # 0,5 * 1 + 0,5 * 3


class TestUsefulLife:
    """A request that already waited longer than the maximum is not processed."""

    def test_request_that_waited_too_long_is_rejected_at_its_turn(self):
        now = [0.0]
        gate = AdmissionGate(
            max_wait_seconds=10.0,
            initial_service_seconds=0.3,
            clock=lambda: now[0],
        )
        calls = 0

        async def work():
            nonlocal calls
            calls += 1

        async def scenario():
            with gate.admit() as ticket:
                now[0] += 11.0  # espero su turno mas que el maximo
                await ticket.run(work, connected)

        with pytest.raises(ServiceOverloadedError):
            run(scenario())
        assert calls == 0

    def test_request_within_its_useful_life_is_processed(self):
        now = [0.0]
        gate = AdmissionGate(
            max_wait_seconds=10.0,
            initial_service_seconds=0.3,
            clock=lambda: now[0],
        )

        async def work():
            return "ok"

        async def scenario():
            with gate.admit() as ticket:
                now[0] += 9.0
                return await ticket.run(work, connected)

        assert run(scenario()) == "ok"
