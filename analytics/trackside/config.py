"""Configuration surfaces for trackside analytics tuning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrendFilterConfig:
    """Tunable thresholds for line trend detection and filtering."""

    iqr_k: float = 1.8
    min_samples: int = 4
    strong_min_samples: int = 7
    line_stddev_cap_m: float = 6.0
    speed_noise_cap_kmh: float = 2.8
    cluster_apex_threshold_m: float = 6.0
    related_sessions_max: int = 8


TREND_FILTERS = TrendFilterConfig()
