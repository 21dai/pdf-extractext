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
3. Antes de extraer, si el cliente ya se fue, no hace el trabajo.
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
            raise ServiceOverloadedError(max(1, math.ceil(estimated_wait)))
        self.pending += 1
        return Ticket(self)

    def _observe(self, seconds: float) -> None:
        self.service_seconds += self.smoothing * (seconds - self.service_seconds)


class Ticket:
    """Place of an admitted request; free it with `release` or a with block."""

    def __init__(self, gate: AdmissionGate):
        self._gate = gate
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
        """
        async with self._gate._turn:
            if await is_disconnected():
                raise ClientDisconnectedError()
            started = self._gate._clock()
            try:
                return await work()
            finally:
                self._gate._observe(self._gate._clock() - started)
