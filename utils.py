#!/usr/bin/env python3
"""
ai-roster - utility functions for data loading, validation, and logging.

Provides:
- YAML/MD data loaders with validation against AGENTS.md §4 rules
- Logging setup (file + console) per AGENTS.md §6
- Helper calculations (hour arithmetic, date utilities, etc.)
"""

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SKILL_HIERARCHY = ["Acute", "Resus", "Triage", "Shift Coordinator"]
VALID_CLASSIFICATIONS = {"RN", "CN", "Graduate"}
VALID_SHIFT_TYPES = {"D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"}
DAY_SHIFTS = {"D8", "D12", "P8", "P12", "L3", "DISCO"}
NIGHT_SHIFTS = {"N8", "N12"}
GRADUATE_ALLOWED_SHIFTS = {"D8", "P8", "L3", "DISCO", "N8"}
SHIFT_ORDER = ["D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"]
SCALE = 100  # integer scaling factor for CP-SAT float arithmetic
REST_PERIOD_SECONDS = 11 * 3600  # 11 hours in seconds

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logger = logging.getLogger("ai-roster")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(run_id: str) -> logging.Logger:
    """Configure logging for a single run.

    Writes DEBUG+ to output/roster_<run_id>.log and INFO+ to console.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ai-roster")
    logger.setLevel(logging.DEBUG)

    # File handler — full detail
    fh = logging.FileHandler(OUTPUT_DIR / f"roster_{run_id}.log")
    fh.setLevel(logging.DEBUG)

    # Console handler — summary only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> Any:
    """Load and return parsed YAML from *path*, raising on parse errors."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def load_definitions(path: Path | None = None) -> dict[str, dict]:
    """Load shift definitions from definitions.yaml."""
    path = path or PROJECT_ROOT / "definitions.yaml"
    logger = logging.getLogger("ai-roster")
    data = load_yaml(path)
    logger.info("Loaded shift definitions from %s (%d shifts)", path.name, len(data))
    return data


def load_staff(path: Path | None = None) -> list[dict]:
    """Load staff list from staff.yaml."""
    path = path or PROJECT_ROOT / "staff.yaml"
    logger = logging.getLogger("ai-roster")
    data = load_yaml(path)
    logger.info("Loaded %d staff members from %s", len(data), path.name)
    return data


def load_roster(path: Path | None = None) -> dict:
    """Load roster configuration from roster.yaml."""
    path = path or PROJECT_ROOT / "roster.yaml"
    logger = logging.getLogger("ai-roster")
    data = load_yaml(path)
    logger.info("Loaded roster period %s → %s from %s",
                data["dates"]["start"], data["dates"]["end"], path.name)
    return data


def load_hard_constraints(path: Path | None = None) -> list[dict]:
    """Parse hard_constraints.md into a list of constraint records.

    Each record has: id (str), text (str), category (str).
    """
    path = path or PROJECT_ROOT / "hard_constraints.md"
    return _parse_constraint_file(path, "hard")


def load_soft_constraints(path: Path | None = None) -> list[dict]:
    """Parse soft_constraints.md into a list of constraint records."""
    path = path or PROJECT_ROOT / "soft_constraints.md"
    return _parse_constraint_file(path, "soft")


def load_weights(
    path: Path | None = None,
    known_soft_ids: set[str] | None = None,
    known_unfilled_tier_ids: set[str] | None = None,
) -> dict[str, int]:
    """Load soft-constraint weights from weights.yaml.

    Validates that every registered constraint ID has a corresponding entry.
    Raises ValueError if any are missing — this prevents the silent weight=1
    fallback bug where a key mismatch caused all weights to collapse to 1.

    Parameters
    ----------
    known_soft_ids
        Set of all soft constraint IDs (from ``constraints.get_soft_constraint_ids()``).
    known_unfilled_tier_ids
        Set of all unfilled-tier IDs (from ``solver.RosterModel.UNFILLED_TIER_IDS``).
    """
    path = path or PROJECT_ROOT / "weights.yaml"
    data = load_yaml(path)
    logger = logging.getLogger("ai-roster")
    logger.info("Loaded %d weights from %s", len(data), path.name)

    # Validate: every registered constraint ID must have a weight entry.
    missing: list[str] = []
    if known_soft_ids is not None:
        for cid in known_soft_ids:
            if cid not in data:
                missing.append(cid)
    if known_unfilled_tier_ids is not None:
        for cid in known_unfilled_tier_ids:
            if cid not in data:
                missing.append(cid)
    if missing:
        raise ValueError(
            f"weights.yaml is missing entries for {len(missing)} constraint ID(s): "
            f"{', '.join(sorted(missing))}. "
            f"Every registered constraint must have a corresponding weight entry."
        )

    return data


def load_config(path: Path | None = None,
                known_hard_ids: set[str] | None = None,
                known_soft_ids: set[str] | None = None) -> dict | None:
    """Load constraint toggle config from config.yaml.

    Returns None if the file doesn't exist or has no ``constraints`` section
    (all constraints enabled — normal operation).

    Returns
    -------
    dict or None
        ``{"hard": {"enabled": [str]}, "soft": {"enabled": [str]}}`` when
        the config is present.  Each ``enabled`` list contains the constraint
        IDs that should be active; everything else is skipped.

    Parameters
    ----------
    known_hard_ids / known_soft_ids
        Sets of valid constraint IDs used for validation.  Unknown IDs are
        logged as warnings but do not cause the config to be rejected.
    """
    path = path or PROJECT_ROOT / "config.yaml"
    logger = logging.getLogger("ai-roster")

    if not path.exists():
        logger.info("No config.yaml found — all constraints enabled")
        return None

    data = load_yaml(path)
    if not data or not isinstance(data, dict) or "constraints" not in data:
        logger.info("config.yaml has no constraints section — all constraints enabled")
        return None

    constraints = data["constraints"]
    if constraints is None:
        # `constraints:` with no value → treat as empty mapping
        constraints = {}
    elif not isinstance(constraints, dict):
        logger.info("config.yaml: constraints is not a mapping — all constraints enabled")
        return None

    result: dict = {"hard": {"enabled": []}, "soft": {"enabled": []}}

    for kind in ("hard", "soft"):
        kind_data = constraints.get(kind, {}) or {}
        enabled = kind_data.get("enabled", [])
        if not isinstance(enabled, list):
            # enabled is None (all commented out) or wrong type —
            # treat as "section absent for this kind", i.e. all enabled
            logger.info(
                "config.yaml: constraints.%s.enabled is not a list — all %s constraints enabled",
                kind, kind,
            )
            continue
        for cid in enabled:
            if not isinstance(cid, str):
                logger.warning("config.yaml: constraints.%s.enabled entry %r is not a string — skipping", kind, cid)
                continue
            # Validate against known IDs if provided
            known = known_hard_ids if kind == "hard" else known_soft_ids
            if known is not None and cid not in known:
                raise ValueError(
                    f"config.yaml: unknown {kind} constraint ID {cid!r} — "
                    f"ensure it is registered in constraints.py"
                )
            result[kind]["enabled"] = result[kind].get("enabled") or []
            result[kind]["enabled"].append(cid)

    hard_label = len(result["hard"]["enabled"]) if result["hard"]["enabled"] else "all"
    soft_label = len(result["soft"]["enabled"]) if result["soft"]["enabled"] else "all"
    logger.info(
        "Loaded config.yaml: %s hard, %s soft constraints enabled",
        hard_label, soft_label,
    )
    return result


def _parse_constraint_file(path: Path, kind: str) -> list[dict]:
    """Generic parser for hard_constraints.md / soft_constraints.md.

    Extracts [H#...] / [S#...] tags and their associated text.

    - Regex accepts [A-Za-z0-9] (not just hex) so IDs like [S#s1a2t3u4] parse.
    - Only starts a new record when the tag is at the start of a bullet line.
      In-body references (e.g. "[H#d9a8b7c6]/[H#a3d8f6c1]" inside a body) are
      treated as prose, not new constraints.
    - Rejects a tag from the wrong file kind (H# in soft doc or vice versa).
    - Detects and rejects duplicate definitions of the same ID.
    """
    tag_re = re.compile(r"\[(?P<tag>[HS]#[A-Za-z0-9]{8})\]")
    bullet_tag_re = re.compile(r"^-\s*(~~)?\[(?P<tag>[HS]#[A-Za-z0-9]{8})\]")
    constraints: list[dict] = []
    current: dict[str, str] | None = None
    seen_ids: set[str] = set()

    with open(path, "r") as f:
        for line_no, line in enumerate(f, 1):
            stripped = line.strip()
            # Skip section headers (## ...)
            if stripped.startswith("##"):
                continue

            # Check for a constraint tag at the start of a bullet point
            bm = bullet_tag_re.match(stripped)
            if bm:
                tag = bm.group("tag")
                tag_kind = tag[0]
                # Cross-kind reference check (case-insensitive: kind="hard"/"soft", tag="H"/"S")
                if tag_kind.lower() != kind[0]:
                    raise ValueError(
                        f"{path.name}:{line_no}: {tag} found in {kind} file "
                        f"(expected {'H#' if kind == 'hard' else 'S#'})"
                    )
                # Duplicate check
                if tag in seen_ids:
                    raise ValueError(
                        f"{path.name}:{line_no}: duplicate definition of {tag}"
                    )
                seen_ids.add(tag)

                if current is not None:
                    constraints.append(current)
                current = {"id": tag, "text": "", "kind": kind}
                # Strip the tag (and optional strikethrough) from text
                text_after = bullet_tag_re.sub("", stripped).strip()
                if text_after:
                    current["text"] += text_after + " "
                continue

            # Check for any tag anywhere in the line (in-body reference)
            # These are treated as prose, not new constraints — even if cross-kind,
            # since cross-references in prose are legitimate (e.g. soft doc citing
            # a hard constraint by ID).
            tm = tag_re.search(stripped)
            if tm and not bm:
                # In-body reference — treat as prose, don't start a new record
                continue

            if current is not None:
                if stripped and not stripped.startswith("-"):
                    # continuation of text
                    current["text"] += stripped + " "
                elif stripped.startswith("- "):
                    # bullet point under current constraint
                    current["text"] += stripped[2:] + " "

    if current is not None:
        constraints.append(current)

    logger = logging.getLogger("ai-roster")
    logger.info("Parsed %d %s constraints from %s", len(constraints), kind, path.name)
    return constraints


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_staff_records(
    records: list[dict],
    roster_dates: set[str] | set[date] | None = None,
) -> list[dict]:
    """Validate every staff record per AGENTS.md §4.

    Returns validated list (same objects) or raises ValueError with details.
    If roster_dates is provided, warns about red_requests/holidays outside the
    roster period.
    """
    seen_names: set[str] = set()

    for i, rec in enumerate(records):
        # name uniqueness
        name = rec.get("name")
        if not name or name in seen_names:
            raise ValueError(
                f"staff.yaml row {i + 1}: name '{name}' is {'missing' if not name else 'duplicate'}"
            )
        seen_names.add(name)

        # classification
        classification = rec.get("classification")
        if classification not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"staff.yaml row {i + 1} ({name}): "
                f"classification must be one of {VALID_CLASSIFICATIONS}, got '{classification}'"
            )

        # skill_tags — must be a contiguous prefix of SKILL_HIERARCHY
        skill_tags = rec.get("skill_tags", [])
        if not isinstance(skill_tags, list):
            raise ValueError(
                f"staff.yaml row {i + 1} ({name}): skill_tags must be a list"
            )
        for tag in skill_tags:
            if tag not in SKILL_HIERARCHY:
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): unknown skill level '{tag}'"
                )
        # Check contiguous prefix
        for j, tag in enumerate(skill_tags):
            if tag != SKILL_HIERARCHY[j]:
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): skill_tags must be a contiguous "
                    f"prefix of {SKILL_HIERARCHY}; found {skill_tags}"
                )

        # contracted_hours_per_fortnight
        hours = rec.get("contracted_hours_per_fortnight")
        if not isinstance(hours, (int, float)) or hours <= 0:
            raise ValueError(
                f"staff.yaml row {i + 1} ({name}): "
                f"contracted_hours_per_fortnight must be a positive number, got {hours}"
            )

        # red_requests — list of date strings
        red_requests = rec.get("red_requests", [])
        if not isinstance(red_requests, list):
            raise ValueError(
                f"staff.yaml row {i + 1} ({name}): red_requests must be a list"
            )
        for d in red_requests:
            try:
                date.fromisoformat(d)
            except (ValueError, TypeError):
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): invalid red_request date '{d}'"
                )
        if roster_dates:
            for d in red_requests:
                if d not in roster_dates:
                    logger.warning(
                        "staff.yaml: %s has red_request date '%s' outside "
                        "the roster period — it will have no effect",
                        name, d,
                    )

        # holidays — list of {start, end} objects
        holidays = rec.get("holidays", [])
        if not isinstance(holidays, list):
            raise ValueError(
                f"staff.yaml row {i + 1} ({name}): holidays must be a list"
            )
        for h in holidays:
            if not isinstance(h, dict) or "start" not in h or "end" not in h:
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): holiday entry must have start and end"
                )
            try:
                start = date.fromisoformat(h["start"])
                end = date.fromisoformat(h["end"])
            except (ValueError, TypeError):
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): invalid holiday date"
                )
            if start > end:
                raise ValueError(
                    f"staff.yaml row {i + 1} ({name}): holiday start ({h['start']}) "
                    f"must not be after end ({h['end']})"
                )
        if roster_dates:
            roster_date_set: set[date] = {
                d if isinstance(d, date) else date.fromisoformat(d)
                for d in roster_dates
            }
            roster_start = min(roster_date_set)
            roster_end = max(roster_date_set)
            for h in holidays:
                h_start = date.fromisoformat(h["start"])
                h_end = date.fromisoformat(h["end"])
                if h_end < roster_start or h_start > roster_end:
                    logger.warning(
                        "staff.yaml: %s has holiday %s–%s outside "
                        "the roster period — it will have no effect",
                        name, h["start"], h["end"],
                    )

    return records


def validate_roster_period(roster_data: dict) -> tuple[date, date]:
    """Validate the roster period is a whole multiple of 14 days.

    Returns (start_date, end_date).
    """
    raw_start = roster_data["dates"]["start"]
    raw_end = roster_data["dates"]["end"]
    if isinstance(raw_start, date):
        start = raw_start
    else:
        start = date.fromisoformat(str(raw_start))
    if isinstance(raw_end, date):
        end = raw_end
    else:
        end = date.fromisoformat(str(raw_end))

    delta = (end - start).days + 1  # inclusive
    if delta <= 0:
        raise ValueError(f"Roster end ({end}) must be on or after start ({start})")
    if delta % 14 != 0:
        raise ValueError(
            f"Roster period must span a whole multiple of 14 days; "
            f"got {delta} days ({start} to {end})"
        )

    return start, end


def validate_roster_positions(roster_data: dict, definitions: dict,
                              start_date: date, end_date: date) -> list[dict]:
    """Validate every roster position entry.

    Returns a flat list of position dicts, each with its resolved date,
    day-of-week name, shift type, required skill level, and slot_id.
    """
    positions: list[dict] = []
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                 "Saturday", "Sunday"]

    roster_positions = roster_data.get("roster_positions", {})

    # Track slot counters per (date, shift, skill_label) — counter resets each date
    # so slot_id means "the nth <shift>/<skill> position on this day", stable across
    # every week. Per D7(a).
    slot_counters: dict[tuple[str, str, str | None], int] = {}

    current = start_date
    while current <= end_date:
        day_name = day_names[current.weekday()]
        day_entries = roster_positions.get(day_name, [])
        if not isinstance(day_entries, list):
            raise ValueError(f"roster.yaml: '{day_name}' must be a list of positions")

        for pos in day_entries:
            shift = pos.get("shift")
            required_skill = pos.get("required_skill_level")

            if shift not in VALID_SHIFT_TYPES:
                raise ValueError(
                    f"roster.yaml ({day_name}): unknown shift type '{shift}'"
                )

            if required_skill is not None and required_skill not in SKILL_HIERARCHY:
                raise ValueError(
                    f"roster.yaml ({day_name}): unknown skill level "
                    f"'{required_skill}'"
                )

            skill_label = required_skill if required_skill is not None else "General"
            counter_key = (current.isoformat(), shift, skill_label)
            slot_counters[counter_key] = slot_counters.get(counter_key, 0) + 1
            n = slot_counters[counter_key]
            slot_id = f"{shift}-{skill_label}-{n}"

            positions.append({
                "date": current.isoformat(),
                "day_name": day_name,
                "shift": shift,
                "required_skill_level": required_skill,
                "slot_id": slot_id,
            })

        current += timedelta(days=1)

    return positions


# ---------------------------------------------------------------------------
# Date / hour helpers
# ---------------------------------------------------------------------------


def generate_dates(start_date: date, end_date: date) -> list[date]:
    """Return all dates from start_date to end_date inclusive."""
    return [start_date + timedelta(days=i)
            for i in range((end_date - start_date).days + 1)]


def get_fortnight_blocks(dates: list[date]) -> list[list[date]]:
    """Split a sorted date list into 14-day blocks."""
    blocks = []
    for i in range(0, len(dates), 14):
        blocks.append(dates[i:i + 14])
    return blocks


def is_weekend(d: date) -> bool:
    """Return True if *d* is Saturday or Sunday."""
    return d.weekday() >= 5


def shift_paid_hours(shift_name: str, definitions: dict) -> float:
    """Return the paid_hours for a shift type from definitions."""
    return definitions[shift_name]["paid_hours"]


def shift_span_hours(shift_name: str, definitions: dict) -> float:
    """Return the span_hours for a shift type from definitions."""
    return definitions[shift_name]["span_hours"]


def shift_crosses_midnight(shift_name: str, definitions: dict) -> bool:
    """Return whether a shift crosses midnight."""
    return definitions[shift_name]["crosses_midnight"]


def shift_start_time(shift_name: str, definitions: dict) -> datetime:
    """Return the start time of a shift as a datetime (date part ignored)."""
    t = datetime.strptime(definitions[shift_name]["start"], "%H:%M:%S")
    return t


def shift_end_time(shift_name: str, definitions: dict) -> datetime:
    """Return the end time of a shift as a datetime (date part ignored)."""
    t = datetime.strptime(definitions[shift_name]["end"], "%H:%M:%S")
    return t


def hours_to_scaled(hours: float) -> int:
    """Convert a float hour value to the scaled integer used by CP-SAT."""
    return int(round(hours * SCALE))


def scaled_to_hours(scaled: int) -> float:
    """Convert a scaled integer back to float hours."""
    return scaled / SCALE


def fair_share_deviation(
    model: Any,
    per_staff: list[Any],
    contracted: list[int],
    prefix: str = "dev",
    max_val: int = 76,
) -> Any:
    """Build CP-SAT constraints for sum of absolute deviations from proportional fair share.

    Given per-staff values (CP-SAT IntVars for hours worked) and contracted hours
    for each staff member, builds constraints for |per_staff[i] - target[i]| where
    target[i] = round(total * contracted[i] / sum(contracted)).

    All per-staff values are in whole paid hours (8 or 12 per shift). The target
    is computed in whole hours via Python-side arithmetic. Returns the total
    deviation IntVar — no scaling, no division by n.

    This is the core helper for objective rescaling (§2.3): it replaces the
    old "multiply by n to avoid division" pattern that inflated deviations
    by n× (n = staff count), causing objectives of ~160M instead of ~1e4.
    """
    n = len(per_staff)
    if n == 0:
        return model.NewIntVar(0, 0, f"{prefix}_total")

    # Total pool (IntVar)
    total_pool = model.NewIntVar(0, n * max_val, f"{prefix}_total_pool")
    model.Add(total_pool == sum(per_staff))

    sum_contracted = sum(contracted)
    if sum_contracted == 0:
        dev_zero = model.NewIntVar(0, 0, f"{prefix}_total")
        return dev_zero

    # Build deviation for each staff member
    total_dev = model.NewIntVar(0, n * max_val, f"{prefix}_total")
    dev_terms: list = []
    for i in range(n):
        target = round(total_pool * contracted[i] / sum_contracted)
        dev = model.NewIntVar(0, max_val, f"{prefix}_{i}")
        model.Add(dev >= per_staff[i] - target)
        model.Add(dev >= target - per_staff[i])
        dev_terms.append(dev)
    model.Add(total_dev == sum(dev_terms))
    return total_dev


def compute_adjusted_hours(
    contracted_hours: float,
    holidays: list[dict],
    block_dates: list[str],
) -> int:
    """[H#a3d8f6c1] Compute adjusted contracted hours for one 14-day block.

    adjusted_hours = floor(contracted_hours_per_fortnight * available_days / 14)
    where available_days = 14 - (count of block days falling within any holiday range).

    Red requests do not factor in. Returns SCALE-d integer.
    """
    if not block_dates:
        return 0
    # Collect all holiday dates in a set to avoid double-counting
    # overlapping holiday ranges
    holiday_dates_set: set[date] = set()
    for h in holidays:
        h_start = date.fromisoformat(h["start"])
        h_end = date.fromisoformat(h["end"])
        current = h_start
        while current <= h_end:
            holiday_dates_set.add(current)
            current += timedelta(days=1)
    # Count how many block dates fall within any holiday range
    holiday_days = sum(
        1 for bd in block_dates
        if date.fromisoformat(bd) in holiday_dates_set
    )
    available = 14 - holiday_days
    contracted_scaled = int(round(contracted_hours * SCALE))
    return contracted_scaled * available // 14
