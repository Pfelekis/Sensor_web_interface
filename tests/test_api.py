import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app, _subscribers

BASE = "http://test"

SAMPLE = [
    {"timestamp": "2024-01-01T00:00:00+00:00", "value": 25.0, "unit": "°C"},
]


@pytest.mark.asyncio
async def test_index_returns_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_history_returns_json_array():
    with patch("backend.main.get_history", new=AsyncMock(return_value=SAMPLE)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["value"] == 25.0


@pytest.mark.asyncio
async def test_history_at_most_100_items():
    big = [{"timestamp": "2024-01-01T00:00:00+00:00", "value": float(i), "unit": "°C"} for i in range(100)]
    with patch("backend.main.get_history", new=AsyncMock(return_value=big)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    assert len(response.json()) <= 100


@pytest.mark.asyncio
async def test_stream_content_type_and_first_event():
    reading = SAMPLE[0]

    async def fake_get():
        return reading

    # Pre-load a subscriber queue so the endpoint finds data immediately
    import asyncio
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(reading)
    _subscribers.append(q)

    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers["content-type"]
                    async for chunk in response.aiter_bytes():
                        assert b"data:" in chunk
                        break
    finally:
        if q in _subscribers:
            _subscribers.remove(q)
