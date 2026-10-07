"""Admission control for POST /extract: backpressure inside each process.

Sin control, en el modelo abierto (Vegeta: tasa fija sin esperar respuestas)
los requests se acumulan mas rapido de lo que se procesan; los ultimos
esperan mas que el timeout del cliente, y el servidor igual los procesa: CPU
gastado en respuestas que nadie lee, mientras los nuevos tambien vencen.

La compuerta:

1. Admite requests mientras su cola tenga lugar (`max_pending`). Llena, el
   siguiente recibe 503 con Retry-After al instante, antes de leer el PDF.
   La cola se acota por cantidad y no por una estimacion de tiempo: durante
   un ataque la CPU esta saturada y cada extraccion tarda mas, pero esa cola
   se vacia mucho mas rapido cuando el ataque termina; una estimacion hecha
   en el momento admitia de menos y dejaba capacidad sin usar. El limite
   tambien acota la memoria de los PDFs que esperan.
2. Corre una extraccion por vez: los admitidos esperan su turno en asyncio
   (barato) en vez de bloquear un hilo cada uno contra el lock de PDFium. El
   event loop sigue atendiendo HTTP mientras se extrae. Con `queue_order`
   "size", el turno es del PDF mas liviano que espera (sale rapido y no queda
   detras de uno pesado); el que ya espero `priority_age_seconds` pasa
   primero, para que ninguno se quede sin turno.
3. Cuando le toca el turno, si el cliente ya se fue o si el request no
   llegaria a terminar dentro de `max_wait_seconds` (su tiempo util: lo que
   ya espero mas una extraccion pesimista, el promedio mas 4 desvios, como el
   temporizador de retransmision de TCP en la RFC 6298), no hace el trabajo:
   el primero no tiene a quien responderle y el segundo recibe 503 al
   instante. Asi nunca se gasta CPU en algo que va a vencer.
"""

import asyncio
import itertools
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

from app.core.exceptions import ClientDisconnectedError, ServiceOverloadedError

Result = TypeVar("Result")
QueueOrder = Literal["fifo", "size"]

# Margen del chequeo del tiempo util: promedio + 4 desvios, como el RTO de TCP.
# Con la maquina saturada un PDF grande tarda varias veces el promedio.
DEVIATION_MARGIN = 4


class AdmissionGate:
    """Decide which requests enter, and run their work one at a time."""

    def __init__(
        self,
        max_wait_seconds: float,
        max_pending: int,
        initial_service_seconds: float,
        smoothing: float = 0.05,
        queue_order: QueueOrder = "fifo",
        priority_age_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Initialize the gate.

        Args:
            max_wait_seconds: Useful life of a request: if its wait plus a
                pessimistic extraction (average + 4 deviations) exceeds it, it
                is rejected without processing
            max_pending: Requests admitted at the same time (queue size)
            initial_service_seconds: Service time assumed until there are
                measurements; the average feeds the useful-life check and the
                Retry-After
            smoothing: Weight of each new measurement in the moving average;
                0.05 weighs ~20 extractions, about a whole queue
            queue_order: "fifo" (arrival order) or "size" (lightest first)
            priority_age_seconds: With "size", a request that waited this
                long goes first; half the useful life if not given
            clock: Monotonic clock, injectable for tests
        """
        self.max_wait_seconds = max_wait_seconds
        self.max_pending = max_pending
        self.service_seconds = initial_service_seconds
        self.service_deviation_seconds = 0.0
        self.smoothing = smoothing
        self.pending = 0
        self._clock = clock
        if priority_age_seconds is None:
            priority_age_seconds = max_wait_seconds / 2
        self.queue_order = queue_order
        self.priority_age_seconds = priority_age_seconds
        self._turn = _Turn(queue_order, priority_age_seconds, clock)

    def admit(self) -> "Ticket":
        """Admit a request, or reject it if the queue is full.

        Raises:
            ServiceOverloadedError: If `max_pending` requests are already in.
        """
        if self.pending >= self.max_pending:
            raise self._overloaded(self.pending * self.service_seconds)
        self.pending += 1
        return Ticket(self, admitted_at=self._clock())

    def _overloaded(self, estimated_wait: float) -> ServiceOverloadedError:
        return ServiceOverloadedError(max(1, math.ceil(estimated_wait)))

    def _observe(self, seconds: float) -> None:
        # El desvio se actualiza con el promedio anterior (RFC 6298).
        error = abs(seconds - self.service_seconds)
        self.service_deviation_seconds += self.smoothing * (
            error - self.service_deviation_seconds
        )
        self.service_seconds += self.smoothing * (seconds - self.service_seconds)

    def _pessimistic_service_seconds(self) -> float:
        return self.service_seconds + DEVIATION_MARGIN * self.service_deviation_seconds


@dataclass(eq=False)
class _Waiter:
    cost: float
    admitted_at: float
    arrival: int
    granted: "asyncio.Future[None]"


class _Turn:
    """One extraction at a time, choosing who goes next among those waiting."""

    def __init__(
        self,
        order: QueueOrder,
        priority_age_seconds: float,
        clock: Callable[[], float],
    ):
        self._order = order
        self._priority_age_seconds = priority_age_seconds
        self._clock = clock
        self._busy = False
        self._waiting: list[_Waiter] = []
        self._arrivals = itertools.count()

    async def acquire(self, cost: float, admitted_at: float) -> None:
        if not self._busy:
            self._busy = True
            return
        granted: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        waiter = _Waiter(cost, admitted_at, next(self._arrivals), granted)
        self._waiting.append(waiter)
        try:
            await granted
        except asyncio.CancelledError:
            if granted.cancelled():
                self._waiting.remove(waiter)
            else:
                # Le dieron el turno justo cuando lo cancelaban: lo pasa.
                self.release()
            raise

    def release(self) -> None:
        """Give the turn to the next waiter, or leave it free."""
        while self._waiting:
            waiter = self._next()
            self._waiting.remove(waiter)
            if not waiter.granted.done():  # los cancelados se saltean
                waiter.granted.set_result(None)
                return
        self._busy = False

    def _next(self) -> _Waiter:
        oldest = min(self._waiting, key=lambda waiter: waiter.arrival)
        if self._order == "fifo":
            return oldest
        if self._clock() - oldest.admitted_at >= self._priority_age_seconds:
            return oldest
        return min(self._waiting, key=lambda waiter: (waiter.cost, waiter.arrival))


class Ticket:
    """Place of an admitted request; free it with `release` or a with block."""

    def __init__(self, gate: AdmissionGate, admitted_at: float):
        self._gate = gate
        self._admitted_at = admitted_at
        self._upload_seconds = 0.0
        self._released = False

    def __enter__(self) -> "Ticket":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def body_received(self) -> None:
        """Note that the whole PDF arrived, to know how long the upload took."""
        self._upload_seconds = self._gate._clock() - self._admitted_at

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._gate.pending -= 1

    async def run(
        self,
        work: Callable[[], Awaitable[Result]],
        is_disconnected: Callable[[], Awaitable[bool]],
        cost: float = 0.0,
    ) -> Result:
        """Wait for the turn and run the work, unless the client already left.

        Args:
            work: The extraction to run
            is_disconnected: Tells if the client already left
            cost: Estimated cost of the work (the PDF size), for size order

        Raises:
            ClientDisconnectedError: If the client disconnected while waiting.
            ServiceOverloadedError: If it would finish after its useful life.
        """
        gate = self._gate
        await gate._turn.acquire(cost, self._admitted_at)
        try:
            if await is_disconnected():
                raise ClientDisconnectedError()
            started = gate._clock()
            # El tiempo util cubre la respuesta, no solo la espera: si lo que
            # espero, mas lo que puede tardar la extraccion, mas la vuelta de
            # la respuesta (que cuesta como lo que tardo en llegar el PDF) se
            # pasa, no llega.
            waited = started - self._admitted_at
            finish_estimate = (
                waited + gate._pessimistic_service_seconds() + self._upload_seconds
            )
            if finish_estimate > gate.max_wait_seconds:
                raise gate._overloaded(gate.pending * gate.service_seconds)
            try:
                return await work()
            finally:
                gate._observe(gate._clock() - started)
        finally:
            gate._turn.release()
