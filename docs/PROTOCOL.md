# Embedded Protocol Reference

This document describes how the firmware on the embedded device should
format and send IMU data to the Python backend.

---

## Option A — UART / Serial (simplest)

### Wire format

One line per sample, 6 comma-separated floats, terminated with `\n`:

```
<accel_x>,<accel_y>,<accel_z>,<gyro_x>,<gyro_y>,<gyro_z>\n
```

### Units

| Field | Unit |
|---|---|
| accel_x/y/z | m/s² |
| gyro_x/y/z | °/s |

### Example output (C)

```c
#include <stdio.h>

void send_imu_sample(float ax, float ay, float az,
                     float gx, float gy, float gz)
{
    printf("%.4f,%.4f,%.4f,%.4f,%.4f,%.4f\n",
           ax, ay, az, gx, gy, gz);
}
```

### Configuration

```bash
export SENSOR_MODE=serial
export SERIAL_PORT=/dev/ttyUSB0   # or /dev/ttyACM0 for STM32 VCP
export BAUD_RATE=115200
python -m uvicorn backend.main:app
```

### Notes

- Lines with fewer or more than 6 fields are silently ignored
- Non-numeric tokens are silently ignored
- The backend reconnects automatically if the port disconnects

---

## Option B — MQTT

### Payload format

JSON object published to the configured topic:

```json
{
  "accel": {"x": 0.12, "y": -0.05, "z": 9.79},
  "gyro":  {"x": 0.30, "y": -0.10, "z": 0.05}
}
```

### Example (C with a lightweight MQTT library)

```c
char buf[128];
snprintf(buf, sizeof(buf),
    "{\"accel\":{\"x\":%.4f,\"y\":%.4f,\"z\":%.4f},"
    "\"gyro\":{\"x\":%.4f,\"y\":%.4f,\"z\":%.4f}}",
    ax, ay, az, gx, gy, gz);
mqtt_publish(client, "imu/data", buf, strlen(buf), 0, 0);
```

### Configuration

```bash
export SENSOR_MODE=mqtt
export MQTT_HOST=192.168.1.10   # broker IP
export MQTT_TOPIC=imu/data
python -m uvicorn backend.main:app
```

### Notes

- Payloads missing `accel` or `gyro` keys are silently dropped
- All six axis values must be numeric; invalid payloads are dropped
- Requires a running MQTT broker (e.g., `mosquitto`)

---

## Choosing Between Serial and MQTT

| | Serial | MQTT |
|---|---|---|
| Firmware complexity | Minimal (`printf`) | Needs MQTT client library |
| Network required | No (USB cable) | Yes (WiFi/Ethernet) |
| Multi-consumer | No | Yes (any number of subscribers) |
| Debugging | Easy (`screen /dev/ttyUSB0`) | Moderate (`mosquitto_sub`) |
| Best for | Development / wired bench | Production / wireless IoT |
