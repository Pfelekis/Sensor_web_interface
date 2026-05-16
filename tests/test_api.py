import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app, _subscribers

BASE = "http://test"

SAMPLE = [{
    "timestamp": "2024-01-01T00:00:00+00:00",
    "accel": {"x": 0.12, "y": -0.05, "z": 9.79},
    "gyro":  {"x": 0.30, "y": -0.10, "z": 0.05},
}]


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
    assert body[0]["accel"]["z"] == pytest.approx(9.79)


@pytest.mark.asyncio
async def test_history_at_most_200_items():
    big = [SAMPLE[0]] * 200
    with patch("backend.main.get_history", new=AsyncMock(return_value=big)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    assert len(response.json()) <= 200


@pytest.mark.asyncio
async def test_stream_content_type_and_first_event():
    reading = SAMPLE[0]
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
