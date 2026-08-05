#!/usr/bin/env python3
"""Tests for config.yaml constraint toggles and solver filtering."""

import logging
import tempfile
from pathlib import Path

import pytest
import yaml

from typing import Any

from constraints import HARD_CONSTRAINTS, SOFT_CONSTRAINTS, get_hard_constraint_ids, get_soft_constraint_ids
from solver import RosterModel
from utils import load_config


# ---------------------------------------------------------------------------
# load_config unit tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Test load_config behaviour."""

    def test_no_file_returns_none(self, tmp_path):
        """When config.yaml doesn't exist, load_config returns None."""
        result = load_config(path=tmp_path / "config.yaml")
        assert result is None

    def test_empty_file_returns_none(self, tmp_path):
        """An empty YAML file (None) returns None."""
        path = tmp_path / "config.yaml"
        path.write_text("")
        result = load_config(path=path)
        assert result is None

    def test_no_constraints_section_returns_none(self, tmp_path):
        """A file with no constraints key returns None."""
        path = tmp_path / "config.yaml"
        path.write_text("some_key: value\n")
        result = load_config(path=path)
        assert result is None

    def test_empty_constraints_returns_empty_lists(self, tmp_path):
        """constraints: {} gives empty enabled lists."""
        path = tmp_path / "config.yaml"
        path.write_text("constraints:\n")
        result = load_config(path=path)
        assert result == {"hard": {"enabled": []}, "soft": {"enabled": []}}

    def test_config_with_hard_enabled_ids(self, tmp_path):
        """Enabled IDs are parsed into lists."""
        path = tmp_path / "config.yaml"
        path.write_text(
            "constraints:\n"
            "  hard:\n"
            "    enabled:\n"
            '      - "[H#e91c63ab]"\n'
            '      - "[H#c1f6e3f5]"\n'
            "  soft:\n"
            "    enabled:\n"
            '      - "[S#a1d6c3d5]"\n'
        )
        result = load_config(path=path)
        assert result is not None
        assert result["hard"]["enabled"] == ["[H#e91c63ab]", "[H#c1f6e3f5]"]
        assert result["soft"]["enabled"] == ["[S#a1d6c3d5]"]

    def test_config_with_soft_enabled_ids(self, tmp_path):
        """Soft enabled IDs are parsed correctly."""
        path = tmp_path / "config.yaml"
        path.write_text(
            "constraints:\n"
            "  soft:\n"
            "    enabled:\n"
            '      - "[S#e9b4a1b3]"\n'
            '      - "[S#d2a7f4a6]"\n'
            '      - "[S#3d9a7ec1]"\n'
        )
        result = load_config(path=path)
        assert result is not None
        assert result["soft"]["enabled"] == ["[S#e9b4a1b3]", "[S#d2a7f4a6]", "[S#3d9a7ec1]"]
        assert result["hard"]["enabled"] == []

    def test_hard_only_config(self, tmp_path):
        """Config with only hard section still returns valid dict."""
        path = tmp_path / "config.yaml"
        path.write_text(
            "constraints:\n"
            "  hard:\n"
            "    enabled:\n"
            '      - "[H#e91c63ab]"\n'
        )
        result = load_config(path=path)
        assert result is not None
        assert result["hard"]["enabled"] == ["[H#e91c63ab]"]
        assert result["soft"]["enabled"] == []

    def test_unknown_hard_id_warns(self, tmp_path):
        """Unknown hard constraint ID logs a warning but doesn't error."""
        path = tmp_path / "config.yaml"
        path.write_text(
            "constraints:\n"
            "  hard:\n"
            "    enabled:\n"
            '      - "[H#nonexistent]"\n'
        )
        result = load_config(path=path)
        assert result is not None
        assert "[H#nonexistent]" in result["hard"]["enabled"]

    def test_unknown_soft_id_warns(self, tmp_path):
        """Unknown soft constraint ID logs a warning but doesn't error."""
        path = tmp_path / "config.yaml"
        path.write_text(
            "constraints:\n"
            "  soft:\n"
            "    enabled:\n"
            '      - "[S#nonexistent]"\n'
        )
        result = load_config(path=path)
        assert result is not None
        assert "[S#nonexistent]" in result["soft"]["enabled"]

    def test_all_known_ids_in_registry(self):
        """Every ID in config.yaml's example must exist in the registry."""
        config_path = Path(__file__).resolve().parent.parent / "config.yaml"
        if not config_path.exists():
            pytest.skip("config.yaml not found")
        data = yaml.safe_load(config_path.read_text()) or {}
        constraints = data.get("constraints", {}) or {}
        commented_ids = set()
        for kind in ("hard", "soft"):
            entries = constraints.get(kind, {}) or {}
            enabled = entries.get("enabled") or []
            for entry in enabled:
                if isinstance(entry, str) and entry.strip().startswith("#"):
                    # Extract ID from commented line like "  # - "[H#...]"
                    import re
                    m = re.search(r"\[([HS]#[a-f0-9]{8})\]", entry)
                    if m:
                        commented_ids.add(m.group(1))
        known = set(get_hard_constraint_ids()) | set(get_soft_constraint_ids())
        unknown = commented_ids - known
        assert not unknown, f"IDs in config.yaml not found in constraints.py: {unknown}"


# ---------------------------------------------------------------------------
# Constraint ID registry tests
# ---------------------------------------------------------------------------


class TestConstraintRegistry:
    """Test get_hard_constraint_ids / get_soft_constraint_ids."""

    def test_hard_ids_match_registry(self):
        """Returned IDs match the HARD_CONSTRAINTS list."""
        ids = get_hard_constraint_ids()
        registry_ids = [c.constraint_id for c in HARD_CONSTRAINTS]
        assert ids == registry_ids

    def test_soft_ids_match_registry(self):
        """Returned IDs match the SOFT_CONSTRAINTS list."""
        ids = get_soft_constraint_ids()
        registry_ids = [c.constraint_id for c in SOFT_CONSTRAINTS]
        assert ids == registry_ids

    def test_all_ids_are_unique(self):
        """No duplicate IDs across hard + soft."""
        all_ids = get_hard_constraint_ids() + get_soft_constraint_ids()
        assert len(all_ids) == len(set(all_ids))

    def test_hard_ids_are_formatted(self):
        """Hard constraint IDs start with [H#]."""
        for cid in get_hard_constraint_ids():
            assert cid.startswith("[H#"), f"Bad hard ID format: {cid}"

    def test_soft_ids_are_formatted(self):
        """Soft constraint IDs start with [S#]."""
        for cid in get_soft_constraint_ids():
            assert cid.startswith("[S#"), f"Bad soft ID format: {cid}"


# ---------------------------------------------------------------------------
# Solver constraint filtering tests
# ---------------------------------------------------------------------------


class TestSolverConstraintFiltering:
    """Test that RosterModel filters constraints by config."""

    @staticmethod
    def _make_model(constraint_config=None, enabled_hard_count=None, enabled_soft_count=None):
        """Build a minimal RosterModel and return constraint application counts.

        We intercept the constraint.apply() calls to count them without
        needing a full CP-SAT solve.
        """
        from ortools.sat.python import cp_model

        staff_list: list[Any] = [
            type("S", (), {"name": "Alice", "is_graduate": False,
                           "red_requests": [], "holidays": []})(),
        ]
        staff_by_name = {"Alice": staff_list[0]}
        staff_names = ["Alice"]
        all_dates = ["2026-08-03", "2026-08-04"]
        blocks = [["2026-08-03", "2026-08-04"]]
        positions = [
            {"date": "2026-08-03", "shift": "D8", "required_skill_level": None, "day_name": "Monday"},
            {"date": "2026-08-04", "shift": "D8", "required_skill_level": None, "day_name": "Tuesday"},
        ]
        definitions = {
            "D8": {"start": "07:00:00", "end": "15:30:00", "span_hours": 8.5, "paid_hours": 8.0, "crosses_midnight": False},
        }
        weights = {}

        model = RosterModel(  # type: ignore[arg-type]
            staff_list=staff_list,
            positions=positions,
            definitions=definitions,
            weights=weights,
            blocks=blocks,
            constraint_config=constraint_config,
        )

        # Patch constraint.apply to count calls
        hard_called = []
        soft_called = []

        # Save original apply methods keyed by constraint_id before patching
        original_hard_apply: dict[str, callable] = {}
        original_soft_apply: dict[str, callable] = {}
        for cls in HARD_CONSTRAINTS:
            original_hard_apply[cls.constraint_id] = cls.apply
        for cls in SOFT_CONSTRAINTS:
            original_soft_apply[cls.constraint_id] = cls.apply

        for cls in HARD_CONSTRAINTS:
            cid = cls.constraint_id
            def make_apply(called_list, cid, orig_cls):
                def wrapped(*args, **kwargs):
                    called_list.append(cid)
                return wrapped
            cls.apply = make_apply(hard_called, cid, cls)

        for cls in SOFT_CONSTRAINTS:
            cid = cls.constraint_id
            def make_apply(called_list, cid, orig_cls):
                def wrapped(*args, **kwargs):
                    called_list.append(cid)
                return wrapped
            cls.apply = make_apply(soft_called, cid, cls)

        model._create_variables()
        model._apply_hard_constraints()
        model._apply_soft_constraints()

        # Restore original apply methods
        for cls in HARD_CONSTRAINTS:
            cls.apply = original_hard_apply[cls.constraint_id]
        for cls in SOFT_CONSTRAINTS:
            cls.apply = original_soft_apply[cls.constraint_id]

        return hard_called, soft_called

    def test_all_constraints_applied_when_no_config(self):
        """Without config, all constraints are applied."""
        hard_called, soft_called = self._make_model()
        assert len(hard_called) == len(HARD_CONSTRAINTS)
        assert len(soft_called) == len(SOFT_CONSTRAINTS)

    def test_only_enabled_hard_constraints_applied(self):
        """Only hard constraints in enabled list are applied."""
        enabled_ids = [HARD_CONSTRAINTS[0].constraint_id]
        config = {"hard": {"enabled": enabled_ids}, "soft": {"enabled": []}}
        hard_called, soft_called = self._make_model(constraint_config=config)
        assert len(hard_called) == 1
        assert hard_called[0] == enabled_ids[0]

    def test_no_hard_constraints_applied_when_enabled_empty(self):
        """Empty enabled list means no hard constraints applied."""
        config = {"hard": {"enabled": []}, "soft": {"enabled": []}}
        hard_called, soft_called = self._make_model(constraint_config=config)
        assert len(hard_called) == 0
        assert len(soft_called) == 0

    def test_only_enabled_soft_constraints_applied(self):
        """Only soft constraints in enabled list are applied."""
        enabled_ids = [SOFT_CONSTRAINTS[0].constraint_id]
        config = {"hard": {"enabled": []}, "soft": {"enabled": enabled_ids}}
        hard_called, soft_called = self._make_model(constraint_config=config)
        assert len(hard_called) == 0
        assert len(soft_called) == 1
        assert soft_called[0] == enabled_ids[0]

    def test_subset_of_constraints_applied(self):
        """A mix of hard and soft enabled constraints works."""
        hard_ids = [HARD_CONSTRAINTS[0].constraint_id, HARD_CONSTRAINTS[1].constraint_id]
        soft_ids = [SOFT_CONSTRAINTS[0].constraint_id]
        config = {"hard": {"enabled": hard_ids}, "soft": {"enabled": soft_ids}}
        hard_called, soft_called = self._make_model(constraint_config=config)
        assert len(hard_called) == 2
        assert len(soft_called) == 1
        assert set(hard_called) == set(hard_ids)
        assert soft_called[0] == soft_ids[0]

    def test_unknown_id_in_config_does_not_crash(self):
        """Unknown ID in config is skipped without error."""
        config = {"hard": {"enabled": ["[H#nonexistent]"]}, "soft": {"enabled": []}}
        hard_called, soft_called = self._make_model(constraint_config=config)
        assert len(hard_called) == 0
        assert len(soft_called) == 0
