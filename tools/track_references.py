"""Track reference templates for corner detection.

Each template defines the corners for a track/direction combo using
distance-from-start positions from a known reference lap. When analyzing
any lap, we match sample distances to these ranges to label corners.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from domain.run_data import RunData


MPS_TO_MPH = 2.23694
M_TO_FT = 3.28084

@dataclass
class TrackCorner:
    name: str
    direction: str  # "L" or "R"
    entry_dist_m: float
    apex_dist_m: float
    exit_dist_m: float
    notes: str = ""


@dataclass
class TrackReference:
    track_name: str
    track_direction: str  # "CW" or "CCW"
    lap_distance_m: float
    corners: List[TrackCorner]

    def corner_at_distance(self, dist_m: float) -> Optional[TrackCorner]:
        for c in self.corners:
            if c.entry_dist_m <= dist_m <= c.exit_dist_m:
                return c
        return None

    def corner_phase_at_distance(self, dist_m: float) -> Tuple[Optional[TrackCorner], str]:
        for c in self.corners:
            if c.entry_dist_m <= dist_m <= c.exit_dist_m:
                if dist_m < c.apex_dist_m - 5:
                    phase = "entry"
                elif dist_m > c.apex_dist_m + 5:
                    phase = "exit"
                else:
                    phase = "apex"
                return c, phase
        return None, ""


def build_hpr_full_ccw() -> TrackReference:
    """HPR Full Course, CCW direction.

    Reference: session 87.csv lap 2 (1:55.37), Paul on R6 Race, Sept 29 2024.
    Lap start distance: 4044m from session start.
    All distances below are relative to lap start (S/F line).

    Turn numbering matches HPR official full-course map.
    T9 encompasses both 9a and 9b (right kink then left kink).
    """
    # Reference lap 2 start distance from session start
    REF_LAP_START_M = 4044.0

    # These were derived from the heading/speed trace of lap 2:
    #   t=0s   → dist=0m,     heading=102° (S/F line, 116mph)
    #   t=115s → dist=4023m,  heading=102° (back at S/F)
    # Total lap distance ≈ 4023m ≈ 2.50mi (track is listed as 2.55mi)

    corners = [
        # T1: first corner after S/F, left turn
        # Brake from 116mph, min ~61mph, hard lean left
        TrackCorner("T1", "L",
                    entry_dist_m=100,   # ~t=2s, braking starts
                    apex_dist_m=200,    # ~t=5s, min speed
                    exit_dist_m=290,    # ~t=8s, back upright
                    notes="Left, brake from 116 to 61mph"),

        # T2: right hairpin, slowest turn on this section
        # Brake to 45mph, long turning at 15°/0.5s
        TrackCorner("T2", "R",
                    entry_dist_m=325,   # ~t=9s, braking into right
                    apex_dist_m=405,    # ~t=12.5s, slowest point
                    exit_dist_m=530,    # ~t=17s, gas out
                    notes="Right hairpin, min 45mph"),

        # T3: right sweeper under power, onto back straight
        # Constant lean, accelerating 71→108mph
        TrackCorner("T3", "R",
                    entry_dist_m=560,   # ~t=18s
                    apex_dist_m=660,    # ~t=21s
                    exit_dist_m=830,    # ~t=25s, straightening
                    notes="Right sweeper, accel 71→108mph"),

        # BACK STRAIGHT: 830m to 1300m, 112→140mph

        # T4: fast right turn after back straight
        # Hard brake from 140mph, right with hard lean
        TrackCorner("T4", "R",
                    entry_dist_m=1325,  # ~t=33.5s, braking starts
                    apex_dist_m=1490,   # ~t=37s
                    exit_dist_m=1570,   # ~t=39.5s
                    notes="Right, brake from 140 to 80mph"),

        # T5: left turn
        # Brake to 51mph, hard left
        TrackCorner("T5", "L",
                    entry_dist_m=1590,  # ~t=40s
                    apex_dist_m=1680,   # ~t=42.5s
                    exit_dist_m=1740,   # ~t=45.5s, start of accel
                    notes="Left, brake to 51mph"),

        # T6: right hairpin (Danny's Lesson)
        # Short accel then HARD brake to 37mph, big right turn
        TrackCorner("T6", "R",
                    entry_dist_m=1845,  # ~t=48s, braking starts
                    apex_dist_m=1950,   # ~t=52s, min speed 37mph
                    exit_dist_m=2035,   # ~t=56s, gas out
                    notes="Right hairpin, hard brake to 37mph"),

        # T7: fast right sweeper
        # Brake from 105 to 78mph, steady turn at 9°/0.5s
        TrackCorner("T7", "R",
                    entry_dist_m=2200,  # ~t=60s
                    apex_dist_m=2315,   # ~t=63s
                    exit_dist_m=2440,   # ~t=66.5s
                    notes="Right sweeper, 78mph min"),

        # T8: left hairpin (To Hell on a Bobsled)
        # Brake from 91 to 32mph, biggest heading change
        TrackCorner("T8", "L",
                    entry_dist_m=2460,  # ~t=67s
                    apex_dist_m=2600,   # ~t=72.5s, min 32mph
                    exit_dist_m=2680,   # ~t=76s
                    notes="Left hairpin, min 32mph"),

        # T9: fast kinks (9a right + 9b left), minimal speed loss
        # 67→95mph, barely slowing
        TrackCorner("T9", "R",  # net direction is roughly right
                    entry_dist_m=2680,  # ~t=76s
                    apex_dist_m=2755,   # ~t=79s, midpoint
                    exit_dist_m=2870,   # ~t=82s
                    notes="Fast kinks 9a(R)+9b(L), 76→95mph"),

        # T10: right turn
        # Brake to 70mph, hard lean right
        TrackCorner("T10", "R",
                    entry_dist_m=2910,  # ~t=82.5s
                    apex_dist_m=2985,   # ~t=85s
                    exit_dist_m=3080,   # ~t=87s
                    notes="Right, brake to 70mph"),

        # T11: big right turn (Ladder to Heaven)
        # Brake to 48mph, long turning
        TrackCorner("T11", "R",
                    entry_dist_m=3120,  # ~t=88s
                    apex_dist_m=3230,   # ~t=92s
                    exit_dist_m=3325,   # ~t=96s
                    notes="Right, brake to 48mph, long turn"),

        # T12: fast left sweeper, no braking
        # 79→100mph, just leaning
        TrackCorner("T12", "L",
                    entry_dist_m=3395,  # ~t=98s
                    apex_dist_m=3450,   # ~t=99.5s
                    exit_dist_m=3520,   # ~t=101s
                    notes="Left sweeper, 85-100mph, no brake"),

        # T13: left turn, hard braking
        # Brake from 100 to 47mph
        TrackCorner("T13", "L",
                    entry_dist_m=3560,  # ~t=101.5s
                    apex_dist_m=3640,   # ~t=104.5s
                    exit_dist_m=3665,   # ~t=106s
                    notes="Left, hard brake to 47mph"),

        # T14: quick right (Prairie Corkscrew)
        TrackCorner("T14", "R",
                    entry_dist_m=3680,  # ~t=106.5s
                    apex_dist_m=3715,   # ~t=107.5s
                    exit_dist_m=3745,   # ~t=108.5s
                    notes="Right, 59→66mph"),

        # T15: left, then hard on gas to front straight
        TrackCorner("T15", "L",
                    entry_dist_m=3755,  # ~t=109s
                    apex_dist_m=3820,   # ~t=110s
                    exit_dist_m=3900,   # ~t=112s
                    notes="Left, then gas to 116mph front straight"),
    ]

    return TrackReference(
        track_name="HPR Full",
        track_direction="CCW",
        lap_distance_m=4023.0,
        corners=corners,
    )


# Registry of known tracks
TRACK_REFERENCES: Dict[str, TrackReference] = {
    "HPR Full:CCW": build_hpr_full_ccw(),
}


def get_reference(track_name: str, direction: str) -> Optional[TrackReference]:
    key = f"{track_name}:{direction}"
    return TRACK_REFERENCES.get(key)


def detect_track(rd_lap: RunData) -> Optional[TrackReference]:
    """Try to auto-detect track from lap distance and turn count.

    For now, just returns HPR Full CCW if lap distance is roughly right.
    """
    if not rd_lap.distance_m:
        return None
    d0 = rd_lap.distance_m[0] or 0
    d_end = rd_lap.distance_m[-1] or 0
    lap_dist = d_end - d0

    # HPR Full is ~4023m
    if 3800 < lap_dist < 4300:
        return TRACK_REFERENCES.get("HPR Full:CCW")

    return None
