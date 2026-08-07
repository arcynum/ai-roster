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

from utils import (
    DAY_SHIFTS,
    NIGHT_SHIFTS,
    REST_PERIOD_SECONDS,
    SCALE,
    SHIFT_ORDER,
    fair_share_deviation,
)

if TYPE_CHECKING:
    from ortools.sat.python import cp_model
    from models import Staff


def _emit_compatibility_constraints(
    model,
    compat: list[list[bool]],
    assignments,
    staff_names: list[str],
    num_staff: int,
    all_dates: list[str],
    pos_by_date: dict[str, list[int]],
    pos_shift: list[str],
) -> None:
    """Emit `a + b <= 1` for every incompatible shift-pair on consecutive days.

    Shared across NoDoubleBooking, RestPeriodConstraint, and NightToDayRest.
    """
    for si in range(num_staff):
        for di in range(len(all_dates) - 1):
            date_d = all_dates[di]
            date_d1 = all_dates[di + 1]
            positions_d = pos_by_date.get(date_d, [])
            positions_d1 = pos_by_date.get(date_d1, [])
            if not positions_d or not positions_d1:
                continue
            for pi_d in positions_d:
                shift_a = pos_shift[pi_d]
                shift_a_idx = SHIFT_ORDER.index(shift_a)
                for pi_d1 in positions_d1:
                    shift_b = pos_shift[pi_d1]
                    shift_b_idx = SHIFT_ORDER.index(shift_b)
                    if not compat[shift_a_idx][shift_b_idx]:
                        model.Add(
                            assignments[si][pi_d] + assignments[si][pi_d1] <= 1
                        )


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
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        # Coverage is enforced in _create_variables() — this constraint
        # exists so the constraint registry includes it and the solver can
        # report unfilled positions in _extract_assignments().
        pass


class SkillLevelRequirement(BaseHardConstraint):
    """[H#c18b42de] [H#5e6ad8f4] [H#84a1d5c9] [H#91bc3d7e] [H#b72e41fa]
    Skill level matching with threshold semantics.

    A staff member is only assignable to a position if their highest skill
    rank >= the position's required skill rank. Positions with required_skill_rank
    == -1 (null) impose no restriction.

    The skill hierarchy (Acute < Resus < Triage < Shift Coordinator) is validated
    at data-loading time (utils.validate_staff_yaml ensures skill_tags is a
    contiguous prefix). The threshold check below enforces "higher satisfies lower"
    at solve time. This class covers both [H#5e6ad8f4] and [H#84a1d5c9].
    """

    constraint_id = "[H#5e6ad8f4]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        # Precompute staff highest skill ranks
        staff_ranks: list[int] = [staff.highest_skill_rank for staff in staff_list]

        # Precompute position required skill ranks
        pos_required_ranks: list[int] = [
            p.get("required_skill_rank", -1) for p in positions
        ]

        for si, staff in enumerate(staff_list):
            staff_rank = staff_ranks[si]
            for pi, pos in enumerate(positions):
                required_rank = pos_required_ranks[pi]
                x = assignments[si][pi]
                if required_rank < 0:
                    # Null skill level — no restriction (H#91bc3d7e)
                    continue
                # Enforce: if staff assigned, their rank must meet requirement
                model.Add(staff_rank >= required_rank).OnlyEnforceIf(x)


class SkillLevelHierarchy(BaseHardConstraint):
    """[H#84a1d5c9] [H#6db3f120] Hierarchical skill levels.

    No-op at CP-SAT level. The skill hierarchy is enforced by
    SkillLevelRequirement ([H#5e6ad8f4]) via threshold semantics.
    Data validation in utils.validate_staff_yaml ensures skill_tags is always
    a contiguous prefix of the hierarchy (e.g. [Acute, Resus] not [Resus]).
    This class exists only as a toggle entry in config.yaml.
    """

    constraint_id = "[H#84a1d5c9]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        pass


class NoDoubleBooking(BaseHardConstraint):
    """[H#e91c63ab] A staff member's assigned shifts must not overlap.

    Uses a precomputed 8x8 compatibility table of (shift_on_day_d,
    shift_on_day_d+1) pairs that are incompatible due to wall-clock overlap.
    """

    constraint_id = "[H#e91c63ab]"
    SHIFT_TYPES = SHIFT_ORDER

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):

        compat = self._build_compatibility_table(definitions)
        num_staff = len(staff_names)

        pos_shift: list[str] = [p["shift"] for p in positions]
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        _emit_compatibility_constraints(
            model, compat, assignments, staff_names, num_staff,
            all_dates, pos_by_date, pos_shift,
        )

    def _build_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8x8 compatibility table.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        do NOT overlap. False means they overlap and are incompatible.
        """
        from datetime import datetime, timedelta

        n = len(SHIFT_ORDER)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(SHIFT_ORDER):
            for b_idx, shift_b in enumerate(SHIFT_ORDER):
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
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
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
    SHIFT_TYPES = SHIFT_ORDER

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):

        compat = self._build_compatibility_table(definitions)
        num_staff = len(staff_names)

        pos_shift: list[str] = [p["shift"] for p in positions]
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        _emit_compatibility_constraints(
            model, compat, assignments, staff_names, num_staff,
            all_dates, pos_by_date, pos_shift,
        )

    def _build_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8x8 compatibility table.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        have a gap of at least 11 hours between them.
        """
        from datetime import datetime, timedelta

        n = len(SHIFT_ORDER)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(SHIFT_ORDER):
            for b_idx, shift_b in enumerate(SHIFT_ORDER):
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
                compat[a_idx][b_idx] = gap >= REST_PERIOD_SECONDS

        return compat


class NightToDayRest(BaseHardConstraint):
    """[H#f4c9b6c8] At least 1 full day off between night and day shifts.

    A night shift (N8/N12) on day d forbids any day shift (D8/D12/P8/P12/L3/DISCO)
    on day d+1, and vice versa. Uses a precomputed 8×8 compatibility table where
    compat[a][b] == True only when both shifts are in the same category (both
    day or both night).
    """

    constraint_id = "[H#f4c9b6c8]"
    SHIFT_TYPES = SHIFT_ORDER

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):

        compat = self._build_night_day_compatibility_table(definitions)
        num_staff = len(staff_names)

        pos_shift: list[str] = [p["shift"] for p in positions]
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        _emit_compatibility_constraints(
            model, compat, assignments, staff_names, num_staff,
            all_dates, pos_by_date, pos_shift,
        )

    def _build_night_day_compatibility_table(
        self, definitions: dict
    ) -> list[list[bool]]:
        """Build 8×8 compatibility table for night↔day transitions.

        compat[a][b] == True means shift_a on day d and shift_b on day d+1
        are in the same category (both day or both night). False means they
        are in different categories and are incompatible.
        """
        n = len(SHIFT_ORDER)
        compat: list[list[bool]] = [[True] * n for _ in range(n)]

        for a_idx, shift_a in enumerate(SHIFT_ORDER):
            for b_idx, shift_b in enumerate(SHIFT_ORDER):
                a_is_night = shift_a in NIGHT_SHIFTS
                b_is_night = shift_b in NIGHT_SHIFTS
                # Incompatible when one is night and the other is day
                if a_is_night != b_is_night:
                    compat[a_idx][b_idx] = False

        return compat


class RedRequestConstraint(BaseHardConstraint):
    """[H#a5d0c7d9] Never roster on red-requested dates."""

    constraint_id = "[H#a5d0c7d9]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
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
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
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
    """[H#f0c5b2c4] Absolute 76 paid-hour cap per 14-day block.

    Enforced in solver._create_variables() via IntVar upper bound of
    76 * SCALE on every staff-hour variable. This is a variable bound,
    not a soft constraint — the solver never produces a solution exceeding
    76 hours. The ContractedHoursFloor ([H#d9a8b7c6]) enforces the lower
    bound; this enforces the upper bound.
    """

    constraint_id = "[H#f0c5b2c4]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        # Enforced in solver._create_variables() via IntVar(0, 76*SCALE) bounds.
        pass


class ContractedHoursFloor(BaseHardConstraint):
    """[H#d9a8b7c6] Staff must meet contracted hours floor per block.

    Holidays proportionally reduce the floor; red requests do not.
    Uses precomputed adjusted_hours via utils.compute_adjusted_hours.

    NOTE: This constraint was reclassified from hard to soft (see
    ContractedHoursFloorSoft).  It remains here as a registry entry so the
    constraint ID is discoverable via get_hard_constraint_ids(), but it does
    nothing at the CP-SAT level — the soft floor handles the real logic.
    """

    constraint_id = "[H#d9a8b7c6]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        # No-op — reclassified to soft constraint (ContractedHoursFloorSoft).
        pass


class ContractedHoursFloorSoft(BaseSoftConstraint):
    """[S#d9a8b7c6] Soft contracted-hours floor — minimises shortfall fairly.

    Reclassified from [H#d9a8b7c6].  Where the total contracted-hours floor
    exceeds available roster hours (which is normal — staff headcount is
    provisioned above minimum coverage), this constraint creates a per-staff,
    per-block shortfall slack variable and penalises the total shortfall in
    the objective, distributing it as evenly as possible across all staff.

    The absolute ceiling (H#f0c5b2c4, 76h) and overtime cap (H#e8f7d6c5,
    contracted + 12h) remain as hard constraints and are unaffected by this.
    """

    constraint_id = "[S#d9a8b7c6]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):
        from utils import compute_adjusted_hours

        if staff_hours_vars is None:
            return

        self._shortfall_vars: list[list[cp_model.IntVar]] = []

        for si, staff in enumerate(staff_list):
            shortfall_row: list[cp_model.IntVar] = []
            for bi, block in enumerate(blocks):
                block_strs = [d if isinstance(d, str) else d.isoformat() for d in block]
                adj = compute_adjusted_hours(
                    staff.contracted_hours_per_fortnight,
                    staff.holidays,
                    block_strs,
                )
                # shortfall >= adjusted_hours - staff_hours, >= 0
                max_shortfall = adj  # upper bound = full adjusted hours
                sv = model.NewIntVar(0, max_shortfall,
                                     f"shortfall_{staff_names[si]}_b{bi}")
                model.Add(sv >= adj - staff_hours_vars[si][bi])
                model.Add(sv >= 0)
                shortfall_row.append(sv)
            self._shortfall_vars.append(shortfall_row)

        # Minimise sum of all shortfalls — spreads the gap fairly.
        all_shortfalls: list[cp_model.IntVar] = [
            sv for row in self._shortfall_vars for sv in row
        ]
        if all_shortfalls:
            total_shortfall = model.NewIntVar(0,
                len(all_shortfalls) * 76 * SCALE, "total_shortfall")
            model.Add(total_shortfall == sum(all_shortfalls))
            if objective_terms is not None:
                objective_terms.append(total_shortfall * weight)
            else:
                model.Minimize(total_shortfall * weight)


class OvertimeCap(BaseHardConstraint):
    """[H#e8f7d6c5] Max 12 paid hours of overtime above contracted per block."""

    constraint_id = "[H#e8f7d6c5]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, staff_hours_vars=None):
        if staff_hours_vars is None:
            return
        # Per [H#e8f7d6c5]: effective cap = min(76, contracted + 12)
        # Uses raw contracted_hours_per_fortnight (not holiday-adjusted).
        for si, staff in enumerate(staff_list):
            contracted_scaled = int(round(staff.contracted_hours_per_fortnight * SCALE))
            overtime_cap_scaled = min(76 * SCALE, contracted_scaled + 12 * SCALE)
            for bi in range(len(blocks)):
                model.Add(staff_hours_vars[si][bi] <= overtime_cap_scaled)


# ---------------------------------------------------------------------------
# Soft constraint implementations
# ---------------------------------------------------------------------------


class OvertimeDistribution(BaseSoftConstraint):
    """[S#e9b4a1b3] Distribute overtime evenly across staff.

    Penalises deviation of each staff member's overtime from the mean,
    using a scaled formulation (like WeekendFairness) that avoids division.
    Ensures extra shifts are evenly distributed between all staff.
    """

    constraint_id = "[S#e9b4a1b3]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):
        if staff_hours_vars is None:
            return

        num_staff = len(staff_names)
        num_blocks = len(blocks)

        # Compute overtime per staff per block: max(0, hours - contracted)
        # Work in whole hours (not scaled) for the fairness helper.
        overtime_vars: list[cp_model.IntVar] = []
        for si, staff in enumerate(staff_list):
            contracted_whole = int(round(staff.contracted_hours_per_fortnight))
            for bi in range(num_blocks):
                ot = model.NewIntVar(0, 76, f"ot_{staff_names[si]}_b{bi}")
                model.Add(ot >= staff_hours_vars[si][bi] // SCALE - contracted_whole)
                model.Add(ot >= 0)
                overtime_vars.append(ot)

        contracted_list = [int(round(s.contracted_hours_per_fortnight)) for s in staff_list]
        total_deviation = fair_share_deviation(
            model, overtime_vars, contracted_list, "ot_dev",
        )
        if objective_terms is not None:
            objective_terms.append(total_deviation * weight)
        else:
            model.Minimize(total_deviation * weight)


class WeekdayNightFairness(BaseSoftConstraint):
    """[S#d2a7f4a6] Equal distribution of weekday night shifts by contracted hours.

    Penalises deviation of each staff's weekday night hours from their proportional
    share based on contracted hours, per 14-day block. Uses NIGHT_SHIFTS
    from utils (N8, N12 only — DISCO is a day shift per AGENTS.md §5).

    Weekend nights (Saturday/Sunday N8/N12) are excluded because they fall under
    weekend penalty loading (which replaces night loading per EB12 rules) and are
    tracked separately by SaturdayFairness/SundayFairness. Only Monday–Friday nights
    count here — the true "most hated shift" pool that needs fair distribution.
    """

    constraint_id = "[S#d2a7f4a6]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):
        from datetime import date as date_type

        if staff_hours_vars is None:
            return

        num_staff = len(staff_names)
        num_blocks = len(blocks)

        # Build position-index → date and shift lookups
        pos_date: list[str] = [p["date"] for p in positions]

        total_night_dev = model.NewIntVar(0, num_staff * num_blocks * 76, "total_night_dev")

        for bi, block in enumerate(blocks):
            block_set = set(block)

            # Night position indices and their paid hours for this block
            # EXCLUDE weekend nights (Saturday/Sunday) per plan.md §1.3a
            night_pos_indices: list[int] = []
            night_hours: list[int] = []
            for pi, pos in enumerate(positions):
                if pos["date"] in block_set and pos["shift"] in NIGHT_SHIFTS:
                    pos_dt = date_type.fromisoformat(pos["date"])
                    if pos_dt.weekday() not in (5, 6):  # exclude Saturday/Sunday
                        night_pos_indices.append(pi)
                        paid = definitions[pos["shift"]]["paid_hours"]
                        night_hours.append(int(paid))

            if not night_pos_indices:
                continue

            # Per-staff night hours for this block (whole hours)
            staff_night_hours_block: list[cp_model.IntVar] = []
            for si in range(num_staff):
                terms = [
                    night_hours[j] * assignments[si][night_pos_indices[j]]
                    for j in range(len(night_pos_indices))
                ]
                nh = model.NewIntVar(0, 76, f"night_h_{staff_names[si]}_b{bi}")
                model.Add(nh == sum(terms))
                staff_night_hours_block.append(nh)

            # Compute proportional expected night hours per staff per block
            # target_i = round(total_pool * contracted_i / sum(contracted))
            contracted_list = [int(round(s.contracted_hours_per_fortnight)) for s in staff_list]
            night_dev_block = fair_share_deviation(
                model, staff_night_hours_block, contracted_list,
                prefix=f"night_dev_b{bi}",
            )
            total_night_dev += night_dev_block

        if num_blocks > 0:
            model.Add(total_night_dev >= 0)
        if objective_terms is not None:
            objective_terms.append(total_night_dev * weight)
        else:
            model.Minimize(total_night_dev * weight)


class SaturdayFairness(BaseSoftConstraint):
    """[S#s1a2t3u4] Share Saturday hours across staff.

    Minimizes the sum of absolute deviations of each staff member's Saturday
    hours from the mean. Saturday is the most valuable weekend day (150% loading)
    and should be distributed fairly. Replaces the blended WeekendFairness
    ([S#a1d6c3d5]) with a Saturday-specific fairness pool per plan.md §1.3b.
    """

    constraint_id = "[S#s1a2t3u4]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):

        # Identify Saturday position indices and their paid hours (whole hours)
        sat_pos_indices: list[int] = []
        sat_hours: list[int] = []
        for pi, pos in enumerate(positions):
            if pos["day_name"] == "Saturday":
                sat_pos_indices.append(pi)
                paid = definitions[pos["shift"]]["paid_hours"]
                sat_hours.append(int(paid))

        if not sat_pos_indices:
            return

        # Per-staff Saturday hours (whole hours)
        staff_sat_hours: list[cp_model.IntVar] = []
        for si in range(len(staff_names)):
            terms = [
                sat_hours[j] * assignments[si][sat_pos_indices[j]]
                for j in range(len(sat_pos_indices))
            ]
            sh = model.NewIntVar(0, 76, f"sat_h_{staff_names[si]}")
            model.Add(sh == sum(terms))
            staff_sat_hours.append(sh)

        contracted_list = [int(round(s.contracted_hours_per_fortnight)) for s in staff_list]
        total_deviation = fair_share_deviation(
            model, staff_sat_hours, contracted_list, "sat_dev",
        )
        if objective_terms is not None:
            objective_terms.append(total_deviation * weight)
        else:
            model.Minimize(total_deviation * weight)


class SundayFairness(BaseSoftConstraint):
    """[S#s2u3n4d5] Share Sunday hours across staff.

    Minimizes the sum of absolute deviations of each staff member's Sunday
    hours from the mean. Sunday is the most valuable shift day (200% loading)
    and should be distributed fairly. Replaces the blended WeekendFairness
    ([S#a1d6c3d5]) with a Sunday-specific fairness pool per plan.md §1.3b.
    """

    constraint_id = "[S#s2u3n4d5]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):

        # Identify Sunday position indices and their paid hours (whole hours)
        sun_pos_indices: list[int] = []
        sun_hours: list[int] = []
        for pi, pos in enumerate(positions):
            if pos["day_name"] == "Sunday":
                sun_pos_indices.append(pi)
                paid = definitions[pos["shift"]]["paid_hours"]
                sun_hours.append(int(paid))

        if not sun_pos_indices:
            return

        # Per-staff Sunday hours (whole hours)
        staff_sun_hours: list[cp_model.IntVar] = []
        for si in range(len(staff_names)):
            terms = [
                sun_hours[j] * assignments[si][sun_pos_indices[j]]
                for j in range(len(sun_pos_indices))
            ]
            sh = model.NewIntVar(0, 76, f"sun_h_{staff_names[si]}")
            model.Add(sh == sum(terms))
            staff_sun_hours.append(sh)

        contracted_list = [int(round(s.contracted_hours_per_fortnight)) for s in staff_list]
        total_deviation = fair_share_deviation(
            model, staff_sun_hours, contracted_list, "sun_dev",
        )
        if objective_terms is not None:
            objective_terms.append(total_deviation * weight)
        else:
            model.Minimize(total_deviation * weight)


class ConsecutiveShiftDiscouraged(BaseSoftConstraint):
    """[S#30c6f5ad] Discourage runs of consecutive same-shift days.

    Tiered penalty per run length:
      L=2: 0 (ideal)
      L=1 or L=3: 0.1 * W  (mildly discouraged)
      L=4: 1 * W  (strongly discouraged)
      L>=5: (L-3) * W  (escalating)

    Uses run_start booleans and run-length enumeration per AGENTS.md §8.
    Sub-labels: S#30c6f5ad·L=n for traceability.
    """

    constraint_id = "[S#30c6f5ad]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):

        num_staff = len(staff_names)
        num_dates = len(all_dates)

        # Build position-index → date and shift lookups
        pos_date: list[str] = [p["date"] for p in positions]
        pos_shift: list[str] = [p["shift"] for p in positions]

        # Group position indices by date
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        # SHIFT_INDEX maps shift type to an index 0-7, plus 8 = "unassigned"
        SHIFT_INDEX = {s: i for i, s in enumerate(SHIFT_ORDER)}
        UNASSIGNED = len(SHIFT_ORDER)  # 8

        # For each staff, for each date, determine which shift type they work
        # We use auxiliary IntVars: shift_type[s][d] = 0..7 for actual shifts, 8 for unassigned
        shift_type_vars: list[list[cp_model.IntVar]] = []
        for si in range(num_staff):
            row: list[cp_model.IntVar] = []
            for di in range(num_dates):
                date_str = all_dates[di]
                pos_indices = pos_by_date.get(date_str, [])
                if not pos_indices:
                    zero = model.NewIntVar(8, 8, f"shift_{staff_names[si]}_d{di}")
                    row.append(zero)
                    continue

                # shift_type = k if staff works shift k on this day, else 8 (unassigned)
                st = model.NewIntVar(0, UNASSIGNED, f"shift_{staff_names[si]}_d{di}")

                # For each shift type k in positions on this date:
                # If staff works any position with shift k, then st = k
                # We need: st == k iff any assignment BoolVar for shift k is 1
                shift_k_vars: dict[str, list[cp_model.IntVar]] = {}
                for pi in pos_indices:
                    shift_name = pos_shift[pi]
                    shift_k_vars.setdefault(shift_name, []).append(assignments[si][pi])

                shift_worked_vars: dict[str, cp_model.IntVar] = {}
                for shift_name, bool_vars in shift_k_vars.items():
                    k = SHIFT_INDEX[shift_name]
                    sw = model.NewBoolVar(f"worked_{staff_names[si]}_{date_str}_{shift_name}")
                    shift_worked_vars[shift_name] = sw
                    model.Add(sum(bool_vars) >= 1).OnlyEnforceIf(sw)
                    model.Add(sum(bool_vars) == 0).OnlyEnforceIf(sw.Not())
                    model.Add(st == k).OnlyEnforceIf(sw)
                    model.Add(st != k).OnlyEnforceIf(sw.Not())

                # If no shift is worked, st == 8
                no_work = model.NewBoolVar(f"no_work_{staff_names[si]}_{date_str}")
                model.Add(sum(shift_worked_vars.values()) == 0).OnlyEnforceIf(no_work)
                model.Add(st == UNASSIGNED).OnlyEnforceIf(no_work)

                row.append(st)
            shift_type_vars.append(row)

        # For each staff, for each consecutive day pair, compute same[d] = 1 if
        # shift_type[s][d] == shift_type[s][d+1] and both != UNASSIGNED
        same_vars: list[list[cp_model.IntVar]] = []
        for si in range(num_staff):
            row: list[cp_model.IntVar] = []
            for di in range(num_dates - 1):
                s_d = shift_type_vars[si][di]
                s_d1 = shift_type_vars[si][di + 1]
                # Three-way reification: same = 1 iff shifts equal AND both worked
                eq = model.NewBoolVar(f"eq_{staff_names[si]}_d{di}")
                model.Add(s_d == s_d1).OnlyEnforceIf(eq)
                model.Add(s_d != s_d1).OnlyEnforceIf(eq.Not())
                not_unassigned_d = model.NewBoolVar(f"not_unassigned_{staff_names[si]}_d{di}")
                not_unassigned_d1 = model.NewBoolVar(f"not_unassigned_{staff_names[si]}_d{di+1}")
                model.Add(s_d != UNASSIGNED).OnlyEnforceIf(not_unassigned_d)
                model.Add(s_d == UNASSIGNED).OnlyEnforceIf(not_unassigned_d.Not())
                model.Add(s_d1 != UNASSIGNED).OnlyEnforceIf(not_unassigned_d1)
                model.Add(s_d1 == UNASSIGNED).OnlyEnforceIf(not_unassigned_d1.Not())
                same = model.NewBoolVar(f"same_{staff_names[si]}_d{di}")
                model.AddBoolAnd([eq, not_unassigned_d, not_unassigned_d1]).OnlyEnforceIf(same)
                model.AddBoolOr([eq.Not(), not_unassigned_d.Not(), not_unassigned_d1.Not()]).OnlyEnforceIf(same.Not())
                row.append(same)
            same_vars.append(row)

        # Compute run_start[d]: 1 if day d is worked and (d-1 is unassigned or different shift)
        # run_start[0] = 1 if shift_type[0] != UNASSIGNED
        # run_start[d] = (same[d-1] == 0) AND (shift_type[d] != UNASSIGNED)
        run_start_vars: list[list[cp_model.IntVar]] = []
        for si in range(num_staff):
            row: list[cp_model.IntVar] = []
            for di in range(num_dates):
                if di == 0:
                    rs = model.NewBoolVar(f"run_start_{staff_names[si]}_d0")
                    model.Add(shift_type_vars[si][di] != UNASSIGNED).OnlyEnforceIf(rs)
                    model.Add(shift_type_vars[si][di] == UNASSIGNED).OnlyEnforceIf(rs.Not())
                else:
                    not_same = model.NewBoolVar(f"not_same_{staff_names[si]}_d{di-1}")
                    model.Add(same_vars[si][di - 1] == 0).OnlyEnforceIf(not_same)
                    model.Add(same_vars[si][di - 1] == 1).OnlyEnforceIf(not_same.Not())
                    not_unassigned = model.NewBoolVar(f"not_unassigned_{staff_names[si]}_d{di}")
                    model.Add(shift_type_vars[si][di] != UNASSIGNED).OnlyEnforceIf(not_unassigned)
                    model.Add(shift_type_vars[si][di] == UNASSIGNED).OnlyEnforceIf(not_unassigned.Not())
                    rs = model.NewBoolVar(f"run_start_{staff_names[si]}_d{di}")
                    model.Add(rs == 1).OnlyEnforceIf(not_same, not_unassigned)
                    model.Add(rs == 0).OnlyEnforceIf(not_same.Not())
                    model.Add(rs == 0).OnlyEnforceIf(not_unassigned.Not())
                row.append(rs)
            run_start_vars.append(row)

        # For each staff, enumerate run lengths and compute tiered penalties
        total_penalty = model.NewIntVar(0, num_staff * num_dates * 10 * weight, "consec_penalty")

        penalty_terms: list[cp_model.IntVar] = []
        for si in range(num_staff):
            for di in range(num_dates):
                rs = run_start_vars[si][di]
                # For each possible run length L from 1 to max_run
                max_run = num_dates - di
                for L in range(1, max_run + 1):
                    # "run of exactly L starts at di" requires:
                    # - run_start[di] = 1
                    # - same[di] = 1, same[di+1] = 1, ..., same[di+L-2] = 1 (if L >= 2)
                    # - same[di+L-1] = 0 (if L < num_dates - di), OR end of block
                    if L == 1:
                        # Same conjunction machinery as L >= 2: [rs] + (not_same_next if not end)
                        conj_bools: list[cp_model.IntVar] = [rs]
                        if di + 1 < num_dates:
                            not_same_next = model.NewBoolVar(f"not_same_next_{staff_names[si]}_d{di}")
                            model.Add(same_vars[si][di] == 0).OnlyEnforceIf(not_same_next)
                            model.Add(same_vars[si][di] == 1).OnlyEnforceIf(not_same_next.Not())
                            conj_bools.append(not_same_next)
                        exact_L = model.NewBoolVar(f"exact_L{L}_{staff_names[si]}_d{di}")
                        model.AddBoolAnd(conj_bools).OnlyEnforceIf(exact_L)
                        model.AddBoolOr([b.Not() for b in conj_bools]).OnlyEnforceIf(exact_L.Not())
                    else:
                        # Build conjunction: rs=1 AND same[di]=1 AND ... AND same[di+L-2]=1 AND (same[di+L-1]=0 OR end)
                        conj_bools: list[cp_model.IntVar] = [rs]
                        for k in range(L - 1):
                            conj_bools.append(same_vars[si][di + k])
                        if di + L < num_dates:
                            not_same_next = model.NewBoolVar(f"not_same_next_{staff_names[si]}_d{di+L-1}")
                            model.Add(same_vars[si][di + L - 1] == 0).OnlyEnforceIf(not_same_next)
                            model.Add(same_vars[si][di + L - 1] == 1).OnlyEnforceIf(not_same_next.Not())
                            conj_bools.append(not_same_next)

                        exact_L = model.NewBoolVar(f"exact_L{L}_{staff_names[si]}_d{di}")
                        model.Add(exact_L == 1).OnlyEnforceIf(*conj_bools)
                        for cb in conj_bools:
                            model.Add(exact_L == 0).OnlyEnforceIf(cb.Not())

                    # Apply tiered penalty for this run length
                    if L == 2:
                        # Ideal: no penalty
                        pass
                    elif L == 1 or L == 3:
                        # Mild: 0.1 * W — scale by 10 to keep integer: 0.1 * W * 10 = W
                        # We use W // 10 as penalty per run to avoid fractional weights
                        tier_penalty = model.NewIntVar(0, weight, f"tier_L{L}_{staff_names[si]}_d{di}")
                        model.Add(tier_penalty == weight // 10).OnlyEnforceIf(exact_L)
                        model.Add(tier_penalty == 0).OnlyEnforceIf(exact_L.Not())
                        penalty_terms.append(tier_penalty)
                    elif L == 4:
                        # Strong: 1 * W
                        tier_penalty = model.NewIntVar(0, weight, f"tier_L{L}_{staff_names[si]}_d{di}")
                        model.Add(tier_penalty == weight).OnlyEnforceIf(exact_L)
                        model.Add(tier_penalty == 0).OnlyEnforceIf(exact_L.Not())
                        penalty_terms.append(tier_penalty)
                    else:
                        # Escalating: (L-3) * W
                        esc = (L - 3) * weight
                        tier_penalty = model.NewIntVar(0, esc, f"tier_L{L}_{staff_names[si]}_d{di}")
                        model.Add(tier_penalty == esc).OnlyEnforceIf(exact_L)
                        model.Add(tier_penalty == 0).OnlyEnforceIf(exact_L.Not())
                        penalty_terms.append(tier_penalty)

        if penalty_terms:
            model.Add(total_penalty == sum(penalty_terms))
            if objective_terms is not None:
                objective_terms.append(total_penalty)
            else:
                model.Minimize(total_penalty)


class SkillLevelTiebreaker(BaseSoftConstraint):
    """[S#7b4e19fc] Prefer assigning staff at their highest skill level.

    Penalizes over-qualification: when a staff member with highest_skill_rank >
    required_rank is assigned to a position, the penalty equals the gap.
    Low weight (5) ensures it's only a tiebreaker.
    """

    constraint_id = "[S#7b4e19fc]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):

        num_staff = len(staff_names)
        num_positions = len(positions)

        # Pre-compute required_skill_rank for each position
        pos_required_rank: list[int] = [p.get("required_skill_rank", -1) for p in positions]

        # For each staff, compute over-qualification for each position
        penalty_terms: list[cp_model.IntVar] = []
        max_penalty = 0
        for si, staff in enumerate(staff_list):
            staff_rank = staff.highest_skill_rank
            for pi in range(num_positions):
                required_rank = pos_required_rank[pi]
                if required_rank < 0:
                    continue  # null requirement, no over-qualification
                if staff_rank < required_rank:
                    continue  # staff doesn't meet minimum (shouldn't happen with hard constraint)

                over_qual = staff_rank - required_rank
                if over_qual == 0:
                    continue  # exact match, no penalty
                max_penalty += over_qual

                # penalty = over_qual * assignments[si][pi]
                term = model.NewIntVar(0, over_qual, f"sq_{staff_names[si]}_{pi}")
                model.Add(term == over_qual * assignments[si][pi])
                penalty_terms.append(term)

        if penalty_terms:
            total_sq = model.NewIntVar(0, max_penalty, "skill_tiebreaker")
            model.Add(total_sq == sum(penalty_terms))
            if objective_terms is not None:
                objective_terms.append(total_sq * weight)
            else:
                model.Minimize(total_sq * weight)


class DayNightRunCountPenalty(BaseSoftConstraint):
    """[S#6c1e9a4d] Penalise excessive day/night category run counts.

    Counts separate runs of day-category and night-category shifts per staff,
    per 14-day block. Penalty = (max(0, day_run_count - 2) + max(0, night_run_count - 2)) * W.
    Only fires beyond 2 runs per category per block. Uses day/night classification
    from utils.DAY_SHIFTS/NIGHT_SHIFTS.
    """

    constraint_id = "[S#6c1e9a4d]"

    def apply(self, model, staff_list, staff_by_name, assignments, staff_names,
              definitions, all_dates, blocks, positions, weight, staff_hours_vars=None,
              objective_terms=None):

        num_staff = len(staff_names)

        # Build position-index → date and shift lookups
        pos_shift: list[str] = [p["shift"] for p in positions]

        # Group position indices by date
        pos_by_date: dict[str, list[int]] = {}
        for i, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(i)

        all_penalty_terms: list[cp_model.IntVar] = []

        for bi, block in enumerate(blocks):
            block_set = set(block)
            block_dates = [d for d in all_dates if d in block_set]
            block_size = len(block_dates)
            if block_size == 0:
                continue

            # Map date string → index within this block
            date_to_idx: dict[str, int] = {d: i for i, d in enumerate(block_dates)}

            # For each staff, for each date in block, determine category:
            # DAY=0, NIGHT=1, OFF=2
            category_vars: list[list[cp_model.IntVar]] = []
            for si in range(num_staff):
                row: list[cp_model.IntVar] = []
                for bi_di, date_str in enumerate(block_dates):
                    pos_indices = pos_by_date.get(date_str, [])
                    if not pos_indices:
                        off = model.NewIntVar(2, 2, f"cat_{staff_names[si]}_b{bi}_d{bi_di}")
                        row.append(off)
                        continue

                    cat = model.NewIntVar(0, 2, f"cat_{staff_names[si]}_b{bi}_d{bi_di}")

                    day_worked = model.NewBoolVar(f"day_worked_{staff_names[si]}_b{bi}_d{bi_di}")
                    night_worked = model.NewBoolVar(f"night_worked_{staff_names[si]}_b{bi}_d{bi_di}")

                    day_bools = [assignments[si][pi] for pi in pos_indices if pos_shift[pi] in DAY_SHIFTS]
                    if day_bools:
                        model.Add(sum(day_bools) >= 1).OnlyEnforceIf(day_worked)
                        model.Add(sum(day_bools) == 0).OnlyEnforceIf(day_worked.Not())
                    else:
                        model.Add(day_worked == 0)

                    night_bools = [assignments[si][pi] for pi in pos_indices if pos_shift[pi] in NIGHT_SHIFTS]
                    if night_bools:
                        model.Add(sum(night_bools) >= 1).OnlyEnforceIf(night_worked)
                        model.Add(sum(night_bools) == 0).OnlyEnforceIf(night_worked.Not())
                    else:
                        model.Add(night_worked == 0)

                    model.Add(cat == 0).OnlyEnforceIf(day_worked)
                    model.Add(cat == 1).OnlyEnforceIf(night_worked)
                    model.Add(cat == 2).OnlyEnforceIf(day_worked.Not(), night_worked.Not())

                    row.append(cat)
                category_vars.append(row)

            # Compute category run_start per block
            cat_run_start: list[list[cp_model.IntVar]] = []
            for si in range(num_staff):
                row: list[cp_model.IntVar] = []
                for bi_di in range(block_size):
                    if bi_di == 0:
                        rs = model.NewBoolVar(f"cat_rs_{staff_names[si]}_b{bi}_d0")
                        model.Add(category_vars[si][bi_di] != 2).OnlyEnforceIf(rs)
                        model.Add(category_vars[si][bi_di] == 2).OnlyEnforceIf(rs.Not())
                    else:
                        prev_cat = category_vars[si][bi_di - 1]
                        curr_cat = category_vars[si][bi_di]
                        different = model.NewBoolVar(f"cat_diff_{staff_names[si]}_b{bi}_d{bi_di}")
                        model.Add(prev_cat != curr_cat).OnlyEnforceIf(different)
                        model.Add(prev_cat == curr_cat).OnlyEnforceIf(different.Not())
                        worked = model.NewBoolVar(f"cat_worked_{staff_names[si]}_b{bi}_d{bi_di}")
                        model.Add(curr_cat != 2).OnlyEnforceIf(worked)
                        model.Add(curr_cat == 2).OnlyEnforceIf(worked.Not())
                        rs = model.NewBoolVar(f"cat_rs_{staff_names[si]}_b{bi}_d{bi_di}")
                        model.Add(rs == 1).OnlyEnforceIf(different, worked)
                        model.Add(rs == 0).OnlyEnforceIf(different.Not())
                        model.Add(rs == 0).OnlyEnforceIf(worked.Not())
                    row.append(rs)
                cat_run_start.append(row)

            # Compute penalties per staff for this block
            for si in range(num_staff):
                day_terms = []
                night_terms = []
                for bi_di in range(block_size):
                    rs = cat_run_start[si][bi_di]
                    cat = category_vars[si][bi_di]

                    is_day = model.NewBoolVar(f"is_day_{staff_names[si]}_b{bi}_d{bi_di}")
                    model.Add(cat == 0).OnlyEnforceIf(is_day)
                    model.Add(cat != 0).OnlyEnforceIf(is_day.Not())
                    day_term = model.NewIntVar(0, 1, f"day_term_{staff_names[si]}_b{bi}_d{bi_di}")
                    model.Add(day_term == rs).OnlyEnforceIf(is_day)
                    model.Add(day_term == 0).OnlyEnforceIf(is_day.Not())
                    day_terms.append(day_term)

                    is_night = model.NewBoolVar(f"is_night_{staff_names[si]}_b{bi}_d{bi_di}")
                    model.Add(cat == 1).OnlyEnforceIf(is_night)
                    model.Add(cat != 1).OnlyEnforceIf(is_night.Not())
                    night_term = model.NewIntVar(0, 1, f"night_term_{staff_names[si]}_b{bi}_d{bi_di}")
                    model.Add(night_term == rs).OnlyEnforceIf(is_night)
                    model.Add(night_term == 0).OnlyEnforceIf(is_night.Not())
                    night_terms.append(night_term)

                staff_day_runs = model.NewIntVar(0, block_size, f"staff_day_runs_{staff_names[si]}_b{bi}")
                staff_night_runs = model.NewIntVar(0, block_size, f"staff_night_runs_{staff_names[si]}_b{bi}")
                model.Add(staff_day_runs == sum(day_terms))
                model.Add(staff_night_runs == sum(night_terms))

                day_excess = model.NewIntVar(0, block_size, f"day_excess_{staff_names[si]}_b{bi}")
                night_excess = model.NewIntVar(0, block_size, f"night_excess_{staff_names[si]}_b{bi}")
                model.Add(day_excess >= staff_day_runs - 2)
                model.Add(day_excess >= 0)
                model.Add(night_excess >= staff_night_runs - 2)
                model.Add(night_excess >= 0)

                staff_penalty = model.NewIntVar(0, 2 * block_size, f"dn_penalty_{staff_names[si]}_b{bi}")
                model.Add(staff_penalty == day_excess + night_excess)
                all_penalty_terms.append(staff_penalty)

        if all_penalty_terms:
            total_penalty = model.NewIntVar(0, len(all_penalty_terms) * 2 * 14, "day_night_penalty")
            model.Add(total_penalty == sum(all_penalty_terms))
            if objective_terms is not None:
                objective_terms.append(total_penalty * weight)
            else:
                model.Minimize(total_penalty * weight)


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
    OvertimeCap,
]

SOFT_CONSTRAINTS = [
    ContractedHoursFloorSoft,
    OvertimeDistribution,
    WeekdayNightFairness,
    SaturdayFairness,
    SundayFairness,
    ConsecutiveShiftDiscouraged,
    DayNightRunCountPenalty,
    SkillLevelTiebreaker,
]


def get_hard_constraint_ids() -> list[str]:
    """Return the constraint_id of every registered hard constraint."""
    return [c.constraint_id for c in HARD_CONSTRAINTS]


def get_soft_constraint_ids() -> list[str]:
    """Return the constraint_id of every registered soft constraint."""
    return [c.constraint_id for c in SOFT_CONSTRAINTS]
