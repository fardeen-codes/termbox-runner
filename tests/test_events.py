"""Tests for Server-Sent Events broker and streaming."""

import asyncio
import pytest
from termbox_runner.events import get_event_broker


@pytest.mark.asyncio
async def test_event_broker_pub_sub():
    broker = get_event_broker()
    received = []

    async def reader():
        async for chunk in broker.subscribe("run_test_123"):
            received.append(chunk)

    task = asyncio.create_task(reader())
    await asyncio.sleep(0.01)

    await broker.publish("run_test_123", "step_finish", {"exit_code": 0})
    await broker.close_stream("run_test_123")
    await task

    assert len(received) == 1
    assert "step_finish" in received[0]
    assert "exit_code" in received[0]
