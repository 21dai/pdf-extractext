"""Unit tests for the admission gate of POST /extract (backpressure).

The gate admits requests while its queue has room, runs one extraction at a
time, and skips the work of clients that already left or that waited longer
than their useful life.
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


def make_gate(**overrides) -> AdmissionGate:
    options = {
        "max_wait_seconds": 10.0,
        "max_pending": 3,
        "initial_service_seconds": 0.3,
    }
    options.update(overrides)
    return AdmissionGate(**options)


class TestAdmission:
    """The queue is bounded by count: it protects memory without guessing times.

    Una estimacion de tiempo al llegar admitia de menos: durante un ataque la
    CPU esta saturada y cada extraccion tarda mas, pero esa cola se vacia mucho
    mas rapido cuando el ataque termina. El tiempo util lo controla el chequeo
    exacto en el turno (TestUsefulLife).
    """

    def test_admits_until_the_queue_is_full(self):
        gate = make_gate(max_pending=3)

        tickets = [gate.admit() for _ in range(3)]

        assert gate.pending == 3
        for ticket in tickets:
            ticket.release()

    def test_rejects_with_retry_after_when_the_queue_is_full(self):
        gate = make_gate(max_pending=3, initial_service_seconds=0.5)
        tickets = [gate.admit() for _ in range(3)]

        with pytest.raises(ServiceOverloadedError) as error:
            gate.admit()

        assert error.value.retry_after_seconds == 2  # 3 x 0,5 s hacia arriba
        assert gate.pending == 3
        for ticket in tickets:
            ticket.release()

    def test_retry_after_is_at_least_one_second(self):
        gate = make_gate(max_pending=1, initial_service_seconds=0.01)
        ticket = gate.admit()

        with pytest.raises(ServiceOverloadedError) as error:
            gate.admit()

        assert error.value.retry_after_seconds == 1
        ticket.release()

    def test_releasing_a_ticket_frees_its_place(self):
        gate = make_gate()
        ticket = gate.admit()
        ticket.release()
        ticket.release()  # liberar dos veces no descuenta de mas

        assert gate.pending == 0

    def test_ticket_is_released_when_used_as_context_manager(self):
        gate = make_gate()

        with gate.admit():
            assert gate.pending == 1

        assert gate.pending == 0


class TestTurns:
    def test_runs_the_work_and_returns_its_result(self):
        gate = make_gate()

        async def work():
            return "markdown"

        async def scenario():
            with gate.admit() as ticket:
                return await ticket.run(work, connected)

        assert run(scenario()) == "markdown"

    def test_runs_one_extraction_at_a_time(self):
        gate = make_gate(max_pending=10)
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
        gate = make_gate()
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
        gate = make_gate(
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
        gate = make_gate(
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
        gate = make_gate(
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

    def test_request_that_would_finish_after_its_useful_life_is_rejected(self):
        """The useful life covers the answer, not only the wait.

        Con la maquina lenta, un request que empezo a los 27,9 s de 28 tardo
        mas de 2 s en extraerse y Vegeta lo conto como timeout (30,004 s).
        """
        now = [0.0]
        gate = make_gate(
            max_wait_seconds=10.0,
            initial_service_seconds=2.0,
            clock=lambda: now[0],
        )
        calls = 0

        async def work():
            nonlocal calls
            calls += 1

        async def scenario():
            with gate.admit() as ticket:
                now[0] += 9.0  # 9 s de espera + 2 s de extraccion > 10 s
                await ticket.run(work, connected)

        with pytest.raises(ServiceOverloadedError):
            run(scenario())
        assert calls == 0


class TestServiceTimeEstimate:
    def test_a_single_slow_extraction_barely_moves_the_estimate(self):
        """By default the average weighs ~20 extractions, about a whole queue.

        El promedio da el Retry-After: con uno que pesaba ~5 muestras, un par de
        PDFs grandes seguidos lo inflaba.
        """
        now = [0.0]
        gate = make_gate(
            max_wait_seconds=10.0, initial_service_seconds=0.3, clock=lambda: now[0]
        )

        async def slow_work():
            now[0] += 3.0

        async def scenario():
            with gate.admit() as ticket:
                await ticket.run(slow_work, connected)

        run(scenario())
        assert gate.service_seconds == pytest.approx(0.3 + 0.05 * (3.0 - 0.3))


class TestQueueOrder:
    """Size order: the lightest waiting PDF runs first, unless one waited long.

    En el spike el profesor tiene p50 1,88 s con un promedio de ~3,9 s
    (100 VUs / 25,35 req/s): sus PDFs livianos salen rapido. Atendiendo por
    orden de llegada, todos esperan lo mismo que los pesados.
    """

    def run_in_order(self, gate: AdmissionGate, costs, before_release=None):
        """Occupy the turn, queue one request per cost and return the run order."""
        order = []

        async def scenario():
            release_first = asyncio.Event()

            async def first_work():
                await release_first.wait()

            async def one(cost):
                async def work():
                    order.append(cost)

                with gate.admit() as ticket:
                    await ticket.run(work, connected, cost=cost)

            with gate.admit() as first:
                running = asyncio.create_task(first.run(first_work, connected, cost=0))
                await asyncio.sleep(0)  # el primero toma el turno
                waiting = []
                for cost in costs:
                    waiting.append(asyncio.create_task(one(cost)))
                    await asyncio.sleep(0)  # llegan en este orden
                if before_release:
                    before_release()
                release_first.set()
                await running
                await asyncio.gather(*waiting)

        run(scenario())
        return order

    def test_size_order_runs_the_lightest_waiting_request_first(self):
        gate = make_gate(max_pending=10, queue_order="size")

        assert self.run_in_order(gate, [300, 100, 200]) == [100, 200, 300]

    def test_fifo_order_keeps_the_arrival_order(self):
        gate = make_gate(max_pending=10, queue_order="fifo")

        assert self.run_in_order(gate, [300, 100, 200]) == [300, 100, 200]

    def test_a_request_that_waited_long_runs_before_lighter_ones(self):
        """No starvation: past the age limit the oldest goes first."""
        now = [0.0]
        gate = make_gate(
            max_wait_seconds=60.0,
            max_pending=10,
            queue_order="size",
            priority_age_seconds=14.0,
            clock=lambda: now[0],
        )

        def time_passes():
            now[0] += 15.0  # todos esperaron mas que el limite de edad

        order = self.run_in_order(gate, [300, 100, 200], before_release=time_passes)

        assert order == [300, 100, 200]

    def test_a_cancelled_waiter_does_not_block_the_queue(self):
        gate = make_gate(max_pending=10, queue_order="size")
        order = []

        async def scenario():
            release_first = asyncio.Event()

            async def first_work():
                await release_first.wait()

            async def work():
                order.append("segundo")

            with gate.admit() as first:
                running = asyncio.create_task(first.run(first_work, connected, cost=0))
                await asyncio.sleep(0)
                with gate.admit() as gone:
                    abandoned = asyncio.create_task(gone.run(work, connected, cost=1))
                    await asyncio.sleep(0)
                    abandoned.cancel()  # el cliente se fue mientras esperaba
                with gate.admit() as second:
                    waiting = asyncio.create_task(second.run(work, connected, cost=5))
                    await asyncio.sleep(0)
                    release_first.set()
                    await running
                    await waiting

        run(scenario())
        assert order == ["segundo"]
