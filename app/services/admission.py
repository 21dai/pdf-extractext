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
2. Corre una extraccion por vez: los admitidos esperan en un semaforo de
   asyncio (barato) en vez de bloquear un hilo cada uno contra el lock de
   PDFium. El event loop sigue atendiendo HTTP mientras se extrae.
3. Cuando le toca el turno, si el cliente ya se fue o si el request no
   llegaria a terminar dentro de `max_wait_seconds` (su tiempo util: lo que
   ya espero mas el tiempo promedio de una extraccion), no hace el trabajo:
   el primero no tiene a quien responderle y el segundo recibe 503 al
   instante. Asi nunca se gasta CPU en algo que va a vencer.
"""

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.exceptions import ClientDisconnectedError, ServiceOverloadedError

Result = TypeVar("Result")


class AdmissionGate:
    """Decide which requests enter, and run their work one at a time."""

    def __init__(
        self,
        max_wait_seconds: float,
        max_pending: int,
        initial_service_seconds: float,
        smoothing: float = 0.05,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Initialize the gate.

        Args:
            max_wait_seconds: Useful life of a request: if its wait plus an
                average extraction exceeds it, it is rejected without processing
            max_pending: Requests admitted at the same time (queue size)
            initial_service_seconds: Service time assumed until there are
                measurements; the average feeds the useful-life check and the
                Retry-After
            smoothing: Weight of each new measurement in the moving average;
                0.05 weighs ~20 extractions, about a whole queue
            clock: Monotonic clock, injectable for tests
        """
        self.max_wait_seconds = max_wait_seconds
        self.max_pending = max_pending
        self.service_seconds = initial_service_seconds
        self.smoothing = smoothing
        self.pending = 0
        self._clock = clock
        self._turn = asyncio.Semaphore(1)

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
        self.service_seconds += self.smoothing * (seconds - self.service_seconds)


class Ticket:
    """Place of an admitted request; free it with `release` or a with block."""

    def __init__(self, gate: AdmissionGate, admitted_at: float):
        self._gate = gate
        self._admitted_at = admitted_at
        self._released = False

    def __enter__(self) -> "Ticket":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._gate.pending -= 1

    async def run(
        self,
        work: Callable[[], Awaitable[Result]],
        is_disconnected: Callable[[], Awaitable[bool]],
    ) -> Result:
        """Wait for the turn and run the work, unless the client already left.

        Raises:
            ClientDisconnectedError: If the client disconnected while waiting.
            ServiceOverloadedError: If it would finish after its useful life.
        """
        gate = self._gate
        async with gate._turn:
            if await is_disconnected():
                raise ClientDisconnectedError()
            started = gate._clock()
            # El tiempo util cubre la respuesta, no solo la espera: si lo que
            # espero mas lo que tarda una extraccion se pasa, ya no llega.
            finish_estimate = started - self._admitted_at + gate.service_seconds
            if finish_estimate > gate.max_wait_seconds:
                raise gate._overloaded(gate.pending * gate.service_seconds)
            try:
                return await work()
            finally:
                gate._observe(gate._clock() - started)
