# Constraint Implementation Audit & Plan

## Hard Constraints (13 constraint IDs across 11 classes)

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
| **⚠️ Partial** | `[H#e91c63ab]` | No overlap (wall-clock) | `NoDoubleBooking` | Compatibility table built and applied, but **only checks for actual time overlap**. Does **not** check the 11-hour rest period (that's a separate constraint). |
| **✅ Fully** | `[H#30479c74]` | Graduate shift restriction | `GraduateShiftConstraint` | Fully implemented — forbids Graduates from D12, P12, N12 |
| **❌ Not Impl** | `[H#c1f6e3f5]` | 11-hour rest between shifts (wall-clock) | `RestPeriodConstraint` | `apply()` is `pass` / `TODO`. The compatibility table in `NoDoubleBooking` only catches overlaps, not insufficient rest. **This means shifts like N8 (ends 07:15) → D8 (starts 07:00 next day) [overlap] are caught, but N8 (ends 07:15) → D8 (starts 08:00 next day) [7h 15m gap] is NOT caught.** |
| **❌ Not Impl** | `[H#f4c9b6c8]` | Day off between night↔day transitions | `NightToDayRest` | `apply()` is `pass` / `TODO`. Completely missing. |
| **✅ Fully** | `[H#a5d0c7d9]` | No rostering on red-request dates | `RedRequestConstraint` | Fully implemented |
| **✅ Fully** | `[H#b6e1d8e0]` | No rostering on holidays | `HolidayConstraint` | Fully implemented |
| **⚠️ Partial** | `[H#f0c5b2c4]` | 76h absolute paid-hour cap per block | `MaxHoursConstraint` | Class says "enforced in `_create_variables()` via IntVar upper bound" — the IntVar is created with `0, 76*SCALE` range, but this is a **variable bound**, not a constraint that can be violated and reported. It silently limits hours but doesn't distinguish between "under contracted" and "over contracted". The class's `apply()` is `pass`. |
| **❌ Not Impl** | `[H#d9a8b7c6]` | Contracted hours floor (adjusted for holidays) | `ContractedHoursFloor` | `apply()` is `pass` / `TODO`. **Completely missing.** Staff can be assigned zero hours and the model won't complain. |
| **❌ Not Impl** | `[H#a3d8f6c1]` | Holiday proration formula | — | **Completely missing.** No code computes `adjusted_hours` per staff per block. |
| **❌ Not Impl** | `[H#e8f7d6c5]` | 12h overtime cap above raw contracted | `OvertimeCap` | `apply()` is `pass` / `TODO`. **Completely missing.** Note: `definitions.yaml` comment still says "24h overtime cap" — needs updating. |
| **❌ Not Impl** | `[H#c92f5e1b]` | Casuals only for null skill level positions | — | **Completely missing.** No casual assignment variable, no restriction logic. |
| **✅ Fully** | `[H#71b4d9ac]` | Unlimited casual supply | — | Trivially satisfied by design (no per-casual tracking) |
| **✅ Fully** | `[H#4ef8a2c3]` | Casuals exempt from individual constraints | — | Trivially satisfied (casuals not tracked as individuals) |

## Soft Constraints (7 constraint IDs across 5 classes)

| Status | Constraint ID | Description | Class | Notes |
|--------|--------------|-------------|-------|-------|
| **❌ Not Impl** | `[S#e9b4a1b3]` | Even overtime distribution | `OvertimeDistribution` | `apply()` is `pass` / `TODO` |
| **❌ Not Impl** | `[S#d2a7f4a6]` | Night shift fairness by contracted hours | `NightShiftFairness` | `apply()` is `pass` / `TODO` |
| **✅ Fully** | `[S#a1d6c3d5]` | Weekend hours fairness | `WeekendFairness` | Fully implemented — minimizes deviation from proportional weekend hours |
| **❌ Not Impl** | `[S#30c6f5ad]` | Consecutive same-shift run length penalty (tiered) | `ConsecutiveShiftDiscouraged` | `apply()` is `pass` / `TODO`. Per AGENTS.md §8: needs run_start booleans, run-length booleans, and tiered penalties (0 / 0.1W / 1W / (L-3)W) |
| **❌ Not Impl** | `[S#7b4e19fc]` | Skill level tiebreaker (minimize over-qualification) | `SkillLevelTiebreaker` | `apply()` is `pass` / `TODO` |
| **❌ Not Impl** | `[S#6c1e9a4d]` | Day/night category run-count penalty | — | **Completely missing — no class at all.** Per AGENTS.md §8: needs category (day/night) run_start booleans, then `(max(0, day_run_count - 2) + max(0, night_run_count - 2)) * W` |
| **❌ Not Impl** | `[S#3d9a7ec1]` | Casual usage minimization (last resort) | — | **Completely missing — no class at all.** Needs casual assignment variable + weight 100000 penalty. Must only apply to null-skill-level positions. |

## Summary

| Category | Count |
|----------|-------|
| Fully implemented | 12 |
| Partially implemented | 4 |
| Not implemented (class exists, `apply()` = pass) | 6 |
| Not implemented (no class at all) | 3 |
| **Total constraint IDs** | **25** |

## Out-of-sync items (code/docs vs constraint files)

1. **`definitions.yaml` line 11**: Comment says "24h overtime cap" — should say "12h" per `[H#e8f7d6c5]`
2. **Tests use stale shift definitions**: `test_constraints.py` defines shifts with different times than `definitions.yaml` (e.g., N8 starts 20:30 in tests vs 22:45 in data). Tests won't catch real-world overlap/rest bugs.
