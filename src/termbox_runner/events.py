"""Server-Sent Events (SSE) broker and event dispatcher for live run telemetry."""

import asyncio
from collections import defaultdict
import json
from typing import Any, AsyncGenerator, Dict, Set


class RunEventBroker:
    """Pub/sub broker distributing real-time execution events to SSE listeners."""

    def __init__(self):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> AsyncGenerator[str, None]:
        """Subscribe to live events for a given run ID."""
        q = asyncio.Queue()
        async with self._lock:
            self._subscribers[run_id].add(q)
        try:
            while True:
                data = await q.get()
                if data is None:
                    break
                yield f"data: {json.dumps(data)}\n\n"
        finally:
            async with self._lock:
                self._subscribers[run_id].discard(q)
                if not self._subscribers[run_id]:
                    del self._subscribers[run_id]

    async def publish(self, run_id: str, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish an event to all subscribers listening to run_id."""
        event_obj = {"run_id": run_id, "type": event_type, "payload": payload}
        async with self._lock:
            queues = list(self._subscribers.get(run_id, []))
        for q in queues:
            await q.put(event_obj)

    async def close_stream(self, run_id: str) -> None:
        """Signal completion of stream to subscribers."""
        async with self._lock:
            queues = list(self._subscribers.get(run_id, []))
        for q in queues:
            await q.put(None)


_global_broker = RunEventBroker()


def get_event_broker() -> RunEventBroker:
    """Return singleton event broker."""
    return _global_broker
