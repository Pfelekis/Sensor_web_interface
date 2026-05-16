import asyncio
import math
import os
import random
from datetime import datetime, timezone


class SensorReader:
    def __init__(self) -> None:
        self.mode = os.getenv("SENSOR_MODE", "simulate")
        self.unit = os.getenv("SENSOR_UNIT", "°C")

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
        t = 0
        while True:
            value = 25.0 + 5.0 * math.sin(2 * math.pi * t / 60) + random.gauss(0, 0.3)
            await queue.put({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": round(value, 2),
                "unit": self.unit,
            })
            t += 1
            await asyncio.sleep(1.0)

    async def _read_serial(self, queue: asyncio.Queue) -> None:
        import serial  # noqa: PLC0415
        port = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
        baud = int(os.getenv("BAUD_RATE", "115200"))
        ser = serial.Serial(port, baud, timeout=1)
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, ser.readline)
            text = line.decode("utf-8", errors="ignore").strip()
            if text:
                try:
                    await queue.put({
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "value": round(float(text), 2),
                        "unit": self.unit,
                    })
                except ValueError:
                    pass

    async def _read_mqtt(self, queue: asyncio.Queue) -> None:
        import paho.mqtt.client as mqtt  # noqa: PLC0415
        host = os.getenv("MQTT_HOST", "localhost")
        topic = os.getenv("MQTT_TOPIC", "sensor/value")
        loop = asyncio.get_running_loop()

        def on_message(_client, _userdata, msg):
            try:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "value": round(float(msg.payload.decode()), 2),
                        "unit": self.unit,
                    },
                )
            except ValueError:
                pass

        client = mqtt.Client()
        client.on_message = on_message
        client.connect(host)
        client.subscribe(topic)
        client.loop_start()
        while True:
            await asyncio.sleep(1)
