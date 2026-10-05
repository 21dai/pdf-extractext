"""Admission control for POST /extract: backpressure inside each process.

Sin control, en el modelo abierto (Vegeta: tasa fija sin esperar respuestas)
los requests se acumulan mas rapido de lo que se procesan; los ultimos
esperan mas que el timeout del cliente, y el servidor igual los procesa: CPU
gastado en respuestas que nadie lee, mientras los nuevos tambien vencen.

La compuerta:

1. Admite un request solo si su espera estimada (pendientes x tiempo de
   servicio promedio) no supera el maximo; si no, lo rechaza al instante con
   503 y Retry-After, antes de leer el PDF.
2. Corre una extraccion por vez: los admitidos esperan en un semaforo de
   asyncio (barato) en vez de bloquear un hilo cada uno contra el lock de
   PDFium. El event loop sigue atendiendo HTTP mientras se extrae.
3. Cuando le toca el turno, si el cliente ya se fue o si el request ya
   espero mas que el maximo (su tiempo util), no hace el trabajo: el
   primero no tiene a quien responderle y el segundo recibe 503 al instante.
   Este chequeo es exacto; la estimacion del punto 1 solo corta lo que
   claramente no va a llegar.
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
        initial_service_seconds: float,
        smoothing: float = 0.2,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Initialize the gate.

        Args:
            max_wait_seconds: Longest estimated wait a request is admitted with
            initial_service_seconds: Service time assumed until there are
                measurements
            smoothing: Weight of each new measurement in the moving average
            clock: Monotonic clock, injectable for tests
        """
        self.max_wait_seconds = max_wait_seconds
        self.service_seconds = initial_service_seconds
        self.smoothing = smoothing
        self.pending = 0
        self._clock = clock
        self._turn = asyncio.Semaphore(1)

    def admit(self) -> "Ticket":
        """Admit a request, or reject it if it would wait too long.

        Raises:
            ServiceOverloadedError: If the estimated wait exceeds the maximum.
        """
        estimated_wait = self.pending * self.service_seconds
        if estimated_wait > self.max_wait_seconds:
            raise self._overloaded(estimated_wait)
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
            ServiceOverloadedError: If it waited longer than the maximum.
        """
        gate = self._gate
        async with gate._turn:
            if await is_disconnected():
                raise ClientDisconnectedError()
            started = gate._clock()
            if started - self._admitted_at > gate.max_wait_seconds:
                raise gate._overloaded(gate.pending * gate.service_seconds)
            try:
                return await work()
            finally:
                gate._observe(gate._clock() - started)
