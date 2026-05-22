import pytest

from logic.answer_utils import (
    format_duration_for_display,
    parse_duration,
)
from logic.grader import grade_attempt


# ── parse_duration ─────────────────────────────────────────────────────────────

class TestParseDuration:
    def test_plain_number_treated_as_seconds(self):
        assert parse_duration(90) == 90.0
        assert parse_duration(90.0) == 90.0
        assert parse_duration("90") == 90.0

    def test_plain_number_string_with_comma(self):
        assert parse_duration("1,5") == 1.5

    def test_seconds_aliases(self):
        for alias in ("s", "sec", "secs", "second", "seconds", "sekund", "sekunder"):
            assert parse_duration(f"5{alias}") == 5.0, alias
            assert parse_duration(f"5 {alias}") == 5.0, alias

    def test_minutes_aliases(self):
        for alias in ("m", "min", "mins", "minute", "minutes", "minut", "minuter"):
            assert parse_duration(f"3{alias}") == 180.0, alias
            assert parse_duration(f"3 {alias}") == 180.0, alias

    def test_hours_aliases(self):
        for alias in ("h", "hr", "hrs", "hour", "hours", "timme", "timmar", "tim"):
            assert parse_duration(f"2{alias}") == 7200.0, alias
            assert parse_duration(f"2 {alias}") == 7200.0, alias

    def test_days_aliases(self):
        for alias in ("d", "day", "days", "dag", "dagar"):
            assert parse_duration(f"1{alias}") == 86400.0, alias
            assert parse_duration(f"1 {alias}") == 86400.0, alias

    def test_compound_with_spaces(self):
        assert parse_duration("1h 20min") == 4800.0
        assert parse_duration("1 hour 20 minutes") == 4800.0
        assert parse_duration("1d 2h 3min 4s") == 86400 + 7200 + 180 + 4

    def test_compound_without_spaces(self):
        assert parse_duration("1h20min") == 4800.0
        assert parse_duration("1h20min30s") == 4800.0 + 30

    def test_swedish_compound(self):
        assert parse_duration("1 timme 20 minuter") == 4800.0
        assert parse_duration("2 dagar 3 timmar") == 2 * 86400 + 3 * 3600

    def test_fractional_hours(self):
        assert parse_duration("1.5h") == 5400.0
        assert parse_duration("0.5 min") == 30.0

    def test_none_and_bool_return_none(self):
        assert parse_duration(None) is None
        assert parse_duration(True) is None
        assert parse_duration(False) is None

    def test_empty_string_returns_none(self):
        assert parse_duration("") is None
        assert parse_duration("   ") is None

    def test_unparseable_string_returns_none(self):
        assert parse_duration("hello world") is None
        assert parse_duration("abc") is None

    def test_unit_not_matched_inside_other_units(self):
        # "mg" should not parse "m" as minutes and leave "g" dangling.
        result = parse_duration("20mg")
        assert result is None

    def test_zero_duration(self):
        assert parse_duration("0s") == 0.0
        assert parse_duration(0) == 0.0

    def test_large_duration(self):
        # 365 days
        assert parse_duration("365d") == 365 * 86400.0


# ── format_duration_for_display ───────────────────────────────────────────────

class TestFormatDurationForDisplay:
    def test_zero_seconds(self):
        assert format_duration_for_display(0) == "0s"

    def test_seconds_only(self):
        assert format_duration_for_display(45) == "45s"

    def test_minutes_only(self):
        assert format_duration_for_display(120) == "2min"

    def test_hours_only(self):
        assert format_duration_for_display(3600) == "1h"

    def test_days_only(self):
        assert format_duration_for_display(86400) == "1d"

    def test_hours_and_minutes(self):
        assert format_duration_for_display(4800) == "1h 20min"

    def test_days_hours_minutes_seconds(self):
        total = 86400 + 7200 + 180 + 4
        assert format_duration_for_display(total) == "1d 2h 3min 4s"

    def test_minutes_and_seconds(self):
        assert format_duration_for_display(90) == "1min 30s"

    def test_none_returns_none(self):
        assert format_duration_for_display(None) is None

    def test_float_input(self):
        assert format_duration_for_display(3600.0) == "1h"

    def test_whole_second_strips_decimal(self):
        assert format_duration_for_display(61.0) == "1min 1s"


# ── grader integration ─────────────────────────────────────────────────────────

class TestGraderDuration:
    def _snapshot(self, correct_answer, tolerance=0, tolerance_percent=None):
        return {
            "correct_answer": correct_answer,
            "tolerance": tolerance,
            "tolerance_percent": tolerance_percent,
            "is_scored": True,
            "answer_type": "duration",
        }

    def test_exact_match(self):
        result = grade_attempt(
            {"q1": self._snapshot(4800)},
            {"q1": "1h 20min"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_within_tolerance(self):
        result = grade_attempt(
            {"q1": self._snapshot(4800, tolerance=60)},
            {"q1": "1h 19min"},  # 4740s, diff = 60
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_outside_tolerance(self):
        result = grade_attempt(
            {"q1": self._snapshot(4800, tolerance=30)},
            {"q1": "1h 19min"},  # diff = 60, tolerance = 30
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_swedish_input(self):
        result = grade_attempt(
            {"q1": self._snapshot(3600)},
            {"q1": "1 timme"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_compact_no_spaces(self):
        result = grade_attempt(
            {"q1": self._snapshot(4830)},
            {"q1": "1h20min30s"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_plain_number_as_seconds(self):
        result = grade_attempt(
            {"q1": self._snapshot(90)},
            {"q1": "90"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_wrong_answer(self):
        result = grade_attempt(
            {"q1": self._snapshot(3600)},
            {"q1": "30min"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_unparseable_user_answer(self):
        result = grade_attempt(
            {"q1": self._snapshot(3600)},
            {"q1": "garbage"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_percent_tolerance(self):
        # 10% of 3600 = 360s tolerance → 3300s user answer should pass
        result = grade_attempt(
            {"q1": self._snapshot(3600, tolerance_percent=10)},
            {"q1": "55min"},  # 3300s
        )
        assert result.question_snapshots["q1"]["is_correct"] is True


class TestGraderDurationRoundToUnit:
    def _snapshot(self, correct_answer, round_to_unit, tolerance=0):
        return {
            "correct_answer": correct_answer,
            "tolerance": tolerance,
            "tolerance_percent": None,
            "is_scored": True,
            "answer_type": "duration",
            "round_to_unit": round_to_unit,
        }

    def test_round_to_min_exact(self):
        # 4020s = 1h 7min; user answers "1h 7min" → exact match after rounding
        result = grade_attempt(
            {"q1": self._snapshot(4020, "min")},
            {"q1": "1h 7min"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_round_to_min_close_enough(self):
        # Correct = 4010s (rounds to 4020 = 67min); user says "1h 6min 40s" = 4000s (rounds to 4020)
        result = grade_attempt(
            {"q1": self._snapshot(4010, "min")},
            {"q1": "1h 6min 40s"},  # 4000s → rounds to 67min = 4020s
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_round_to_min_different_minutes(self):
        # Correct = 4020s (67min); user says "1h 8min" = 4080s (rounds to 68min) → wrong
        result = grade_attempt(
            {"q1": self._snapshot(4020, "min")},
            {"q1": "1h 8min"},  # 4080s → rounds to 4080 (68min) ≠ 4020
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_round_to_hour(self):
        # Correct = 37440s (10h 24min); rounds to 10h = 36000s; user says "10h" → correct
        result = grade_attempt(
            {"q1": self._snapshot(37440, "h")},
            {"q1": "10h"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_round_to_hour_wrong(self):
        # Correct = 37440s (10h 24min); rounds to 10h = 36000
        # User says "10h 31min" = 37860s; round(10.517h) = 11h = 39600 → wrong
        result = grade_attempt(
            {"q1": self._snapshot(37440, "h")},
            {"q1": "10h 31min"},  # 37860s → rounds to 11h = 39600
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_round_to_day(self):
        # Correct = 88200s (24h 30min); rounds to 1d = 86400s; user says "1d" → correct
        result = grade_attempt(
            {"q1": self._snapshot(88200, "d")},
            {"q1": "1d"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_no_round_to_unit_still_works(self):
        # round_to_unit=None should behave like normal duration grading
        result = grade_attempt(
            {"q1": self._snapshot(3600, None)},
            {"q1": "1h"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True


class TestGraderTimeOfDayRoundToUnit:
    def _snapshot(self, correct_answer, round_to_unit, tolerance=0):
        return {
            "correct_answer": correct_answer,
            "tolerance": tolerance,
            "tolerance_percent": None,
            "is_scored": True,
            "answer_type": "time_of_day",
            "round_to_unit": round_to_unit,
        }

    def test_round_to_hour(self):
        # Correct = 630 min (10:30); rounds to 600 (10:00); user says "10:00" = 600 → correct
        result = grade_attempt(
            {"q1": self._snapshot(630, "h")},
            {"q1": "10:00"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True

    def test_round_to_hour_wrong(self):
        # Correct = 630 (10:30 → round(10.5h)=10h → 600 minutes = 10:00)
        # User says "10:59" = 659 min; round(659/60)=round(10.98)=11 → 11h = 660 ≠ 600 → wrong
        result = grade_attempt(
            {"q1": self._snapshot(630, "h")},
            {"q1": "10:59"},  # 659 min → rounds to 11:00 = 660 ≠ 600
        )
        assert result.question_snapshots["q1"]["is_correct"] is False

    def test_round_to_min_no_change(self):
        # time_of_day already in minutes; round_to_unit="min" = round to 1 minute (no change)
        result = grade_attempt(
            {"q1": self._snapshot(637, "min")},
            {"q1": "10:37"},
        )
        assert result.question_snapshots["q1"]["is_correct"] is True
