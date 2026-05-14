"""
Rule engine for FR-INS-001.

Five rules evaluated in priority order:
  1. POSITIONAL_SNORING  (priority 8) — back-sleeper + high snore ratio
  2. ALCOHOL_CORRELATION (priority 7) — alcohol logged + high snore intensity
  3. CHRONIC_SNORING     (priority 9) — 5+ consecutive poor nights (highest priority)
  4. IMPROVEMENT_TREND   (priority 6) — score improved > 15 pts vs 7-night average
  5. SLEEP_DEBT          (priority 7) — < 6 h on 3+ of last 5 nights

Returns at most 3 insights sorted by priority (highest first).
"""
from typing import List, Optional


def evaluate_rules(
    *,
    sleep_quality_score: float,
    snore_ratio: float,
    avg_snore_intensity: float = 0.0,
    duration_minutes: int = 480,
    recent_scores: Optional[List[float]] = None,
    recent_durations: Optional[List[int]] = None,
    alcohol_units_today: float = 0.0,
    sleep_position: Optional[str] = None,
) -> List[dict]:
    """
    Evaluate all rules against the current session + recent history.

    Parameters
    ----------
    sleep_quality_score  : 0-100 score for the current session (higher = better)
    snore_ratio          : fraction of current session spent snoring (0.0-1.0)
    avg_snore_intensity  : 0-100 average intensity during snoring windows
    duration_minutes     : sleep duration for current session
    recent_scores        : sleep quality scores for previous sessions, most-recent first
    recent_durations     : sleep durations (minutes) for previous sessions, most-recent first
    alcohol_units_today  : number of alcohol units logged for this session's date
    sleep_position       : declared sleep position ("back" | "side" | "stomach" | None)

    Returns
    -------
    List of up to 3 insight dicts (sorted by priority desc), each with keys:
      insight_type, priority, title, body, action_url, rule_name
    """
    recent_scores    = recent_scores    or []
    recent_durations = recent_durations or []

    candidates: List[dict] = []

    # ── Rule 1: POSITIONAL_SNORING ────────────────────────────────────────────
    if sleep_position == "back" and snore_ratio >= 0.5:
        candidates.append({
            "rule_name":    "POSITIONAL_SNORING",
            "insight_type": "tip",
            "priority":     8,
            "title":        "Back-sleeping is worsening your snoring",
            "body": (
                f"Snoring occupied {snore_ratio * 100:.0f}% of your night. "
                "Side-sleeping keeps your airway open and can reduce snoring by up to 50%. "
                "Try placing a pillow behind your back to stay on your side."
            ),
            "action_url": "sleepsense://tips/positional-snoring",
        })

    # ── Rule 2: ALCOHOL_CORRELATION ───────────────────────────────────────────
    if alcohol_units_today > 0 and avg_snore_intensity >= 70:
        candidates.append({
            "rule_name":    "ALCOHOL_CORRELATION",
            "insight_type": "tip",
            "priority":     7,
            "title":        "Alcohol amplified your snoring tonight",
            "body": (
                f"Your snore intensity was {avg_snore_intensity:.0f}/100 on a night you "
                f"logged {alcohol_units_today:.0f} drink(s). Alcohol relaxes throat muscles — "
                "try stopping drinks 3 hours before bed."
            ),
            "action_url": "sleepsense://tips/alcohol-snoring",
        })

    # ── Rule 3: CHRONIC_SNORING ───────────────────────────────────────────────
    # Fires when current sleep_quality_score < 50 AND at least 4 of the last 4
    # recorded scores are also < 50 (= 5 consecutive poor nights total).
    if sleep_quality_score < 50 and len(recent_scores) >= 4:
        consecutive_bad = sum(1 for s in recent_scores[:4] if s < 50)
        if consecutive_bad >= 4:
            candidates.append({
                "rule_name":    "CHRONIC_SNORING",
                "insight_type": "warning",
                "priority":     9,
                "title":        "5 consecutive nights of poor sleep detected",
                "body": (
                    "Your sleep score has been below 50 for 5 nights in a row. "
                    "Chronic snoring at this level may indicate obstructive sleep apnea. "
                    "Consider consulting a sleep specialist."
                ),
                "action_url": "sleepsense://tips/sleep-specialist",
            })

    # ── Rule 4: IMPROVEMENT_TREND ─────────────────────────────────────────────
    if len(recent_scores) >= 7:
        seven_night_avg = sum(recent_scores[:7]) / 7
        delta = sleep_quality_score - seven_night_avg
        if delta > 15:
            candidates.append({
                "rule_name":    "IMPROVEMENT_TREND",
                "insight_type": "achievement",
                "priority":     6,
                "title":        f"Sleep improving — up {delta:.0f} pts vs your 7-night average",
                "body": (
                    f"Tonight's score ({sleep_quality_score:.0f}) is {delta:.0f} points above "
                    f"your 7-night average ({seven_night_avg:.0f}). "
                    "Whatever you changed — keep it up!"
                ),
                "action_url": "sleepsense://tips/sleep-improvement",
            })

    # ── Rule 5: SLEEP_DEBT ────────────────────────────────────────────────────
    if len(recent_durations) >= 5:
        short_nights = sum(1 for d in recent_durations[:5] if d < 360)   # < 6 hours
        if short_nights >= 3:
            candidates.append({
                "rule_name":    "SLEEP_DEBT",
                "insight_type": "warning",
                "priority":     7,
                "title":        "Sleep debt building — averaging under 6 hours",
                "body": (
                    f"{short_nights} of your last 5 nights were under 6 hours. "
                    "Adults need 7–9 hours. Sleep debt amplifies snoring and impairs recovery. "
                    "Try shifting your bedtime 30 minutes earlier tonight."
                ),
                "action_url": "sleepsense://tips/sleep-hygiene",
            })

    candidates.sort(key=lambda x: x["priority"], reverse=True)
    return candidates[:3]
