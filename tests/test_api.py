import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app, _subscribers

BASE = "http://test"

# SSE stream payload (enriched by filter)
STREAM_READING = {
    "timestamp": "2024-01-01T00:00:00+00:00",
    "accel":    {"x": 0.12,  "y": -0.05, "z": 9.79},
    "gyro":     {"x": 0.30,  "y": -0.10, "z": 0.05},
    "angles":   {"roll": 1.5, "pitch": 0.7},
    "position": {"x": 0.001, "y": 0.002, "z": 0.003},
}

# History payload (raw only — no angles/position stored in DB)
HISTORY_READING = {
    "timestamp": "2024-01-01T00:00:00+00:00",
    "accel": {"x": 0.12, "y": -0.05, "z": 9.79},
    "gyro":  {"x": 0.30, "y": -0.10, "z": 0.05},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _first_sse_chunk(reading: dict) -> bytes:
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(reading)
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as resp:
                    assert resp.status_code == 200
                    async for chunk in resp.aiter_bytes():
                        return chunk
    finally:
        if q in _subscribers:
            _subscribers.remove(q)
    return b""


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
    assert response.json()["status"] == "ok"
    assert "subscribers" in response.json()


# ---------------------------------------------------------------------------
# Reset position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reset_position_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        response = await client.post("/reset-position")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_reset_position_clears_filter_state():
    from backend.main import _filter
    _filter._pos = [9.9, 9.9, 9.9]
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
        await client.post("/reset-position")
    assert _filter._pos == [0.0, 0.0, 0.0]


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_history_returns_json_array():
    with patch("backend.main.get_history", new=AsyncMock(return_value=[HISTORY_READING])):
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
    assert response.json() == []


@pytest.mark.asyncio
async def test_history_response_schema():
    with patch("backend.main.get_history", new=AsyncMock(return_value=[HISTORY_READING])):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
            response = await client.get("/history")
    item = response.json()[0]
    assert {"x", "y", "z"} == item["accel"].keys()
    assert {"x", "y", "z"} == item["gyro"].keys()


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stream_content_type():
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(STREAM_READING)
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as resp:
                    assert "text/event-stream" in resp.headers["content-type"]
    finally:
        if q in _subscribers:
            _subscribers.remove(q)


@pytest.mark.asyncio
async def test_stream_cache_control_header():
    q: asyncio.Queue = asyncio.Queue()
    q.put_nowait(STREAM_READING)
    _subscribers.append(q)
    try:
        with patch("backend.main.insert_reading", new=AsyncMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as client:
                async with client.stream("GET", "/stream") as resp:
                    assert resp.headers.get("cache-control") == "no-cache"
    finally:
        if q in _subscribers:
            _subscribers.remove(q)


@pytest.mark.asyncio
async def test_stream_emits_data_prefix():
    chunk = await _first_sse_chunk(STREAM_READING)
    assert chunk.startswith(b"data: ")


@pytest.mark.asyncio
async def test_stream_event_is_valid_json():
    chunk = await _first_sse_chunk(STREAM_READING)
    payload = json.loads(chunk.decode().removeprefix("data: ").strip())
    assert "accel"    in payload
    assert "gyro"     in payload
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_stream_event_contains_angles():
    chunk = await _first_sse_chunk(STREAM_READING)
    payload = json.loads(chunk.decode().removeprefix("data: ").strip())
    assert "angles" in payload
    assert {"roll", "pitch"} == payload["angles"].keys()


@pytest.mark.asyncio
async def test_stream_event_contains_position():
    chunk = await _first_sse_chunk(STREAM_READING)
    payload = json.loads(chunk.decode().removeprefix("data: ").strip())
    assert "position" in payload
    assert {"x", "y", "z"} == payload["position"].keys()


@pytest.mark.asyncio
async def test_stream_axis_values_match_source():
    chunk = await _first_sse_chunk(STREAM_READING)
    payload = json.loads(chunk.decode().removeprefix("data: ").strip())
    assert payload["accel"]["z"] == pytest.approx(STREAM_READING["accel"]["z"])
    assert payload["gyro"]["x"]  == pytest.approx(STREAM_READING["gyro"]["x"])
