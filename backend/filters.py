import math


class ComplementaryFilter:
    """
    Estimates roll and pitch from a 6 DOF IMU using a complementary filter.
    Also tracks relative position via dead-reckoning (double-integration of
    gravity-compensated acceleration).

    Yaw requires a magnetometer (9 DOF) and is intentionally not computed.
    Dead-reckoning position drifts over time — call reset_position() periodically.
    """

    ALPHA = 0.98  # gyro weight; (1 - ALPHA) = accelerometer weight
    G     = 9.81  # m/s²

    def __init__(self, dt: float = 0.1) -> None:
        self.dt    = dt
        self.roll  = 0.0  # degrees, rotation around X-axis
        self.pitch = 0.0  # degrees, rotation around Y-axis
        self._vel  = [0.0, 0.0, 0.0]
        self._pos  = [0.0, 0.0, 0.0]

    def update(self, accel: dict, gyro: dict) -> dict:
        ax, ay, az = accel["x"], accel["y"], accel["z"]
        gx, gy     = gyro["x"],  gyro["y"]

        # Absolute tilt from accelerometer (noisy but drift-free)
        accel_roll  = math.degrees(math.atan2(ay, az))
        accel_pitch = math.degrees(math.atan2(-ax, math.sqrt(ay**2 + az**2)))

        # Complementary filter: gyro for fast motion, accel corrects slow drift
        self.roll  = self.ALPHA * (self.roll  + gx * self.dt) + (1 - self.ALPHA) * accel_roll
        self.pitch = self.ALPHA * (self.pitch + gy * self.dt) + (1 - self.ALPHA) * accel_pitch

        # Rotate gravity vector into sensor frame using estimated roll/pitch
        r, p = math.radians(self.roll), math.radians(self.pitch)
        grav = [
            -self.G * math.sin(p),
             self.G * math.cos(p) * math.sin(r),
             self.G * math.cos(p) * math.cos(r),
        ]

        # Linear acceleration with gravity removed
        lin = [ax - grav[0], ay - grav[1], az - grav[2]]

        # Dead-reckoning: integrate accel → velocity → position
        for i in range(3):
            self._vel[i] += lin[i] * self.dt
            self._pos[i] += self._vel[i] * self.dt

        return {
            "angles": {
                "roll":  round(self.roll,  2),
                "pitch": round(self.pitch, 2),
            },
            "position": {
                "x": round(self._pos[0], 4),
                "y": round(self._pos[1], 4),
                "z": round(self._pos[2], 4),
            },
        }

    def reset_position(self) -> None:
        self._vel = [0.0, 0.0, 0.0]
        self._pos = [0.0, 0.0, 0.0]
