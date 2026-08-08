# Implementation Progress — ai-roster plan2.md

Last updated: 2026-08-08T22:05:00
Status: IN PROGRESS

## Baseline (recorded before any changes)
- Test suite: 1 failed, 178 passed, 1 skipped (test_longer_runs_incur_penalty + PytestUnknownMarkWarning)
- Full `main.py` run: FAILS — IndexError in `OvertimeDistribution.apply()` → `fair_share_deviation()` at `utils.py:695`

## Steps

### §1.1 — Fix ConsecutiveShiftDiscouraged reification bug (both code paths)
Status: DONE
Files touched:
- `constraints.py` (lines ~907 and ~1092)
Notes:
- Bug: `model.add_bool_or([av.Not() for av in and_sh_vars]).only_enforce_if(same.Not())` should be `add_bool_and` (De Morgan: NOT(A OR B) = NOT A AND NOT B)
- Two occurrences: `_apply_with_shared_vars` (~line 907) and `_apply_fallback` (~line 1092)
- Fix: replaced with `model.Add(sum(and_sh_vars) == 0).only_enforce_if(same.Not())` in both paths
- Added regression test `test_same_reification_forced_on_consecutive_identical_shift` that directly tests the reification mechanism in isolation
Verification:
- `pytest tests/test_soft_constraints.py::TestConsecutiveShiftDiscouraged` — 3/3 passed
### §1.2 — Fix OvertimeDistribution IndexError (blocking main.py)
Status: DONE
Files touched:
- `constraints.py` (OvertimeDistribution.apply, ~lines 634-662)
Notes:
- Bug: overtime_vars was flat list of num_staff * num_blocks elements, but contracted_list had only num_staff elements
- fair_share_deviation expects per_staff and contracted to have same length n
- Fix: compute overtime per staff member (sum across blocks), not per staff-block pair
Verification:
- `pytest tests/test_soft_constraints.py::TestOvertimeDistribution` — 2/2 passed
- `pytest tests/ -q` — 180 passed (was 178 + 1 fixed + 1 new regression test)
### §1.3 — Run full test suite + full main.py run (new baseline)
Status: DONE
Files touched:
- (none — verification only)
Notes:
- Full test suite: 180 passed, 1 skipped, 1 warning (PytestUnknownMarkWarning for slow marker)
- main.py: FEASIBLE, objective 289150300, solve time 300.42s, 184 assignments, 220 unfilled
- 3 verifier violations (pre-existing, not in plan scope): position coverage, skill level insufficient, rest period gap
Verification:
- `pytest tests/ -q` — 180 passed, 1 skipped
- `main.py` — completed with above numbers
### §2.1 — D4: Saturday/Sunday fairness per-block (not whole-period)
Status: NOT STARTED
Files touched:
- `constraints.py` (_DayOfWeekFairness.apply, ~lines 740-789)
Notes:
- Restructure to loop over blocks like WeekdayNightFairness does
- Filter day_pos_indices to positions within each block's date set
- Compute staff_day_hours and fair_share_deviation per block, sum into total_deviation across blocks
- Add regression test: 2-block roster where one staff works all Saturdays in block 1 and none in block 2
Verification:
- (pending)
### §2.2 — D6: Add solver: section to config.yaml
Status: NOT STARTED
Files touched:
- `config.yaml`
Notes:
- Add solver: max_time_in_seconds, num_workers, random_seed
- Document keys in header comment
- AGENTS.md §10 already describes the mechanism
Verification:
- (pending)
### §2.3 — D10: pyproject.toml + direct deps + cleanup
Status: NOT STARTED
Files touched:
- `pyproject.toml` (new)
- `requirements.txt` (delete)
- `pyrightconfig.json` (delete)
- `AGENTS.md` §12 (update module map reference)
Notes:
- Runtime deps: ortools, PyYAML, jinja2
- Dev deps: pytest, ruff, ty
- Add [tool.ruff], [tool.ty], [tool.pytest.ini_options] with slow marker
- Add scripts/check.sh
Verification:
- `ruff check . && ty check . && pytest tests/` all clean
### §3.1 — Split constraints.py + ModelContext dataclass
Status: NOT STARTED
Files touched:
- `constraints/__init__.py` (new)
- `constraints/base.py` (new) — BaseConstraint, BaseHardConstraint, BaseSoftConstraint, shared helpers
- `constraints/hard.py` (new) — all hard constraint classes
- `constraints/soft.py` (new) — all soft constraint classes
- `constraints/registry.py` (new) — HARD_CONSTRAINTS, SOFT_CONSTRAINTS, getter functions
- `constraints.py` (delete)
- `AGENTS.md` §12 (update module map)
Notes:
- ModelContext dataclass replaces 10-13 positional parameters in apply() signatures
- constraints/__init__.py re-exports everything so imports unchanged
- Pure refactor — should not change any test outcome
Verification:
- `pytest tests/` — 180/180 passing, no warnings
### §3.2 — Trim AGENTS.md and README
Status: NOT STARTED
Files touched:
- `AGENTS.md`
- `README.md`
Notes:
- AGENTS.md: delete parenthetical change-history asides (~3% cut needed)
- README: replace duplicated content with one-line pointers to AGENTS.md (~600 words target)
Verification:
- Word counts: AGENTS.md < 3000, README < 800
### §3.3 — Remove strikethrough lines from constraint docs
Status: NOT STARTED
Files touched:
- `hard_constraints.md` (line 23)
- `soft_constraints.md` (line 36)
Notes:
- Replace with HTML comments documenting reclassification/replacement
Verification:
- grep -n '~~' confirms zero strikethrough spans remain
### §3.4 — Test fixture consolidation
Status: NOT STARTED
Files touched:
- `tests/conftest.py`
- `tests/test_constraints.py`
Notes:
- Extract repeated ~20-30 line setup blocks into pytest.fixture parametrization
- Lower priority, not blocking
Verification:
- `pytest tests/` still passes
## Deviations from plan2.md
- §1.2 (OvertimeDistribution fix) inserted between §1.1 and §1.3 — it's blocking main.py and was not explicitly listed as a separate step, but is required to get a clean baseline
## Open questions
- None yet
