# Sensor Web Interface

A real-time sensor dashboard with a Python FastAPI backend and a browser-based frontend.
The backend ingests data from an embedded device (serial/MQTT) and streams it to the browser via Server-Sent Events (SSE).

## Architecture

```
[Embedded Device] ──serial/MQTT──► [Python Backend (FastAPI)] ──SSE──► [Browser (HTMX + Chart.js)]
                                           │
                                      [SQLite DB]
```

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, uvicorn |
| Real-time | Server-Sent Events (SSE) |
| Frontend | HTML, HTMX, Chart.js |
| Storage | SQLite (via aiosqlite) |
| Embedded link | pyserial or paho-mqtt |
| Tests | pytest, pytest-asyncio, httpx |

## Project Structure

```
sensor_web_interface/
├── CLAUDE.md
├── .claude/
│   └── agents/
│       ├── orchestrator.md
│       ├── web-implementer.md
│       ├── python-simulator.md
│       └── test-writer.md
├── backend/
│   ├── main.py          # FastAPI app + SSE endpoint
│   ├── sensor.py        # Serial/MQTT reader + simulator
│   ├── database.py      # SQLite models and helpers
│   └── requirements.txt
├── frontend/
│   ├── index.html       # Dashboard (HTMX + Chart.js)
│   └── static/
│       └── style.css
└── tests/
    ├── test_api.py
    ├── test_sensor.py
    └── test_database.py
```

## Multi-Agent Workflow

This project uses four Claude Code sub-agents:

- **orchestrator** — breaks down tasks, delegates to specialists, resolves blockers
- **web-implementer** — owns the frontend (HTML/HTMX/Chart.js)
- **python-simulator** — owns the backend (FastAPI, SSE, sensor simulation)
- **test-writer** — owns the test suite (pytest)

## Running Locally

```bash
# Install deps
pip install -r backend/requirements.txt

# Start the server (simulator mode — no real hardware needed)
uvicorn backend.main:app --reload

# Open browser
open http://localhost:8000
```

## Running Tests

```bash
pytest tests/ -v
```
