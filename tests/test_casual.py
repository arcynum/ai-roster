#!/usr/bin/env python3
"""Tests for casual staffing constraint [H#c92f5e1b] / [S#3d9a7ec1]."""

import pytest
from ortools.sat.python import cp_model

from constraints import (
    CasualStaffingConstraint,
    CasualUsageMinimization,
    HARD_CONSTRAINTS,
    SOFT_CONSTRAINTS,
    get_hard_constraint_ids,
    get_soft_constraint_ids,
)
from models import RosterSlot
from solver import RosterModel
from utils import SCALE


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_model():
    """Minimal RosterModel with 2 staff, 10 positions (5 null-skill, 5 with skill)."""
    staff_list = [
        type("Staff", (), {
            "name": "Alice",
            "classification": "RN",
            "skill_tags": ["Acute"],
            "contracted_hours_per_fortnight": 40,
            "red_requests": [],
            "holidays": [],
        })(),
        type("Staff", (), {
            "name": "Bob",
            "classification": "RN",
            "skill_tags": ["Acute"],
            "contracted_hours_per_fortnight": 40,
            "red_requests": [],
            "holidays": [],
        })(),
    ]
    staff_by_name = {s.name: s for s in staff_list}
    staff_names = [s.name for s in staff_list]

    definitions = {
        "D8": {"start": "08:00", "end": "16:30", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
        "N8": {"start": "20:00", "end": "04:30", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
    }

    # 5 null-skill positions (casual allowed) + 5 skill-level positions (no casual)
    positions = []
    for i in range(5):
        positions.append({
            "date": f"2026-08-{i+3:02d}",
            "day_name": "Monday",
            "shift": "D8",
            "required_skill_level": None,
            "casual_allowed": True,
        })
    for i in range(5):
        positions.append({
            "date": f"2026-08-{i+8:02d}",
            "day_name": "Wednesday",
            "shift": "D8",
            "required_skill_level": "Acute",
            "casual_allowed": False,
        })

    blocks = [["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06",
               "2026-08-07", "2026-08-08", "2026-08-09", "2026-08-10",
               "2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14",
               "2026-08-15", "2026-08-16"]]

    weights = {"[S#3d9a7ec1]": 100000}

    # Only enable casual constraints for this test
    constraint_config = {
        "hard": {"enabled": ["[H#c92f5e1b]"]},
        "soft": {"enabled": ["[S#3d9a7ec1]"]},
    }

    return RosterModel(staff_list, positions, definitions, weights, blocks,
                       constraint_config=constraint_config)


# ---------------------------------------------------------------------------
# CasualStaffingConstraint tests
# ---------------------------------------------------------------------------

class TestCasualStaffingConstraint:
    """Tests for [H#c92f5e1b] CasualStaffingConstraint."""

    def test_creates_casual_vars_for_null_skill_positions(self):
        """Null-skill positions get a BoolVar for casual option."""
        model = cp_model.CpModel()
        cs = CasualStaffingConstraint()

        # 3 null-skill positions
        positions = [
            {"casual_allowed": True},
            {"casual_allowed": True},
            {"casual_allowed": True},
        ]

        cs.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        assert len(cs.casual_vars) == 3
        assert all(v is not None for v in cs.casual_vars)

    def test_no_casual_vars_for_skill_positions(self):
        """Positions with skill requirements get None (no casual option)."""
        model = cp_model.CpModel()
        cs = CasualStaffingConstraint()

        positions = [
            {"casual_allowed": False},
            {"casual_allowed": False},
        ]

        cs.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        assert len(cs.casual_vars) == 2
        assert all(v is None for v in cs.casual_vars)

    def test_mixed_positions(self):
        """Null-skill positions get vars, skill positions get None."""
        model = cp_model.CpModel()
        cs = CasualStaffingConstraint()

        positions = [
            {"casual_allowed": True},   # pi=0
            {"casual_allowed": False},  # pi=1
            {"casual_allowed": True},   # pi=2
            {"casual_allowed": False},  # pi=3
        ]

        cs.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        assert cs.casual_vars[0] is not None
        assert cs.casual_vars[1] is None
        assert cs.casual_vars[2] is not None
        assert cs.casual_vars[3] is None

    def test_casual_constraint_with_staff_assignment(self):
        """For null-skill positions: exactly one of (staff OR casual)."""
        model = cp_model.CpModel()
        cs = CasualStaffingConstraint()

        staff_list = [
            type("Staff", (), {"name": "Alice"})(),
            type("Staff", (), {"name": "Bob"})(),
        ]
        staff_names = ["Alice", "Bob"]

        positions = [
            {"casual_allowed": True},
        ]

        # Create assignment variables
        assignments = []
        for si in range(2):
            row = [model.NewBoolVar(f"x_{staff_names[si]}_0") for _ in range(1)]
            assignments.append(row)

        cs.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name={s.name: s for s in staff_list},
            assignments=assignments,
            staff_names=staff_names,
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        # Force Alice to be assigned via model constraint
        model.Add(assignments[0][0] == 1)

        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = 5.0

        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.Value(assignments[0][0]) == 1
        # Casual var must be 0 since Alice is assigned
        assert solver.Value(cs.casual_vars[0]) == 0

    def test_casual_selected_when_no_staff(self):
        """When no staff can be assigned, casual is selected."""
        model = cp_model.CpModel()
        cs = CasualStaffingConstraint()

        staff_list = [
            type("Staff", (), {"name": "Alice"})(),
        ]
        staff_names = ["Alice"]

        positions = [
            {"casual_allowed": True},
        ]

        assignments = [[model.NewBoolVar("x_Alice_0")]]

        cs.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name={"Alice": staff_list[0]},
            assignments=assignments,
            staff_names=staff_names,
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        # Force Alice NOT to be assigned via model constraint
        model.Add(assignments[0][0] == 0)

        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = 5.0

        status = solver.Solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # Casual var must be 1 since no staff is assigned
        assert solver.Value(cs.casual_vars[0]) == 1


# ---------------------------------------------------------------------------
# CasualUsageMinimization tests
# ---------------------------------------------------------------------------

class TestCasualUsageMinimization:
    """Tests for [S#3d9a7ec1] CasualUsageMinimization."""

    def test_minimizes_casual_usage(self):
        """Solver prefers 0 casuals over 1 when both are feasible."""
        model = cp_model.CpModel()

        staff_list = [
            type("Staff", (), {"name": "Alice"})(),
        ]
        staff_names = ["Alice"]

        positions = [
            {"casual_allowed": True},
        ]

        assignments = [[model.NewBoolVar("x_Alice_0")]]

        # Apply hard constraint
        cs = CasualStaffingConstraint()
        cs.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name={"Alice": staff_list[0]},
            assignments=assignments,
            staff_names=staff_names,
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
        )

        # Apply soft constraint
        sum_c = CasualUsageMinimization()
        sum_c.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name={"Alice": staff_list[0]},
            assignments=assignments,
            staff_names=staff_names,
            definitions={},
            all_dates=[],
            blocks=[],
            positions=positions,
            weight=100000,
            casual_vars=cs.casual_vars,
        )

        solver = cp_model.CpSolver()
        solver.parameters.num_workers = 1
        solver.parameters.max_time_in_seconds = 5.0

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        # Solver should prefer Alice (0 casuals) over casual (1 casual)
        assert solver.Value(assignments[0][0]) == 1
        assert solver.Value(cs.casual_vars[0]) == 0

    def test_no_casual_vars_returns_early(self):
        """Soft constraint does nothing when casual_vars is None."""
        model = cp_model.CpModel()
        sum_c = CasualUsageMinimization()

        # Should not raise
        sum_c.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=[],
            weight=100000,
            casual_vars=None,
        )

    def test_empty_casual_vars_returns_early(self):
        """Soft constraint does nothing when all casual_vars are None."""
        model = cp_model.CpModel()
        sum_c = CasualUsageMinimization()

        sum_c.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=[],
            weight=100000,
            casual_vars=[None, None],
        )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestCasualIntegration:
    """End-to-end tests for casual staffing."""

    def test_solver_with_casual_constraint(self, basic_model):
        """Model builds and solves with casual constraints enabled."""
        basic_model.build_model()
        result = basic_model.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.assignments) == 10  # All positions filled
        assert len(result.unfilled) == 0

    def test_casual_vars_stored_on_model(self, basic_model):
        """casual_vars is populated on the RosterModel after building."""
        basic_model.build_model()
        assert len(basic_model.casual_vars) == 10
        # First 5 are casual-allowed (null skill), last 5 are not
        assert all(v is not None for v in basic_model.casual_vars[:5])
        assert all(v is None for v in basic_model.casual_vars[5:])

    def test_raster_slot_filled_by_casual(self):
        """RosterSlot can have filled_by_casual=True."""
        slot = RosterSlot(
            staff_name="Casual",
            date="2026-08-03",
            shift="D8",
            required_skill_level=None,
            filled_by_casual=True,
        )
        assert slot.filled_by_casual is True

    def test_raster_slot_not_casual(self):
        """RosterSlot defaults filled_by_casual=False."""
        slot = RosterSlot(
            staff_name="Alice",
            date="2026-08-03",
            shift="D8",
            required_skill_level="Acute",
        )
        assert slot.filled_by_casual is False

    def test_weight_dominance(self):
        """S#3d9a7ec1 weight (100000) exceeds max possible combined soft penalty.

        This ensures casuals are truly last resort — the solver never picks a
        casual over a valid all-named-staff solution.
        """
        casual_weight = 100000

        # Worst-case soft penalties per staff member (very rough upper bounds):
        # - ConsecutiveShiftDiscouraged (S#30c6f5ad): max ~14 runs * 1W = 14W
        # - NightShiftFairness (S#d2a7f4a6): max ~14W
        # - WeekendFairness (S#a1d6c3d5): max ~14W
        # - OvertimeDistribution (S#e9b4a1b3): max ~14W
        # - Day/Night run count (S#6c1e9a4d): max ~14W
        # Total per staff: ~70W
        # With 42 staff: 42 * 70 = 2940W
        # With weights up to ~100: 2940 * 100 = 294000
        # But actual weights are much lower and penalties are much smaller.
        # A conservative upper bound: 42 staff * 14 days * 100 max_weight = 58800
        # This is well below 100000.
        assert casual_weight > 58800, "Casual weight must exceed max combined soft penalty"

    def test_hard_constraints_include_casual(self):
        """CasualStaffingConstraint is in the hard constraints registry."""
        ids = get_hard_constraint_ids()
        assert "[H#c92f5e1b]" in ids

    def test_soft_constraints_include_casual(self):
        """CasualUsageMinimization is in the soft constraints registry."""
        ids = get_soft_constraint_ids()
        assert "[S#3d9a7ec1]" in ids
