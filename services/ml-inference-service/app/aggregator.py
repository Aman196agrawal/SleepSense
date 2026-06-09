"""
Chunk-level result aggregation (FR-ML-004).
Converts per-window classification + intensity into a single chunk summary.
"""
from typing import List


def aggregate(window_results: List[dict]) -> dict:
    """
    Aggregate per-window results into a chunk-level summary.

    Parameters
    ----------
    window_results : list of dicts with keys:
        start_sec, end_sec, class, confidence, intensity

    Returns
    -------
    {
        snore_windows : int,
        total_windows : int,
        snore_ratio   : float  [0, 1],
        avg_intensity : float  [0, 100]  — average over snoring windows only,
        max_intensity : float  [0, 100]  — max across all windows,
        per_event     : list[dict]       — the input list unchanged,
    }
    """
    total = len(window_results)
    if total == 0:
        return {
            "snore_windows": 0,
            "total_windows": 0,
            "snore_ratio":   0.0,
            "avg_intensity": 0.0,
            "max_intensity": 0.0,
            "per_event":     [],
        }

    snoring = [r for r in window_results if r["class"] == "snoring"]

    snore_ratio   = round(len(snoring) / total, 3)
    avg_intensity = round(sum(r["intensity"] for r in snoring) / len(snoring), 1) if snoring else 0.0
    max_intensity = round(max((r["intensity"] for r in window_results), default=0.0), 1)

    return {
        "snore_windows": len(snoring),
        "total_windows": total,
        "snore_ratio":   snore_ratio,
        "avg_intensity": avg_intensity,
        "max_intensity": max_intensity,
        "per_event":     window_results,
    }
