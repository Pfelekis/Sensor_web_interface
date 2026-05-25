# Progress & Session Notes

## Project

`sensor_web_interface` — Real-time 6 DOF IMU dashboard (FastAPI + SSE + Chart.js)

**Branch:** `claude/embedded-web-interface-plan-tyuy8`

---

## What Is Done

### Infrastructure
- [x] Multi-agent setup: `orchestrator`, `web-implementer`, `python-simulator`, `test-writer` in `.claude/agents/`
- [x] `pyproject.toml` with `asyncio_mode = "auto"`

### Backend (`backend/`)
- [x] `sensor.py` — `SensorReader` with three modes: `simulate` (default), `serial` (CSV over UART), `mqtt` (JSON payload)
- [x] `sensor.py` — Configurable sample rate via `SENSOR_RATE_HZ` env var (default 10 Hz)
- [x] `sensor.py` — Serial mode has reconnect loop (no crash on disconnect)
- [x] `sensor.py` — MQTT mode validates payload keys before queuing
- [x] `database.py` — async SQLite with 7-column schema (timestamp + accel xyz + gyro xyz)
- [x] `database.py` — Index on `timestamp` column
- [x] `database.py` — `get_reading_count()` helper
- [x] `main.py` — pub-sub broadcaster (sensor → DB at 1 Hz → all SSE subscribers)
- [x] `main.py` — Per-client queue capped at `maxsize=50` (slow clients drop frames, don’t crash)
- [x] `main.py` — `QueueFull` handled gracefully in broadcaster
- [x] `main.py` — SSE response has `Cache-Control: no-cache` and `X-Accel-Buffering: no`
- [x] `main.py` — `/health` endpoint returns status + subscriber count

### Frontend (`frontend/`)
- [x] Two Chart.js line charts: Accelerometer (m/s²) and Gyroscope (°/s)
- [x] 3 datasets per chart (X=red, Y=green, Z=blue)
- [x] Rolling 200-point window (20 s at 10 Hz)
- [x] Pre-populates from `/history` on load
- [x] Live connection status indicator
- [x] Dark theme, responsive 2-column grid

### Tests (`tests/`)
- [x] `test_database.py` — 12 tests: table creation, index, idempotency, insert/retrieve, empty list, precision, negatives, count, limit, ordering, default limit
- [x] `test_sensor.py` — 12 tests: schema, types, ISO8601, UTC timezone, gravity plausibility, XY near zero, gyro range, 10 Hz rate, 3 sequential readings, monotonic timestamps, unknown mode error
- [x] `test_api.py` — 13 tests: HTML, health ok, subscriber count, history array, empty history, schema, limit, stream content-type, cache-control header, data prefix, valid JSON, axis values roundtrip

---

## Known Limitations / Future Work

- [ ] No time-range filter on `/history` (e.g., `?since=<timestamp>`)
- [ ] No WebSocket alternative for bidirectional control
- [ ] No authentication / API key on endpoints
- [ ] DB writes use a new connection per call — consider a persistent pool under high load
- [ ] Serial reconnect uses bare `except Exception` — could log the specific error
- [ ] Frontend `fetch('/history')` silently swallows errors — add a visual error state
- [ ] No pagination on `/history`
- [ ] No Docker / docker-compose file yet

---

## Key Design Decisions

| Decision | Reason |
|---|---|
| SSE over WebSocket | Sensor data is one-directional; SSE is simpler and auto-reconnects |
| 10 Hz SSE, 1 Hz DB | Keep UI smooth without hammering SQLite |
| Per-client queue with maxsize | Prevents memory growth if a browser tab goes idle |
| CSV serial protocol | Minimal firmware code; easy to `printf` from C |
| JSON MQTT payload | Human-readable, easy to inspect with `mosquitto_sub` |

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `SENSOR_MODE` | `simulate` | `simulate` / `serial` / `mqtt` |
| `SENSOR_RATE_HZ` | `10` | Sample rate for simulator |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial device path |
| `BAUD_RATE` | `115200` | Serial baud rate |
| `MQTT_HOST` | `localhost` | MQTT broker hostname |
| `MQTT_TOPIC` | `imu/data` | MQTT topic to subscribe |
