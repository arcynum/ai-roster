# AI-Roster — Progress Tracker

Based on `plan.md` (Update Plan v2). This file serves as the restart point for all remaining changes.

---

## §0. Re-audit (previous plan) — ✅ COMPLETE

Casual purge, unfilled-first coverage, tiered unfilled mechanism, soft-floor reclassification — all confirmed implemented. No leftover casual code.

---

## §1. Preference/desirability model — ✅ COMPLETE

### §1.2 Revised tier design — ✅ COMPLETE
- Tier ordering: skill-required (220000) > Sunday (210000) > Saturday (200000) > weekday day (160000) > weekday night (140000)
- New IDs minted: `S#f1a2b3c4`, `S#a2b3c4d5`, `S#b3c4d5e6`, `S#c4d5e6f7`
- Old tier IDs retired in `weights.yaml` comments
- `_apply_coverage_constraint` in `solver.py:266-326` implements the ordering
- `soft_constraints.md:24-34` documents all 5 tiers

### §1.3a NightShiftFairness weekend exclusion — ✅ COMPLETE
- `constraints.py:658-661`: excludes Saturday/Sunday (`weekday() not in (5, 6)`)
- `weights.yaml:9`: weight 50 for weekday-only night fairness

### §1.3b WeekendFairness split — ✅ COMPLETE
- `SaturdayFairness` (`S#s1a2t3u4`) and `SundayFairness` (`S#s2u3n4d5`) classes in `constraints.py:708-829`
- Old `WeekendFairness` (`S#a1d6c3d5`) removed from `SOFT_CONSTRAINTS` registry
- `soft_constraints.md:36-39` documents the replacement

### §1.4 DISCO classification — ✅ COMPLETE (implicit)
- DISCO stays in `DAY_SHIFTS`, falls through to weekday day tier (4) in coverage constraint
- No explicit confirm received, but implementation is correct per existing AGENTS.md convention

---

## §2. Single unified "Roster by Shift" table — ✅ COMPLETE

**Changes made:**
1. `output.py:229-297`: Replaced `shift_slot_tables` with `shift_slot_table` (flat dict of slot_id→{date→staff}) and `slot_meta_list` (list of slot metadata with day_validity)
2. `output.py:340-341`: Return `shift_slot_table` + `slot_meta_list` instead of `shift_slot_tables`
3. `templates/roster.html:238-269`: Single `<table>` over `slot_meta_list`, with `—` greyed cells for slots that don't exist on a given day-of-week
4. `tests/test_output.py:265-274`: Updated test to check new flat structure

---

## §3. Weight bug fix — ✅ COMPLETE

### §3.1 Bracket mismatch — ✅ FIXED
- `weights.yaml` now uses bracketed keys (`"[S#30c6f5ad]"`) matching the convention everywhere else
- Confirmed: `constraints.py` uses `constraint_id = "[S#...]"` format

### §3.2 Startup validation — ✅ FIXED
- `utils.py:133-173` `load_weights()` validates every registered soft constraint ID and unfilled tier ID has a corresponding entry
- Raises `ValueError` if any are missing
- Called from `main.py:74-77` with `known_soft_ids` and `known_unfilled_tier_ids`

### §3.3 Test fix — ✅ COMPLETE (was already done)
- `tests/test_integration.py:177-216` already uses `get_soft_constraint_ids()` and `RosterModel.UNFILLED_TIER_IDS`
- Uses bracketed keys, exercises the actual runtime lookup path
- All 3 integration tests pass

### §3.4 Re-tune with real data — ⏸ BLOCKED (see §6 — weights were still flat=1 in last run)
- Weights correctly formatted, tests pass, but need to verify actual roster output reflects real weights

---

## §4. Hours summary split — ✅ COMPLETE

**Changes made:**
1. `output.py:310-395`: Compute both `available_no_overtime` (holiday-prorated) and `available_with_overtime` (min(76, raw+12)) per block
2. `output.py:404-419`: Return new fields: `total_available_no_overtime`, `total_available_with_overtime`, `total_surplus_no_overtime`, `total_surplus_with_overtime`, plus percentage-based labels
3. `templates/roster.html:145-186`: Run Summary shows 5 cards (Required, Available contracted, Available with OT, Surplus no OT, Surplus with OT); Block table shows 7 columns
4. `templates/roster.html:153,155`: Caveat tooltips on with-overtime cards
5. `tests/test_output.py:287-306`: Updated test for new field names

---

## §5. Constraint ID reconciliation — PARTIALLY COMPLETE

### §5.1 Unfilled sub-tier IDs in soft_constraints.md — ✅ COMPLETE
- `soft_constraints.md:24-34` documents all 5 tiers with their weights

### §5.2 Hard constraints documentation — ✅ COMPLETE (with caveats)
- `hard_constraints.md` has 19 distinct `[H#...]` IDs
- `constraints.py` has 11 registered classes
- Some IDs are implemented indirectly (H#a3d8f6c1 in `compute_adjusted_hours`, H#d9a8b7c6 reclassified to soft, H#84a1d5c9/H#6db3f120 merged into SkillLevelRequirement)
- No explicit "implemented elsewhere" annotation, but the markdown files are readable and accurate
- `config.yaml` has all 11 hard constraint IDs commented out

### §5.3 Automated sync check — ✅ COMPLETE
- `tests/test_constraint_sync.py` — 4 tests: hard ID sync, soft ID sync, allow-list pointer validation, duplicate ID check
- `IMPLEMENTED_ELSEWHERE` dict tracks IDs implemented indirectly (8 entries with pointers)
- All 139 tests pass

### §5.4 Wording pass — ✅ COMPLETE
- `soft_constraints.md` updated with new tier descriptions ✅
- `hard_constraints.md` has strikethrough for reclassified H#d9a8b7c6 ✅
- `AGENTS.md` §7 fill-order was already correct (matches new tier ordering) ✅
- `AGENTS.md` §9 weight-dominance: updated `S#a1c4f6d7` → `S#c4d5e6f7` (weekday night, 140000) ✅
- `README.md:150` config example: updated `S#a1d6c3d5` → `S#s1a2t3u4` (SaturdayFairness) ✅

---

## §6. Other issues — ✅ ALL RESOLVED

### §6 "Parsed vs applied" log message — ✅ FIXED
- `main.py:70-74`: added log line showing "N documented in hard_constraints.md, M registered as classes"
- Gap is now transparent to the reader

### §6 AGENTS.md updates — ✅ FIXED (see §5.4)
- §7 fill-order was already correct ✅
- §9 weight-dominance: updated to `S#c4d5e6f7` (weekday night) ✅

### §6 README.md quick pass — ✅ FIXED
- `README.md:150`: updated `S#a1d6c3d5` → `S#s1a2t3u4` (SaturdayFairness) ✅

### §6 NightShiftFairness renaming — ✅ RENAMED
- `NightShiftFairness` → `WeekdayNightFairness` in `constraints.py` and `tests/test_soft_constraints.py`
- ID `[S#d2a7f4a6]` unchanged
- Docstring already said "weekday night" — name now matches behavior

---

## Remaining Tasks (Priority Order)

1. ~~**§3.3 Fix test_integration.py** — update weight-dominance test to use actual runtime IDs (bracketed) and new unfilled tier IDs.~~ ✅ ALREADY DONE

2. ~~**§2 Unified "Roster by Shift" table** — replace per-shift-type tables with a single 15-row table.~~ ✅ DONE

3. ~~**§4 Hours summary split** — add with-overtime figure alongside contracted-only.~~ ✅ DONE

4. ~~**§5.3 Automated sync check** — add a test that parses `.md` files for constraint IDs and asserts each is registered or in an allow-list.~~ ✅ DONE

5. ~~**§5.4 Wording pass** — update `AGENTS.md` §7/§9 and `README.md` to reflect new tier ordering and current IDs.~~ ✅ DONE

6. ~~**§6 "Parsed vs applied" log message** — clarify the startup log to distinguish "documented" from "implemented as constraints".~~ ✅ DONE

7. ~~**§6 NightShiftFairness renaming** — rename to `WeekdayNightFairness`.~~ ✅ DONE

8. **§3.4 Re-tune with real data** — ⏸ IN PROGRESS. Weights confirmed correct in log output. Solver still running (large problem: 42 staff, 404 positions, 16968 variables). HTML output pending.
