"""Cooperative cancellation primitive shared by engines and executors."""

from __future__ import annotations

import asyncio

from .errors import AutomationCancelled


class CancellationToken:
    """An explicit cancellation signal; it never executes cleanup commands itself."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise AutomationCancelled("Automation was cancelled.")
