#!/usr/bin/env python3
"""
ai-roster - data models for staff, shifts, and roster positions.

Provides:
- Classification enum
- Staff dataclass with helper methods
- Shift dataclass
- RosterPosition dataclass
- RosterSlot (assignment) dataclass for solver output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Classification(Enum):
    """Staff classification — independent of skill level."""
    RN = "RN"
    CN = "CN"
    GRADUATE = "Graduate"


# ---------------------------------------------------------------------------
# Skill level helpers
# ---------------------------------------------------------------------------

SKILL_HIERARCHY = ["Acute", "Resus", "Triage", "Shift Coordinator"]
SKILL_RANK = {level: i for i, level in enumerate(SKILL_HIERARCHY)}


def skill_rank(level: str) -> int:
    """Return the rank of a skill level in the hierarchy."""
    return SKILL_RANK[level]


def satisfies_requirement(staff_skill_rank: int, required_rank: int) -> bool:
    """Check if a staff member's highest skill rank meets a requirement.

    Uses threshold semantics: a higher rank satisfies lower requirements.
    """
    return staff_skill_rank >= required_rank


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Staff:
    """Represents a single staff member.

    Attributes:
        name: Unique identifier for this staff member.
        classification: RN, CN, or Graduate.
        skill_tags: Held skill levels (contiguous prefix of hierarchy).
        contracted_hours_per_fortnight: Paid hours floor per 14-day block.
        red_requests: Dates this staff member must not be rostered.
        holidays: List of {start, end} unavailable date ranges.
    """
    name: str
    classification: Classification
    skill_tags: list[str]
    contracted_hours_per_fortnight: float
    red_requests: list[str] = field(default_factory=list)
    holidays: list[dict] = field(default_factory=list)

    @property
    def highest_skill_rank(self) -> int:
        """Return the rank of this staff member's highest skill level."""
        if not self.skill_tags:
            return -1
        return max(SKILL_RANK[tag] for tag in self.skill_tags)

    @property
    def highest_skill_level(self) -> Optional[str]:
        """Return the name of this staff member's highest skill level."""
        if not self.skill_tags:
            return None
        return max(self.skill_tags, key=lambda t: SKILL_RANK[t])

    @property
    def is_graduate(self) -> bool:
        """Shortcut: is this staff member classified as Graduate?"""
        return self.classification == Classification.GRADUATE


@dataclass
class Shift:
    """Represents a shift type definition.

    Attributes:
        name: Shift type identifier (e.g. "D8", "N12").
        start: Start time string (HH:MM:SS).
        end: End time string (HH:MM:SS).
        crosses_midnight: Whether the shift spans midnight.
        span_hours: Wall-clock duration including unpaid break.
        paid_hours: Actual worked/paid duration (span minus break).
        unpaid_break_minutes: Length of the unpaid break.
    """
    name: str
    start: str
    end: str
    crosses_midnight: bool
    span_hours: float
    paid_hours: float
    unpaid_break_minutes: int

    @property
    def is_night_shift(self) -> bool:
        """Whether this shift is classified as a night shift."""
        from utils import NIGHT_SHIFTS
        return self.name in NIGHT_SHIFTS

    @property
    def is_day_shift(self) -> bool:
        """Whether this shift is classified as a day shift."""
        from utils import DAY_SHIFTS
        return self.name in DAY_SHIFTS


@dataclass
class RosterPosition:
    """A single roster position to be filled on a given day.

    Attributes:
        date: Date this position is for.
        day_name: Day-of-week name (e.g. "Monday").
        shift: Shift type (e.g. "D8").
        required_skill_level: Minimum skill level required, or None.
        required_skill_rank: Numeric rank of the requirement, or -1 if None.
    """
    date: str
    day_name: str
    shift: str
    required_skill_level: Optional[str] = None
    required_skill_rank: int = -1

    def __post_init__(self):
        if self.required_skill_level is not None:
            self.required_skill_rank = SKILL_RANK[self.required_skill_level]


@dataclass
class RosterSlot:
    """A resolved assignment: staff member → roster position.

    This is the output representation after the solver runs.
    """
    staff_name: str
    date: str
    shift: str
    required_skill_level: Optional[str] = None
    filled_by_casual: bool = False
