from __future__ import annotations
import time
import asyncio

class Stats:
    def __init__(self):
        self.received = 0
        self.unique_processed = 0
        self.duplicate_dropped = 0
        self.start_time = time.time()
        self._lock = asyncio.Lock()

    async def inc_received(self, n: int = 1):
        async with self._lock:
            self.received += n

    async def inc_unique(self, n: int = 1):
        async with self._lock:
            self.unique_processed += n

    async def inc_duplicate(self, n: int = 1):
        async with self._lock:
            self.duplicate_dropped += n

    def uptime(self) -> float:
        return time.time() - self.start_time
