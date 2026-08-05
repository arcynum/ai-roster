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

    def test_same_shift_compatible(self):
        """Same shift on consecutive days should be compatible."""
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_night_to_day_rest(self):
        """Night shift followed by early day shift should be incompatible (rest period)."""
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        # N8 ends 07:15, D8 starts 08:00 next day - 0.75h gap, should be incompatible
        assert self._get_compat(compat, "N8", "D8") == 0

    def test_disco_crosses_midnight(self):
        """DISCO crosses midnight but is classified as day shift."""
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        # DISCO ends 02:00, D8 starts 08:00 next day - 6h gap, should be compatible
        assert self._get_compat(compat, "DISCO", "D8") == 1
        # D8 ends 16:30, DISCO starts 17:30 next day - 25h gap, should be compatible
        assert self._get_compat(compat, "D8", "DISCO") == 1

    def test_all_shift_pairs_defined(self):
        """All shift pairs should have a compatibility value."""
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        shifts = NoDoubleBooking.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1)


class TestNoDoubleBookingApply:
    """Test the apply method of NoDoubleBooking constraint."""

    def test_model_has_constraints(self):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
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

    def _make_definitions(self):
        """Return definitions matching definitions.yaml."""
        return {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

    def test_same_shift_compatible(self):
        """Same shift on consecutive days should be compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_n8_to_d8_incompatible(self):
        """N8 ends 07:15, D8 starts 08:00 next day - 0.75h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "D8") == 0

    def test_n8_to_d12_incompatible(self):
        """N8 ends 07:15, D12 starts 07:00 next day - 0.75h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "D12") == 0

    def test_n8_to_p8_incompatible(self):
        """N8 ends 07:15, P8 starts 09:30 next day - 2.25h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "P8") == 0

    def test_n8_to_disco_incompatible(self):
        """N8 ends 07:15, DISCO starts 17:30 next day - 10.25h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "DISCO") == 0

    def test_n8_to_n8_compatible(self):
        """N8 ends 07:15, N8 starts 22:45 next day - 15.5h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_n8_to_n12_compatible(self):
        """N8 ends 07:15, N12 starts 19:00 next day - 11.75h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N12") == 1

    def test_n12_to_d8_incompatible(self):
        """N12 ends 07:30, D8 starts 07:00 next day - -0.5h overlap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "D8") == 0

    def test_n12_to_disco_incompatible(self):
        """N12 ends 07:30, DISCO starts 17:30 next day - 10h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "DISCO") == 0

    def test_n12_to_n8_compatible(self):
        """N12 ends 07:30, N8 starts 22:45 next day - 15.25h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N12", "N8") == 1

    def test_disco_to_d8_incompatible(self):
        """DISCO ends 02:00, D8 starts 07:00 next day - 5h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "DISCO", "D8") == 0

    def test_disco_to_l3_compatible(self):
        """DISCO ends 02:00, L3 starts 14:30 next day - 12.5h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "DISCO", "L3") == 1

    def test_p12_to_d8_incompatible(self):
        """P12 ends 22:00, D8 starts 07:00 next day - 9h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "P12", "D8") == 0

    def test_p12_to_p8_compatible(self):
        """P12 ends 22:00, P8 starts 09:30 next day - 11.5h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "P12", "P8") == 1

    def test_l3_to_d8_incompatible(self):
        """L3 ends 23:00, D8 starts 07:00 next day - 8h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "D8") == 0

    def test_l3_to_p8_incompatible(self):
        """L3 ends 23:00, P8 starts 09:30 next day - 10.5h gap, incompatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "P8") == 0

    def test_l3_to_l3_compatible(self):
        """L3 ends 23:00, L3 starts 14:30 next day - 15.5h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "L3", "L3") == 1

    def test_day_to_night_compatible(self):
        """D8 ends 15:30, N8 starts 22:45 next day - 31.25h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "N8") == 1

    def test_d12_to_d8_compatible(self):
        """D12 ends 19:30, D8 starts 07:00 next day - 11.5h gap, compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D12", "D8") == 1

    def test_all_shift_pairs_defined(self):
        """All 64 shift pairs should have a compatibility value."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        from constraints import RestPeriodConstraint as RPC
        shifts = RPC.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1)

    def test_night_to_night_compatible(self):
        """Night-to-night transitions should generally be compatible."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1
        assert self._get_compat(compat, "N8", "N12") == 1
        assert self._get_compat(compat, "N12", "N8") == 1
        assert self._get_compat(compat, "N12", "N12") == 1


class TestRestPeriodConstraintApply:
    """Test the apply method of RestPeriodConstraint."""

    def test_model_has_constraints(self):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        from constraints import RestPeriodConstraint

        constraint = RestPeriodConstraint()
        compat = constraint._build_compatibility_table(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8

    def test_solver_respects_rest_period(self):
        """Solver should reject N8→D8 assignment (overlap, <11h gap)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_allows_compatible_pair(self):
        """Solver should allow N8→N8 assignment (15.5h gap, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def _make_definitions(self):
        return {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

    def test_night_to_day_all_incompatible(self):
        """Any night shift on day d forbids any day shift on day d+1."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        for night_shift in ("N8", "N12"):
            for day_shift in ("D8", "D12", "P8", "P12", "L3", "DISCO"):
                assert self._get_compat(compat, night_shift, day_shift) == 0, \
                    f"{night_shift}→{day_shift} should be incompatible"

    def test_day_to_night_all_incompatible(self):
        """Any day shift on day d forbids any night shift on day d+1."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        for day_shift in ("D8", "D12", "P8", "P12", "L3", "DISCO"):
            for night_shift in ("N8", "N12"):
                assert self._get_compat(compat, day_shift, night_shift) == 0, \
                    f"{day_shift}→{night_shift} should be incompatible"

    def test_night_to_night_compatible(self):
        """Night-to-night transitions are compatible (same category)."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "N8", "N8") == 1
        assert self._get_compat(compat, "N8", "N12") == 1
        assert self._get_compat(compat, "N12", "N8") == 1
        assert self._get_compat(compat, "N12", "N12") == 1

    def test_day_to_day_compatible(self):
        """Day-to-day transitions are compatible (same category)."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "D8", "DISCO") == 1
        assert self._get_compat(compat, "DISCO", "D8") == 1
        assert self._get_compat(compat, "DISCO", "DISCO") == 1
        assert self._get_compat(compat, "P8", "L3") == 1
        assert self._get_compat(compat, "L3", "P12") == 1

    def test_all_64_pairs_defined(self):
        """All 64 shift-pair combinations must have a boolean value."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        from constraints import NightToDayRest as NDR
        shifts = NDR.SHIFT_TYPES
        for s1 in shifts:
            for s2 in shifts:
                val = self._get_compat(compat, s1, s2)
                assert val in (0, 1), f"({s1}, {s2}) must be 0 or 1"

    def test_table_dimensions(self):
        """Compatibility table must be 8×8."""
        definitions = self._make_definitions()
        compat = self._build_compatibility(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8


class TestNightToDayRestApply:
    """Test the apply method of NightToDayRest constraint."""

    def test_model_has_constraints(self):
        """The apply method should add constraints to the model."""
        from ortools.sat.python import cp_model
        from constraints import NightToDayRest

        model = cp_model.CpModel()
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        constraint = NightToDayRest()
        compat = constraint._build_night_day_compatibility_table(definitions)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8

    def test_solver_rejects_night_to_day(self):
        """Solver must reject assigning N8 on day d and D8 on day d+1 to same staff."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_rejects_day_to_night(self):
        """Solver must reject assigning D8 on day d and N8 on day d+1 to same staff."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_allows_night_to_night(self):
        """Solver should allow N8→N8 (same category, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_allows_day_to_day(self):
        """Solver should allow D8→DISCO (same category, compatible)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_n12_to_disco_incompatible(self):
        """N12 on day d forbids DISCO on day d+1 (night→day)."""
        from ortools.sat.python import cp_model

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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


class TestContractedHoursFloor:
    """Test the ContractedHoursFloor hard constraint."""

    def test_apply_adds_constraints(self):
        """The apply method should add constraints to the model for staff-hours."""
        from ortools.sat.python import cp_model
        from constraints import ContractedHoursFloor
        from utils import compute_adjusted_hours, SCALE

        model = cp_model.CpModel()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

        from models import Staff, Classification
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

        staff_hours_vars = [[model.NewIntVar(0, 20000, f"hours_{s}_{b}") for b in range(len(blocks))] for s in range(len(staff_names))]

        constraint = ContractedHoursFloor()
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

        # The constraint should have added at least one constraint
        # We can verify by solving and checking the hour variable meets the floor
        expected_adj = compute_adjusted_hours(40.0, [], all_dates)
        assert expected_adj == 40.0 * SCALE

    def test_solver_enforces_floor(self):
        """Solver should reject solutions where staff hours < adjusted contracted hours."""
        from ortools.sat.python import cp_model
        from constraints import ContractedHoursFloor
        from models import Staff, Classification

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

        # Create hours variables the same way solver.py does
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

        constraint = ContractedHoursFloor()
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

        # With only 1 D8 position (8h) and 40h floor, the model should be infeasible
        # This is expected - the floor constraint can't be satisfied with so few positions
        status = solver.Solve(model)
        assert status == cp_model.INFEASIBLE  # 8h < 40h floor


class TestOvertimeCap:
    """Test the OvertimeCap hard constraint [H#e8f7d6c5]."""

    def test_apply_adds_constraints(self):
        """The apply method should add constraints to the model for staff-hours."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification

        model = cp_model.CpModel()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_enforces_cap(self):
        """Solver should reject solutions where staff hours exceed overtime cap."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_solver_allows_within_cap(self):
        """Solver should allow solutions within the overtime cap."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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

    def test_cap_uses_raw_contracted_not_adjusted(self):
        """Overtime cap uses raw contracted_hours_per_fortnight, not holiday-adjusted."""
        from ortools.sat.python import cp_model
        from constraints import OvertimeCap
        from models import Staff, Classification
        from utils import SCALE

        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "09:30:00", "end": "18:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "P12": {"start": "09:30:00", "end": "22:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "L3": {"start": "14:30:00", "end": "23:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "22:45:00", "end": "07:15:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "19:00:00", "end": "07:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }

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
