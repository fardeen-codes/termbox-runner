"""Pytest configuration and shared test fixtures."""

import asyncio
from typing import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient

from termbox_runner.api import app, get_executor_dependency, get_storage_dependency
from termbox_runner.runner import MockTaskExecutor, TaskExecutor
from termbox_runner.storage import RunStorage


@pytest.fixture
def mock_executor() -> MockTaskExecutor:
    """Fixture providing a mock executor."""
    return MockTaskExecutor()


@pytest.fixture
async def test_storage() -> AsyncGenerator[RunStorage, None]:
    """Fixture providing an isolated in-memory SQLite storage."""
    storage = RunStorage(":memory:")
    await storage.init_db()
    yield storage
    await storage.close()


@pytest.fixture
async def async_client(test_storage: RunStorage, mock_executor: MockTaskExecutor) -> AsyncGenerator[AsyncClient, None]:
    """Fixture providing an async HTTP client wired with mock dependencies."""
    app.dependency_overrides[get_storage_dependency] = lambda: test_storage
    app.dependency_overrides[get_executor_dependency] = lambda: mock_executor

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
