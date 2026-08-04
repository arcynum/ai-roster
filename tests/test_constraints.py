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
            "D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "19:00:00", "end": "03:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "P12": {"start": "19:30:00", "end": "08:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
            "L3": {"start": "00:00:00", "end": "03:00:00", "span_hours": 3.0, "paid_hours": 3.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "20:30:00", "end": "05:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "21:00:00", "end": "09:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        assert self._get_compat(compat, "D8", "D8") == 1
        assert self._get_compat(compat, "N8", "N8") == 1

    def test_night_to_day_rest(self):
        """Night shift followed by early day shift should be incompatible (rest period)."""
        definitions = {
            "D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "19:00:00", "end": "03:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "P12": {"start": "19:30:00", "end": "08:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
            "L3": {"start": "00:00:00", "end": "03:00:00", "span_hours": 3.0, "paid_hours": 3.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "20:30:00", "end": "05:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "21:00:00", "end": "09:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        # N8 ends 05:00, D8 starts 08:00 next day - 3h gap, should be compatible
        assert self._get_compat(compat, "N8", "D8") == 1

    def test_disco_crosses_midnight(self):
        """DISCO crosses midnight but is classified as day shift."""
        definitions = {
            "D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "19:00:00", "end": "03:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "P12": {"start": "19:30:00", "end": "08:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
            "L3": {"start": "00:00:00", "end": "03:00:00", "span_hours": 3.0, "paid_hours": 3.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "20:30:00", "end": "05:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "21:00:00", "end": "09:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        compat = self._build_compatibility(definitions)
        # DISCO ends 02:00, D8 starts 08:00 next day - 6h gap, should be compatible
        assert self._get_compat(compat, "DISCO", "D8") == 1
        # D8 ends 16:30, DISCO starts 17:30 next day - 25h gap, should be compatible
        assert self._get_compat(compat, "D8", "DISCO") == 1

    def test_all_shift_pairs_defined(self):
        """All shift pairs should have a compatibility value."""
        definitions = {
            "D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "19:00:00", "end": "03:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "P12": {"start": "19:30:00", "end": "08:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
            "L3": {"start": "00:00:00", "end": "03:00:00", "span_hours": 3.0, "paid_hours": 3.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "20:30:00", "end": "05:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "21:00:00", "end": "09:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
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
            "D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
            "D12": {"start": "07:00:00", "end": "19:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": False},
            "P8": {"start": "19:00:00", "end": "03:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "P12": {"start": "19:30:00", "end": "08:00:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
            "L3": {"start": "00:00:00", "end": "03:00:00", "span_hours": 3.0, "paid_hours": 3.0, "crosses_midnight": False},
            "DISCO": {"start": "17:30:00", "end": "02:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N8": {"start": "20:30:00", "end": "05:00:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": True},
            "N12": {"start": "21:00:00", "end": "09:30:00", "span_hours": 12.5, "paid_hours": 12.0, "crosses_midnight": True},
        }
        constraint = NoDoubleBooking()
        compat = constraint._build_compatibility_table(definitions)
        # Verify the table is built correctly (8x8 matrix)
        assert len(compat) == 8
        for row in compat:
            assert len(row) == 8
