#!/usr/bin/env python3
"""
Tests for verify.py — independent hard-constraint verifier.

One positive (clean) and one negative (violation) case per hard constraint.
Deliberately does NOT reuse constraints.py logic — these are independent checks.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from models import Classification, RosterSlot, Staff
from solver import SolveResult
from verify import VerifierResult, Violation, verify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Minimal 14-day block for testing
_BLOCK_DATES = [date(2026, 8, 3) + timedelta(days=i) for i in range(14)]
_BLOCK_STRS = [d.isoformat() for d in _BLOCK_DATES]


def _definitions() -> dict:
    """Real definitions from definitions.yaml."""
    from utils import load_definitions
    return load_definitions()


def _positions_single_d8() -> list[dict]:
    """One D8 position per day of a 14-day block."""
    positions = []
    for i, d in enumerate(_BLOCK_DATES):
        positions.append({
            "date": d.isoformat(),
            "day_name": d.strftime("%A"),
            "shift": "D8",
            "required_skill_level": None,
            "slot_id": "D8-General-1",
        })
    return positions


def _positions_skill_required() -> list[dict]:
    """One D8 position requiring Resus per day."""
    positions = []
    for i, d in enumerate(_BLOCK_DATES):
        positions.append({
            "date": d.isoformat(),
            "day_name": d.strftime("%A"),
            "shift": "D8",
            "required_skill_level": "Resus",
            "slot_id": "D8-Resus-1",
        })
    return positions


def _staff_alice() -> Staff:
    return Staff(
        name="Alice",
        classification=Classification.RN,
        skill_tags=["Acute", "Resus"],
        contracted_hours_per_fortnight=56.0,
    )


def _staff_bob() -> Staff:
    return Staff(
        name="Bob",
        classification=Classification.RN,
        skill_tags=["Acute"],
        contracted_hours_per_fortnight=56.0,
    )


def _staff_grad() -> Staff:
    return Staff(
        name="GradStudent",
        classification=Classification.GRADUATE,
        skill_tags=["Acute"],
        contracted_hours_per_fortnight=40.0,
    )


def _make_result(
    assignments: list[RosterSlot],
    unfilled: list[dict] | None = None,
) -> SolveResult:
    """Build a minimal SolveResult for verify()."""
    return SolveResult(
        status="OPTIMAL",
        objective_value=0,
        solve_time_s=0.1,
        assignments=assignments,
        unfilled=unfilled or [],
        staff_hours={},
        shortfall={},
        soft_penalty={},
    )


# ---------------------------------------------------------------------------
# H#4d9f81c2 / H#7a3e5f91 — Coverage
# ---------------------------------------------------------------------------


class TestCoverage:
    def test_positive_all_positions_filled(self):
        """Every position assigned once → no violations."""
        week_dates = _BLOCK_DATES[:7]
        assignments = [
            RosterSlot(staff_name="Alice", date=d.isoformat(), shift="D8")
            for d in week_dates
        ]
        positions = [
            {"date": d.isoformat(), "day_name": d.strftime("%A"), "shift": "D8",
             "required_skill_level": None, "slot_id": "D8-General-1"}
            for d in week_dates
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            positions,
            [_BLOCK_STRS],
        )
        assert vr.is_clean, f"Expected clean, got violations: {[v.message for v in vr.violations]}"

    def test_negative_missing_position(self):
        """One position not filled and not unfilled → violation."""
        assignments = [
            RosterSlot(staff_name="Alice", date=d.isoformat(), shift="D8")
            for d in _BLOCK_DATES[:13]
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            _positions_single_d8(),
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("Position D8 on" in v.message for v in vr.violations)


# ---------------------------------------------------------------------------
# H#5e6ad8f4 / H#b72e41fa — Skill level threshold
# ---------------------------------------------------------------------------


class TestSkillLevels:
    def test_positive_skill_sufficient(self):
        """Resus-skilled staff on Resus-required shift → clean."""
        week_dates = _BLOCK_DATES[:7]
        assignments = [
            RosterSlot(staff_name="Alice", date=d.isoformat(), shift="D8",
                       required_skill_level="Resus")
            for d in week_dates
        ]
        positions = [
            {"date": d.isoformat(), "day_name": d.strftime("%A"), "shift": "D8",
             "required_skill_level": "Resus", "slot_id": "D8-Resus-1"}
            for d in week_dates
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            positions,
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_skill_insufficient(self):
        """Acute-only staff on Resus-required shift → violation."""
        assignments = [
            RosterSlot(staff_name="Bob", date=d.isoformat(), shift="D8",
                       required_skill_level="Resus")
            for d in _BLOCK_DATES[:1]
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_bob()],
            _definitions(),
            _positions_skill_required(),
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("Skill level insufficient" in v.message for v in vr.violations)


# ---------------------------------------------------------------------------
# H#e91c63ab — No shift overlap
# ---------------------------------------------------------------------------


class TestNoOverlap:
    def test_positive_no_overlap(self):
        """D8 then P8 on consecutive days → clean."""
        d1 = _BLOCK_DATES[0]
        d2 = _BLOCK_DATES[1]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="D8"),
            RosterSlot(staff_name="Alice", date=d2.isoformat(), shift="P8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
                {"date": d2.isoformat(), "day_name": "Tuesday", "shift": "P8",
                 "required_skill_level": None, "slot_id": "P8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_overlap_same_day(self):
        """Two shifts on the same day → overlap violation."""
        d1 = _BLOCK_DATES[0]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="D8"),
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="P8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "P8",
                 "required_skill_level": None, "slot_id": "P8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("overlap" in v.message.lower() for v in vr.violations)


# ---------------------------------------------------------------------------
# H#c1f6e3f5 — 11-hour rest period
# ---------------------------------------------------------------------------


class TestRestPeriod:
    def test_positive_adequate_rest(self):
        """D8 then D8 next day → 15h gap, clean."""
        d1 = _BLOCK_DATES[0]
        d2 = _BLOCK_DATES[1]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="D8"),
            RosterSlot(staff_name="Alice", date=d2.isoformat(), shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
                {"date": d2.isoformat(), "day_name": "Tuesday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_insufficient_rest(self):
        """D8 ends 15:30, P8 starts 15:00 same day → insufficient rest."""
        d1 = _BLOCK_DATES[0]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="D8"),
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="P8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "P8",
                 "required_skill_level": None, "slot_id": "P8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("rest" in v.message.lower() or "overlap" in v.message.lower()
                   for v in vr.violations)


# ---------------------------------------------------------------------------
# H#f4c9b6c8 — No night↔day on adjacent days
# ---------------------------------------------------------------------------


class TestNightDayTransition:
    def test_positive_day_to_day(self):
        """D8 on Monday, D8 on Tuesday → clean."""
        d1 = _BLOCK_DATES[0]
        d2 = _BLOCK_DATES[1]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="D8"),
            RosterSlot(staff_name="Alice", date=d2.isoformat(), shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
                {"date": d2.isoformat(), "day_name": "Tuesday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_night_to_day(self):
        """N8 on Monday, D8 on Tuesday → violation."""
        d1 = _BLOCK_DATES[0]
        d2 = _BLOCK_DATES[1]
        assignments = [
            RosterSlot(staff_name="Alice", date=d1.isoformat(), shift="N8"),
            RosterSlot(staff_name="Alice", date=d2.isoformat(), shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": d1.isoformat(), "day_name": "Monday", "shift": "N8",
                 "required_skill_level": None, "slot_id": "N8-1"},
                {"date": d2.isoformat(), "day_name": "Tuesday", "shift": "D8",
                 "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("transition" in v.message.lower() for v in vr.violations)


# ---------------------------------------------------------------------------
# H#a5d0c7d9 — No red-request assignments
# ---------------------------------------------------------------------------


class TestRedRequests:
    def test_positive_no_red_conflict(self):
        """Alice has no red requests, assigned freely → clean."""
        assignments = [
            RosterSlot(staff_name="Alice", date=_BLOCK_DATES[0].isoformat(), shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[0].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_on_red_request(self):
        """Alice red-requests 2026-08-03, assigned that day → violation."""
        alice = Staff(
            name="Alice",
            classification=Classification.RN,
            skill_tags=["Acute", "Resus"],
            contracted_hours_per_fortnight=56.0,
            red_requests=["2026-08-03"],
        )
        assignments = [
            RosterSlot(staff_name="Alice", date="2026-08-03", shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [alice],
            _definitions(),
            [
                {"date": "2026-08-03", "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("red-request" in v.message.lower() for v in vr.violations)


# ---------------------------------------------------------------------------
# H#b6e1d8e0 — No holiday assignments
# ---------------------------------------------------------------------------


class TestHolidays:
    def test_positive_no_holiday_conflict(self):
        """Alice on holiday 08-05 to 08-07, assigned 08-03 → clean."""
        alice = Staff(
            name="Alice",
            classification=Classification.RN,
            skill_tags=["Acute", "Resus"],
            contracted_hours_per_fortnight=56.0,
            holidays=[{"start": "2026-08-05", "end": "2026-08-07"}],
        )
        assignments = [
            RosterSlot(staff_name="Alice", date="2026-08-03", shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [alice],
            _definitions(),
            [
                {"date": "2026-08-03", "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_on_holiday(self):
        """Alice on holiday 08-05 to 08-07, assigned 08-06 → violation."""
        alice = Staff(
            name="Alice",
            classification=Classification.RN,
            skill_tags=["Acute", "Resus"],
            contracted_hours_per_fortnight=56.0,
            holidays=[{"start": "2026-08-05", "end": "2026-08-07"}],
        )
        assignments = [
            RosterSlot(staff_name="Alice", date="2026-08-06", shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [alice],
            _definitions(),
            [
                {"date": "2026-08-06", "day_name": "Wednesday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("holiday" in v.message.lower() for v in vr.violations)


# ---------------------------------------------------------------------------
# H#f0c5b2c4 — 76h absolute cap per block
# ---------------------------------------------------------------------------


class TestAbsoluteCap:
    def test_positive_within_cap(self):
        """Alice 5 shifts × 8h = 40h in block → clean."""
        assignments = [
            RosterSlot(staff_name="Alice", date=_BLOCK_DATES[i].isoformat(), shift="D8")
            for i in range(5)
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[i].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"}
                for i in range(5)
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_exceeds_76h(self):
        """Alice 10 shifts × 8h = 80h in block → violation."""
        assignments = [
            RosterSlot(staff_name="Alice", date=_BLOCK_DATES[i].isoformat(), shift="D8")
            for i in range(10)
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[i].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"}
                for i in range(10)
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("Absolute cap exceeded" in v.message for v in vr.violations)


# ---------------------------------------------------------------------------
# H#e8f7d6c5 — 12h overtime cap per block
# ---------------------------------------------------------------------------


class TestOvertimeCap:
    def test_positive_within_overtime_cap(self):
        """Alice contracted 56h, assigned 56h → clean."""
        assignments = [
            RosterSlot(staff_name="Alice", date=_BLOCK_DATES[i].isoformat(), shift="D8")
            for i in range(7)
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_alice()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[i].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"}
                for i in range(7)
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_exceeds_overtime_cap(self):
        """Alice contracted 40h, cap = 52h, assigned 60h → violation."""
        alice = Staff(
            name="Alice",
            classification=Classification.RN,
            skill_tags=["Acute", "Resus"],
            contracted_hours_per_fortnight=40.0,
        )
        # 7.5 D8 shifts = 60h > min(76, 40+12=52)
        assignments = [
            RosterSlot(staff_name="Alice", date=_BLOCK_DATES[i].isoformat(), shift="D8")
            for i in range(7)
        ]
        vr = verify(
            _make_result(assignments),
            [alice],
            _definitions(),
            [
                {"date": _BLOCK_DATES[i].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"}
                for i in range(7)
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("Overtime cap exceeded" in v.message for v in vr.violations)


# ---------------------------------------------------------------------------
# H#30479c74 — Graduate shift restrictions
# ---------------------------------------------------------------------------


class TestGraduateRestrictions:
    def test_positive_graduate_allowed_shift(self):
        """Graduate on D8 (allowed) → clean."""
        assignments = [
            RosterSlot(staff_name="GradStudent", date=_BLOCK_DATES[0].isoformat(), shift="D8"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_grad()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[0].isoformat(), "day_name": "Monday",
                 "shift": "D8", "required_skill_level": None, "slot_id": "D8-1"},
            ],
            [_BLOCK_STRS],
        )
        assert vr.is_clean

    def test_negative_graduate_restricted_shift(self):
        """Graduate on N12 (not allowed) → violation."""
        assignments = [
            RosterSlot(staff_name="GradStudent", date=_BLOCK_DATES[0].isoformat(), shift="N12"),
        ]
        vr = verify(
            _make_result(assignments),
            [_staff_grad()],
            _definitions(),
            [
                {"date": _BLOCK_DATES[0].isoformat(), "day_name": "Monday",
                 "shift": "N12", "required_skill_level": None, "slot_id": "N12-1"},
            ],
            [_BLOCK_STRS],
        )
        assert not vr.is_clean
        assert any("Graduate" in v.message and "restricted" in v.message for v in vr.violations)


# ---------------------------------------------------------------------------
# H#a3d8f6c1 — Holiday proration cross-check (soft constraint, never fails)
# ---------------------------------------------------------------------------


class TestHolidayProration:
    def test_positive_proration_computed(self):
        """Proration check never produces violations (soft constraint)."""
        holiday_start = date(2026, 8, 5)
        alice = Staff(
            name="Alice",
            classification=Classification.RN,
            skill_tags=["Acute", "Resus"],
            contracted_hours_per_fortnight=56.0,
            holidays=[{"start": "2026-08-05", "end": "2026-08-05"}],
        )
        # Assign Alice on all non-holiday days (13 days × 8h = 104h, but only 7 shifts to stay under cap)
        assignments = [
            RosterSlot(staff_name="Alice", date=d.isoformat(), shift="D8")
            for d in _BLOCK_DATES if d != holiday_start
        ][:7]
        positions = [
            {"date": a.date, "day_name": date.fromisoformat(a.date).strftime("%A"),
             "shift": "D8", "required_skill_level": None, "slot_id": "D8-General-1"}
            for a in assignments
        ]
        vr = verify(
            _make_result(assignments),
            [alice],
            _definitions(),
            positions,
            [_BLOCK_STRS],
        )
        assert vr.is_clean


# ---------------------------------------------------------------------------
# VerifierResult
# ---------------------------------------------------------------------------


class TestVerifierResult:
    def test_is_clean_with_no_violations(self):
        vr = VerifierResult(violations=[])
        assert vr.is_clean

    def test_is_not_clean_with_violations(self):
        vr = VerifierResult(violations=[
            Violation(
                constraint_id="[H#test]", staff_name=None, date=None, message="test"
            )
        ])
        assert not vr.is_clean

    def test_checks_counters(self):
        vr = VerifierResult(checks_run=10, checks_passed=9, checks_failed=1)
        assert vr.checks_run == 10
        assert vr.checks_passed == 9
        assert vr.checks_failed == 1
        assert not vr.is_clean
