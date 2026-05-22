"""Answer parsing and formatting utilities.

Centralises all logic for interpreting and normalising student answers across
the three supported answer types:

- **numeric**:    plain numbers with optional unit strings (e.g. "10.3 mg/g").
- **duration**:   compound time expressions (e.g. "1h 20min", "2d 3h 15s").
  Formula must return total seconds. Supports English and Swedish aliases.
- **time_of_day**: a clock time represented as minutes since midnight.
  Accepted input formats: "17:34", "17.34", "1734", "17 34".

Unit normalisation (``is_known_unit``, ``normalize_unit``) uses a Redis-backed
alias map populated from the Unit / UnitAlias ORM models, with a 5-minute TTL.
"""
import json
import re
from decimal import Decimal
from math import isfinite
from pathlib import Path


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

def _coerce_number(value):
    """Convert supported numeric values to float."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip().replace(",", ".")
        try:
            return float(stripped)
        except ValueError:
            pass
    raise ValueError(f"Unsupported numeric value: {value!r}")


def _to_int_if_whole(value: float):
    """Return int if value has no fractional part, else return as-is."""
    int_val = int(value)
    return int_val if value == int_val else value


def parse_numeric_answer(value):
    """Parse a plain numeric value; return float or None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if isfinite(parsed) else None
    if isinstance(value, str):
        stripped = value.strip().replace(",", ".")
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return parsed if isfinite(parsed) else None
    return None


# Matches a number (int or float, with optional sign/scientific notation)
# followed by an optional unit string.
# e.g. "10.3 mg/g" -> ("10.3", "mg/g"), "42" -> ("42", "")
_NUMERIC_UNIT_RE = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)\s*(.*?)\s*$"
)


def parse_numeric_with_unit(value):
    """Return (number: float | None, unit: str) for a string that may contain a unit."""
    if isinstance(value, (int, float)):
        parsed = float(value) if isfinite(float(value)) else None
        return parsed, ""
    if not isinstance(value, str) or not value.strip():
        return None, ""
    m = _NUMERIC_UNIT_RE.match(value.strip())
    if not m:
        return None, value.strip()
    num_str, unit = m.group(1).replace(",", "."), m.group(2)
    try:
        parsed = float(num_str)
    except ValueError:
        return None, unit
    return (parsed if isfinite(parsed) else None), unit


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

# Each entry: (seconds_per_unit, [aliases, longest-first])
_DURATION_UNIT_SECONDS = [
    (86400, ['dagar', 'days', 'dag', 'day', 'd']),
    (3600,  ['timmar', 'hours', 'timme', 'hour', 'tim', 'hrs', 'hr', 'h']),
    (60,    ['minutes', 'minuter', 'minute', 'minut', 'mins', 'min', 'm']),
    (1,     ['seconds', 'sekunder', 'second', 'sekund', 'secs', 'sec', 's']),
]

_DURATION_ALIAS_TO_SECONDS: dict[str, int] = {
    alias: mult
    for mult, aliases in _DURATION_UNIT_SECONDS
    for alias in aliases
}

# Sorted longest-first so e.g. "minutes" is tried before "min" before "m".
_DURATION_ALIASES_SORTED = sorted(_DURATION_ALIAS_TO_SECONDS, key=len, reverse=True)

# Matches <number><optional_whitespace><unit>, where unit is NOT followed by
# another letter (prevents "m" matching inside "mg", "ml", etc.).
# The lookahead covers both ASCII and Swedish letters (å, ä, ö) so that Swedish
# compound words do not produce false unit matches.
_DURATION_TOKEN_RE = re.compile(
    r'(\d+(?:[.,]\d+)?)\s*(' + '|'.join(re.escape(a) for a in _DURATION_ALIASES_SORTED) + r')(?![a-zA-ZåäöÅÄÖ])',
    re.IGNORECASE,
)


def parse_duration(value) -> float | None:
    """Parse a duration expression; return total seconds as float or None.

    Handles compound strings ("1d 20min", "2h 30s", "1 hour 20 minutes 30 seconds"),
    Swedish aliases (timmar/minuter/sekunder/dagar), compact notation without spaces
    ("1h20min30s"), and plain numbers (treated as seconds).
    Returns None for unparseable input.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        return f if isfinite(f) else None
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    tokens = _DURATION_TOKEN_RE.findall(text)
    if not tokens:
        # Plain number with no unit — treat as seconds.
        return parse_numeric_answer(text)

    total = 0.0
    for num_str, unit_str in tokens:
        total += float(num_str.replace(',', '.')) * _DURATION_ALIAS_TO_SECONDS[unit_str.lower()]
    return total if isfinite(total) else None


def format_duration_for_display(seconds) -> str | None:
    """Format a total-seconds value as a compact human-readable duration.

    Examples: 4800 → "1h 20min", 86461 → "1d 1min 1s", 90 → "1min 30s", 0 → "0s".
    """
    if seconds is None:
        return None
    try:
        remaining = float(seconds)
    except (TypeError, ValueError):
        return None

    if remaining < 0:
        return f"{_to_int_if_whole(remaining)}s"

    parts = []
    for label, unit_sec in [('d', 86400), ('h', 3600), ('min', 60)]:
        if remaining >= unit_sec:
            count = int(remaining // unit_sec)
            remaining -= count * unit_sec
            parts.append(f"{count}{label}")

    if remaining > 0 or not parts:
        sec_val = _to_int_if_whole(round(remaining, 6))
        parts.append(f"{sec_val}s")

    return ' '.join(parts)


# ---------------------------------------------------------------------------
# Time-of-day parsing
# ---------------------------------------------------------------------------

# Accepted formats: "17:34", "17.34", "1734", "17 34"
# All variants must resolve to valid hour (0-23) and minute (0-59).
_TIME_COLON_RE = re.compile(r"^\s*(\d{1,2})\s*[:.\s]\s*(\d{2})\s*$")
_TIME_COMPACT_RE = re.compile(r"^\s*(\d{3,4})\s*$")


def parse_time_of_day(value):
    """Parse a time-of-day value; return minutes since midnight or None.

    Accepted forms: "17:34", "17.34", "17 34", "1734", int/float (treated as minutes).
    Returns None for invalid or out-of-range values.
    """
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        minutes = int(round(float(value)))
        return minutes if 0 <= minutes <= 1439 else None

    if not isinstance(value, str):
        return None

    text = value.strip()

    # "17:34", "17.34", "17 34"
    m = _TIME_COLON_RE.match(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if hour > 23 or minute > 59:
            return None
        return hour * 60 + minute

    # "1734" or "934" (compact)
    m = _TIME_COMPACT_RE.match(text)
    if m:
        raw = m.group(1)
        if len(raw) <= 3:
            # e.g. "934" → hour=9, minute=34
            hour = int(raw[:-2])
            minute = int(raw[-2:])
        else:
            # e.g. "1734" → hour=17, minute=34
            hour = int(raw[:-2])
            minute = int(raw[-2:])
        if hour > 23 or minute > 59:
            return None
        return hour * 60 + minute

    return None


def format_time_of_day(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM string."""
    h, m = divmod(int(minutes), 60)
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------

def format_answer_for_display(value, answer_type="numeric"):
    """Format a correct answer value for display.

    - "numeric":    strips trailing .0 (2.0 → 2)
    - "time_of_day": converts minutes-since-midnight → "HH:MM"
    - "duration":   converts seconds → compact string ("1h 20min")
    """
    if value is None:
        return value
    if answer_type == "time_of_day":
        try:
            return format_time_of_day(int(round(float(value))))
        except (TypeError, ValueError):
            return value
    if answer_type == "duration":
        return format_duration_for_display(value)
    try:
        return _to_int_if_whole(float(value))
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------

# Cache key and TTL for the unit alias map stored in Redis.
# 300 s matches the cat-request cache TTL so both warm up together after a deploy.
_UNIT_ALIAS_CACHE_KEY = "unit_aliases"
_UNIT_ALIAS_CACHE_TTL = 300  # seconds — shared across all Gunicorn workers via Redis


def _build_unit_alias_map_from_db() -> dict[str, str] | None:
    """Build the alias→canonical map by querying the Unit / UnitAlias tables.

    Returns None if the DB is unreachable (no app context, test environment, etc.)
    so callers can fall back to the bundled JSON.
    """
    try:
        from logic.database.init.init_db import db
        from logic.database.init.class_db import Unit
        from sqlalchemy import select
    except Exception:  # noqa: BLE001
        return None

    try:
        units = db.session.execute(select(Unit)).scalars().unique().all()
    except Exception:  # noqa: BLE001
        return None

    alias_map: dict[str, str] = {}
    for unit in units:
        if not isinstance(unit.name, str):
            continue
        canonical = unit.name.strip().lower()
        if canonical:
            alias_map[canonical] = canonical
        for alias_obj in unit.aliases:
            if isinstance(alias_obj.alias, str):
                alias_key = alias_obj.alias.strip().lower()
                if alias_key:
                    alias_map[alias_key] = canonical
    return alias_map


def _build_unit_alias_map_from_json() -> dict[str, str]:
    """Build the alias→canonical map from the bundled ``logic/default/units.json``.

    Used as a fallback when the database is not available (tests, cold start
    before the first request context exists).
    """
    units_path = Path(__file__).resolve().parent / "default" / "units.json"
    with units_path.open(encoding="utf-8") as handle:
        unit_groups = json.load(handle)

    alias_map: dict[str, str] = {}
    for unit_group in unit_groups:
        if not isinstance(unit_group, dict):
            continue
        for canonical_unit, aliases in unit_group.items():
            if not isinstance(canonical_unit, str):
                continue
            normalized_canonical = canonical_unit.strip().lower()
            if normalized_canonical:
                alias_map[normalized_canonical] = normalized_canonical
            if not isinstance(aliases, list):
                continue
            for alias in aliases:
                if isinstance(alias, str):
                    alias_map[alias.strip().lower()] = normalized_canonical
    return alias_map


def _load_unit_alias_map() -> dict[str, str]:
    """Resolve the unit-alias map.

    Reads from the shared cache (Redis when available); rebuilds from the
    DB on miss; falls back to the bundled JSON if the DB is not reachable
    (tests, no app context, etc.).
    """
    from logic.cache import get_cache

    cache = get_cache()
    cached = cache.get_json(_UNIT_ALIAS_CACHE_KEY)
    if isinstance(cached, dict):
        return cached

    alias_map = _build_unit_alias_map_from_db()
    if alias_map is None or not alias_map:
        alias_map = _build_unit_alias_map_from_json()

    cache.set_json(
        _UNIT_ALIAS_CACHE_KEY, alias_map, ttl_seconds=_UNIT_ALIAS_CACHE_TTL
    )
    return alias_map


def invalidate_unit_cache():
    """Drop the shared unit-alias cache so all workers refresh on next read."""
    from logic.cache import get_cache

    get_cache().delete(_UNIT_ALIAS_CACHE_KEY)


def is_known_unit(unit: str) -> bool:
    """Return True if unit is a recognised canonical unit or alias.

    An empty/None unit is always valid (question has no unit requirement).
    """
    if not unit or not isinstance(unit, str) or not unit.strip():
        return True
    return unit.strip().lower() in _load_unit_alias_map()


def normalize_unit(value, allow_blank_alias=False):
    """Return the canonical form of a unit string via the alias map.

    Args:
        value: Raw unit string from student input or template definition.
        allow_blank_alias: If True, an empty string is looked up in the map
            (useful when a blank alias represents a dimensionless canonical unit).

    Returns:
        Lowercase canonical unit string, or the lowercased input if no alias
        entry is found. Returns "" for non-string or empty input.
    """
    if not isinstance(value, str):
        return ""

    stripped = value.strip()
    if not stripped:
        if allow_blank_alias:
            return _load_unit_alias_map().get("", "")
        return ""

    return _load_unit_alias_map().get(stripped.lower(), stripped.lower())


# ---------------------------------------------------------------------------
# Tolerance helpers
# ---------------------------------------------------------------------------

def compute_effective_tolerance(correct_number, tolerance, tolerance_percent):
    """Return the effective tolerance value to use for grading.

    If tolerance_percent is set and > 0, tolerance = abs(correct_number) * pct / 100.
    Otherwise falls back to absolute tolerance (floor at 0).
    """
    if tolerance_percent is not None:
        try:
            pct = float(tolerance_percent)
        except (TypeError, ValueError):
            pct = 0.0
        if pct > 0 and correct_number is not None:
            return abs(float(correct_number)) * pct / 100.0

    if tolerance is not None:
        try:
            t = float(tolerance)
            return t if t >= 0 else 0.0
        except (TypeError, ValueError):
            pass
    return 0.0
