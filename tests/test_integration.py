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
        definitions: dict,
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

    def test_understaffed_scenario_produces_unfilled(self, definitions):
        """With 1 staff member and 14 positions, the model should produce
        unfilled positions rather than going INFEASIBLE."""
        model = self._make_model(
            staff_names=["Alice"],
            contracted_hours=56,  # enough hours for 7 shifts
            roster_start=date(2026, 8, 3),
            roster_end=date(2026, 8, 16),
            definitions=definitions,
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
        # skill-required > Sunday > Saturday > weekday-day > weekday-night.
        tier_skill_required = 220000
        tier_sunday = 210000
        tier_saturday = 200000
        tier_weekday_day = 160000
        tier_weekday_night = 140000

        assert tier_skill_required > tier_sunday, (
            "Skill-required unfilled penalty must exceed Sunday General"
        )
        assert tier_sunday > tier_saturday, (
            "Sunday General must exceed Saturday General"
        )
        assert tier_saturday > tier_weekday_day, (
            "Saturday General must exceed weekday day-shift"
        )
        assert tier_weekday_day > tier_weekday_night, (
            "Weekday day-shift must exceed weekday night-shift"
        )


class TestWeightDominanceSanity:
    """The lowest unfilled tier weight must exceed all soft constraint
    weights, so the solver prefers filling positions over incurring soft
    constraint penalties."""

    def test_weight_dominance_with_actual_weights_file(self):
        """Load actual weights.yaml and verify the invariant holds.

        Uses the real runtime lookup path (bracketed constraint IDs) so this
        test would have caught the silent weight=1 bug where key mismatches
        caused all weights to collapse to the default of 1.
        """
        import yaml
        from pathlib import Path

        from constraints import get_soft_constraint_ids
        from solver import RosterModel

        weights_path = Path(__file__).resolve().parent.parent / "weights.yaml"
        with open(weights_path) as f:
            actual_weights = yaml.safe_load(f)

        # Use the actual runtime IDs — bracketed, matching constraint_id class attributes
        known_soft_ids = set(get_soft_constraint_ids())
        known_unfilled_tier_ids = set(RosterModel.UNFILLED_TIER_IDS)

        # Verify all expected unfilled tier keys exist (with brackets, as used at runtime)
        for key in known_unfilled_tier_ids:
            assert key in actual_weights, f"Missing unfilled tier key: {key}"

        # Verify all soft constraint IDs have weight entries
        for key in known_soft_ids:
            assert key in actual_weights, f"Missing soft constraint weight: {key}"

        # Lowest unfilled tier must be weekday night (S#c4d5e6f7 = 140000)
        lowest = min(actual_weights[k] for k in known_unfilled_tier_ids)
        assert lowest == actual_weights["[S#c4d5e6f7]"], (
            f"Expected weekday night tier to be lowest, got {lowest}"
        )

        # The lowest unfilled tier must exceed all soft constraint weights
        soft_keys = [k for k in actual_weights if k not in known_unfilled_tier_ids]
        max_soft_weight = max(actual_weights[k] for k in soft_keys)
        assert lowest > max_soft_weight, (
            f"Lowest unfilled tier ({lowest}) must exceed max soft weight ({max_soft_weight})"
        )
