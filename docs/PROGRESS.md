# Progress & Session Notes

## Project

`sensor_web_interface` — Real-time 6 DOF IMU dashboard (FastAPI + SSE + Chart.js + Three.js)

**Branch:** `claude/embedded-web-interface-plan-tyuy8`

---

## Architecture: Where Code Runs

```
[Embedded Target]         [Python Backend]           [Browser]
 MCU firmware             runs on your laptop        JavaScript
 reads IMU chip           or a Raspberry Pi

 accel/gyro data  ──►  complementary filter   ──►  Chart.js charts
 (raw, CSV/MQTT)         roll/pitch angles          Three.js 3D cube
                         dead-reckoning pos          2D path canvas
                         SQLite persistence
```

**Key rule:** Filter runs on the server (Python), not the MCU. In production,
you’d move it to the MCU to reduce bandwidth (send angles instead of raw data).

---

## What Is Done

### Backend
- [x] `sensor.py` — simulate / serial / mqtt modes, configurable `SENSOR_RATE_HZ`
- [x] `database.py` — 7-column SQLite schema + timestamp index + `get_reading_count()`
- [x] `filters.py` — `ComplementaryFilter`: roll/pitch estimation + dead-reckoning position
- [x] `main.py` — broadcaster enriches each reading with filter output before fan-out
- [x] `main.py` — `POST /reset-position` resets filter velocity + position state
- [x] `main.py` — `/health`, SSE headers (`Cache-Control`, `X-Accel-Buffering`)

### Frontend
- [x] Accelerometer chart — 3-axis rolling 200-point line chart
- [x] Gyroscope chart — 3-axis rolling 200-point line chart
- [x] **Three.js 3D cube** — PCB-shaped box rotates with roll/pitch in real-time
- [x] **2D movement path** — auto-scaling X-Y canvas with gradient trail, start/end markers
- [x] Reset button — clears path canvas + calls `POST /reset-position`
- [x] History preload feeds raw charts only (filter state cannot be replayed)

### Tests (51 total)
- [x] `test_filters.py` — 16 tests: schema, flat convergence, 45°/30° tilt, gyro integration, position, reset
- [x] `test_database.py` — 12 tests
- [x] `test_sensor.py` — 12 tests
- [x] `test_api.py` — 15 tests: includes reset-position, SSE angles/position schema

---

## Known Limitations

- [ ] **Yaw drifts** — need a magnetometer (9 DOF) for stable yaw
- [ ] **Dead-reckoning drifts** — unavoidable without GPS; useful for <5 s gestures only
- [ ] No time-range filter on `/history`
- [ ] No authentication
- [ ] No Docker file
- [ ] DB uses one connection per write — fine for demo, consider a pool at scale

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SENSOR_MODE` | `simulate` | `simulate` / `serial` / `mqtt` |
| `SENSOR_RATE_HZ` | `10` | Sample rate for simulator |
| `SERIAL_PORT` | `/dev/ttyUSB0` | Serial device |
| `BAUD_RATE` | `115200` | Baud rate |
| `MQTT_HOST` | `localhost` | MQTT broker |
| `MQTT_TOPIC` | `imu/data` | MQTT topic |

## Serial Protocol (firmware side)

```c
// One printf per sample, at your desired rate:
printf("%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
       accel_x, accel_y, accel_z,
       gyro_x,  gyro_y,  gyro_z);
```
