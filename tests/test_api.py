import asyncio
import json
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


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_index_returns_html():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "subscribers" in body


@pytest.mark.asyncio
async def test_health_subscriber_count_reflects_connections():
    before = len(_subscribers)
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.get("/health")
    assert response.json()["subscribers"] == before


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

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
async def test_history_empty_returns_empty_list():
    with patch("backend.main.get_history", new=AsyncMock(return_value=[])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_history_response_schema():
    with patch("backend.main.get_history", new=AsyncMock(return_value=SAMPLE)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    item = response.json()[0]
    assert "timestamp" in item
    assert {"x", "y", "z"} == item["accel"].keys()
    assert {"x", "y", "z"} == item["gyro"].keys()


@pytest.mark.asyncio
async def test_history_at_most_200_items():
    big = [SAMPLE[0]] * 200
    with patch("backend.main.get_history", new=AsyncMock(return_value=big)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    assert len(response.json()) <= 200


# ---------------------------------------------------------------------------
# Stream (SSE)
# ---------------------------------------------------------------------------

async def _stream_first_chunk(reading: dict) -> bytes:
    """Helper: open /stream, return the first chunk, then close."""
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(reading)
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as response:
                    assert response.status_code == 200
                    async for chunk in response.aiter_bytes():
                        return chunk
    finally:
        if q in _subscribers:
            _subscribers.remove(q)
    return b""


@pytest.mark.asyncio
async def test_stream_content_type():
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(SAMPLE[0])
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as response:
                    assert "text/event-stream" in response.headers["content-type"]
    finally:
        if q in _subscribers:
            _subscribers.remove(q)


@pytest.mark.asyncio
async def test_stream_cache_control_header():
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(SAMPLE[0])
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as response:
                    assert response.headers.get("cache-control") == "no-cache"
    finally:
        if q in _subscribers:
            _subscribers.remove(q)


@pytest.mark.asyncio
async def test_stream_emits_data_prefix():
    chunk = await _stream_first_chunk(SAMPLE[0])
    assert chunk.startswith(b"data: ")


@pytest.mark.asyncio
async def test_stream_event_is_valid_json():
    chunk = await _stream_first_chunk(SAMPLE[0])
    raw = chunk.decode().removeprefix("data: ").strip()
    payload = json.loads(raw)  # raises if not valid JSON
    assert "accel" in payload
    assert "gyro" in payload
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_stream_event_axis_values_match_source():
    reading = SAMPLE[0]
    chunk = await _stream_first_chunk(reading)
    payload = json.loads(chunk.decode().removeprefix("data: ").strip())
    assert payload["accel"]["z"] == pytest.approx(reading["accel"]["z"])
    assert payload["gyro"]["x"]  == pytest.approx(reading["gyro"]["x"])
