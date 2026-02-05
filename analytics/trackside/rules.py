"""Compatibility wrapper for legacy rule-based insight generation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from analytics.trackside.signals import generate_signals
from analytics.trackside.synthesis import synthesize_insights


def generate_insights(
    segments: Iterable[Dict[str, Any]],
    comparison_label: str,
) -> List[Dict[str, Any]]:
    """Generate synthesized insights from extracted signals."""
    signals = generate_signals(segments, comparison_label=comparison_label)
    return synthesize_insights(segments, signals, comparison_label=comparison_label)
