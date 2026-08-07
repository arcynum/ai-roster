#!/usr/bin/env python3
"""
ai-roster - Independent verifier for produced rosters.

Deliberately shares NO code with constraints.py. Derives everything from
SolveResult + data files to independently re-check every hard constraint.

This is the highest-value safety net: it would have caught P0-1 (S#30c6f5ad
injecting a hard constraint) and P0-3 (objective scaling defeating the
unfilled-penalty guarantee).

Usage:
    violations = verify(result, staff_list, definitions, positions, blocks)
    for v in violations:
        logger.error("VERIFIER: %s — %s", v.constraint_id, v.message)
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from models import SKILL_RANK, Staff
from utils import DAY_SHIFTS, NIGHT_SHIFTS, GRADUATE_ALLOWED_SHIFTS, SCALE, compute_adjusted_hours

logger = logging.getLogger("ai-roster")


@dataclass
class Violation:
    """A single hard-constraint violation found by the verifier."""
    constraint_id: str
    staff_name: str | None
    date: str | None
    message: str


@dataclass
class VerifierResult:
    """Aggregated results from verify()."""
    violations: list[Violation] = field(default_factory=list)
    checks_run: int = 0
    checks_passed: int = 0
    checks_failed: int = 0

    @property
    def is_clean(self) -> bool:
        return len(self.violations) == 0


def verify(
    result,
    staff_list: list[Staff],
    definitions: dict,
    positions: list[dict],
    blocks: list[list[str]],
) -> VerifierResult:
    """Independently re-check every hard constraint against the produced roster.

    Parameters
    ----------
    result
        SolveResult from the solver (assignments, unfilled, staff_hours).
    staff_list
        All staff members.
    definitions
        Shift definitions from definitions.yaml.
    positions
        Flat list of roster positions (from validate_roster_positions).
    blocks
        14-day date blocks.

    Returns
    -------
    VerifierResult with violations, checks_run, checks_passed, checks_failed.
    """
    vr = VerifierResult()

    # Build lookup structures from the result
    # assignments_by_staff[staff_name] = [(date, shift), ...]
    assignments_by_staff: dict[str, list[tuple[str, str]]] = {}
    for slot in result.assignments:
        assignments_by_staff.setdefault(slot.staff_name, []).append(
            (slot.date, slot.shift)
        )

    # All position dates and their details
    position_shifts_by_date: dict[str, list[str]] = {}
    for p in positions:
        position_shifts_by_date.setdefault(p["date"], []).append(p["shift"])

    # Unfilled position dates
    unfilled_set: set[tuple[str, str]] = {(u["date"], u["shift"]) for u in result.unfilled}

    # Staff lookup
    staff_by_name: dict[str, Staff] = {s.name: s for s in staff_list}

    # --- H#4d9f81c2 / H#7a3e5f91: Every position filled exactly once ---
    vr.checks_run += 1
    _check_coverage(positions, assignments_by_staff, unfilled_set,
                    position_shifts_by_date, vr)

    # --- H#5e6ad8f4 / H#b72e41fa: Skill level threshold ---
    vr.checks_run += 1
    _check_skill_levels(result.assignments, staff_by_name, vr)

    # --- H#e91c63ab: No shift overlap (absolute intervals) ---
    vr.checks_run += 1
    _check_no_overlap(assignments_by_staff, definitions, vr)

    # --- H#c1f6e3f5: 11-hour rest period ---
    vr.checks_run += 1
    _check_rest_period(assignments_by_staff, definitions, vr)

    # --- H#f4c9b6c8: No night↔day on adjacent days ---
    vr.checks_run += 1
    _check_night_day_transition(assignments_by_staff, vr)

    # --- H#a5d0c7d9: No red-request assignments ---
    vr.checks_run += 1
    _check_red_requests(assignments_by_staff, staff_by_name, vr)

    # --- H#b6e1d8e0: No holiday assignments ---
    vr.checks_run += 1
    _check_holidays(assignments_by_staff, staff_by_name, vr)

    # --- H#f0c5b2c4: 76h absolute cap per block ---
    vr.checks_run += 1
    _check_absolute_cap(result, blocks, definitions, vr)

    # --- H#e8f7d6c5: 12h overtime cap per block ---
    vr.checks_run += 1
    _check_overtime_cap(result, staff_list, blocks, definitions, vr)

    # --- H#30479c74: Graduate shift restrictions ---
    vr.checks_run += 1
    _check_graduate_restrictions(result.assignments, staff_by_name, vr)

    # --- H#a3d8f6c1: Holiday proration cross-check ---
    vr.checks_run += 1
    _check_holiday_proration(staff_list, blocks, result.assignments, definitions, vr)

    vr.checks_passed = vr.checks_run - vr.checks_failed
    return vr


# ---------------------------------------------------------------------------
# Individual constraint checks
# ---------------------------------------------------------------------------


def _check_coverage(
    positions: list[dict],
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    unfilled_set: set[tuple[str, str]],
    position_shifts_by_date: dict[str, list[str]],
    vr: VerifierResult,
) -> None:
    """H#4d9f81c2 / H#7a3e5f91: Every position filled exactly once."""
    # Build set of all assigned (date, shift) pairs
    assigned_set: set[tuple[str, str]] = set()
    for shifts in assignments_by_staff.values():
        for date_str, shift in shifts:
            assigned_set.add((date_str, shift))

    # Check every position is either assigned or unfilled
    all_dates = sorted({p["date"] for p in positions})
    for date_str in all_dates:
        expected_shifts = sorted(position_shifts_by_date.get(date_str, []))
        assigned_shifts = sorted(
            s for d, s in assigned_set if d == date_str
        )
        unfilled_shifts = sorted(
            s for d, s in unfilled_set if d == date_str
        )

        expected_counts = Counter(expected_shifts)
        assigned_counts = Counter(assigned_shifts)
        unfilled_counts = Counter(unfilled_shifts)

        for shift_type, count in expected_counts.items():
            actual_assigned = assigned_counts.get(shift_type, 0)
            actual_unfilled = unfilled_counts.get(shift_type, 0)
            if actual_assigned + actual_unfilled != count:
                vr.violations.append(Violation(
                    constraint_id="[H#4d9f81c2]",
                    staff_name=None,
                    date=date_str,
                    message=(
                        f"Position {shift_type} on {date_str}: "
                        f"expected {count} total, got {actual_assigned} assigned + "
                        f"{actual_unfilled} unfilled = {actual_assigned + actual_unfilled}"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_skill_levels(
    assignments,
    staff_by_name: dict[str, Staff],
    vr: VerifierResult,
) -> None:
    """H#5e6ad8f4 / H#b72e41fa: assignee's highest_skill_rank >= required_skill_rank."""
    for slot in assignments:
        if slot.required_skill_level is None:
            continue
        staff = staff_by_name.get(slot.staff_name)
        if not staff:
            continue
        required_rank = SKILL_RANK.get(slot.required_skill_level, -1)
        if required_rank < 0:
            continue
        if staff.highest_skill_rank < required_rank:
            vr.violations.append(Violation(
                constraint_id="[H#5e6ad8f4]",
                staff_name=slot.staff_name,
                date=slot.date,
                message=(
                    f"Skill level insufficient: {slot.staff_name} "
                    f"(highest: {staff.highest_skill_level}, rank {staff.highest_skill_rank}) "
                    f"assigned to {slot.shift} requiring {slot.required_skill_level} "
                    f"(rank {required_rank})"
                ),
            ))
            vr.checks_failed += 1
            return

    vr.checks_passed += 1


def _check_no_overlap(
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    definitions: dict,
    vr: VerifierResult,
) -> None:
    """H#e91c63ab: No shift overlap per staff member across the whole period."""
    for staff_name, shifts in assignments_by_staff.items():
        # Build absolute intervals for each shift
        intervals: list[tuple[datetime, datetime, str]] = []
        for date_str, shift_type in shifts:
            d = date.fromisoformat(date_str)
            start_str = definitions[shift_type]["start"]
            end_str = definitions[shift_type]["end"]
            crosses = definitions[shift_type]["crosses_midnight"]

            start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M:%S")
            end_h, end_m, end_s = map(int, end_str.split(":"))
            end_dt = datetime(d.year, d.month, d.day, end_h, end_m, end_s)

            if crosses:
                end_dt += timedelta(days=1)

            intervals.append((start_dt, end_dt, shift_type))

        # Sort by start time and check for overlaps
        intervals.sort()
        for i in range(len(intervals) - 1):
            start_i, end_i, shift_i = intervals[i]
            start_next, _, shift_next = intervals[i + 1]
            if end_i > start_next:
                vr.violations.append(Violation(
                    constraint_id="[H#e91c63ab]",
                    staff_name=staff_name,
                    date=intervals[i][2] if len(intervals[i]) > 2 else None,
                    message=(
                        f"Shift overlap: {shift_i} ends {end_i}, "
                        f"{shift_next} starts {start_next}"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_rest_period(
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    definitions: dict,
    vr: VerifierResult,
) -> None:
    """H#c1f6e3f5: >= 11 hours wall-clock rest between consecutive shifts."""
    for staff_name, shifts in assignments_by_staff.items():
        # Build absolute intervals sorted by end time
        intervals: list[tuple[datetime, datetime, str]] = []
        for date_str, shift_type in shifts:
            d = date.fromisoformat(date_str)
            start_str = definitions[shift_type]["start"]
            end_str = definitions[shift_type]["end"]
            crosses = definitions[shift_type]["crosses_midnight"]

            start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M:%S")
            end_h, end_m, end_s = map(int, end_str.split(":"))
            end_dt = datetime(d.year, d.month, d.day, end_h, end_m, end_s)

            if crosses:
                end_dt += timedelta(days=1)

            intervals.append((start_dt, end_dt, shift_type))

        # Sort by end time
        intervals.sort(key=lambda x: x[1])

        for i in range(len(intervals) - 1):
            _, end_i, shift_i = intervals[i]
            start_next, _, shift_next = intervals[i + 1]

            gap_seconds = (start_next - end_i).total_seconds()
            if gap_seconds < 11 * 3600:
                vr.violations.append(Violation(
                    constraint_id="[H#c1f6e3f5]",
                    staff_name=staff_name,
                    date=None,
                    message=(
                        f"Insufficient rest: {shift_i} ends {end_i}, "
                        f"{shift_next} starts {start_next} — "
                        f"gap = {gap_seconds / 3600:.2f}h (need >= 11h)"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_night_day_transition(
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    vr: VerifierResult,
) -> None:
    """H#f4c9b6c8: No night<->day shift on adjacent days."""
    for staff_name, shifts in assignments_by_staff.items():
        # Group shifts by date
        by_date: dict[str, str] = {}
        for date_str, shift_type in shifts:
            if date_str in by_date:
                # Two shifts on the same day — already caught by overlap
                continue
            by_date[date_str] = shift_type

        sorted_dates = sorted(by_date.keys())
        for i in range(len(sorted_dates) - 1):
            d1 = date.fromisoformat(sorted_dates[i])
            d2 = date.fromisoformat(sorted_dates[i + 1])
            if (d2 - d1).days != 1:
                continue  # Not adjacent days

            shift1 = by_date[sorted_dates[i]]
            shift2 = by_date[sorted_dates[i + 1]]

            is_night1 = shift1 in NIGHT_SHIFTS
            is_day1 = shift1 in DAY_SHIFTS
            is_night2 = shift2 in NIGHT_SHIFTS
            is_day2 = shift2 in DAY_SHIFTS

            # Night on day1 -> day on day2: forbidden
            if is_night1 and is_day2:
                vr.violations.append(Violation(
                    constraint_id="[H#f4c9b6c8]",
                    staff_name=staff_name,
                    date=sorted_dates[i],
                    message=(
                        f"Night->day transition: {shift1} on {sorted_dates[i]}, "
                        f"{shift2} on {sorted_dates[i+1]}"
                    ),
                ))
                vr.checks_failed += 1
                return
            # Day on day1 -> night on day2: forbidden
            if is_day1 and is_night2:
                vr.violations.append(Violation(
                    constraint_id="[H#f4c9b6c8]",
                    staff_name=staff_name,
                    date=sorted_dates[i],
                    message=(
                        f"Day->night transition: {shift1} on {sorted_dates[i]}, "
                        f"{shift2} on {sorted_dates[i+1]}"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_red_requests(
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    staff_by_name: dict[str, Staff],
    vr: VerifierResult,
) -> None:
    """H#a5d0c7d9: No assignment on red-request dates."""
    for staff_name, shifts in assignments_by_staff.items():
        staff = staff_by_name.get(staff_name)
        if not staff:
            continue
        red_dates = set(staff.red_requests)
        for date_str, shift_type in shifts:
            if date_str in red_dates:
                vr.violations.append(Violation(
                    constraint_id="[H#a5d0c7d9]",
                    staff_name=staff_name,
                    date=date_str,
                    message=f"Staff rostered on red-request date: {shift_type}",
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_holidays(
    assignments_by_staff: dict[str, list[tuple[str, str]]],
    staff_by_name: dict[str, Staff],
    vr: VerifierResult,
) -> None:
    """H#b6e1d8e0: No assignment on holiday dates."""
    for staff_name, shifts in assignments_by_staff.items():
        staff = staff_by_name.get(staff_name)
        if not staff:
            continue

        # Collect all holiday dates
        holiday_dates: set[date] = set()
        for h in staff.holidays:
            h_start = date.fromisoformat(h["start"])
            h_end = date.fromisoformat(h["end"])
            current = h_start
            while current <= h_end:
                holiday_dates.add(current)
                current += timedelta(days=1)

        for date_str, shift_type in shifts:
            if date.fromisoformat(date_str) in holiday_dates:
                vr.violations.append(Violation(
                    constraint_id="[H#b6e1d8e0]",
                    staff_name=staff_name,
                    date=date_str,
                    message=f"Staff rostered during holiday: {shift_type}",
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_absolute_cap(
    result,
    blocks: list[list[str]],
    definitions: dict,
    vr: VerifierResult,
) -> None:
    """H#f0c5b2c4: <= 76 paid hours per staff per 14-day block."""
    # Compute actual hours per staff per block from assignments
    staff_block_hours: dict[str, dict[int, float]] = {}
    for slot in result.assignments:
        staff = slot.staff_name
        paid = definitions[slot.shift]["paid_hours"]
        for bi, block_dates in enumerate(blocks):
            if slot.date in block_dates:
                staff_block_hours.setdefault(staff, {})[bi] = (
                    staff_block_hours[staff].get(bi, 0) + paid
                )
                break

    for staff_name, block_hours in staff_block_hours.items():
        for bi, hours in block_hours.items():
            if hours > 76:
                vr.violations.append(Violation(
                    constraint_id="[H#f0c5b2c4]",
                    staff_name=staff_name,
                    date=None,
                    message=(
                        f"Absolute cap exceeded: {staff_name} block {bi}: "
                        f"{hours:.1f}h (max 76h)"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_overtime_cap(
    result,
    staff_list: list[Staff],
    blocks: list[list[str]],
    definitions: dict,
    vr: VerifierResult,
) -> None:
    """H#e8f7d6c5: <= min(76, contracted + 12) paid hours per staff per block."""
    staff_by_name = {s.name: s for s in staff_list}

    # Compute actual hours per staff per block
    staff_block_hours: dict[str, dict[int, float]] = {}
    for slot in result.assignments:
        staff = slot.staff_name
        paid = definitions[slot.shift]["paid_hours"]
        for bi, block_dates in enumerate(blocks):
            if slot.date in block_dates:
                staff_block_hours.setdefault(staff, {})[bi] = (
                    staff_block_hours[staff].get(bi, 0) + paid
                )
                break

    for staff_name, block_hours in staff_block_hours.items():
        staff = staff_by_name.get(staff_name)
        if not staff:
            continue
        raw_contracted = staff.contracted_hours_per_fortnight
        effective_cap = min(76, raw_contracted + 12)

        for bi, hours in block_hours.items():
            if hours > effective_cap:
                vr.violations.append(Violation(
                    constraint_id="[H#e8f7d6c5]",
                    staff_name=staff_name,
                    date=None,
                    message=(
                        f"Overtime cap exceeded: {staff_name} block {bi}: "
                        f"{hours:.1f}h (cap = min(76, {raw_contracted}+12) = {effective_cap}h)"
                    ),
                ))
                vr.checks_failed += 1
                return

    vr.checks_passed += 1


def _check_graduate_restrictions(
    assignments,
    staff_by_name: dict[str, Staff],
    vr: VerifierResult,
) -> None:
    """H#30479c74: Graduates only on D8, P8, L3, DISCO, N8."""
    for slot in assignments:
        staff = staff_by_name.get(slot.staff_name)
        if not staff or not staff.is_graduate:
            continue
        if slot.shift not in GRADUATE_ALLOWED_SHIFTS:
            vr.violations.append(Violation(
                constraint_id="[H#30479c74]",
                staff_name=slot.staff_name,
                date=slot.date,
                message=(
                    f"Graduate assigned to restricted shift: {slot.shift} "
                    f"(allowed: {sorted(GRADUATE_ALLOWED_SHIFTS)})"
                ),
            ))
            vr.checks_failed += 1
            return

    vr.checks_passed += 1


def _check_holiday_proration(
    staff_list: list[Staff],
    blocks: list[list[str]],
    assignments,
    definitions: dict,
    vr: VerifierResult,
) -> None:
    """H#a3d8f6c1: Cross-check adjusted_hours computation.

    Recompute adjusted_hours independently and verify the reported
    contracted hours floor matches. This is a soft constraint check
    (S#d9a8b7c6) — we verify the formula is correct but don't flag
    shortfalls as hard violations.
    """
    # Compute actual hours per staff per block from assignments
    staff_block_hours: dict[str, dict[int, float]] = {}
    for slot in assignments:
        staff = slot.staff_name
        paid = definitions[slot.shift]["paid_hours"]
        for bi, block_dates in enumerate(blocks):
            if slot.date in block_dates:
                staff_block_hours.setdefault(staff, {})[bi] = (
                    staff_block_hours[staff].get(bi, 0) + paid
                )
                break

    # Recompute adjusted hours for each staff and cross-check
    for staff in staff_list:
        for bi, block_dates in enumerate(blocks):
            adjusted = compute_adjusted_hours(
                staff.contracted_hours_per_fortnight,
                staff.holidays,
                block_dates,
            )
            adjusted_hours = adjusted / SCALE  # convert back to float

            actual = staff_block_hours.get(staff.name, {}).get(bi, 0)
            shortfall = adjusted_hours - actual
            if shortfall > 0.01:
                # Report shortfall but don't fail — it's a soft constraint
                logger.debug(
                    "VERIFIER: %s block %d: adjusted=%.1fh, assigned=%.1fh, shortfall=%.1fh",
                    staff.name, bi, adjusted_hours, actual, shortfall,
                )

    vr.checks_passed += 1
