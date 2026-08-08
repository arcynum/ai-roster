#!/usr/bin/env python3
"""Shared pytest fixtures for the ai-roster test suite.

Provides:
- `definitions`: loaded from definitions.yaml via utils.load_definitions()
- `staff_factory`: factory to create models.Staff instances
- `position_factory`: factory to create roster position dicts
- `roster_model`: fixture to build a RosterModel for tests
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from models import Classification, Staff
from solver import RosterModel
from utils import load_definitions


@pytest.fixture
def definitions() -> dict[str, dict]:
    """Load shift definitions from definitions.yaml."""
    return load_definitions()


@pytest.fixture
def staff_factory() -> Any:
    """Factory to create Staff instances for tests.

    Usage:
        make_staff("Alice", classification="RN", skill_tags=["Acute"])
    """
    def _make(
        name: str,
        classification: str = "RN",
        skill_tags: list[str] | None = None,
        contracted_hours_per_fortnight: float = 56.0,
        red_requests: list[str] | None = None,
        holidays: list[dict] | None = None,
    ) -> Staff:
        return Staff(
            name=name,
            classification=Classification(classification),
            skill_tags=skill_tags or ["Acute"],
            contracted_hours_per_fortnight=contracted_hours_per_fortnight,
            red_requests=red_requests or [],
            holidays=holidays or [],
        )
    return _make


@pytest.fixture
def position_factory() -> Any:
    """Factory to create roster position dicts for tests.

    Usage:
        make_position("2026-08-03", "D8", required_skill_level="Acute")
    """
    def _make(
        date_str: str,
        shift: str = "D8",
        required_skill_level: str | None = None,
        slot_id: str | None = None,
    ) -> dict:
        return {
            "date": date_str,
            "shift": shift,
            "required_skill_level": required_skill_level,
            "slot_id": slot_id or f"{shift}-General-1",
        }
    return _make


@pytest.fixture
def roster_model(
    staff_factory: Any,
    position_factory: Any,
    definitions: dict[str, dict],
) -> Any:
    """Build a minimal RosterModel for tests.

    Creates a 14-day roster with a small set of staff and positions
    covering all shift types.
    """
    start = date(2026, 8, 3)  # Monday
    end = date(2026, 8, 16)   # Sunday (14 days)
    dates = [start + timedelta(days=i) for i in range(14)]
    date_strs = [d.isoformat() for d in dates]

    staff = [
        staff_factory("Alice", classification="RN", skill_tags=["Acute", "Resus"]),
        staff_factory("Bob", classification="RN", skill_tags=["Acute"]),
        staff_factory("Carol", classification="CN", skill_tags=["Acute", "Resus", "Triage"]),
        staff_factory("Dave", classification="Graduate", skill_tags=["Acute"]),
    ]

    positions = []
    for d in date_strs:
        positions.append(position_factory(d, "D8", "Acute"))
        positions.append(position_factory(d, "N12", "Resus"))

    blocks = [[d.isoformat() for d in dates]]

    weights = {
        "[S#d9a8b7c6]": 1000,
        "[S#30c6f5ad]": 500,
        "[S#d2a7f4a6]": 2000,
        "[S#s1a2t3u4]": 1500,
        "[S#s2u3n4d5]": 1500,
        "[S#e9b4a1b3]": 600,
        "[S#6c1e9a4d]": 600,
        "[S#f1a2b3c4]": 140000,
        "[S#a2b3c4d5]": 140000,
        "[S#b3c4d5e6]": 140000,
        "[S#e7f3a2b1]": 140000,
        "[S#c4d5e6f7]": 140000,
    }

    return RosterModel(
        staff_list=staff,
        positions=positions,
        definitions=definitions,
        weights=weights,
        blocks=blocks,
    )
