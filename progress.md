# Progress — AI-Roster Code Review & Implementation Plan

## Plan file: plan.md

## User decisions (from plan.md §0.1)
- D1: (a) — Normalise deviations to whole hours + restate dominance invariant
- D2: (a) — Restate dominance as marginal cost
- D3: (a) — per-block run-length scope for S#30c6f5ad
- D4: (a) — per-block Sat/Sun fairness
- D5: (a) — code is right (empty enabled = all enabled)
- D6: (a) — expose solver config in config.yaml
- D7: (a) — reset slot_id counter per date
- D8: (b) for Coverage + MaxHours; (a) for ContractedHoursFloor + SkillLevelHierarchy
- D9: (a) — delete line 10 of soft_constraints.md (duplicate S#a1d6c3d5)
- D10: (a) — pyproject.toml + direct deps + ruff + ty
- D11: (a) — split constraints.py
- D12: (a) — match run_id to doc (YYYYMMDD_HHMMSS)

---

## Execution order from plan.md §7

### Step 1: Ground truth — resolve §6.1 contradictions
- [x] D9: soft_constraints.md line 10 — duplicate [S#a1d6c3d5] already removed
- [x] soft_constraints.md line 20 — [H#f4c9b6c8] citation is legitimate cross-reference
- [x] config.yaml line 22 — [H#d9a8b7c6] already commented out
- [x] AGENTS.md §9 — already restated as marginal bound
- [x] AGENTS.md §10 — empty `enabled:` list semantics already documented correctly
- [x] AGENTS.md §6 vs main.py — run_id format already matches doc (DONE)
- [x] AGENTS.md §6 vs template — UNFILLED marker already documented as "planned but not yet implemented"
- [x] AGENTS.md §7 — overtime cap history already trimmed

**Status: COMPLETE — 2026-08-07**

#### Already resolved (no change needed):
- D9: `soft_constraints.md` — no non-struck-out [S#a1d6c3d5] found (already removed)
- `soft_constraints.md` line 20 `[H#f4c9b6c8]` citation — legitimate cross-reference in prose
- `config.yaml` line 22 — [H#d9a8b7c6] already commented out
- AGENTS.md §9 — already restated as marginal bound
- AGENTS.md §10 — empty `enabled:` list semantics already documented correctly

### Step 2: P0 correctness — §2.1, §2.2, §2.5, §2.4, §2.7
- [x] §2.1: S#30c6f5ad three-way reification — replaced `Add(same==1).OnlyEnforceIf(not_unassigned_d, not_unassigned_d1)` with proper `AddBoolAnd`/`AddBoolOr` conjunction (§2.1, constraints.py:909-930)
- [x] §2.2: S#30c6f5ad·L=1 penalty — L==1 now uses same `AddBoolAnd`/`AddBoolOr` machinery as L≥2; removed dead `total_penalty * 1` multiplier (§2.2, constraints.py:971-984, 1021-1024)
- [x] §2.5: Constraint-markdown parser — regex `[A-Za-z0-9]` (not hex-only); bullet-start-only new records; in-body references treated as prose; duplicate ID detection; `assert` → `ValueError` (§2.5, utils.py:254-330)
- [x] §2.4: slot_id collision — counter key changed from `(week_offset, day_name, shift, skill_label)` to `(date, shift, skill_label)`; deleted magic 15-row cap in output.py (§2.4, utils.py:457-498; output.py:267-272)
- [x] §2.7: Overtime traffic light — period-level comparison now uses `contracted × len(blocks)` instead of single-block contracted (§2.7, output.py:144-149)

**Status: COMPLETE — 2026-08-07**

All 139 tests pass. Solve still hits 300s limit (expected — §2.3 objective rescaling not yet implemented).

### Step 3: §2.3 Objective rescaling
- [x] Add _fair_share_deviation() helper using whole paid hours
- [x] Fix WeekdayNightFairness expected_night computation
- [x] Delete utils.NIGHT_HOURS dict
- [x] Restate and implement marginal dominance bound

**Status: COMPLETE — 2026-08-07**

### Step 4: §5.1 Verifier
- [ ] Create verify.py with independent hard constraint checks
- [ ] Wire into main._run() between solve and output
- [ ] Add tests/test_verify.py

**Status: NOT STARTED**

### Step 5: §2.6, §2.8, §2.9, §2.10
- [ ] §2.6: Soft-constraint penalties never reported
- [ ] §2.8: CP-SAT search log not captured
- [ ] §2.9: INFEASIBLE not treated as failure
- [ ] §2.10: Config-toggle semantics + make Coverage/MaxHours toggles honest

**Status: NOT STARTED**

### Step 6: §3 performance refactor
- [ ] §3.1: Shared shift-type indicator variables
- [ ] §3.2: SkillLevelRequirement proper model.Add
- [ ] §3.3: S#30c6f5ad per-block run enumeration
- [ ] §3.4: Extract duplication helpers
- [ ] §3.5: ModelContext dataclass

**Status: NOT STARTED**

### Step 7: §5.3/§5.4 test rebuild, §4 hygiene, §6 docs
- [ ] §5.3: Fix test fixtures (real definitions, real Staff dataclass)
- [ ] §5.4: Extend test_constraint_sync.py
- [ ] §5.5: Add missing coverage (e2e smoke, regression tests)
- [ ] §4: Delete dead code, move imports, error handling, template fixes
- [ ] §6: Documentation updates

**Status: NOT STARTED**

### Step 8: Optional — snake_case migration
- [ ] Mechanical pass: OR-Tools CamelCase → snake_case

**Status: NOT STARTED**

---

Last updated: 2026-08-07 (Step 2 complete)
