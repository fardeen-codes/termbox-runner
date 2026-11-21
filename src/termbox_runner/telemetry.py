"""System resource telemetry, performance profiling, and metric calculation helpers."""

import os
from typing import Tuple


def get_system_load_average() -> Tuple[float, float, float]:
    """Return 1-minute, 5-minute, and 15-minute system load averages."""
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return (0.0, 0.0, 0.0)
