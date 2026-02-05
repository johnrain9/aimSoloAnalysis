"""Aligned time/distance series container for analytics.

RunData is the standardized entry point for analytics modules. All arrays
must be aligned by index (same length as time_s). Dynamic channels store
optional arrays by channel name.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RunData:
    time_s: List[Optional[float]]
    distance_m: Optional[List[Optional[float]]]
    lat: Optional[List[Optional[float]]]
    lon: Optional[List[Optional[float]]]
    speed: Optional[List[Optional[float]]]
    channels: Dict[str, List[Optional[float]]] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)

    def validate_lengths(self) -> None:
        """Validate that all series align to time_s length."""
        expected = len(self.time_s)
        for series in [self.distance_m, self.lat, self.lon, self.speed]:
            if series is None:
                continue
            if len(series) != expected:
                raise ValueError("RunData series length mismatch")
        for name, series in self.channels.items():
            if len(series) != expected:
                raise ValueError(f"RunData channel length mismatch: {name}")
