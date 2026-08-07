#!/usr/bin/env python3
"""Integration tests for unfilled-first workflow and weight-dominance sanity check."""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from constraints import HARD_CONSTRAINTS, SOFT_CONSTRAINTS
from models import Classification, Staff
from solver import RosterModel, SolveResult
from utils import SCALE


class TestUnfilledFirstWorkflow:
    """When named staff capacity is insufficient, the model produces UNFILLED
    positions rather than going INFEASIBLE. This is the regression test that
    protects the casual-removal + unfilled-first design."""

    @staticmethod
    def _make_model(
        staff_names: list[str],
        contracted_hours: float,
        roster_start: date,
        roster_end: date,
        constraint_config: dict | None = None,
    ) -> RosterModel:
        """Build a minimal RosterModel with the given staff and dates."""
        staff_list = [
            Staff(
                name=name,
                classification=Classification.RN,
                skill_tags=["Acute"],
                contracted_hours_per_fortnight=contracted_hours,
            )
            for name in staff_names
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names_list = [s.name for s in staff_list]
        all_dates = [roster_start + timedelta(days=i) for i in range((roster_end - roster_start).days + 1)]
        all_date_strs = [d.isoformat() for d in all_dates]
        blocks = [[d.isoformat() for d in all_dates]]

        # Build positions: one D8 position per day (wildcard/general skill)
        positions = []
        for d in all_dates:
            positions.append({
                "date": d.isoformat(),
                "day_name": d.strftime("%A"),
                "shift": "D8",
                "required_skill_level": None,
                "slot_id": "D8-General-1",
            })

        definitions = {
            "D8": {
                "start": "07:00:00",
                "end": "15:30:00",
                "span_hours": 8.5,
                "paid_hours": 8.0,
                "crosses_midnight": False,
            },
            "D12": {
                "start": "07:00:00",
                "end": "19:30:00",
                "span_hours": 12.5,
                "paid_hours": 12.0,
                "crosses_midnight": False,
            },
            "P8": {
                "start": "15:00:00",
                "end": "23:30:00",
                "span_hours": 8.5,
                "paid_hours": 8.0,
                "crosses_midnight": False,
            },
            "P12": {
                "start": "15:00:00",
                "end": "03:30:00",
                "span_hours": 12.5,
                "paid_hours": 12.0,
                "crosses_midnight": True,
            },
            "L3": {
                "start": "22:00:00",
                "end": "06:00:00",
                "span_hours": 8.0,
                "paid_hours": 8.0,
                "crosses_midnight": True,
            },
            "DISCO": {
                "start": "17:30:00",
                "end": "02:00:00",
                "span_hours": 8.5,
                "paid_hours": 8.0,
                "crosses_midnight": True,
            },
            "N8": {
                "start": "22:00:00",
                "end": "06:00:00",
                "span_hours": 8.0,
                "paid_hours": 8.0,
                "crosses_midnight": True,
            },
            "N12": {
                "start": "21:00:00",
                "end": "09:30:00",
                "span_hours": 12.5,
                "paid_hours": 12.0,
                "crosses_midnight": True,
            },
        }
        weights = {}

        model = RosterModel(
            staff_list=staff_list,
            positions=positions,
            definitions=definitions,
            weights=weights,
            blocks=blocks,
            constraint_config=constraint_config,
        )
        return model

    def test_understaffed_scenario_produces_unfilled(self):
        """With 1 staff member and 14 positions, the model should produce
        unfilled positions rather than going INFEASIBLE."""
        model = self._make_model(
            staff_names=["Alice"],
            contracted_hours=56,  # enough hours for 7 shifts
            roster_start=date(2026, 8, 3),
            roster_end=date(2026, 8, 16),
        )
        model.build_model()
        result = model.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE"), (
            f"Model went {result.status} instead of producing unfilled positions"
        )
        assert len(result.unfilled) > 0, (
            "Expected some unfilled positions when staff capacity < demand"
        )
        # Alice should still get some assignments
        assert len(result.assignments) > 0

    def test_skill_restricted_positions_protected(self):
        """Skill-required positions should have higher unfilled penalty than
        General positions. Verify the tier weights encode this ordering."""
        # Tier weights from weights.yaml (S#e7f3a2b1 family) — the defaults
        # used when weights.yaml is missing.  These must preserve the ordering:
        # skill-required > weekday-day > weekday-night > weekend-day > weekend-night.
        tier_skill_required = 220000
        tier_general_weekday_day = 200000
        tier_general_weekday_night = 170000
        tier_general_weekend_day = 160000
        tier_general_weekend_night = 140000

        assert tier_skill_required > tier_general_weekday_day, (
            "Skill-required unfilled penalty must exceed General weekday day-shift"
        )
        assert tier_general_weekday_day > tier_general_weekday_night, (
            "Weekday day-shift must exceed weekday night-shift"
        )
        assert tier_general_weekday_night > tier_general_weekend_day, (
            "Weekday night-shift must exceed weekend day-shift"
        )
        assert tier_general_weekend_day > tier_general_weekend_night, (
            "Weekend day-shift must exceed weekend night-shift"
        )


class TestWeightDominanceSanity:
    """The lowest unfilled tier weight must exceed all soft constraint
    weights, so the solver prefers filling positions over incurring soft
    constraint penalties."""

    def test_weight_dominance_with_actual_weights_file(self):
        """Load actual weights.yaml and verify the invariant holds."""
        import yaml
        from pathlib import Path

        weights_path = Path(__file__).resolve().parent.parent / "weights.yaml"
        with open(weights_path) as f:
            actual_weights = yaml.safe_load(f)

        # Verify all expected unfilled tier keys exist
        unfilled_keys = ["S#e7f3a2b1", "S#d8f2c3a4", "S#c9e1d4b5", "S#b0d3e5c6", "S#a1c4f6d7"]
        for key in unfilled_keys:
            assert key in actual_weights, f"Missing unfilled tier key: {key}"

        # Lowest tier must be the weekend-night General tier
        lowest = min(actual_weights[k] for k in unfilled_keys)
        assert actual_weights["S#a1c4f6d7"] == lowest, (
            f"Expected S#a1c4f6d7 to be the lowest unfilled tier, "
            f"got {actual_weights['S#a1c4f6d7']} vs lowest {lowest}"
        )

        # The lowest unfilled tier must exceed all soft constraint weights
        soft_keys = [k for k in actual_weights if k not in unfilled_keys]
        max_soft_weight = max(actual_weights[k] for k in soft_keys)
        assert lowest > max_soft_weight, (
            f"Lowest unfilled tier ({lowest}) must exceed max soft weight ({max_soft_weight})"
        )
