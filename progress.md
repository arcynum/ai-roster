# AI-Roster — Progress Log

## Completed

### §1 Remove Casual Staffing (all items done)
- **1.1 Deleted** `CasualStaffingConstraint` class (`[H#c92f5e1b]`, `[H#71b4d9ac]`, `[H#4ef8a2c3]`) from `constraints.py`
- **1.2 Deleted** `CasualUsageMinimization` class (`[S#3d9a7ec1]`) from `constraints.py`
- **1.3 Removed** both classes from `HARD_CONSTRAINTS` and `SOFT_CONSTRAINTS` registry lists
- **1.4 Removed** `self.casual_vars` from `RosterModel` (declaration, capture, attribute)
- **1.5 Removed** `casual_usage` from `SolveResult` (docstring, dataclass fields)
- **1.6 Simplified** coverage constraint — removed `casual_allowed` branching; now just `sum(staff_vars) + unfilled_var == 1` for all positions
- **1.7 Removed** `apply_kwargs["casual_vars"]` pass-through in soft constraint loop
- **1.8 Updated** log line to drop casual count
- **1.9 Removed** `filled_by_casual` field from `RosterSlot` in `models.py`
- **1.10 Removed** `casual_allowed` from position builder in `utils.py`
- **1.11 Removed** `casual_usage` from `_build_context()` in `output.py`
- **1.12 Updated** `weights.yaml` — removed `[S#3d9a7ec1]` entry, updated `[S#d9a8b7c6]` comment
- **1.13 Updated** `config.yaml` — removed casual hard/soft toggle entries, fixed indentation
- **1.14 Updated** `hard_constraints.md` — removed casual section (3 constraint IDs)
- **1.15 Updated** `soft_constraints.md` — removed `[S#3d9a7ec1]` entry, updated `[S#d9a8b7c6]` comment
- **1.16 Updated** `AGENTS.md` — removed casual references from §6 (logging), §7 (fill order), §8 (modeling notes), §9 (weight dominance)
- **1.17 Updated** `README.md` — removed casual bullets from constraint types and output sections
- **1.18 Deleted** `tests/test_casual.py` entirely
- **1.19 Updated** `tests/test_config.py` — removed `[S#3d9a7ec1]` from test input and assertion

### Verification
- All 130 tests pass
- Full run completes successfully: 404 assignments, 0 unfilled, FEASIBLE, 300s
- No remaining casual references in codebase (outside plan.md, progress.md)
