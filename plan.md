# Constraint Implementation Audit & Plan

## Hard Constraints (22 constraint IDs across 12 classes)

| Status | Constraint ID | Description | Class | Notes |
|--------|--------------|-------------|-------|-------|
| **✅ Fully** | `[H#4d9f81c2]` | Roster positions must be filled | `CoverageConstraint` | Enforced in `_create_variables()` via `sum(staff_vars) == 1` |
| **✅ Fully** | `[H#7a3e5f91]` | Each entry is a single position | — | Data validation in `validate_roster_positions()` |
| **✅ Fully** | `[H#c18b42de]` | Zero or one skill level per position | — | Validated in `validate_roster_positions()` |
| **⚠️ Partial** | `[H#5e6ad8f4]` | Skill level matching (threshold) | `SkillLevelRequirement` | Class exists but `apply()` is `pass` / `TODO`. Data validation ensures valid skill_tags, but the CP-SAT model never enforces the threshold check. |
| **✅ Fully** | `[H#91bc3d7e]` | Null skill level = no restriction | — | Handled by `required_skill_rank == -1` logic |
| **✅ Fully** | `[H#2f74e6ab]` | Multiple same-shift entries = separate positions | — | Each roster.yaml entry becomes a separate position index |
| **⚠️ Partial** | `[H#84a1d5c9]` | Skill level hierarchy (higher satisfies lower) | `SkillLevelHierarchy` | Class exists but `apply()` is `pass` / `TODO`. Data validation ensures contiguous prefix, but CP-SAT never encodes the threshold implication. |
| **✅ Fully** | `[H#6db3f120]` | Skill level ordering | — | `SKILL_HIERARCHY` list defines the order |
| **✅ Fully** | `[H#b72e41fa]` | Minimum skill level requirement | — | Handled by `required_skill_rank` in roster positions |
| **✅ Fully** | `[H#e91c63ab]` | No overlap (wall-clock) | `NoDoubleBooking` | Precomputed compatibility table + forbidden-assignment constraints per staff per consecutive day pair. |
| **✅ Fully** | `[H#d9a8b7c6]` | Contracted hours floor (adjusted for holidays) | `ContractedHoursFloor` | Fully implemented — `apply()` adds `model.Add(staff_hours_vars[si][bi] >= adjusted)` per staff per block. Receives `staff_hours_vars` matrix from `solver.py`. |
| **✅ Fully** | `[H#30479c74]` | Graduate shift restriction | `GraduateShiftConstraint` | Fully implemented — forbids Graduates from D12, P12, N12 |
| **✅ Fully** | `[H#c1f6e3f5]` | 11-hour rest between shifts (wall-clock) | `RestPeriodConstraint` | Precomputed 8×8 compatibility table + forbidden-assignment constraints per staff per consecutive day pair. Only N8→D8, N8→D12, N8→DISCO, N12→D8, N12→DISCO, DISCO→D8, DISCO→P8, L3→P8, L3→D8 are incompatible (all <11h gap). Uses `span_hours` from `definitions.yaml`.
| **✅ Fully** | `[H#f4c9b6c8]` | Day off between night↔day transitions | `NightToDayRest` | Precomputed 8×8 compatibility table (night↔day category mismatch = incompatible) + forbidden-assignment constraints per staff per consecutive day pair. Night shifts: N8, N12. Day shifts: D8, D12, P8, P12, L3, DISCO. Mixed-category pairs are forbidden. Casuals exempt per `[H#4ef8a2c3]`. |
| **✅ Fully** | `[H#a5d0c7d9]` | No rostering on red-request dates | `RedRequestConstraint` | Fully implemented |
| **✅ Fully** | `[H#b6e1d8e0]` | No rostering on holidays | `HolidayConstraint` | Fully implemented |
| **⚠️ Partial** | `[H#f0c5b2c4]` | 76h absolute paid-hour cap per block | `MaxHoursConstraint` | Class says "enforced in `_create_variables()` via IntVar upper bound" — the IntVar is created with `0, 76*SCALE` range, but this is a **variable bound**, not a constraint that can be violated and reported. It silently limits hours but doesn't distinguish between "under contracted" and "over contracted". The class's `apply()` is `pass`. |
| **✅ Fully** | `[H#a3d8f6c1]` | Holiday proration formula | `compute_adjusted_hours()` | Implemented in `utils.py` — computes `adjusted = floor(contracted * available_days / 14)` per staff per block, accounting for holiday overlap. Used by `[H#d9a8b7c6]`. |
| **✅ Fully** | `[H#e8f7d6c5]` | 12h overtime cap above raw contracted | `OvertimeCap` | Fully implemented — `apply()` adds `model.Add(staff_hours_vars[si][bi] <= min(76*SCALE, contracted+12*SCALE))` per staff per block. Uses raw `contracted_hours_per_fortnight` (not holiday-adjusted). |
| **✅ Fully** | `[H#c92f5e1b]` | Casuals only for null skill level positions | `CasualStaffingConstraint` | Fully implemented — creates `BoolVar` per null-skill position; enforces `sum(staff_vars) + casual_var == 1` for casual-allowed positions. For skill-required positions, standard "exactly one named staff" applies. Casuals are exempt from all individual constraints (rest, holidays, hours, etc.) by design. |
| **✅ Fully** | `[H#71b4d9ac]` | Unlimited casual supply | — | Trivially satisfied by design (no per-casual tracking, no capacity limits) |
| **✅ Fully** | `[H#4ef8a2c3]` | Casuals exempt from individual constraints | — | Trivially satisfied (casuals not tracked as individuals, not subject to rest/hours/holiday constraints) |

## Soft Constraints (7 constraint IDs across 7 classes)

| Status | Constraint ID | Description | Class | Notes |
|--------|--------------|-------------|-------|-------|
| **✅ Fully** | `[S#e9b4a1b3]` | Even overtime distribution | `OvertimeDistribution` | Fully implemented — deviation-from-mean overtime, uses `staff_hours_vars`. Weight=20. |
| **✅ Fully** | `[S#d2a7f4a6]` | Night shift fairness by contracted hours | `NightShiftFairness` | Fully implemented — proportional night hours deviation per staff per block. Weight=50. |
| **✅ Fully** | `[S#a1d6c3d5]` | Weekend hours fairness | `WeekendFairness` | Fully implemented — minimizes deviation from proportional weekend hours. Weight=50. |
| **✅ Fully** | `[S#30c6f5ad]` | Consecutive same-shift run length penalty (tiered) | `ConsecutiveShiftDiscouraged` | Fully implemented — `shift_type_vars` → `same_vars` → `run_start_vars` → `exact_L` enumeration. Tiered: L=2→0, L=1/3→W//10, L=4→W, L≥5→(L-3)W. Weight=500. |
| **✅ Fully** | `[S#7b4e19fc]` | Skill level tiebreaker (minimize over-qualification) | `SkillLevelTiebreaker` | Fully implemented — linear penalty `over_qual * assignment_bool`. Skips null skill positions. Weight=5. |
| **✅ Fully** | `[S#6c1e9a4d]` | Day/night category run-count penalty | `DayNightRunCountPenalty` | Fully implemented — `category_vars` (DAY/NIGHT/OFF) → `cat_run_start` → excess penalty for >2 runs per category. Weight=300. |
| **✅ Fully** | `[S#3d9a7ec1]` | Casual usage minimization (last resort) | `CasualUsageMinimization` | Fully implemented — minimizes sum of casual `BoolVar`s with weight 100000. Weight exceeds max possible combined penalty from every other soft constraint, ensuring casuals are always last resort. Receives `casual_vars` from `CasualStaffingConstraint` via `solver.py`. |

## Summary

| Category | Count |
|----------|-------|
| Fully implemented | 26 |
| Partially implemented | 3 |
| Not implemented (class exists, `apply()` = pass) | 0 |
| Not implemented (no class at all) | 0 |
| **Total constraint IDs** | **29** |

## Out-of-sync items (code/docs vs constraint files)

_None._

## Recent Changes

- **2026-08-05**: Fixed roster build failure — 4 soft constraint `apply()` methods (`WeekendFairness`, `ConsecutiveShiftDiscouraged`, `SkillLevelTiebreaker`, `DayNightRunCountPenalty`) missing `staff_hours_vars=None` parameter, causing `TypeError` when `solver.py` passed it to all soft constraints. Also fixed 2 CP-SAT reification bugs: `sw == sum(bool_vars) >= 1` in `ConsecutiveShiftDiscouraged` and `day_worked == sum(day_bools) >= 1` / `night_worked == sum(night_bools) >= 1` in `DayNightRunCountPenalty` — these parsed as chained comparisons `(sw == sum(bool_vars)) >= 1` instead of reified constraints. Fixed by replacing with `.OnlyEnforceIf()` pairs. Roster generation: OPTIMAL, 404 assignments, 0 casual, 0 unfilled. All 136 tests pass.
- **2026-08-05**: Implemented all 5 remaining soft constraints (S#e9b4a1b3, S#d2a7f4a6, S#30c6f5ad, S#7b4e19fc, S#6c1e9a4d). **3 bugs fixed during implementation**:
  1. `ConsecutiveShiftDiscouraged` shift_type_vars: lines 763/771 created duplicate `shift_worked` BoolVars per shift type, leaving `st` IntVars unconstrained. Merged into single loop with shared `shift_worked_vars` dict.
  2. `ConsecutiveShiftDiscouraged` L=1: `model.Add(rs == 0).OnlyEnforceIf(exact_L.Not())` forced `rs=0` when `rs` was actually `1`, causing INFEASIBLE. Removed the line.
  3. `SkillLevelTiebreaker`: `NewIntVar(0, sum(t for t in penalty_terms), ...)` summed IntVars → not a valid upper bound. Accumulated `max_penalty` as integer during loop.
  - `OvertimeDistribution`: constraints.py:539, weight=20, deviation-from-mean overtime.
  - `NightShiftFairness`: constraints.py:574, weight=50, proportional night hours deviation.
  - `ConsecutiveShiftDiscouraged`: constraints.py:702, weight=500, run-length enumeration with tiered penalties.
  - `SkillLevelTiebreaker`: constraints.py:896, weight=5, linear over-qualification penalty.
  - `DayNightRunCountPenalty`: constraints.py:943, weight=300, category run counting with excess penalty.
  - All 5 classes registered in `SOFT_CONSTRAINTS` list. `config.yaml` updated: hard constraints disabled, 5 soft constraint IDs enabled.
  - Added `tests/test_soft_constraints.py` with 11 tests across 5 test classes.
  - All 136 tests pass.
- **2026-08-05**: Implemented `[H#c92f5e1b]` / `[S#3d9a7ec1]` (casual staffing) — `CasualStaffingConstraint` hard constraint creates `BoolVar` per null-skill position enforcing "exactly one named staff OR casual"; `CasualUsageMinimization` soft constraint minimizes sum of casual vars with weight 100000. Added `filled_by_casual` field to `RosterSlot`, `casual_allowed` tag to positions in `utils.py`. Updated `solver.py` to store/pass `casual_vars` between hard and soft constraints, and extract casual assignments in output. Updated `config.yaml` with single casual hard constraint entry (covers all 3 casual IDs). Added 15 tests in `tests/test_casual.py`. All 125 tests pass. Roster generation produces OPTIMAL with 404 assignments, 0 casual, 0 unfilled.
- **2026-08-05**: Implemented `[H#e8f7d6c5]` (12h overtime cap above raw contracted) — `OvertimeCap` class with `apply()` adding `model.Add(staff_hours_vars[si][bi] <= min(76*SCALE, contracted+12*SCALE))` per staff per block. Uses raw `contracted_hours_per_fortnight` (not holiday-adjusted). Added 4 tests (positive: within cap, boundary at cap; negative: exceeds cap, raw vs adjusted). All 110 tests pass. Roster generation produces OPTIMAL with 404 assignments, 0 unfilled.
- **2026-08-05**: Implemented `[H#d9a8b7c6]` (contracted hours floor) and `[H#a3d8f6c1]` (holiday proration) — `ContractedHoursFloor` class with `apply()` adding `model.Add(staff_hours_vars[si][bi] >= adjusted)` per staff per block. Added `compute_adjusted_hours()` to `utils.py` for holiday proration. Wired `staff_hours_vars` into `solver.py` hard/soft constraint `apply()` calls. Updated `output.py` and `templates/roster.html` to display adjusted hours with traffic light (green ≥100%, yellow 85–99%, red <85%). Added 10 tests (8 for `compute_adjusted_hours`, 2 for `ContractedHoursFloor`). Fixed `definitions.yaml` comment: "24h" → "12h" overtime cap. All 106 tests pass. Roster generation produces feasible output.
- **2026-08-05**: Implemented `[H#c1f6e3f5]` (11-hour rest period constraint) — `RestPeriodConstraint` class with precomputed compatibility table. Fixed stale shift definitions in all test classes to match `definitions.yaml`. All 84 tests pass.
- **2026-08-05**: Implemented `[H#f4c9b6c8]` (night↔day transition rest constraint) — `NightToDayRest` class with 8×8 compatibility table enforcing full day-off between night (N8/N12) and day (D8/D12/P8/P12/L3/DISCO) shifts. Added 11 tests across `TestNightToDayRestCompatibilityTable` and `TestNightToDayRestApply`. Fixed test isolation bug in `test_config.py::_make_model()` — restored original `apply()` methods via `constraint_id`-keyed dict instead of broken shallow-copy restoration. All 96 tests pass. Roster generation produces OPTIMAL with 404 assignments, 0 unfilled.
