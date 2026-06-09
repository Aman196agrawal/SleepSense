"""
Pattern engine: analyses stored session + lifestyle data to produce
specific, data-driven insights instead of random templates.
"""
from collections import Counter
from typing import List
from app.models import SleepSession, LifestyleLog


def _format_hour_range(hour: int) -> str:
    """Format a 24-hour clock hour as a human-readable AM/PM range.

    Examples: 0 -> "12–1 AM", 12 -> "12–1 PM", 23 -> "11 PM–12 AM".
    """
    hour = hour % 24
    next_hour = (hour + 1) % 24

    def _h12(h: int) -> int:
        return 12 if h % 12 == 0 else h % 12

    def _suffix(h: int) -> str:
        return "AM" if h < 12 else "PM"

    if _suffix(hour) == _suffix(next_hour):
        return f"{_h12(hour)}–{_h12(next_hour)} {_suffix(hour)}"
    return f"{_h12(hour)} {_suffix(hour)}–{_h12(next_hour)} {_suffix(next_hour)}"


def generate_pattern_insights(
    user_id: str,
    sessions: List[SleepSession],
    lifestyle_logs: List[LifestyleLog],
) -> List[dict]:
    if not sessions:
        return []

    insights: List[dict] = []
    by_date = {s.started_at.strftime("%Y-%m-%d"): s for s in sessions if s.started_at}
    scores = [s.sleep_quality_score for s in sessions if s.sleep_quality_score is not None]

    # ── 1. Consecutive bad nights ────────────────────────────────────────────
    streak = 0
    for s in sessions:                          # sessions already newest-first
        if s.sleep_quality_score and s.sleep_quality_score < 60:
            streak += 1
        else:
            break
    if streak >= 3:
        avg_bad = round(sum(s.sleep_quality_score for s in sessions[:streak]
                            if s.sleep_quality_score) / streak, 1)
        insights.append({
            "type": "warning",
            "title": f"{streak} consecutive below-average nights",
            "body": (f"Your sleep score has been under 60 for {streak} nights in a row "
                     f"(avg {avg_bad}). Consider reviewing your sleep environment or "
                     f"consulting a specialist."),
            "priority": 9,
        })

    # ── 2. Week-over-week trend ──────────────────────────────────────────────
    if len(scores) >= 7:
        new_avg = sum(scores[:7]) / 7
        if len(scores) >= 14:
            old_avg = sum(scores[7:14]) / 7
        else:
            old_avg = sum(scores[7:]) / len(scores[7:]) if scores[7:] else new_avg
        change = new_avg - old_avg
        if change >= 5:
            insights.append({
                "type": "achievement",
                "title": f"Sleep improving — up {change:.0f} pts this week",
                "body": (f"Your 7-night average is {new_avg:.0f}, up from {old_avg:.0f} "
                         f"the week before. Whatever you changed — keep it up!"),
                "priority": 7,
            })
        elif change <= -5:
            insights.append({
                "type": "warning",
                "title": f"Sleep declining — down {abs(change):.0f} pts this week",
                "body": (f"Your 7-night average is {new_avg:.0f}, down from {old_avg:.0f}. "
                         f"Review your bedtime routine and stress levels."),
                "priority": 8,
            })

    # ── 3. Peak snoring time pattern ─────────────────────────────────────────
    recent = sessions[:5]
    peak_hours = [s.peak_snoring_hour for s in recent if s.peak_snoring_hour is not None]
    if len(peak_hours) >= 3:
        top_hour, count = Counter(peak_hours).most_common(1)[0]
        if count >= 3:
            hour_str = _format_hour_range(top_hour)
            insights.append({
                "type": "tip",
                "title": f"Snoring consistently peaks at {hour_str}",
                "body": (f"Your snoring intensifies around {hour_str} on {count} of your "
                         f"last {len(recent)} nights — likely during REM sleep. "
                         f"Try limiting screen time and alcohol before bed."),
                "priority": 6,
            })

    # ── 4. Short sleep duration warning ─────────────────────────────────────
    if len(recent) >= 3:
        durations = [s.duration_minutes for s in recent if s.duration_minutes]
        if durations:
            avg_dur = sum(durations) / len(durations)
            short_count = sum(1 for d in durations if d < 360)
            if short_count >= 3:
                h, m = divmod(int(avg_dur), 60)
                insights.append({
                    "type": "warning",
                    "title": f"Averaging only {h}h {m}m of sleep",
                    "body": (f"Adults need 7–9 hours. Your recent average of {h}h {m}m "
                             f"may compound snoring. Try shifting your bedtime 30 min earlier."),
                    "priority": 7,
                })

    # ── 5. Recording streak achievement ─────────────────────────────────────
    if len(sessions) >= 7:
        dates = sorted(
            {s.started_at.date() for s in sessions[:14] if s.started_at},
            reverse=True
        )
        streak_days = 1
        for i in range(1, len(dates)):
            if (dates[i - 1] - dates[i]).days == 1:
                streak_days += 1
            else:
                break
        if streak_days >= 7:
            insights.append({
                "type": "achievement",
                "title": f"{streak_days}-night recording streak!",
                "body": (f"Great consistency! {streak_days} nights of data lets SleepSense "
                         f"identify meaningful patterns and give you more accurate insights."),
                "priority": 5,
            })

    # ── 6. Best day-of-week pattern ──────────────────────────────────────────
    if len(sessions) >= 14:
        day_scores: dict = {}
        for s in sessions[:28]:
            if s.sleep_quality_score and s.started_at:
                day = s.started_at.strftime("%A")
                day_scores.setdefault(day, []).append(s.sleep_quality_score)
        day_avgs = {d: sum(v) / len(v) for d, v in day_scores.items() if len(v) >= 2}
        if len(day_avgs) >= 2:
            best = max(day_avgs, key=day_avgs.get)
            worst = min(day_avgs, key=day_avgs.get)
            if day_avgs[best] - day_avgs[worst] >= 10:
                insights.append({
                    "type": "tip",
                    "title": f"{best}s are your best sleep nights",
                    "body": (f"You average {day_avgs[best]:.0f} on {best}s vs "
                             f"{day_avgs[worst]:.0f} on {worst}s. "
                             f"Think about what you do differently on {best}s."),
                    "priority": 4,
                })

    # ── 7. Lifestyle correlations ────────────────────────────────────────────
    if lifestyle_logs:
        log_by_date = {log.logged_date: log for log in lifestyle_logs}

        # Alcohol impact
        alc_scores, clean_scores = [], []
        for s in sessions:
            if not s.started_at or s.sleep_quality_score is None:
                continue
            d = s.started_at.strftime("%Y-%m-%d")
            log = log_by_date.get(d)
            if log:
                if log.alcohol_units > 0:
                    alc_scores.append(s.sleep_quality_score)
                else:
                    clean_scores.append(s.sleep_quality_score)

        if len(alc_scores) >= 3 and len(clean_scores) >= 3:
            alc_avg = sum(alc_scores) / len(alc_scores)
            clean_avg = sum(clean_scores) / len(clean_scores)
            diff = clean_avg - alc_avg
            if diff >= 5:
                insights.append({
                    "type": "tip",
                    "title": f"Alcohol costs you {diff:.0f} sleep quality points",
                    "body": (f"On nights you log alcohol your score averages {alc_avg:.0f}, "
                             f"vs {clean_avg:.0f} on alcohol-free nights. "
                             f"Try stopping drinks 3 hours before bed."),
                    "priority": 8,
                })

        # Exercise benefit
        ex_scores, rest_scores = [], []
        for s in sessions:
            if not s.started_at or s.sleep_quality_score is None:
                continue
            d = s.started_at.strftime("%Y-%m-%d")
            log = log_by_date.get(d)
            if log:
                if log.exercise_minutes >= 20:
                    ex_scores.append(s.sleep_quality_score)
                else:
                    rest_scores.append(s.sleep_quality_score)

        if len(ex_scores) >= 3 and len(rest_scores) >= 3:
            ex_avg = sum(ex_scores) / len(ex_scores)
            rest_avg = sum(rest_scores) / len(rest_scores)
            diff = ex_avg - rest_avg
            if diff >= 5:
                insights.append({
                    "type": "tip",
                    "title": f"Exercise boosts your sleep by {diff:.0f} points",
                    "body": (f"On days you exercise your score averages {ex_avg:.0f}, "
                             f"vs {rest_avg:.0f} on rest days. "
                             f"Even 20–30 min of walking makes a measurable difference."),
                    "priority": 7,
                })

        # High stress impact
        hi_stress = [log_by_date[d] for d in log_by_date if log_by_date[d].stress_level >= 4]
        lo_stress = [log_by_date[d] for d in log_by_date if log_by_date[d].stress_level <= 2]

        def _scores_for_logs(logs_list):
            result = []
            for log in logs_list:
                s = by_date.get(log.logged_date)
                if s and s.sleep_quality_score is not None:
                    result.append(s.sleep_quality_score)
            return result

        hi_s = _scores_for_logs(hi_stress)
        lo_s = _scores_for_logs(lo_stress)
        if len(hi_s) >= 3 and len(lo_s) >= 3:
            diff = sum(lo_s) / len(lo_s) - sum(hi_s) / len(hi_s)
            if diff >= 5:
                insights.append({
                    "type": "tip",
                    "title": f"High-stress days hurt sleep by {diff:.0f} points",
                    "body": (f"Your sleep score drops significantly on high-stress days. "
                             f"Try a 10-minute wind-down routine: deep breathing, "
                             f"no screens, and journaling before bed."),
                    "priority": 6,
                })

    insights.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return insights
