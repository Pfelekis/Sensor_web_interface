import asyncio
import math
import os
import random
from datetime import datetime, timezone

_DEFAULT_RATE_HZ = 10.0


class SensorReader:
    """6 DOF IMU reader: accelerometer (m/s²) + gyroscope (°/s)."""

    def __init__(self) -> None:
        self.mode = os.getenv("SENSOR_MODE", "simulate")
        self.rate_hz = float(os.getenv("SENSOR_RATE_HZ", str(_DEFAULT_RATE_HZ)))

    async def start(self, queue: asyncio.Queue) -> None:
        if self.mode == "simulate":
            await self._simulate(queue)
        elif self.mode == "serial":
            await self._read_serial(queue)
        elif self.mode == "mqtt":
            await self._read_mqtt(queue)
        else:
            raise ValueError(f"Unknown SENSOR_MODE: {self.mode!r}")

    async def _simulate(self, queue: asyncio.Queue) -> None:
        """Sine-wave motion on all axes + Gaussian noise."""
        interval = 1.0 / self.rate_hz
        t = 0
        while True:
            accel = {
                "x": round(0.5 * math.sin(2 * math.pi * t / 200) + random.gauss(0, 0.02), 4),
                "y": round(0.3 * math.cos(2 * math.pi * t / 300) + random.gauss(0, 0.02), 4),
                "z": round(9.81 + 0.2 * math.sin(2 * math.pi * t / 150) + random.gauss(0, 0.02), 4),
            }
            gyro = {
                "x": round(5.0 * math.sin(2 * math.pi * t / 250) + random.gauss(0, 0.05), 4),
                "y": round(3.0 * math.cos(2 * math.pi * t / 400) + random.gauss(0, 0.05), 4),
                "z": round(2.0 * math.sin(2 * math.pi * t / 350) + random.gauss(0, 0.05), 4),
            }
            await queue.put({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "accel": accel,
                "gyro": gyro,
            })
            t += 1
            await asyncio.sleep(interval)

    async def _read_serial(self, queue: asyncio.Queue) -> None:
        """Parse CSV lines: accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z\n"""
        import serial  # noqa: PLC0415
        port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
        baud = int(os.getenv("BAUD_RATE", "115200"))
        loop = asyncio.get_running_loop()
        while True:
            try:
                ser = serial.Serial(port, baud, timeout=1)
                while True:
                    raw = await loop.run_in_executor(None, ser.readline)
                    text = raw.decode("utf-8", errors="ignore").strip()
                    parts = text.split(",")
                    if len(parts) == 6:
                        try:
                            ax, ay, az, gx, gy, gz = (float(p) for p in parts)
                            await queue.put({
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "accel": {"x": round(ax, 4), "y": round(ay, 4), "z": round(az, 4)},
                                "gyro":  {"x": round(gx, 4), "y": round(gy, 4), "z": round(gz, 4)},
                            })
                        except ValueError:
                            pass
            except Exception:  # serial disconnect — wait and retry
                await asyncio.sleep(2.0)

    async def _read_mqtt(self, queue: asyncio.Queue) -> None:
        """Expect JSON payload: {"accel":{x,y,z}, "gyro":{x,y,z}}"""
        import json  # noqa: PLC0415
        import paho.mqtt.client as mqtt  # noqa: PLC0415
        host  = os.getenv("MQTT_HOST",  "localhost")
        topic = os.getenv("MQTT_TOPIC", "imu/data")
        loop  = asyncio.get_running_loop()

        def on_message(_client, _userdata, msg):
            try:
                payload = json.loads(msg.payload.decode())
                reading = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "accel": payload["accel"],
                    "gyro":  payload["gyro"],
                }
                # basic validation before putting on queue
                for key in ("x", "y", "z"):
                    float(reading["accel"][key])
                    float(reading["gyro"][key])
                loop.call_soon_threadsafe(queue.put_nowait, reading)
            except (ValueError, KeyError, TypeError):
                pass

        client = mqtt.Client()
        client.on_message = on_message
        client.connect(host)
        client.subscribe(topic)
        client.loop_start()
        while True:
            await asyncio.sleep(1)
