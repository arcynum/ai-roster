#!/usr/bin/env python3
"""Tests for output.py — shift colors, overtime traffic lights, template rendering."""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from output import (
    SHIFT_COLORS,
    _build_context,
    _day_info,
    _overtime_info,
)
from models import Classification, RosterSlot, Staff
from solver import SolveResult
from utils import SHIFT_ORDER as SHIFT_TYPES


class TestShiftColors:
    """All 8 shift types must have a defined color."""

    def test_all_shifts_have_colors(self):
        for shift in SHIFT_TYPES:
            assert shift in SHIFT_COLORS, f"Missing color for {shift}"

    def test_colors_are_valid_hex(self):
        import re
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for shift, color in SHIFT_COLORS.items():
            assert hex_re.match(color), f"Invalid hex color for {shift}: {color}"

    def test_no_extra_colors(self):
        assert set(SHIFT_COLORS.keys()) == set(SHIFT_TYPES)


class TestDayInfo:
    """Day metadata for matrix headers."""

    def test_weekday(self):
        # 2026-08-03 is a Monday
        d = date(2026, 8, 3)
        info = _day_info(d)
        assert info["day"] == 3
        assert info["abbrev"] == "Mon"
        assert info["day_name"] == "Monday"
        assert info["is_weekend"] is False

    def test_weekend_saturday(self):
        d = date(2026, 8, 8)  # Saturday
        info = _day_info(d)
        assert info["abbrev"] == "Sat"
        assert info["is_weekend"] is True

    def test_weekend_sunday(self):
        d = date(2026, 8, 9)  # Sunday
        info = _day_info(d)
        assert info["abbrev"] == "Sun"
        assert info["is_weekend"] is True


class TestOvertimeTrafficLight:
    """Overtime thresholds: green <=0%, yellow 0-15%, red >15%."""

    def test_under_contracted(self):
        pct, light, badge, label = _overtime_info(40, 56)
        assert pct == 0.0
        assert light == "light-green"
        assert badge == "badge-green"
        assert label == "On track"

    def test_on_contracted(self):
        pct, light, badge, label = _overtime_info(56, 56)
        assert pct == 0.0
        assert light == "light-green"
        assert badge == "badge-green"
        assert label == "On track"

    def test_10_percent_over_yellow(self):
        # 61.6 = 56 * 1.1 -> 10% over
        pct, light, badge, label = _overtime_info(61.6, 56)
        assert pct == pytest.approx(10.0, abs=0.01)
        assert light == "light-yellow"
        assert badge == "badge-yellow"
        assert label == "+10%"

    def test_15_percent_over_yellow_boundary(self):
        # Just under 15% over (14.99%)
        pct, light, badge, label = _overtime_info(64.39, 56)
        assert pct == pytest.approx(14.98, abs=0.01)
        assert light == "light-yellow"
        assert badge == "badge-yellow"
        assert label == "+15%"

    def test_16_percent_over_red(self):
        # 16% over
        pct, light, badge, label = _overtime_info(64.96, 56)
        assert pct == pytest.approx(16.0, abs=0.01)
        assert light == "light-red"
        assert badge == "badge-red"
        assert label == "+16%"

    def test_30_percent_over_red(self):
        # 30% over
        pct, light, badge, label = _overtime_info(72.8, 56)
        assert pct == pytest.approx(30.0, abs=0.01)
        assert light == "light-red"
        assert badge == "badge-red"
        assert label == "+30%"

    def test_zero_contracted(self):
        pct, light, badge, label = _overtime_info(10, 0)
        assert pct == 0.0
        assert light == "light-green"
        assert badge == "badge-green"
        assert label == "On track"


class TestBuildContext:
    """Context dict is built correctly with all required keys."""

    def _make_staff(self, name: str, contracted: float = 56) -> Staff:
        return Staff(
            name=name,
            classification=Classification.RN,
            skill_tags=["Acute"],
            contracted_hours_per_fortnight=contracted,
        )

    def _make_result(
        self,
        staff_names: list[str],
        roster_start: date,
        roster_end: date,
    ) -> SolveResult:
        slots = []
        for si, name in enumerate(staff_names):
            for i in range(5):
                d = roster_start + timedelta(days=si * 5 + i)
                shift = SHIFT_TYPES[(si + i) % len(SHIFT_TYPES)]
                slots.append(RosterSlot(
                    staff_name=name,
                    date=d.isoformat(),
                    shift=shift,
                ))
        return SolveResult(
            status="OPTIMAL",
            objective_value=1000,
            solve_time_s=1.23,
            assignments=slots,
            unfilled=[],
        )

    def test_context_has_all_keys(self):
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice"), self._make_staff("Bob")]
        result = self._make_result(["Alice", "Bob"], start, end)
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)

        assert "generate_time" in ctx
        assert "roster_start" in ctx
        assert "roster_end" in ctx
        assert "solver_status" in ctx
        assert "objective_value" in ctx
        assert "assignments" in ctx
        assert "unfilled" in ctx
        assert "staff_list" in ctx
        assert "all_dates" in ctx
        assert "staff_matrix" in ctx
        assert "staff_info" in ctx
        assert "staff_blocks" in ctx

    def test_all_dates_count(self):
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice")]
        result = self._make_result(["Alice"], start, end)
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)
        assert len(ctx["all_dates"]) == 14

    def test_staff_matrix_has_entries(self):
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice")]
        result = self._make_result(["Alice"], start, end)
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)
        assert "Alice" in ctx["staff_matrix"]
        assert len(ctx["staff_matrix"]["Alice"]) == 14

    def test_staff_info_has_hours(self):
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice", contracted=56)]
        result = self._make_result(["Alice"], start, end)
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)
        info = ctx["staff_info"]["Alice"]
        assert info["total_hours"] > 0
        assert info["shifts"]
        assert "light_class" in info
        assert "badge_class" in info

    def test_staff_blocks_exist(self):
        start = date(2026, 8, 3)
        end = date(2026, 8, 30)
        blocks = [
            [start + timedelta(days=i) for i in range(14)],
            [start + timedelta(days=i) for i in range(14, 28)],
        ]
        staff = [self._make_staff("Alice", contracted=56)]
        result = self._make_result(["Alice"], start, end)
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)
        blocks_data = ctx["staff_blocks"]["Alice"]
        assert len(blocks_data) == 2
        assert blocks_data[0]["block_start"] == "2026-08-03"
        assert blocks_data[1]["block_start"] == "2026-08-17"

    def test_unfilled_staff_in_matrix(self):
        """Staff with no assignments should have all None in matrix."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Nobody")]
        result = SolveResult(status="OPTIMAL", assignments=[], unfilled=[])
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}

        ctx = _build_context(result, staff, definitions, start, end, blocks)
        assert all(v is None for v in ctx["staff_matrix"]["Nobody"].values())
        assert ctx["staff_info"]["Nobody"]["total_hours"] == 0
        assert ctx["staff_info"]["Nobody"]["shifts"] == []

    def test_shift_slot_tables_present(self):
        """shift_slot_tables should be in context with correct structure."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice")]
        result = SolveResult(
            status="OPTIMAL",
            assignments=[],
            unfilled=[{"date": "2026-08-03", "shift": "D8", "slot_id": "D8-General-1"}],
        )
        definitions = {s: {"paid_hours": 8.0, "crosses_midnight": False} for s in SHIFT_TYPES}
        positions = [
            {"shift": "D8", "slot_id": "D8-General-1", "date": "2026-08-03"},
            {"shift": "D12", "slot_id": "D12-General-1", "date": "2026-08-03"},
        ]

        ctx = _build_context(result, staff, definitions, start, end, blocks, positions=positions)

        assert "shift_slot_table" in ctx
        assert "slot_meta_list" in ctx
        assert "D8-General-1" in ctx["shift_slot_table"]
        assert "D12-General-1" in ctx["shift_slot_table"]
        assert ctx["shift_slot_table"]["D8-General-1"]["2026-08-03"] == "UNFILLED"
        # slot_meta_list should contain metadata for each slot
        meta_ids = {m["slot_id"] for m in ctx["slot_meta_list"]}
        assert "D8-General-1" in meta_ids
        assert "D12-General-1" in meta_ids

    def test_hours_summary_present(self):
        """hours_summary should be in context with required keys."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        blocks = [[start + timedelta(days=i) for i in range(14)]]
        staff = [self._make_staff("Alice", contracted=56)]
        result = SolveResult(status="OPTIMAL", assignments=[], unfilled=[])
        definitions = {"D8": {"paid_hours": 8.0, "crosses_midnight": False}}
        positions = [{"shift": "D8", "slot_id": "D8-General-1", "date": f"2026-08-{3+i:02d}"} for i in range(14)]

        ctx = _build_context(result, staff, definitions, start, end, blocks, positions=positions)

        assert "hours_summary" in ctx
        hs = ctx["hours_summary"]
        assert "total_required" in hs
        assert "total_available_no_overtime" in hs
        assert "total_available_with_overtime" in hs
        assert "total_surplus_no_overtime" in hs
        assert "total_surplus_with_overtime" in hs
        assert "total_no_ot_light" in hs
        assert "total_with_ot_light" in hs
        assert "blocks" in hs
        assert len(hs["blocks"]) == 1
        b = hs["blocks"][0]
        assert "required" in b
        assert "available_no_overtime" in b
        assert "available_with_overtime" in b
        assert "surplus_no_overtime" in b
        assert "surplus_with_overtime" in b
        assert "surplus_no_ot_badge" in b
        assert "surplus_with_ot_badge" in b
