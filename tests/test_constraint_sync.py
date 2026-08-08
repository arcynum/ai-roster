#!/usr/bin/env python3
"""Test that every [H#...]/[S#...] ID in the markdown files is registered or allow-listed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from constraints import HARD_CONSTRAINTS, SOFT_CONSTRAINTS, get_hard_constraint_ids, get_soft_constraint_ids
from solver import RosterModel


# IDs documented in markdown files but implemented indirectly (not standalone constraint classes).
# Each entry points to where it's implemented.
IMPLEMENTED_ELSEWHERE = {
    "[H#7a3e5f91]": "enforced by coverage constraint in RosterModel._apply_coverage_constraint — one staff per position",
    "[H#91bc3d7e]": "implemented in SkillLevelRequirement [H#5e6ad8f4] — null required_skill_level allows any staff",
    "[H#b72e41fa]": "implemented in SkillLevelRequirement [H#5e6ad8f4] — minimum skill level, higher satisfies",
    "[H#c18b42de]": "implemented in validate_roster_positions() (utils.py) — validated at load time",
    "[H#2f74e6ab]": "implemented in validate_roster_positions() (utils.py) — slot_id generation for duplicate shift types",
    "[H#a3d8f6c1]": "implemented in compute_adjusted_hours() (utils.py) — holiday proration",
    "[H#d9a8b7c6]": "reclassified as soft constraint ContractedHoursFloorSoft [S#d9a8b7c6]",
    "[H#84a1d5c9]": "merged into SkillLevelRequirement [H#5e6ad8f4]",
    "[H#6db3f120]": "merged into SkillLevelRequirement [H#5e6ad8f4]",
    "[S#a1d6c3d5]": "replaced by SaturdayFairness [S#s1a2t3u4] and SundayFairness [S#s2u3n4d5]",
}


def _extract_ids(md_path: Path) -> set[str]:
    """Extract all [H#...] and [S#...] IDs from a markdown file."""
    text = md_path.read_text()
    return set(re.findall(r'\[[HS]#[A-Za-z0-9]{8}\]', text))


class TestConstraintIdSync:
    """Every [H#...]/[S#...] ID in hard_constraints.md and soft_constraints.md
    must be either a registered constraint_id or in the IMPLEMENTED_ELSEWHERE allow-list."""

    @staticmethod
    def _all_registered_ids() -> set[str]:
        """All registered constraint IDs from code."""
        ids = set(get_hard_constraint_ids()) | set(get_soft_constraint_ids())
        ids |= set(RosterModel.UNFILLED_TIER_IDS)
        return ids

    def test_all_hard_constraint_ids_registered_or_allowed(self):
        """Every [H#...] in hard_constraints.md is registered or in IMPLEMENTED_ELSEWHERE."""
        project_root = Path(__file__).resolve().parent.parent
        md_ids = _extract_ids(project_root / "hard_constraints.md")

        registered = self._all_registered_ids()
        allowed = set(IMPLEMENTED_ELSEWHERE.keys())

        for hid in sorted(md_ids):
            if hid in registered:
                continue  # registered as a constraint class
            if hid in allowed:
                continue  # documented but implemented indirectly
            pytest.fail(
                f"{hid} found in hard_constraints.md but not registered in HARD_CONSTRAINTS "
                f"and not in IMPLEMENTED_ELSEWHERE allow-list"
            )

    def test_all_soft_constraint_ids_registered_or_allowed(self):
        """Every [S#...] in soft_constraints.md is registered or in IMPLEMENTED_ELSEWHERE."""
        project_root = Path(__file__).resolve().parent.parent
        md_ids = _extract_ids(project_root / "soft_constraints.md")

        registered = self._all_registered_ids()
        allowed = set(IMPLEMENTED_ELSEWHERE.keys())

        for sid in sorted(md_ids):
            if sid in registered:
                continue
            if sid in allowed:
                continue
            pytest.fail(
                f"{sid} found in soft_constraints.md but not registered in SOFT_CONSTRAINTS "
                f"and not in IMPLEMENTED_ELSEWHERE allow-list"
            )

    def test_implemented_elsewhere_all_have_pointers(self):
        """Every ID in IMPLEMENTED_ELSEWHERE must have a non-empty pointer string."""
        for hid, pointer in IMPLEMENTED_ELSEWHERE.items():
            assert pointer.strip(), f"{hid} in IMPLEMENTED_ELSEWHERE has empty pointer"

    def test_no_duplicate_constraint_ids(self):
        """All registered constraint IDs must be unique."""
        all_ids = get_hard_constraint_ids() + get_soft_constraint_ids()
        unfilled_ids = list(RosterModel.UNFILLED_TIER_IDS)
        all_ids.extend(unfilled_ids)
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate constraint IDs found: {[i for i in all_ids if all_ids.count(i) > 1]}"
        )

    def test_registered_ids_appear_in_markdown(self):
        """Every registered constraint_id must appear in its corresponding markdown file."""
        project_root = Path(__file__).resolve().parent.parent
        hard_text = (project_root / "hard_constraints.md").read_text()
        soft_text = (project_root / "soft_constraints.md").read_text()

        for cid in get_hard_constraint_ids():
            assert cid in hard_text, (
                f"Registered hard constraint {cid} not found in hard_constraints.md"
            )

        for cid in get_soft_constraint_ids():
            assert cid in soft_text, (
                f"Registered soft constraint {cid} not found in soft_constraints.md"
            )

    def test_registered_ids_appear_in_config(self):
        """Every registered ID must appear in config.yaml (commented or uncommented)."""
        import yaml

        project_root = Path(__file__).resolve().parent.parent
        config_path = project_root / "config.yaml"

        if not config_path.exists():
            # No config = all enabled, which is fine
            return

        config_text = config_path.read_text()
        all_ids = get_hard_constraint_ids() + get_soft_constraint_ids()
        all_ids.extend(RosterModel.UNFILLED_TIER_IDS)

        for cid in all_ids:
            assert cid in config_text, (
                f"Registered ID {cid} not found in config.yaml (commented or uncommented)"
            )

    def test_weights_yaml_has_all_soft_and_unfilled_ids(self):
        """Every registered soft ID and unfilled-tier ID must have a weights.yaml entry,
        and weights.yaml must have no live extra keys (retired comments are fine)."""
        import yaml

        project_root = Path(__file__).resolve().parent.parent
        weights_path = project_root / "weights.yaml"
        weights_text = weights_path.read_text()
        weights_data = yaml.safe_load(weights_text) or {}

        # Keys that are actual weights (not comments)
        live_keys = {k for k in weights_data.keys() if isinstance(k, str)}

        # Check every soft constraint ID has a weight
        for cid in get_soft_constraint_ids():
            assert cid in live_keys, (
                f"Registered soft constraint {cid} has no entry in weights.yaml"
            )

        # Check every unfilled-tier ID has a weight
        for cid in RosterModel.UNFILLED_TIER_IDS:
            assert cid in live_keys, (
                f"Unfilled tier {cid} has no entry in weights.yaml"
            )

        # Check no extra live keys that aren't soft or unfilled
        # (Retired IDs in comments are fine — yaml.safe_load skips comment lines)
        all_known = set(get_soft_constraint_ids()) | set(RosterModel.UNFILLED_TIER_IDS)
        extra = live_keys - all_known
        assert not extra, (
            f"weights.yaml has entries for IDs not registered in code: {sorted(extra)}"
        )
