#!/usr/bin/env python3
"""
ai-roster - constraint base classes and individual constraint implementations.

Provides:
- BaseConstraint abstract base class
- BaseHardConstraint / BaseSoftConstraint subclasses
- Individual constraint implementations for each H# and S# rule
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ortools.sat.python import cp_model
    from models import Staff


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


class BaseConstraint(ABC):
    """Base class for all constraints.

    Subclasses must define:
    - constraint_id: the [H#...] or [S#...] tag
    - constraint_type: "hard" or "soft"
    - apply(): add variables and constraints to the CP-SAT model
    """

    constraint_id: str = ""
    constraint_type: str = ""

    def apply(
        self,
        model: "cp_model.CpModel",
        staff_list: list["Staff"],
        assignments: dict,
        definitions: dict,
    ) -> None:
        """Add variables and constraints to the CP-SAT model."""
        raise NotImplementedError


class BaseHardConstraint(BaseConstraint):
    """Hard constraints must always hold."""

    constraint_type = "hard"


class BaseSoftConstraint(BaseConstraint):
    """Soft constraints are optimization objectives with penalties.

    Subclasses override apply() with an additional weight parameter.
    """

    constraint_type = "soft"

    def apply(  # type: ignore[override]
        self,
        model: "cp_model.CpModel",
        staff_list: list["Staff"],
        assignments: dict,
        definitions: dict,
        weight: int,
    ) -> None:
        """Add penalty variable to the objective function."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Hard constraint implementations (stub)
# ---------------------------------------------------------------------------


class CoverageConstraint(BaseHardConstraint):
    """[H#4d9f81c2] [H#7a3e5f91] Every roster position must be filled."""

    constraint_id = "[H#4d9f81c2]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: ensure every position has exactly one staff assigned
        pass


class SkillLevelRequirement(BaseHardConstraint):
    """[H#c18b42de] [H#5e6ad8f4] [H#91bc3d7e] [H#b72e41fa]
    Skill level matching with threshold semantics."""

    constraint_id = "[H#5e6ad8f4]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: enforce skill level threshold matching
        pass


class SkillLevelHierarchy(BaseHardConstraint):
    """[H#84a1d5c9] [H#6db3f120] Hierarchical skill levels."""

    constraint_id = "[H#84a1d5c9]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: encode hierarchy (higher satisfies lower)
        pass


class NoDoubleBooking(BaseHardConstraint):
    """[H#e91c63ab] One roster position per staff per shift."""

    constraint_id = "[H#e91c63ab]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: forbid assigning same staff to multiple positions in same shift
        pass


class GraduateShiftConstraint(BaseHardConstraint):
    """[H#30479c74] Graduate staff restricted to D8, P8, L3, DISCO, N8."""

    constraint_id = "[H#30479c74]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: forbid assigning Graduate staff to D12, P12, N12
        pass


class RestPeriodConstraint(BaseHardConstraint):
    """[H#c1f6e3f5] Minimum 11 hours between shifts (wall-clock)."""

    constraint_id = "[H#c1f6e3f5]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: enforce 11h gap using span_hours
        pass


class NightToDayRest(BaseHardConstraint):
    """[H#f4c9b6c8] At least 1 full day off between night and day shifts."""

    constraint_id = "[H#f4c9b6c8]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: enforce day-off between night→day and day→night transitions
        pass


class RedRequestConstraint(BaseHardConstraint):
    """[H#a5d0c7d9] Never roster on red-requested dates."""

    constraint_id = "[H#a5d0c7d9]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: forbid assignments on red-request dates
        pass


class HolidayConstraint(BaseHardConstraint):
    """[H#b6e1d8e0] Never roster on holiday dates."""

    constraint_id = "[H#b6e1d8e0]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: forbid assignments on holiday date ranges
        pass


class MaxHoursConstraint(BaseHardConstraint):
    """[H#f0c5b2c4] Absolute 76 paid-hour cap per 14-day block."""

    constraint_id = "[H#f0c5b2c4]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: cap total paid hours per staff per block at 76
        pass


class ContractedHoursFloor(BaseHardConstraint):
    """[H#d9a8b7c6] Staff must meet contracted hours floor per block.

    Holidays proportionally reduce the floor; red requests do not.
    """

    constraint_id = "[H#d9a8b7c6]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: enforce minimum paid hours per staff per block
        pass


class OvertimeCap(BaseHardConstraint):
    """[H#e8f7d6c5] Max 24 paid hours of overtime above contracted per block."""

    constraint_id = "[H#e8f7d6c5]"

    def apply(self, model, staff_list, assignments, definitions):
        # TODO: cap overtime at min(76, contracted + 24)
        pass


# ---------------------------------------------------------------------------
# Soft constraint implementations (stub)
# ---------------------------------------------------------------------------


class OvertimeDistribution(BaseSoftConstraint):
    """[S#e9b4a1b3] Distribute overtime evenly across staff."""

    constraint_id = "[S#e9b4a1b3]"

    def apply(self, model, staff_list, assignments, definitions, weight):
        # TODO: minimize variance in overtime hours across staff
        pass


class NightShiftFairness(BaseSoftConstraint):
    """[S#d2a7f4a6] Equal distribution of night shifts by contracted hours."""

    constraint_id = "[S#d2a7f4a6]"

    def apply(self, model, staff_list, assignments, definitions, weight):
        # TODO: minimize deviation from proportional night shift allocation
        pass


class WeekendFairness(BaseSoftConstraint):
    """[S#a1d6c3d5] Share weekend hours across staff."""

    constraint_id = "[S#a1d6c3d5]"

    def apply(self, model, staff_list, assignments, definitions, weight):
        # TODO: minimize variance in weekend hours across staff
        pass


class ConsecutiveShiftDiscouraged(BaseSoftConstraint):
    """[S#30c6f5ad] Discourage 3+ consecutive days of the same shift type."""

    constraint_id = "[S#30c6f5ad]"

    def apply(self, model, staff_list, assignments, definitions, weight):
        # TODO: penalize runs of 3+ same shift type for same staff
        pass


class SkillLevelTiebreaker(BaseSoftConstraint):
    """[S#7b4e19fc] Prefer assigning staff at their highest skill level."""

    constraint_id = "[S#7b4e19fc]"

    def apply(self, model, staff_list, assignments, definitions, weight):
        # TODO: minimize assigning over-qualified staff to lower slots
        pass


# ---------------------------------------------------------------------------
# Constraint registry
# ---------------------------------------------------------------------------

HARD_CONSTRAINTS = [
    CoverageConstraint,
    SkillLevelRequirement,
    SkillLevelHierarchy,
    NoDoubleBooking,
    GraduateShiftConstraint,
    RestPeriodConstraint,
    NightToDayRest,
    RedRequestConstraint,
    HolidayConstraint,
    MaxHoursConstraint,
    ContractedHoursFloor,
    OvertimeCap,
]

SOFT_CONSTRAINTS = [
    OvertimeDistribution,
    NightShiftFairness,
    WeekendFairness,
    ConsecutiveShiftDiscouraged,
    SkillLevelTiebreaker,
]
