import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.database import get_history, init_db, insert_reading
from backend.sensor import SensorReader

_sensor_queue: asyncio.Queue = asyncio.Queue()
_subscribers: list[asyncio.Queue] = []

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


async def _broadcaster() -> None:
    """Read sensor queue, persist at 1 Hz, fan out to all SSE subscribers."""
    reader = SensorReader()
    asyncio.create_task(reader.start(_sensor_queue))
    persist_tick = 0
    while True:
        reading = await _sensor_queue.get()
        persist_tick += 1
        if persist_tick % 10 == 0:  # write to DB at 1 Hz (sensor runs at 10 Hz)
            await insert_reading(
                timestamp=reading["timestamp"],
                accel=reading["accel"],
                gyro=reading["gyro"],
            )
        for q in list(_subscribers):
            q.put_nowait(reading)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    task = asyncio.create_task(_broadcaster())
    yield
    task.cancel()


app = FastAPI(title="IMU Dashboard", lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/history")
async def history() -> list[dict]:
    return await get_history(limit=200)


@app.get("/stream")
async def stream() -> StreamingResponse:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.append(q)

    async def event_generator():
        try:
            while True:
                reading = await q.get()
                yield f"data: {json.dumps(reading)}\n\n"
        finally:
            _subscribers.remove(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
