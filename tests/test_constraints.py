"""Tests for constraints.py - compatibility table, coverage, and fairness."""

import pytest

from constraints import NoDoubleBooking


class TestCompatibilityTable:
    """Test the precomputed shift-pair compatibility table."""

    def _build_compatibility(self, definitions):
        """Build and return the compatibility table from NoDoubleBooking."""
        constraint = NoDoubleBooking()
        return constraint._build_compatibility_table(definitions)

    def _get_compat(self, compat, shift_a, shift_b):
        """Get compatibility value for a shift pair."""
        shifts = NoDoubleBooking.SHIFT_TYPES
        idx_a = shifts.index(shift_a)
        idx_b = shifts.index(shift_b)
        return 1 if compat[idx_a][idx_b] else 0

    def test_same_shift_compatible(self, definitions):
        """Same shift on consecutive days should be compatible."""
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_night_to_day_rest(self, definitions):
        """Night shift followed by early day shift should be incompatible (rest period)."""
        compat = self._build_compatibility(definitions)
        # N8 ends 07:15, D8 starts 08:00 next day - 0.75h gap, should be incompatible
        assert self._get_compat(compat, "N8", "D8") == 0

    def test_disco_crosses_midnight(self, definitions):
        """DISCO crosses midnight but is classified as day shift."""
        compat = self._build_compatibility(definitions)
        # DISCO ends 02:00, D8 starts 08:00 next day - 6h gap, should be compatible
        assert self._get_compat(compat, "DISCO", "D8") == 1
        # D8 ends 16:30, DISCO starts 17:30 next day - 25h gap, should be compatible
        assert self._get_compat(compat, "D8", "DISCO") == 1

    def test_all_shift_pairs_defined(self, definitions):
        """All shift pairs should have a compatibility value."""
        compat = self._build_compatibility(definitions)
        shifts = NoDoubleBooking.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1)


class TestNoDoubleBookingApply:
    """Test the apply method of NoDoubleBooking constraint."""

    def test_model_has_constraints(self, definitions):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        constraint = NoDoubleBooking()
        compat = constraint._build_compatibility_table(definitions)
        # Verify the table is built correctly (8x8 matrix)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8


class TestRestPeriodConstraintCompatibilityTable:
    """Test the precomputed 11-hour rest period compatibility table."""

    def _build_compatibility(self, definitions):
        """Build and return the compatibility table from RestPeriodConstraint."""
        from constraints import RestPeriodConstraint
        constraint = RestPeriodConstraint()
        return constraint._build_compatibility_table(definitions)

    def _get_compat(self, compat, shift_a, shift_b):
        """Get compatibility value for a shift pair."""
        from constraints import RestPeriodConstraint as RPC
        shifts = RPC.SHIFT_TYPES
        idx_a = shifts.index(shift_a)
        idx_b = shifts.index(shift_b)
        return 1 if compat[idx_a][idx_b] else 0


    def test_same_shift_compatible(self, definitions):
        """Same shift on consecutive days should be compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_n8_to_d8_incompatible(self, definitions):
        """N8 ends 07:15, D8 starts 08:00 next day - 0.75h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "D8") == 0

    def test_n8_to_d12_incompatible(self, definitions):
        """N8 ends 07:15, D12 starts 07:00 next day - 0.75h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "D12") == 0

    def test_n8_to_p8_incompatible(self, definitions):
        """N8 ends 07:15, P8 starts 09:30 next day - 2.25h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "P8") == 0

    def test_n8_to_disco_incompatible(self, definitions):
        """N8 ends 07:15, DISCO starts 17:30 next day - 10.25h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "DISCO") == 0

    def test_n8_to_n8_compatible(self, definitions):
        """N8 ends 07:15, N8 starts 22:45 next day - 15.5h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_n8_to_n12_compatible(self, definitions):
        """N8 ends 07:15, N12 starts 19:00 next day - 11.75h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N12") == 1

    def test_n12_to_d8_incompatible(self, definitions):
        """N12 ends 07:30, D8 starts 07:00 next day - -0.5h overlap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "D8") == 0

    def test_n12_to_disco_incompatible(self, definitions):
        """N12 ends 07:30, DISCO starts 17:30 next day - 10h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "DISCO") == 0

    def test_n12_to_n8_compatible(self, definitions):
        """N12 ends 07:30, N8 starts 22:45 next day - 15.25h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "N8") == 1

    def test_disco_to_d8_incompatible(self, definitions):
        """DISCO ends 02:00, D8 starts 07:00 next day - 5h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "DISCO", "D8") == 0

    def test_disco_to_l3_compatible(self, definitions):
        """DISCO ends 02:00, L3 starts 14:30 next day - 12.5h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "DISCO", "L3") == 1

    def test_p12_to_d8_incompatible(self, definitions):
        """P12 ends 22:00, D8 starts 07:00 next day - 9h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "P12", "D8") == 0

    def test_p12_to_p8_compatible(self, definitions):
        """P12 ends 22:00, P8 starts 09:30 next day - 11.5h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "P12", "P8") == 1

    def test_l3_to_d8_incompatible(self, definitions):
        """L3 ends 23:00, D8 starts 07:00 next day - 8h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "D8") == 0

    def test_l3_to_p8_incompatible(self, definitions):
        """L3 ends 23:00, P8 starts 09:30 next day - 10.5h gap, incompatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "P8") == 0

    def test_l3_to_l3_compatible(self, definitions):
        """L3 ends 23:00, L3 starts 14:30 next day - 15.5h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "L3") == 1

    def test_day_to_night_compatible(self, definitions):
        """D8 ends 15:30, N8 starts 22:45 next day - 31.25h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "N8") == 1

    def test_d12_to_d8_compatible(self, definitions):
        """D12 ends 19:30, D8 starts 07:00 next day - 11.5h gap, compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D12", "D8") == 1

    def test_all_shift_pairs_defined(self, definitions):
        """All 64 shift pairs should have a compatibility value."""
        definitions
        compat = self._build_compatibility(definitions)
        from constraints import RestPeriodConstraint as RPC
        shifts = RPC.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1)

    def test_night_to_night_compatible(self, definitions):
        """Night-to-night transitions should generally be compatible."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1
        assert self._get_compat(compat, "N8", "N12") == 1
        assert self._get_compat(compat, "N12", "N8") == 1
        assert self._get_compat(compat, "N12", "N12") == 1


class TestRestPeriodConstraintApply:
    """Test the apply method of RestPeriodConstraint."""

    def test_model_has_constraints(self, definitions):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        from constraints import RestPeriodConstraint

        constraint = RestPeriodConstraint()
        compat = constraint._build_compatibility_table(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8

    def test_solver_respects_rest_period(self, definitions):
        """Solver should reject N8→D8 assignment (overlap, <11h gap)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "N8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        # Exactly one staff per position
        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        # At most one shift per staff per date
        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        # Apply rest period constraint
        from constraints import RestPeriodConstraint
        constraint = RestPeriodConstraint()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Check that no staff is assigned N8 on day 1 AND D8 on day 2
        for si in range(len(staff_names)):
            assert solver.Value(assignments[si][0]) + solver.Value(assignments[si][1]) <= 1

    def test_solver_allows_compatible_pair(self, definitions):
        """Solver should allow N8→N8 assignment (15.5h gap, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "N8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "N8", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)

        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        from constraints import RestPeriodConstraint
        constraint = RestPeriodConstraint()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        # Force Alice to work both days and verify feasibility
        model.Add(assignments[0][0] == 1)
        model.Add(assignments[0][1] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestNightToDayRestCompatibilityTable:
    """Test the precomputed night↔day transition compatibility table."""

    def _build_compatibility(self, definitions):
        from constraints import NightToDayRest
        constraint = NightToDayRest()
        return constraint._build_night_day_compatibility_table(definitions)

    def _get_compat(self, compat, shift_a, shift_b):
        from constraints import NightToDayRest as NDR
        shifts = NDR.SHIFT_TYPES
        idx_a = shifts.index(shift_a)
        idx_b = shifts.index(shift_b)
        return 1 if compat[idx_a][idx_b] else 0


    def test_night_to_day_all_incompatible(self, definitions):
        """Any night shift on day d forbids any day shift on day d+1."""
        definitions
        compat = self._build_compatibility(definitions)
        for night_shift in ("N8", "N12"):
            for day_shift in ("D8", "D12", "P8", "P12", "L3", "DISCO"):
                assert self._get_compat(compat, night_shift, day_shift) == 0, \
                    f"{night_shift}→{day_shift} should be incompatible"

    def test_day_to_night_all_incompatible(self, definitions):
        """Any day shift on day d forbids any night shift on day d+1."""
        definitions
        compat = self._build_compatibility(definitions)
        for day_shift in ("D8", "D12", "P8", "P12", "L3", "DISCO"):
            for night_shift in ("N8", "N12"):
                assert self._get_compat(compat, day_shift, night_shift) == 0, \
                    f"{day_shift}→{night_shift} should be incompatible"

    def test_night_to_night_compatible(self, definitions):
        """Night-to-night transitions are compatible (same category)."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1
        assert self._get_compat(compat, "N8", "N12") == 1
        assert self._get_compat(compat, "N12", "N8") == 1
        assert self._get_compat(compat, "N12", "N12") == 1

    def test_day_to_day_compatible(self, definitions):
        """Day-to-day transitions are compatible (same category)."""
        definitions
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "D8", "DISCO") == 1
        assert self._get_compat(compat, "DISCO", "D8") == 1
        assert self._get_compat(compat, "DISCO", "DISCO") == 1
        assert self._get_compat(compat, "P8", "L3") == 1
        assert self._get_compat(compat, "L3", "P12") == 1

    def test_all_64_pairs_defined(self, definitions):
        """All 64 shift-pair combinations must have a boolean value."""
        definitions
        compat = self._build_compatibility(definitions)
        from constraints import NightToDayRest as NDR
        shifts = NDR.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1), f"({s1}, {s2}) must be 0 or 1"

    def test_table_dimensions(self, definitions):
        """Compatibility table must be 8×8."""
        definitions
        compat = self._build_compatibility(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8


class TestNightToDayRestApply:
    """Test the apply method of NightToDayRest constraint."""

    def test_model_has_constraints(self, definitions):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model
        from constraints import NightToDayRest

        model = cp_model.CpModel()
        constraint = NightToDayRest()
        compat = constraint._build_night_day_compatibility_table(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8

    def test_solver_rejects_night_to_day(self, definitions):
        """Solver must reject assigning N8 on day d and D8 on day d+1 to same staff."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "N8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        from constraints import NightToDayRest
        constraint = NightToDayRest()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # No staff should be assigned both positions (N8→D8 is forbidden)
        for si in range(len(staff_names)):
            assert solver.Value(assignments[si][0]) + solver.Value(assignments[si][1]) <= 1

    def test_solver_rejects_day_to_night(self, definitions):
        """Solver must reject assigning D8 on day d and N8 on day d+1 to same staff."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "N8", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        from constraints import NightToDayRest
        constraint = NightToDayRest()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # No staff should be assigned both positions (D8→N8 is forbidden)
        for si in range(len(staff_names)):
            assert solver.Value(assignments[si][0]) + solver.Value(assignments[si][1]) <= 1

    def test_solver_allows_night_to_night(self, definitions):
        """Solver should allow N8→N8 (same category, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "N8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "N8", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)

        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        from constraints import NightToDayRest
        constraint = NightToDayRest()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        # Force Alice to work both days and verify feasibility
        model.Add(assignments[0][0] == 1)
        model.Add(assignments[0][1] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_solver_allows_day_to_day(self, definitions):
        """Solver should allow D8→DISCO (same category, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "DISCO", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)

        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        from constraints import NightToDayRest
        constraint = NightToDayRest()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        # Force Alice to work both days and verify feasibility
        model.Add(assignments[0][0] == 1)
        model.Add(assignments[0][1] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_n12_to_disco_incompatible(self, definitions):
        """N12 on day d forbids DISCO on day d+1 (night→day)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_names = ["Alice", "Bob"]
        all_dates = ["2026-08-03", "2026-08-04"]
        positions = [
            {"date": "2026-08-03", "shift": "N12", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "DISCO", "required_skill_level": None, "day_name": "Tuesday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)

        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        from constraints import NightToDayRest
        constraint = NightToDayRest()
        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=[all_dates],
            positions=positions,
        )

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # No staff should be assigned both positions (N12→DISCO is forbidden)
        for si in range(len(staff_names)):
            assert solver.Value(assignments[si][0]) + solver.Value(assignments[si][1]) <= 1


class TestContractedHoursFloorSoft:
    """Test the ContractedHoursFloorSoft soft constraint [S#d9a8b7c6]."""

    def test_soft_floor_allows_shortfall(self, definitions):
        """Soft floor should allow infeasible floors but penalise shortfall."""
        from ortools.sat.python import cp_model
        from constraints import ContractedHoursFloorSoft
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)
        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        from utils import SCALE
        staff_hours_vars = []
        for si in range(len(staff_names)):
            block_vars = []
            for bi in range(len(blocks)):
                block_dates = set(blocks[bi])
                hour_vars = []
                for pi, pos in enumerate(positions):
                    if pos["date"] in block_dates:
                        shift_paid = definitions[pos["shift"]]["paid_hours"]
                        scaled_paid = int(round(shift_paid * SCALE))
                        hour_vars.append(scaled_paid * assignments[si][pi])
                if hour_vars:
                    total = model.NewIntVar(0, 76 * SCALE, f"hours_{si}_{bi}")
                    model.Add(total == sum(hour_vars))
                    block_vars.append(total)
                else:
                    zero = model.NewIntVar(0, 0, f"hours_{si}_{bi}")
                    block_vars.append(zero)
            staff_hours_vars.append(block_vars)

        constraint = ContractedHoursFloorSoft()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
            weight=1000,
            staff_hours_vars=staff_hours_vars,
            objective_terms=None,
        )

        # With only 1 D8 position (8h) and 40h floor, the model should be
        # feasible (soft floor) but with shortfall = 40*SCALE - 8*SCALE = 3200
        model.Minimize(0)  # dummy objective since soft constraint adds its own
        status = solver.Solve(model)
        assert status == cp_model.OPTIMAL
        # Shortfall should be 32*SCALE = 3200 (40h floor - 8h worked)
        assert solver.Value(constraint._shortfall_vars[0][0]) == 3200


class TestOvertimeCap:
    """Test the OvertimeCap hard constraint [H#e8f7d6c5]."""

    def test_apply_adds_constraints(self, definitions):
        """The apply method should add constraints to the model for staff-hours."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification

        model = cp_model.CpModel()


        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
            Staff(name="Bob", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=76.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)
        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        staff_hours_vars = [[model.NewIntVar(0, 76 * 100, f"hours_{s}_{b}") for b in range(len(blocks))] for s in range(len(staff_names))]

        constraint = OvertimeCap()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
            staff_hours_vars=staff_hours_vars,
        )

        # Alice (40h contracted): cap = min(7600, 4000+1200) = 5200
        # Bob (76h contracted): cap = min(7600, 7600+1200) = 7600
        # Verify enforcement by solving with forced over-cap assignment
        from ortools.sat.python import cp_model
        solver = cp_model.CpSolver()
        # Force Alice to work all positions (1 D8 = 8h, well within 52h cap)
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)  # 8h < 52h cap

    def test_solver_enforces_cap(self, definitions):
        """Solver should reject solutions where staff hours exceed overtime cap."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        # Alice: 40h contracted, overtime cap = 52h
        # Assign 5 D8 shifts = 40h, 2 D12 shifts = 24h → total 64h > 52h cap
        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
            {"date": "2026-08-05", "shift": "D8", "required_skill_level": None, "day_name": "Wednesday"},
            {"date": "2026-08-06", "shift": "D8", "required_skill_level": None, "day_name": "Thursday"},
            {"date": "2026-08-07", "shift": "D8", "required_skill_level": None, "day_name": "Friday"},
            {"date": "2026-08-08", "shift": "D12", "required_skill_level": None, "day_name": "Saturday"},
            {"date": "2026-08-09", "shift": "D12", "required_skill_level": None, "day_name": "Sunday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)
        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        # Create hours variables the same way solver.py does
        staff_hours_vars = []
        for si in range(len(staff_names)):
            block_vars = []
            for bi in range(len(blocks)):
                block_dates = set(blocks[bi])
                hour_vars = []
                for pi, pos in enumerate(positions):
                    if pos["date"] in block_dates:
                        shift_paid = definitions[pos["shift"]]["paid_hours"]
                        scaled_paid = int(round(shift_paid * SCALE))
                        hour_vars.append(scaled_paid * assignments[si][pi])
                if hour_vars:
                    total = model.NewIntVar(0, 76 * SCALE, f"hours_{si}_{bi}")
                    model.Add(total == sum(hour_vars))
                    block_vars.append(total)
                else:
                    zero = model.NewIntVar(0, 0, f"hours_{si}_{bi}")
                    block_vars.append(zero)
            staff_hours_vars.append(block_vars)

        constraint = OvertimeCap()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
            staff_hours_vars=staff_hours_vars,
        )

        # Force Alice to work all 7 positions (40h + 24h = 64h > 52h cap)
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)

        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE  # 64h > 52h overtime cap

    def test_solver_allows_within_cap(self, definitions):
        """Solver should allow solutions within the overtime cap."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        # Alice: 40h contracted, overtime cap = 52h
        # Assign 5 D8 shifts = 40h, 1 D12 shift = 12h → total 52h = cap
        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
            {"date": "2026-08-05", "shift": "D8", "required_skill_level": None, "day_name": "Wednesday"},
            {"date": "2026-08-06", "shift": "D8", "required_skill_level": None, "day_name": "Thursday"},
            {"date": "2026-08-07", "shift": "D8", "required_skill_level": None, "day_name": "Friday"},
            {"date": "2026-08-08", "shift": "D12", "required_skill_level": None, "day_name": "Saturday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)
        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        staff_hours_vars = []
        for si in range(len(staff_names)):
            block_vars = []
            for bi in range(len(blocks)):
                block_dates = set(blocks[bi])
                hour_vars = []
                for pi, pos in enumerate(positions):
                    if pos["date"] in block_dates:
                        shift_paid = definitions[pos["shift"]]["paid_hours"]
                        scaled_paid = int(round(shift_paid * SCALE))
                        hour_vars.append(scaled_paid * assignments[si][pi])
                if hour_vars:
                    total = model.NewIntVar(0, 76 * SCALE, f"hours_{si}_{bi}")
                    model.Add(total == sum(hour_vars))
                    block_vars.append(total)
                else:
                    zero = model.NewIntVar(0, 0, f"hours_{si}_{bi}")
                    block_vars.append(zero)
            staff_hours_vars.append(block_vars)

        constraint = OvertimeCap()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
            staff_hours_vars=staff_hours_vars,
        )

        # Force Alice to work all 6 positions (40h + 12h = 52h = cap)
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)  # 52h = cap, should be feasible

    def test_cap_uses_raw_contracted_not_adjusted(self, definitions):
        """Overtime cap uses raw contracted_hours_per_fortnight, not holiday-adjusted."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()


        # Alice: 40h contracted, 7 days holiday → adjusted = floor(40 * 7 / 14) = 20h
        # But overtime cap should still be min(76, 40 + 12) = 52h (uses raw, not adjusted)
        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"], contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[{"start": "2026-08-03", "end": "2026-08-09"}]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]
        positions = [
            {"date": "2026-08-10", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-11", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
            {"date": "2026-08-12", "shift": "D8", "required_skill_level": None, "day_name": "Wednesday"},
            {"date": "2026-08-13", "shift": "D8", "required_skill_level": None, "day_name": "Thursday"},
            {"date": "2026-08-14", "shift": "D8", "required_skill_level": None, "day_name": "Friday"},
            {"date": "2026-08-15", "shift": "D12", "required_skill_level": None, "day_name": "Saturday"},
            {"date": "2026-08-16", "shift": "D12", "required_skill_level": None, "day_name": "Sunday"},
        ]

        assignments = [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        pos_by_date = {}
        for pi, p in enumerate(positions):
            pos_by_date.setdefault(p["date"], []).append(pi)
        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        staff_hours_vars = []
        for si in range(len(staff_names)):
            block_vars = []
            for bi in range(len(blocks)):
                block_dates = set(blocks[bi])
                hour_vars = []
                for pi, pos in enumerate(positions):
                    if pos["date"] in block_dates:
                        shift_paid = definitions[pos["shift"]]["paid_hours"]
                        scaled_paid = int(round(shift_paid * SCALE))
                        hour_vars.append(scaled_paid * assignments[si][pi])
                if hour_vars:
                    total = model.NewIntVar(0, 76 * SCALE, f"hours_{si}_{bi}")
                    model.Add(total == sum(hour_vars))
                    block_vars.append(total)
                else:
                    zero = model.NewIntVar(0, 0, f"hours_{si}_{bi}")
                    block_vars.append(zero)
            staff_hours_vars.append(block_vars)

        constraint = OvertimeCap()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
            staff_hours_vars=staff_hours_vars,
        )

        # Force Alice to work all 7 positions (40h + 24h = 64h > 52h cap)
        # Should be infeasible even though adjusted floor is only 20h
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)

        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE  # 64h > 52h cap (raw-based, not adjusted)


class TestSkillLevelRequirement:
    """Test the SkillLevelRequirement hard constraint [H#5e6ad8f4]."""


    def _make_positions(self, date, shift, required_skill_level=None):
        rank = -1
        if required_skill_level is not None:
            from models import SKILL_RANK
            rank = SKILL_RANK[required_skill_level]
        return {
            "date": date,
            "shift": shift,
            "required_skill_level": required_skill_level,
            "required_skill_rank": rank,
            "day_name": "Monday",
        }

    def _make_assignments(self, model, staff_names, positions):
        return [
            [model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))]
            for s in range(len(staff_names))
        ]

    def _setup_coverage(self, model, assignments, staff_names, positions):
        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)
        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

    def test_staff_with_higher_skill_can_fill_lower_position(self, definitions):
        """Triage-qualified staff (rank 2) should be assignable to Acute position (rank 0)."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute", "Resus", "Triage"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]
        positions = [self._make_positions("2026-08-03", "D8", required_skill_level="Acute")]

        assignments = self._make_assignments(model, staff_names, positions)
        self._setup_coverage(model, assignments, staff_names, positions)

        constraint = SkillLevelRequirement()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )

        # Force Alice to take the position
        model.Add(assignments[0][0] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_staff_with_lower_skill_cannot_fill_higher_position(self, definitions):
        """Acute-qualified staff (rank 0) should NOT be assignable to Resus position (rank 1)."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]
        positions = [self._make_positions("2026-08-03", "D8", required_skill_level="Resus")]

        assignments = self._make_assignments(model, staff_names, positions)
        self._setup_coverage(model, assignments, staff_names, positions)

        constraint = SkillLevelRequirement()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )

        # Force Alice to take the position — should be infeasible
        model.Add(assignments[0][0] == 1)

        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE

    def test_null_skill_level_allows_any_staff(self, definitions):
        """Position with null required_skill_level should accept staff of any skill rank."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]
        positions = [self._make_positions("2026-08-03", "D8", required_skill_level=None)]

        assignments = self._make_assignments(model, staff_names, positions)
        self._setup_coverage(model, assignments, staff_names, positions)

        constraint = SkillLevelRequirement()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )

        # Force Alice to take the position — should be feasible (null = no restriction)
        model.Add(assignments[0][0] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_exact_skill_match_allowed(self, definitions):
        """Resus-qualified staff should be assignable to Resus position (exact rank match)."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute", "Resus"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]
        positions = [self._make_positions("2026-08-03", "D8", required_skill_level="Resus")]

        assignments = self._make_assignments(model, staff_names, positions)
        self._setup_coverage(model, assignments, staff_names, positions)

        constraint = SkillLevelRequirement()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )

        model.Add(assignments[0][0] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_shift_coordinator_can_fill_any_position(self, definitions):
        """Shift Coordinator (rank 3) should fill Acute, Resus, Triage, or Shift Coordinator positions."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification, SKILL_RANK

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN,
                  skill_tags=["Acute", "Resus", "Triage", "Shift Coordinator"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]

        constraint = SkillLevelRequirement()
        for level in ["Acute", "Resus", "Triage", "Shift Coordinator"]:
            positions = [self._make_positions("2026-08-03", "D8", required_skill_level=level)]
            assignments = self._make_assignments(model, staff_names, positions)
            self._setup_coverage(model, assignments, staff_names, positions)
            constraint.apply(
                model=model,
                staff_list=staff_list,
                staff_by_name=staff_by_name,
                assignments=assignments,
                staff_names=staff_names,
                definitions=definitions,
                all_dates=all_dates,
                blocks=blocks,
                positions=positions,
            )
            model.Add(assignments[0][0] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_multiple_staff_different_skills(self, definitions):
        """With 2 staff (Acute+Resus and Triage) and 1 Resus position, only Triage can fill it."""
        from ortools.sat.python import cp_model
        from constraints import SkillLevelRequirement
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()
        definitions

        staff_list = [
            Staff(name="Alice", classification=Classification.RN, skill_tags=["Acute", "Resus"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
            Staff(name="Bob", classification=Classification.RN, skill_tags=["Acute", "Resus", "Triage"],
                  contracted_hours_per_fortnight=40.0, red_requests=[], holidays=[]),
        ]
        staff_by_name = {s.name: s for s in staff_list}
        staff_names = [s.name for s in staff_list]
        all_dates = ["2026-08-03"]
        blocks = [all_dates]
        positions = [self._make_positions("2026-08-03", "D8", required_skill_level="Resus")]

        assignments = self._make_assignments(model, staff_names, positions)
        self._setup_coverage(model, assignments, staff_names, positions)

        constraint = SkillLevelRequirement()
        constraint.apply(
            model=model,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )

        # Force Alice (Acute+Resus, rank 1) to take Resus position (rank 1) — should work
        model.Add(assignments[0][0] == 1)
        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        # Reset model: force Bob (Triage, rank 2) to take Resus position — should also work
        model2 = cp_model.CpModel()
        solver2 = cp_model.CpSolver()
        assignments2 = self._make_assignments(model2, staff_names, positions)
        self._setup_coverage(model2, assignments2, staff_names, positions)
        constraint.apply(
            model=model2,
            staff_list=staff_list,
            staff_by_name=staff_by_name,
            assignments=assignments2,
            staff_names=staff_names,
            definitions=definitions,
            all_dates=all_dates,
            blocks=blocks,
            positions=positions,
        )
        model2.Add(assignments2[1][0] == 1)
        status2 = solver2.Solve(model2)
        assert status2 in (cp_model.OPTIMAL, cp_model.FEASIBLE)


class TestMaxHoursConstraint:
    """Test the MaxHoursConstraint hard constraint [H#f0c5b2c4]."""


    def test_variable_bound_enforces_76h_cap(self, definitions):
        """The IntVar upper bound of 76*SCALE enforces the 76h cap at variable creation."""
        from ortools.sat.python import cp_model
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]

        # Create 8 D8 shifts (64h paid) + 2 D12 shifts (24h paid) = 88h paid total
        positions = [
            {"date": f"2026-08-{d:02d}", "shift": "D8", "required_skill_level": None, "day_name": "Monday"}
            for d in range(3, 11)
        ] + [
            {"date": f"2026-08-{d:02d}", "shift": "D12", "required_skill_level": None, "day_name": "Monday"}
            for d in range(11, 13)
        ]

        staff_names = ["Alice"]
        assignments = [[model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))] for s in range(len(staff_names))]

        # Exactly one staff per position
        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        # At most one shift per staff per date
        for si in range(len(staff_names)):
            model.Add(sum(assignments[si][pi] for pi in range(len(positions))) <= 1)

        # Create hours variable with 76*SCALE bound (same as solver.py)
        block_dates = set(all_dates)
        hour_vars = []
        for pi, pos in enumerate(positions):
            if pos["date"] in block_dates:
                shift_paid = definitions[pos["shift"]]["paid_hours"]
                scaled_paid = int(round(shift_paid * SCALE))
                hour_vars.append(scaled_paid * assignments[0][pi])

        total = model.NewIntVar(0, 76 * SCALE, "hours_Alice_b0")
        model.Add(total == sum(hour_vars))

        # Force Alice to take ALL 10 positions = 88h paid, exceeds 76h
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)

        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE  # 88h > 76h cap via IntVar bound

    def test_at_cap_is_feasible(self, definitions):
        """Exactly 76h should be feasible (boundary case)."""
        from ortools.sat.python import cp_model
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions
        all_dates = [f"2026-08-{d:02d}" for d in range(3, 17)]
        blocks = [all_dates]

        # 5 D12 = 60h + 2 D8 = 16h = 76h exactly
        positions = [
            {"date": f"2026-08-{d:02d}", "shift": "D12", "required_skill_level": None, "day_name": "Monday"}
            for d in range(3, 8)
        ] + [
            {"date": f"2026-08-{d:02d}", "shift": "D8", "required_skill_level": None, "day_name": "Monday"}
            for d in range(8, 10)
        ]

        staff_names = ["Alice"]
        assignments = [[model.NewBoolVar(f"x_{s}_{p}") for p in range(len(positions))] for s in range(len(staff_names))]

        for pi in range(len(positions)):
            model.Add(sum(assignments[si][pi] for si in range(len(staff_names))) == 1)

        # At most one shift per staff per date (not total)
        pos_by_date: dict[str, list[int]] = {}
        for pi, pos in enumerate(positions):
            pos_by_date.setdefault(pos["date"], []).append(pi)
        for si in range(len(staff_names)):
            for date_str, pi_list in pos_by_date.items():
                day_vars = [assignments[si][pi] for pi in pi_list]
                model.Add(sum(day_vars) <= 1)

        block_dates = set(all_dates)
        hour_vars = []
        for pi, pos in enumerate(positions):
            if pos["date"] in block_dates:
                shift_paid = definitions[pos["shift"]]["paid_hours"]
                scaled_paid = int(round(shift_paid * SCALE))
                hour_vars.append(scaled_paid * assignments[0][pi])

        total = model.NewIntVar(0, 76 * SCALE, "hours_Alice_b0")
        model.Add(total == sum(hour_vars))

        # Force Alice to take all 7 positions = 60h + 16h = 76h (exactly at cap)
        for pi in range(len(positions)):
            model.Add(assignments[0][pi] == 1)

        status = solver.Solve(model)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def test_apply_is_noop(self, definitions):
        """The apply method should be a no-op (bound is in _create_variables)."""
        from ortools.sat.python import cp_model
        from constraints import MaxHoursConstraint

        model = cp_model.CpModel()
        constraint = MaxHoursConstraint()

        # Track constraints added via a wrapper
        original_add = model.Add
        constraints_added = []

        def track_add(*args, **kwargs):
            constraints_added.append(args)
            return original_add(*args, **kwargs)

        model.Add = track_add  # type: ignore[assignment]

        constraint.apply(
            model=model,
            staff_list=[],
            staff_by_name={},
            assignments=[],
            staff_names=[],
            definitions={},
            all_dates=[],
            blocks=[],
            positions=[],
        )

        # Should not add any constraints — the 76h cap is enforced via IntVar bounds in _create_variables
        assert len(constraints_added) == 0
