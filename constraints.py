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

from utils import SCALE

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
        staff_by_name: dict[str, "Staff"],
        assignments: list[list["cp_model.IntVar"]],
        staff_names: list[str],
        definitions: dict,
        all_dates: list[str],
        blocks: list[list[str]],
        positions: list[dict],
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
        staff_by_name: dict[str, "Staff"],
        assignments: list[list["cp_model.IntVar"]],
        staff_names: list[str],
        definitions: dict,
        all_dates: list[str],
        blocks: list[list[str]],
        positions: list[dict],
        weight: int,
    ) -> None:
        """Add penalty variable to the objective function."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Hard constraint implementations
# ---------------------------------------------------------------------------


class CoverageConstraint(BaseHardConstraint):
    """[H#4d9f81c2] [H#7a3e5f91] Every roster position must be filled.

    Enforced in solver._create_variables() via "exactly one staff per position".
    This constraint class exists as a registry entry and for reporting unfilled
    positions in the output.
    """

    constraint_id = "[H#4d9f81c2]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        # Coverage is enforced in _create_variables() — this constraint
        # exists so the constraint registry includes it and the solver can
        # report unfilled positions in _extract_assignments().
        pass


class SkillLevelRequirement(BaseHardConstraint):
    """[H#c18b42de] [H#5e6ad8f4] [H#91bc3d7e] [H#b72e41fa]
    Skill level matching with threshold semantics."""

    constraint_id = "[H#5e6ad8f4]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        # TODO: enforce skill level threshold matching
        pass


class SkillLevelHierarchy(BaseHardConstraint):
    """[H#84a1d5c9] [H#6db3f120] Hierarchical skill levels."""

    constraint_id = "[H#84a1d5c9]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        # TODO: encode hierarchy (higher satisfies lower)
        pass


class NoDoubleBooking(BaseHardConstraint):
    """[H#e91c63ab] A staff member's assigned shifts must not overlap.

    Uses a precomputed 8x8 compatibility table of (shift_on_day_d,
    shift_on_day_d+1) pairs that are incompatible due to wall-clock overlap.
    """

    constraint_id = "[H#e91c63ab]"

    # Shift types in the order used by the compatibility table
    SHIFT_TYPES = ["D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"]

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):

        compat = self._build_compatibility_table(definitions)

        num_staff = len(staff_names)
        num_dates = len(all_dates)

        # Build position-index → date and shift lookups
        pos_date: list[str] = [p["date"] for p in positions]
        pos_shift: list[str] = [p["shift"] for p in positions]

        # Group position indices by date
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        # For each staff, each consecutive day pair, each incompatible shift pair
        for si in range(num_staff):
            for di in range(num_dates - 1):
                date_d = all_dates[di]
                date_d1 = all_dates[di + 1]
                positions_d = pos_by_date.get(date_d, [])
                positions_d1 = pos_by_date.get(date_d1, [])
                if not positions_d or not positions_d1:
                    continue

                for pi_d in positions_d:
                    shift_a = pos_shift[pi_d]
                    shift_a_idx = self.SHIFT_TYPES.index(shift_a)
                    for pi_d1 in positions_d1:
                        shift_b = pos_shift[pi_d1]
                        shift_b_idx = self.SHIFT_TYPES.index(shift_b)
                        if not compat[shift_a_idx][shift_b_idx]:
                            model.Add(
                                assignments[si][pi_d] + assignments[si][pi_d1] <= 1
                            )

    def _build_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8x8 compatibility table.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        do NOT overlap. False means they overlap and are incompatible.
        """
        from datetime import datetime, timedelta

        n = len(self.SHIFT_TYPES)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(self.SHIFT_TYPES):
            for b_idx, shift_b in enumerate(self.SHIFT_TYPES):
                a_start_str = definitions[shift_a]["start"]
                a_end_str = definitions[shift_a]["end"]
                a_crosses = definitions[shift_a]["crosses_midnight"]
                b_start_str = definitions[shift_b]["start"]
                b_end_str = definitions[shift_b]["end"]

                # Parse times
                a_start = datetime.strptime(a_start_str, "%H:%M:%S")
                a_end = datetime.strptime(a_end_str, "%H:%M:%S")
                b_start = datetime.strptime(b_start_str, "%H:%M:%S")

                # Absolute end of shift_a on day d (may be next day if crosses midnight)
                a_end_abs = a_end
                if a_crosses:
                    a_end_abs += timedelta(days=1)

                # Absolute start of shift_b on day d+1
                b_start_abs = b_start + timedelta(days=1)

                # Check overlap: intervals [a_start, a_end_abs) and [b_start_abs, ...)
                if a_end_abs > b_start_abs:
                    compat[a_idx][b_idx] = False

        return compat


class GraduateShiftConstraint(BaseHardConstraint):
    """[H#30479c74] Graduate staff restricted to D8, P8, L3, DISCO, N8."""

    constraint_id = "[H#30479c74]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        allowed = {"D8", "P8", "L3", "DISCO", "N8"}
        num_staff = len(staff_names)
        num_positions = len(positions)

        for si in range(num_staff):
            staff = staff_by_name[staff_names[si]]
            if staff.is_graduate:
                for pi in range(num_positions):
                    if positions[pi]["shift"] not in allowed:
                        model.Add(assignments[si][pi] == 0)


class RestPeriodConstraint(BaseHardConstraint):
    """[H#c1f6e3f5] Minimum 11 hours between shifts (wall-clock).

    Uses a precomputed compatibility table of (shift_on_day_d,
    shift_on_day_d+1) pairs where the gap between end-of-shift_a
    and start-of-shift_b is less than 11 hours.
    """

    constraint_id = "[H#c1f6e3f5]"
    SHIFT_TYPES = ["D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"]
    REST_PERIOD_SECONDS = 11 * 3600  # 11 hours in seconds

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):

        compat = self._build_compatibility_table(definitions)

        num_staff = len(staff_names)
        num_dates = len(all_dates)

        pos_date: list[str] = [p["date"] for p in positions]
        pos_shift: list[str] = [p["shift"] for p in positions]

        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        for si in range(num_staff):
            for di in range(num_dates - 1):
                date_d = all_dates[di]
                date_d1 = all_dates[di + 1]
                positions_d = pos_by_date.get(date_d, [])
                positions_d1 = pos_by_date.get(date_d1, [])
                if not positions_d or not positions_d1:
                    continue

                for pi_d in positions_d:
                    shift_a = pos_shift[pi_d]
                    shift_a_idx = self.SHIFT_TYPES.index(shift_a)
                    for pi_d1 in positions_d1:
                        shift_b = pos_shift[pi_d1]
                        shift_b_idx = self.SHIFT_TYPES.index(shift_b)
                        if not compat[shift_a_idx][shift_b_idx]:
                            model.Add(
                                assignments[si][pi_d] + assignments[si][pi_d1] <= 1
                            )

    def _build_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8x8 compatibility table.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        have a gap of at least 11 hours between them.
        """
        from datetime import datetime, timedelta

        n = len(self.SHIFT_TYPES)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(self.SHIFT_TYPES):
            for b_idx, shift_b in enumerate(self.SHIFT_TYPES):
                a_end_str = definitions[shift_a]["end"]
                a_crosses = definitions[shift_a]["crosses_midnight"]
                b_start_str = definitions[shift_b]["start"]

                a_end = datetime.strptime(a_end_str, "%H:%M:%S")
                b_start = datetime.strptime(b_start_str, "%H:%M:%S")

                # Absolute end of shift_a (on day d or d+1 if crosses midnight)
                a_end_abs = a_end
                if a_crosses:
                    a_end_abs += timedelta(days=1)

                # Absolute start of shift_b (always on day d+1)
                b_start_abs = b_start + timedelta(days=1)

                gap = (b_start_abs - a_end_abs).total_seconds()
                compat[a_idx][b_idx] = gap >= self.REST_PERIOD_SECONDS

        return compat


class NightToDayRest(BaseHardConstraint):
    """[H#f4c9b6c8] At least 1 full day off between night and day shifts.

    A night shift (N8/N12) on day d forbids any day shift (D8/D12/P8/P12/L3/DISCO)
    on day d+1, and vice versa. Uses a precomputed 8×8 compatibility table where
    compat[a][b] == True only when both shifts are in the same category (both
    day or both night).
    """

    constraint_id = "[H#f4c9b6c8]"
    SHIFT_TYPES = ["D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"]
    DAY_SHIFTS = {"D8", "D12", "P8", "P12", "L3", "DISCO"}
    NIGHT_SHIFTS = {"N8", "N12"}

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):

        compat = self._build_night_day_compatibility_table(definitions)

        num_staff = len(staff_names)
        num_dates = len(all_dates)

        pos_date: list[str] = [p["date"] for p in positions]
        pos_shift: list[str] = [p["shift"] for p in positions]

        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        for si in range(num_staff):
            for di in range(num_dates - 1):
                date_d = all_dates[di]
                date_d1 = all_dates[di + 1]
                positions_d = pos_by_date.get(date_d, [])
                positions_d1 = pos_by_date.get(date_d1, [])
                if not positions_d or not positions_d1:
                    continue

                for pi_d in positions_d:
                    shift_a = pos_shift[pi_d]
                    shift_a_idx = self.SHIFT_TYPES.index(shift_a)
                    for pi_d1 in positions_d1:
                        shift_b = pos_shift[pi_d1]
                        shift_b_idx = self.SHIFT_TYPES.index(shift_b)
                        if not compat[shift_a_idx][shift_b_idx]:
                            model.Add(
                                assignments[si][pi_d] + assignments[si][pi_d1] <= 1
                            )

    def _build_night_day_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8×8 compatibility table for night↔day transitions.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        are in the same category (both day or both night). False means they
        are in different categories and are incompatible.
        """
        n = len(self.SHIFT_TYPES)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(self.SHIFT_TYPES):
            for b_idx, shift_b in enumerate(self.SHIFT_TYPES):
                a_is_night = shift_a in self.NIGHT_SHIFTS
                b_is_night = shift_b in self.NIGHT_SHIFTS
                # Incompatible when one is night and the other is day
                if a_is_night != b_is_night:
                    compat[a_idx][b_idx] = False

        return compat


class RedRequestConstraint(BaseHardConstraint):
    """[H#a5d0c7d9] Never roster on red-requested dates."""

    constraint_id = "[H#a5d0c7d9]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        num_staff = len(staff_names)
        num_positions = len(positions)

        for si in range(num_staff):
            staff = staff_by_name[staff_names[si]]
            red_dates = set(staff.red_requests)
            for pi in range(num_positions):
                if positions[pi]["date"] in red_dates:
                    model.Add(assignments[si][pi] == 0)


class HolidayConstraint(BaseHardConstraint):
    """[H#b6e1d8e0] Never roster on holiday dates."""

    constraint_id = "[H#b6e1d8e0]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        from datetime import date as date_type, timedelta

        num_staff = len(staff_names)
        num_positions = len(positions)

        for si in range(num_staff):
            staff = staff_by_name[staff_names[si]]
            holiday_dates: set[str] = set()
            for h in staff.holidays:
                start = date_type.fromisoformat(h["start"])
                end = date_type.fromisoformat(h["end"])
                current = start
                while current <= end:
                    holiday_dates.add(current.isoformat())
                    current += timedelta(days=1)
            for pi in range(num_positions):
                if positions[pi]["date"] in holiday_dates:
                    model.Add(assignments[si][pi] == 0)


class MaxHoursConstraint(BaseHardConstraint):
    """[H#f0c5b2c4] Absolute 76 paid-hour cap per 14-day block."""

    constraint_id = "[H#f0c5b2c4]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        # Enforced in _create_variables() via IntVar upper bound
        pass


class ContractedHoursFloor(BaseHardConstraint):
    """[H#d9a8b7c6] Staff must meet contracted hours floor per block.

    Holidays proportionally reduce the floor; red requests do not.
    Uses precomputed adjusted_hours via utils.compute_adjusted_hours.
    """

    constraint_id = "[H#d9a8b7c6]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        from utils import compute_adjusted_hours

        if staff_hours_vars is None:
            return

        from datetime import date as date_type

        for si, staff in enumerate(staff_list):
            for bi, block in enumerate(blocks):
                block_strs = [d if isinstance(d, str) else d.isoformat() for d in block]
                adj = compute_adjusted_hours(
                    staff.contracted_hours_per_fortnight,
                    staff.holidays,
                    block_strs,
                )
                model.Add(staff_hours_vars[si][bi] >= adj)


class OvertimeCap(BaseHardConstraint):
    """[H#e8f7d6c5] Max 12 paid hours of overtime above contracted per block."""

    constraint_id = "[H#e8f7d6c5]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions):
        # TODO: cap overtime at min(76, contracted + 12)
        pass


# ---------------------------------------------------------------------------
# Soft constraint implementations
# ---------------------------------------------------------------------------


class OvertimeDistribution(BaseSoftConstraint):
    """[S#e9b4a1b3] Distribute overtime evenly across staff."""

    constraint_id = "[S#e9b4a1b3]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight):
        # TODO: minimize variance in overtime hours across staff
        pass


class NightShiftFairness(BaseSoftConstraint):
    """[S#d2a7f4a6] Equal distribution of night shifts by contracted hours."""

    constraint_id = "[S#d2a7f4a6]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight):
        # TODO: minimize deviation from proportional night shift allocation
        pass


class WeekendFairness(BaseSoftConstraint):
    """[S#a1d6c3d5] Share weekend hours across staff.

    Minimizes the sum of absolute deviations of each staff member's weekend
    hours from the mean, using a scaled formulation that avoids division.
    """

    constraint_id = "[S#a1d6c3d5]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight):

        num_staff = len(staff_names)
        num_positions = len(positions)

        # Identify weekend position indices and their scaled paid hours
        weekend_pos_indices: list[int] = []
        weekend_scaled_hours: list[int] = []
        for pi, pos in enumerate(positions):
            day_name = pos["day_name"]
            if day_name in ("Saturday", "Sunday"):
                weekend_pos_indices.append(pi)
                paid = definitions[pos["shift"]]["paid_hours"]
                weekend_scaled_hours.append(int(round(paid * SCALE)))

        if not weekend_pos_indices:
            return

        # Per-staff weekend hours (scaled)
        staff_weekend_hours: list[cp_model.IntVar] = []
        for si in range(num_staff):
            terms = [
                weekend_scaled_hours[j] * assignments[si][weekend_pos_indices[j]]
                for j in range(len(weekend_pos_indices))
            ]
            wh = model.NewIntVar(0, 76 * SCALE, f"weekend_h_{staff_names[si]}")
            model.Add(wh == sum(terms))
            staff_weekend_hours.append(wh)

        # Total weekend hours
        total_weekend = model.NewIntVar(0, num_staff * 76 * SCALE, "total_weekend")
        model.Add(total_weekend == sum(staff_weekend_hours))

        # Mean = total_weekend / num_staff (scaled: mean * n = total)
        # Deviation from mean (scaled by n to avoid division):
        # dev[s] = |weekend_hours[s] * n - total_weekend|
        n = num_staff
        deviation_vars: list[cp_model.IntVar] = []
        for si in range(num_staff):
            deviation = model.NewIntVar(0, 76 * SCALE * n, f"dev_wk_{staff_names[si]}")
            model.Add(deviation >= staff_weekend_hours[si] * n - total_weekend)
            model.Add(deviation >= total_weekend - staff_weekend_hours[si] * n)
            deviation_vars.append(deviation)

        # Minimize sum of deviations
        total_deviation = model.NewIntVar(0, 76 * SCALE * n * n, "total_weekend_dev")
        model.Add(total_deviation == sum(deviation_vars))
        model.Minimize(total_deviation * weight)


class ConsecutiveShiftDiscouraged(BaseSoftConstraint):
    """[S#30c6f5ad] Discourage 3+ consecutive days of the same shift type."""

    constraint_id = "[S#30c6f5ad]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight):
        # TODO: penalize runs of 3+ same shift type for same staff
        pass


class SkillLevelTiebreaker(BaseSoftConstraint):
    """[S#7b4e19fc] Prefer assigning staff at their highest skill level."""

    constraint_id = "[S#7b4e19fc]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight):
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


def get_hard_constraint_ids() -> list[str]:
    """Return the constraint_id of every registered hard constraint."""
    return [c.constraint_id for c in HARD_CONSTRAINTS]


def get_soft_constraint_ids() -> list[str]:
    """Return the constraint_id of every registered soft constraint."""
    return [c.constraint_id for c in SOFT_CONSTRAINTS]
