# Architecture

## Data Flow

```
[Embedded device]
      |
      | UART CSV  --or--  MQTT JSON
      ▼
[SensorReader]  (backend/sensor.py)
  mode: simulate | serial | mqtt
  rate: SENSOR_RATE_HZ (default 10 Hz)
      |
      | asyncio.Queue (_sensor_queue)
      ▼
[_broadcaster]  (backend/main.py)
  - pulls readings from _sensor_queue
  - writes to SQLite every 10th reading (1 Hz)
  - fans out to all subscriber queues
      |
      +----------+----------+
      |          |          |
   [q1]       [q2]       [q3]     per-client asyncio.Queue (maxsize=50)
      |          |          |
   [SSE]      [SSE]      [SSE]    GET /stream (one per browser tab)
      |
   [Browser]  (frontend/index.html)
     Chart.js rolling window, 200 points
```

## Module Responsibilities

```
backend/
  sensor.py     SensorReader class — one source of truth for all input modes
  database.py   Pure async functions, no global state, db_path injectable for tests
  main.py       FastAPI app, lifespan wiring, HTTP routes, pub-sub broadcaster

frontend/
  index.html    Self-contained: Chart.js from CDN, EventSource API, no build step
  static/style.css  Dark theme, CSS Grid, axis colour convention

tests/
  test_database.py   Unit tests; use tmp_path, never touch sensor.db
  test_sensor.py     Unit tests; cancel sensor task after each test
  test_api.py        Integration tests; mock DB calls, manage _subscribers manually
```

## SSE Protocol

Each event on `GET /stream`:

```
data: {"timestamp": "2024-01-01T00:00:00.123456+00:00",
        "accel": {"x": 0.12, "y": -0.05, "z": 9.79},
        "gyro":  {"x": 0.30, "y": -0.10, "z": 0.05}}

```

(blank line terminates each SSE event per spec)

## Why SSE over WebSocket

- Data flows only **server → browser** — no need for bidirectional channel
- Browser `EventSource` auto-reconnects; no client-side reconnect logic needed
- Works through HTTP/1.1 proxies with correct headers (`Cache-Control: no-cache`, `X-Accel-Buffering: no`)
- Simpler server implementation: no handshake, no frame encoding

## Persistence Strategy

Sensor runs at 10 Hz; writing every sample would create 864 000 rows/day.
The broadcaster writes every 10th reading (1 Hz = 86 400 rows/day), enough
for historical review without straining SQLite.

History is returned **newest-first** from the DB. The frontend reverses the
array with `.reverse()` before feeding it to the chart.
