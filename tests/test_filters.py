import math
import pytest
from backend.filters import ComplementaryFilter


G     = 9.81
FLAT  = {"x": 0.0, "y": 0.0, "z": G}   # device flat on table
ZERO  = {"x": 0.0, "y": 0.0, "z": 0.0}  # zero gyro (stationary)


def make() -> ComplementaryFilter:
    return ComplementaryFilter(dt=0.1)


def run(f: ComplementaryFilter, accel: dict, gyro: dict, steps: int) -> dict:
    result = {}
    for _ in range(steps):
        result = f.update(accel, gyro)
    return result


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_roll_is_zero():
    assert make().roll == 0.0


def test_initial_pitch_is_zero():
    assert make().pitch == 0.0


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

def test_update_returns_angles_and_position():
    result = make().update(FLAT, ZERO)
    assert "angles"   in result
    assert "position" in result


def test_angles_have_roll_and_pitch():
    result = make().update(FLAT, ZERO)
    assert {"roll", "pitch"} == result["angles"].keys()


def test_position_has_xyz():
    result = make().update(FLAT, ZERO)
    assert {"x", "y", "z"} == result["position"].keys()


def test_output_values_are_floats():
    result = make().update(FLAT, ZERO)
    assert isinstance(result["angles"]["roll"],  float)
    assert isinstance(result["angles"]["pitch"], float)
    assert isinstance(result["position"]["x"],   float)


# ---------------------------------------------------------------------------
# Stationary on flat surface
# ---------------------------------------------------------------------------

def test_flat_roll_converges_to_zero():
    f = make()
    result = run(f, FLAT, ZERO, 100)
    assert abs(result["angles"]["roll"]) < 1.0


def test_flat_pitch_converges_to_zero():
    f = make()
    result = run(f, FLAT, ZERO, 100)
    assert abs(result["angles"]["pitch"]) < 1.0


# ---------------------------------------------------------------------------
# Known tilt angles
# ---------------------------------------------------------------------------

def test_roll_45_degrees():
    """Device tilted 45° around X: ay=g*sin45, az=g*cos45."""
    tilted = {"x": 0.0, "y": G*math.sin(math.radians(45)), "z": G*math.cos(math.radians(45))}
    result = run(make(), tilted, ZERO, 200)
    assert 40.0 < result["angles"]["roll"] < 50.0


def test_pitch_30_degrees():
    """Device tilted 30° nose-up: ax=-g*sin30, az=g*cos30."""
    tilted = {"x": -G*math.sin(math.radians(30)), "y": 0.0, "z": G*math.cos(math.radians(30))}
    result = run(make(), tilted, ZERO, 200)
    assert 25.0 < result["angles"]["pitch"] < 35.0


def test_negative_roll():
    tilted = {"x": 0.0, "y": -G*math.sin(math.radians(20)), "z": G*math.cos(math.radians(20))}
    result = run(make(), tilted, ZERO, 200)
    assert -25.0 < result["angles"]["roll"] < -15.0


# ---------------------------------------------------------------------------
# Gyroscope integration
# ---------------------------------------------------------------------------

def test_positive_gyro_x_increases_roll():
    f = make()
    f.update(FLAT, ZERO)  # initialise
    before = f.roll
    f.update(FLAT, {"x": 10.0, "y": 0.0, "z": 0.0})
    assert f.roll > before


def test_positive_gyro_y_increases_pitch():
    f = make()
    f.update(FLAT, ZERO)
    before = f.pitch
    f.update(FLAT, {"x": 0.0, "y": 10.0, "z": 0.0})
    assert f.pitch > before


# ---------------------------------------------------------------------------
# Position (dead-reckoning)
# ---------------------------------------------------------------------------

def test_stationary_position_near_zero():
    """No linear motion → position should stay very small."""
    result = run(make(), FLAT, ZERO, 50)
    assert abs(result["position"]["x"]) < 0.05
    assert abs(result["position"]["y"]) < 0.05


def test_horizontal_accel_moves_position():
    """Extra 1 m/s² on X axis should move position in X."""
    f = make()
    moving = {"x": 1.0, "y": 0.0, "z": G}  # gravity + horizontal push
    for _ in range(20):
        f.update(moving, ZERO)
    assert f._pos[0] != 0.0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_clears_position():
    f = make()
    moving = {"x": 1.0, "y": 0.0, "z": G}
    run(f, moving, ZERO, 30)
    f.reset_position()
    result = f.update(FLAT, ZERO)
    assert abs(result["position"]["x"]) < 0.05


def test_reset_clears_velocity():
    f = make()
    run(f, {"x": 2.0, "y": 0.0, "z": G}, ZERO, 20)
    f.reset_position()
    assert f._vel == [0.0, 0.0, 0.0]


def test_reset_does_not_change_angles():
    f = make()
    tilted = {"x": -G*math.sin(math.radians(30)), "y": 0.0, "z": G*math.cos(math.radians(30))}
    run(f, tilted, ZERO, 100)
    pitch_before = f.pitch
    f.reset_position()
    assert f.pitch == pitch_before
