"""Tests for utils.py - data loading, validation, and helper functions."""

from datetime import date, timedelta

import pytest

from utils import (
    generate_dates,
    get_fortnight_blocks,
    validate_roster_period,
    validate_roster_positions,
    load_definitions,
    load_staff,
    validate_staff_records,
)
from models import Staff, Classification


class TestValidateRosterPeriod:
    """Test roster period validation with both string and date inputs."""

    def test_valid_date_range(self):
        """Valid 28-day roster period should return start and end dates."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-30",
            }
        }
        start, end = validate_roster_period(roster_data)
        assert start == date(2026, 8, 3)
        assert end == date(2026, 8, 30)

    def test_valid_date_objects(self):
        """Valid roster period with date objects (from PyYAML) should work."""
        roster_data = {
            "dates": {
                "start": date(2026, 8, 3),
                "end": date(2026, 8, 30),
            }
        }
        start, end = validate_roster_period(roster_data)
        assert start == date(2026, 8, 3)
        assert end == date(2026, 8, 30)

    def test_invalid_not_multiple_of_14_days(self):
        """Roster period not a multiple of 14 days should raise ValueError."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-20",  # 18 days, not multiple of 14
            }
        }
        with pytest.raises(ValueError, match="whole multiple of 14"):
            validate_roster_period(roster_data)

    def test_single_fortnight(self):
        """Exactly 14 days should be valid."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-16",  # 13 days = 14 days inclusive
            }
        }
        start, end = validate_roster_period(roster_data)
        assert (end - start).days == 13  # inclusive count = 14

    def test_two_fortnights(self):
        """Exactly 28 days should be valid."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-30",  # 27 days = 28 days inclusive
            }
        }
        start, end = validate_roster_period(roster_data)
        assert (end - start).days == 27  # inclusive count = 28


class TestGenerateDates:
    """Test date generation from start to end."""

    def test_generate_28_days(self):
        """Should generate all dates from start to end inclusive."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 30)
        dates = generate_dates(start, end)
        assert len(dates) == 28
        assert dates[0] == date(2026, 8, 3)
        assert dates[-1] == date(2026, 8, 30)

    def test_generate_14_days(self):
        """Should generate 14 dates for a single fortnight."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        dates = generate_dates(start, end)
        assert len(dates) == 14


class TestGetFortnightBlocks:
    """Test fortnightly block generation."""

    def test_two_blocks_from_28_days(self):
        """28 days should produce 2 blocks of 14 days each."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 30)
        dates = generate_dates(start, end)
        blocks = get_fortnight_blocks(dates)
        assert len(blocks) == 2
        assert len(blocks[0]) == 14
        assert len(blocks[1]) == 14
        assert blocks[0][0] == dates[0]
        assert blocks[1][0] == dates[14]

    def test_one_block_from_14_days(self):
        """14 days should produce 1 block."""
        start = date(2026, 8, 3)
        end = date(2026, 8, 16)
        dates = generate_dates(start, end)
        blocks = get_fortnight_blocks(dates)
        assert len(blocks) == 1
        assert len(blocks[0]) == 14


class TestValidateRosterPositions:
    """Test roster position validation."""

    def test_positions_include_date_and_day(self):
        """Each position dict should have date and day_name fields."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-09",  # 7 days
            },
            "roster_positions": {
                "Monday": [
                    {
                        "shift": "D8",
                        "required_skill_level": "Acute",
                    }
                ],
            },
        }
        definitions = {"D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False}}
        start = date(2026, 8, 3)
        end = date(2026, 8, 9)
        positions = validate_roster_positions(roster_data, definitions, start, end)
        assert len(positions) == 1  # 1 position for Monday only
        for pos in positions:
            assert "date" in pos
            assert "day_name" in pos
            assert isinstance(pos["date"], str)  # date is stored as ISO string

    def test_positions_match_shift_counts(self):
        """Position count should match the entries in roster_positions."""
        roster_data = {
            "dates": {
                "start": "2026-08-03",
                "end": "2026-08-09",  # 7 days
            },
            "roster_positions": {
                "Monday": [
                    {
                        "shift": "D8",
                        "required_skill_level": "Acute",
                    },
                    {
                        "shift": "D8",
                        "required_skill_level": "Acute",
                    },
                    {
                        "shift": "D8",
                        "required_skill_level": "Acute",
                    },
                ],
            },
        }
        definitions = {"D8": {"start": "08:00:00", "end": "16:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False}}
        start = date(2026, 8, 3)
        end = date(2026, 8, 9)
        positions = validate_roster_positions(roster_data, definitions, start, end)
        d8_positions = [p for p in positions if p["shift"] == "D8"]
        assert len(d8_positions) == 3  # 3 positions for Monday only


class TestValidateStaffRecords:
    """Test staff record validation."""

    def test_duplicate_names_raises(self):
        """Duplicate staff names should raise ValueError."""
        records = [
            {"name": "Alice", "classification": "RN", "skill_tags": ["Acute"], "contracted_hours_per_fortnight": 40},
            {"name": "Alice", "classification": "CN", "skill_tags": ["Acute"], "contracted_hours_per_fortnight": 30},
        ]
        with pytest.raises(ValueError, match="duplicate"):
            validate_staff_records(records)

    def test_invalid_classification_raises(self):
        """Invalid classification should raise ValueError."""
        records = [
            {"name": "Bob", "classification": "Nurse", "skill_tags": ["Acute"], "contracted_hours_per_fortnight": 40},
        ]
        with pytest.raises(ValueError, match="classification"):
            validate_staff_records(records)

    def test_invalid_skill_tags_raises(self):
        """Non-contiguous skill tags should raise ValueError."""
        records = [
            {"name": "Charlie", "classification": "RN", "skill_tags": ["Acute", "Triage"], "contracted_hours_per_fortnight": 40},
        ]
        with pytest.raises(ValueError, match="skill_tags"):
            validate_staff_records(records)

    def test_valid_staff_records_pass(self):
        """Valid staff records should not raise."""
        records = [
            {"name": "Alice", "classification": "RN", "skill_tags": ["Acute", "Resus"], "contracted_hours_per_fortnight": 40},
            {"name": "Bob", "classification": "CN", "skill_tags": ["Acute"], "contracted_hours_per_fortnight": 30},
        ]
        # Should not raise
        validate_staff_records(records)
