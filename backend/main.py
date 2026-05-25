import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.database import get_history, init_db, insert_reading
from backend.filters import ComplementaryFilter
from backend.sensor import SensorReader

_sensor_queue: asyncio.Queue = asyncio.Queue()
_subscribers: list[asyncio.Queue] = []

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_reader = SensorReader()
_filter = ComplementaryFilter(dt=1.0 / _reader.rate_hz)


async def _broadcaster() -> None:
    """Read sensor queue, enrich with filter output, persist at 1 Hz, fan out."""
    asyncio.create_task(_reader.start(_sensor_queue))
    persist_tick = 0
    while True:
        reading = await _sensor_queue.get()
        enriched = {**reading, **_filter.update(reading["accel"], reading["gyro"])}
        persist_tick += 1
        if persist_tick % 10 == 0:  # write to DB at ~1 Hz
            await insert_reading(
                timestamp=reading["timestamp"],
                accel=reading["accel"],
                gyro=reading["gyro"],
            )
        for q in list(_subscribers):
            try:
                q.put_nowait(enriched)
            except asyncio.QueueFull:
                pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    task = asyncio.create_task(_broadcaster())
    yield
    task.cancel()


app = FastAPI(title="IMU Dashboard", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "subscribers": len(_subscribers)}


@app.post("/reset-position")
async def reset_position() -> dict:
    _filter.reset_position()
    return {"status": "ok"}


@app.get("/history")
async def history() -> list[dict]:
    return await get_history(limit=200)


@app.get("/stream")
async def stream() -> StreamingResponse:
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _subscribers.append(q)

    async def event_generator():
        try:
            while True:
                reading = await q.get()
                yield f"data: {json.dumps(reading)}\n\n"
        finally:
            _subscribers.remove(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
