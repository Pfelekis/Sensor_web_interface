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
    """Read from the sensor, persist each reading, then fan out to SSE subscribers."""
    reader = SensorReader()
    asyncio.create_task(reader.start(_sensor_queue))
    while True:
        reading = await _sensor_queue.get()
        await insert_reading(
            timestamp=reading["timestamp"],
            value=reading["value"],
            unit=reading["unit"],
        )
        for q in list(_subscribers):
            q.put_nowait(reading)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    task = asyncio.create_task(_broadcaster())
    yield
    task.cancel()


app = FastAPI(title="Sensor Dashboard", lifespan=lifespan)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/history")
async def history() -> list[dict]:
    return await get_history(limit=100)


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
