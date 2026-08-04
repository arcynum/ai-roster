# AGENTS.md — AI-Roster

This is the entry point for any agent (opencode or otherwise) working on this project. Read this file first, in full, before touching code. It is the single source of truth for how the pieces fit together — if another doc, comment, or file conflicts with what's written here, **this file wins**; flag the conflict rather than silently picking one.

---

## 🚧 0. Project Status — Work In Progress. Read before doing anything else.

**This project is not finished. Existing code is not presumed correct.**

- **The ground truth is the constraint/data files** — `hard_constraints.md`, `soft_constraints.md`, `roster.yaml`, `staff.yaml`, `definitions.yaml`, `weights.yaml`, and this document. **Code is not ground truth** until it's been verified against those files line-by-line. If code contradicts them, the code is wrong — not the other way around.
- **The existing test suite is not automatically trustworthy either.** Tests were plausibly written against the broken implementation. If a test asserts behavior that contradicts a hard/soft constraint ID, the test is the thing to fix, not the code you'd otherwise write to satisfy it.
- **You have explicit standing permission to change, rewrite, or delete existing code** in `.py`, and `tests/` when it conflicts with the constraint files — you do not need to ask first, and you do not need to preserve current output behavior for compatibility. There is no live consumer depending on the current (broken) behavior.
- This overrides the "reuse what's already here" step in the Ponytail ladder below (§10, step 2) specifically for `.py`/`tests/`: reuse is still the right instinct everywhere else in the codebase, but for these three, verify against the constraint files first — don't treat "it's already implemented this way" as a reason to keep it.
- When you find and fix a real discrepancy between code and the constraint files, say so plainly in your summary (what was wrong, which constraint ID it violated) rather than quietly patching around it.

---

## 1. Project Overview

This project builds a fortnightly roster for the pediatric emergency ward at TPCH, using Google OR-Tools **CP-SAT** to satisfy a set of hard constraints while optimizing a weighted set of soft constraints.

## 2. Canonical Terminology

The project's history has left three different names for the same underlying concept scattered across files. Going forward, use these terms consistently in **prose, docs, and new code**:

| Canonical term | What it means | Where it actually appears in data |
|---|---|---|
| **Skill level** | A staff member's training/qualification tier | `hard_constraints.md` prose; `roster.yaml`'s `required_skill_level` field (singular, `null` = no requirement) |
| **Held skill levels** | The set of skill levels a staff member has attained | `staff.yaml`'s `skill_tags` field (a list) |
| **Classification** | A staff member's organisational role — separate concept from skill level | `staff.yaml`'s `classification` field: `RN`, `CN`, or `Graduate` |

Do not introduce a fourth synonym ("training level", "skill tag" in prose, etc.) — if you see one in an old doc, treat it as meaning "skill level" and consider updating the doc.

### Classification vs. Skill Level (previously conflated — now resolved)

These are two **independent** attributes on a staff member, not one hierarchy:

- **Classification** — one of `RN`, `CN`, `Graduate`. This is an organisational/employment category, not a proficiency ranking.
- **Skill level hierarchy** — `Acute < Resus < Triage < Shift Coordinator` (4 levels; see `hard_constraints.md` [H#84a1d5c9]/[H#c18b42de]). A staff member with a higher skill level satisfies requirements for all lower ones (threshold semantics, not exact-match).

**Graduate is a classification, not a skill level.** Staff classified as `Graduate` typically hold `skill_tags: [Acute]` in `staff.yaml` — they have a real skill level like anyone else, it's their classification that restricts them. Per [H#30479c74], Graduate-classified staff may only be assigned to D8, P8, L3, DISCO, and N8, regardless of skill level held.

## 3. Core Architecture — File Map

- **`opencode.json`** — the model/provider configuration for the coding agent.
- **`definitions.yaml`** — shift definitions: start time, end time, `span_hours` (wall-clock duration including unpaid break), `paid_hours` (actual worked/paid duration), `unpaid_break_minutes`, and `crosses_midnight` (explicit boolean — never infer this by comparing start/end times). **Which duration field to use matters and they are not interchangeable** — see §5.
- **`roster.yaml`** — the roster period (`dates.start`/`dates.end`) and the list of roster positions required per day of the week, under the `roster_positions:` key. Each entry has `shift` and `required_skill_level` (a skill level string, or `null` meaning no restriction). **This file is the literal source of truth for shift counts and skill requirements per day — don't hardcode counts elsewhere in docs or code; read this file.** Entries repeat identically every week of the roster period.
- **`hard_constraints.md`** — non-negotiable rules, each tagged with a unique `[H#xxxxxxxx]` ID. Must all hold in the final roster.
- **`soft_constraints.md`** — preference rules, each tagged with a unique `[S#xxxxxxxx]` ID, optimized via the objective function. If one isn't satisfied, the solver/output should be able to account for why.
- **`staff.yaml`** — every staff member: `name`, `classification`, `skill_tags` (held skill levels), `contracted_hours_per_fortnight` (a **floor**, not a ceiling — see §7), `red_requests`, `holidays`. See `README.md`'s `staff.yaml` field reference for the full schema, and §4 below for validation rules specific to this file.
- **`weights.yaml`** — objective-function weights keyed by soft constraint ID. These are **relative ordering signals, not literal cost units** — a weight of 100 means "prioritise avoiding this over one weighted 50," not "twice as bad" in any absolute sense. Don't build logic elsewhere that assumes proportionality between weights.
- **`templates/roster.html`** — the Jinja2 template for roster HTML output. Self-contained (inline CSS, no external assets). See §6 for content requirements.
- **`output/`** — created at runtime, not checked into the repo. Holds every run's paired `roster_<run_id>.html` and `roster_<run_id>.log` — see §6 for the full spec.

**Fortnightly blocks**: rosters must span an exact multiple of 14 days. All constraints (max hours, etc.) apply *within* each discrete 14-day block, never averaged across the whole roster period. If `roster.yaml`'s date range isn't a whole multiple of 14 days, the script must error out with a clear message and refuse to build — never silently round, truncate, or prorate.

## 4. Data File Validation

`staff.yaml`, `roster.yaml`, `definitions.yaml`, `hard_constraints.md`, `soft_constraints.md` are hand-edited by humans — treat parsing them as input validation, not just data loading. If a row is malformed, missing a required field, references an undefined skill level/shift/staff member, or a date is out of range: fail loudly with a message naming the file, the row, and the problem. Never silently skip or guess a default.

### `staff.yaml`-specific rules

- **`name` must be unique across the file.** It's the identifier used to cross-reference `red_requests`/`holidays` — a duplicate name is a data error, fail loudly rather than merging or picking one.
- **`classification` must be exactly one of `RN`, `CN`, `Graduate`.** Any other value is a data error.
- **`skill_tags` must be a contiguous prefix of the hierarchy** `Acute < Resus < Triage < Shift Coordinator` — i.e. a staff member can hold `[Acute]`, `[Acute, Resus]`, `[Acute, Resus, Triage]`, or all four, but never a level without every level below it (e.g. `[Resus]` alone, or `[Acute, Triage]` skipping `Resus`, is invalid). This matches every existing entry in `staff.yaml` and is required for the threshold-based skill check in §2/§8 to mean anything. **List order within `skill_tags` is not semantically meaningful** — determine a staff member's actual rank by looking up each tag against the hierarchy, don't rely on list position or count.
- **`contracted_hours_per_fortnight`** is a `paid_hours`-basis figure (see §5) and must be a positive number.
- **`red_requests`** is a list of `YYYY-MM-DD` date strings (may be empty). Does not reduce the contracted-hours floor (see §7 / `H#d9a8b7c6` / `H#a3d8f6c1`).
- **`holidays`** is a list of `{start, end}` date-range objects, both `YYYY-MM-DD` strings (may be empty). A single-day holiday is represented as `start == end` — there is no separate scalar shorthand for a one-day holiday. `start` must not be after `end`. Holidays proportionally reduce the contracted-hours floor for the affected block.

## 5. Shift Definitions & the Day/Night Split

Shifts (from `definitions.yaml`): `D8, D12, P8, P12, L3, DISCO, N8, N12`.

- **Day shifts**: `D8, D12, P8, P12, L3, DISCO`
- **Night shifts**: `N8, N12`

**DISCO exception — read carefully:** DISCO runs 17:30→02:00 and crosses midnight, the same way N8/N12 do. Despite that, **DISCO is classified as a day shift** for all fairness/reporting purposes. This is a deliberate exception, not an oversight — don't "fix" it by moving DISCO into the night bucket.

### Overnight Shift Attribution

Any shift that crosses midnight (DISCO, N8, N12) counts entirely toward the date and 14-day block **it starts on** — never the date it ends on, and never split across both. (Per the exception above, DISCO's hours still land in the day-shift bucket even though the shift itself crosses midnight — attribution-by-start-date and day/night classification are two separate rules.)

### Span Hours vs. Paid Hours

Every shift's stated duration (8.5h for the 8-hour shifts, 12.5h for the 12-hour shifts) includes a **30-minute unpaid break**. `definitions.yaml` gives you both figures explicitly — never derive one from the other via a hardcoded "minus 30 minutes," always read the field:

- **`span_hours`** — wall-clock start-to-end duration, unpaid break included. Use for anything about physical presence/timing: the 11-hour rest-period gap ([H#c1f6e3f5]), the no-double-booking/overlap check ([H#e91c63ab]).
- **`paid_hours`** — `span_hours` minus the break. Use for anything measured against contracted hours: the contracted-hours floor ([H#d9a8b7c6]), the 76h absolute cap ([H#f0c5b2c4]), the 12h overtime cap ([H#e8f7d6c5]), and every hour total / weekend % / night % figure.

**These are not interchangeable.** Using `span_hours` anywhere the constraint files say "hours" (contracted, cap, overtime) overcounts every shift by 30 minutes — across a 14-day block with ~10 shifts that's up to 5 hours of drift per staff member, easily enough to push someone over or under a hard cap incorrectly. If you find code computing hours-worked totals from `span_hours` (or from raw start/end time deltas) for anything contracted-hours-related, that's a bug — fix it to use `paid_hours`.

## 6. Output & Logging

**There are no `result.*.md` files.** Markdown output was removed entirely. Every run produces exactly two files, both in an `output/` subfolder at the project root (create it if it doesn't exist — never write output files to the project root):

- **`output/roster_<run_id>.html`** — the only output artifact. Single self-contained HTML file (inline `<style>`, no external asset dependencies — it must open and render correctly on its own, e.g. as an email attachment or on a machine with no internet access).
- **`output/roster_<run_id>.log`** — the full run log for that same run (see "Logging" below).

`<run_id>` is a timestamp (e.g. `20260803_143012`, local time is fine) generated once per run and shared by both files, so a run's HTML output and its log are always trivially pairable by filename. **Runs are never overwritten** — every invocation adds a new pair of files to `output/`; don't delete or replace prior runs automatically. (If `output/` needs pruning, that's a manual/operator decision, not something the script does.)

### HTML content requirements

The HTML file has three sections, in this order:

1. **Run summary** — generated timestamp, roster period (`dates.start`–`dates.end` from `roster.yaml`), CP-SAT solver status (e.g. `OPTIMAL`/`FEASIBLE`/`INFEASIBLE`), objective value, solve time, assignments count, and unfilled positions count. Displayed as summary cards in a responsive grid.
2. **Messages** — everything that used to live in `result.violations.md`, plus general solver messages: any `UNFILLED` shifts (date, shift type, required skill/classification), any hard constraint that couldn't be satisfied (should never happen in a correct solve, but report it if it does — don't fail silently), which soft constraints incurred a penalty and roughly how much, overtime allocation notes, and **a summary of casual usage** — total casual shifts used, and which dates/shifts they filled, so it's visible at a glance how much the roster relied on casuals rather than named staff. Explicitly says "No violations or unfilled shifts" when there's nothing to report.
3. **Roster** — everything that used to live in `result.staff.md` and `result.roster.md`, as two views:
   - **By date (staff×days matrix)**: one row per staff member, one column per day. Shifts shown as color-coded badges (D8=#E3F2FD, D12=#BBDEFB, P8=#F3E5F5, P12=#E1BEE7, L3=#FFF3E0, DISCO=#FFE0B2, N8=#E8F5E9, N12=#C8E6C9). Weekend columns highlighted with a light indigo background. First column (staff name) is sticky on scroll. Empty cells are blank; unfilled shifts show a red "UNFILLED" marker.
   - **By staff member**: classification, skill tags, contracted hours, total assigned hours, weekend/night hours and %, plus an **overtime traffic light** indicator (green = on or under contracted, yellow = 0–15% over, red = >15% over). Below that, a **block-by-block table** (per 14-day block) showing hours, contracted, overtime %, weekend %, night %, and shift count — each with its own traffic light. Ends with the full shift list as color-coded badges with date tooltips.

### Logging

Use Python's standard `logging` module — no new dependency. Each run:

- Creates a logger configured at the start of the run (in `main.py`, or a small `setup_logging()` helper in `utils.py` if that reads cleaner — don't invent a dedicated logging module for this, it's a few lines).
- Writes to **both** `output/roster_<run_id>.log` (full detail: `DEBUG` and up) and the console (`INFO` and up, so a human running it interactively isn't flooded).
- Covers the **whole run**, not just the solver: data loading and validation (which files were read, any validation failures caught per §4), constraint/model construction, the solve itself (CP-SAT's own log output should be captured here too, not just the final status), and output writing (confirmation the HTML file was written, its path).
- Each log line includes a timestamp, level, and module/logger name, e.g. `2026-08-03 14:30:12 INFO models: loaded 42 staff from staff.yaml`.
- Validation failures and hard-constraint violations should log at `ERROR` or `WARNING` respectively — don't bury a real problem at `INFO`.

## 7. Operational Definitions

### Coverage Shortfalls & Overtime

`contracted_hours_per_fortnight` is a **minimum**, not a cap. The fill order for any roster position, most preferred first, is:

1. **Named staff within their contracted-hours floor.** Optimise this tier for named-staff wellbeing first — well-distributed hours, fair night/weekend load ([S#d2a7f4a6]/[S#a1d6c3d5]), the consecutive-shift preference ([S#30c6f5ad]) — since this is what "the nicest possible roster" for named staff actually means in practice.
2. **Named staff using the overtime flex**, up to 12 additional paid hours above their raw contracted hours ([H#e8f7d6c5]), distributed **as evenly as possible** across all eligible staff ([S#e9b4a1b3]) — don't stack it onto the same few people. All other hard constraints still apply on top of this (max hours, red requests, holidays, skill level requirements) — overtime never overrides a hard constraint, and **never** overrides the 76h absolute ceiling ([H#f0c5b2c4]) either.
3. **Casual staff** ([H#c92f5e1b]/[H#71b4d9ac]/[H#4ef8a2c3]), for positions whose `required_skill_level` is `null` — casuals never fill positions with any specific skill level requirement. This is deliberately the last resort ([S#3d9a7ec1]) — the solver should exhaust tiers 1–2 for a position before reaching for a casual, never substitute a casual just to reduce some other soft-constraint penalty.
4. **`UNFILLED`** — reachable only when neither named staff (even flexed) nor a casual can cover a position. In practice this means gaps requiring Acute, Resus, Triage, or Shift Coordinator with no eligible named staff available, since casuals only ever cover `null`-requirement positions. Record it in the output and note which classification/skill level was required but unavailable.

If hard constraints make it impossible to produce **any** valid roster at all (e.g. a required Shift Coordinator role has zero qualified staff in the entire roster, on a day where the shortfall can't be resolved even via `UNFILLED`), stop and tell the user why — never produce a broken or partial file silently.

**Which hours cap actually binds for named staff:** two separate caps exist and the *lower* one always governs —
- Absolute ceiling: never exceed 76 hours per staff member per 14-day block ([H#f0c5b2c4]). **This never changes regardless of the overtime cap below** — overtime headroom and this ceiling are independent, and the ceiling always wins if they conflict.
- Relative ceiling: never more than 12 **paid** hours of overtime above that person's **raw `contracted_hours_per_fortnight`** in the block ([H#e8f7d6c5] — history: raised to 24 before casual staffing existed in this model, reduced back down to 12 now that casuals can absorb the rest of a coverage gap instead of stretching named staff further).

Note the ceiling and the floor use **different bases on purpose**: the floor ([H#d9a8b7c6]) is measured against `adjusted_hours` (holiday-prorated, per [H#a3d8f6c1]), while this ceiling is measured against the **unadjusted** `contracted_hours_per_fortnight` — a staff member's overtime headroom doesn't shrink just because they had a holiday in the block.

For a staff member contracted at 76h, the relative ceiling has zero room before hitting the absolute one; for someone contracted at 40h, the relative ceiling (52h) binds well before the absolute one. Apply `min(76, contracted_hours_per_fortnight + 12)` as the effective cap per person, per block — and only for named staff; casuals aren't subject to either cap (see [H#4ef8a2c3]).

## 8. Technical Implementation Guide

### Environment & Execution
- CRITICAL RULE: ALWAYS use .venv/bin/python and .venv/bin/pip - NEVER bare python or pip or the system version of python.
- Python 3.x. A virtual environment is provided at `.venv/`.
- Always run python via the venv interpreter: `.venv/bin/python <script_name>.py`.

### Core Solver Logic (CP-SAT)
Google OR-Tools CP-SAT. When implementing or modifying constraints:

1. **Integer arithmetic (scaling)**: CP-SAT only works with integers. All floating-point values (contracted hours like `37.5`, shift `paid_hours` like `12.0`/`8.0`) must be scaled by `self.SCALE` (= `100`). Example: contracted hours of `37.5` becomes `3750`. Note `paid_hours` values are whole/half numbers post-refactor (12.0, 8.0) — don't confuse them with `span_hours` (12.5, 8.5), a different field for a different purpose (see §5).
2. **Skill level hierarchy thresholding**: `Acute < Resus < Triage < Shift Coordinator`. Check requirements with thresholding (e.g. `SKILL_MAP[level] >= required_rank`), not exact equality — this lets higher-qualified staff fill lower roles. (Graduate is a classification, not part of this hierarchy — see §2.)
3. **Constraint lifecycle** for adding a new constraint or preference:
   - Step 1 — Variables: define decision variables (`model.NewBoolVar`, etc.)
   - Step 2 — Constraints: apply logic via `model.Add(...)` / `model.AddForbiddenAssignments(...)`
   - Step 3 — Penalties (soft only): create an integer "violation amount" variable, add to the objective multiplied by its `weights.yaml` weight. **Not every soft constraint is a flat `violation × weight`** — e.g. `S#30c6f5ad` defines its own internal tiers (0 / 0.1×W / 1×W / escalating) on top of the single `weights.yaml` value, which acts as the base unit `W` rather than a flat multiplier. Read the constraint's full text in `soft_constraints.md` before assuming a simple linear penalty is correct.
   - Step 4 — Objective: make sure all new penalty variables are included in `model.Minimize(...)`.
4. **Linkage via IDs**: every hard/soft constraint in code must be tagged with its corresponding ID from the markdown files (e.g. `# [H#a7f2c9d1]`). **IDs must be unique** — if you're adding a new constraint, generate a fresh ID rather than reusing or copy-pasting an existing tag (a duplicate ID was found and fixed during this cleanup; don't reintroduce that pattern).

### CP-SAT Modeling Notes

Concrete patterns for the trickier constraints, so they don't each get reinvented (or gotten wrong) independently:

- **Precompute shift-pair compatibility once, don't model time arithmetic per-assignment.** There are only 8 shift types, so the set of (shift on day *d*, shift on day *d*+1) pairs that violate rest ([H#c1f6e3f5]), overlap ([H#e91c63ab]), or the night/day transition rule ([H#f4c9b6c8]) is small, fixed, and identical for every staff member — it depends only on the two shift types, not on who's assigned. Build an 8×8 (plus an explicit "unassigned" state) boolean compatibility table once at startup from `definitions.yaml`'s absolute start/end times, then enforce it per staff/day-pair as a forbidden-assignment pattern. Don't recompute time-interval overlap logic inline for every staff/day combination — that's the same fixed table being derived over and over, and it's easy for one of those inline derivations to miss the midnight-crossing edge case that H#e91c63ab spells out.
- **Skill-level threshold ([H#5e6ad8f4]/[H#84a1d5c9]/[H#b72e41fa]):** a straightforward reified implication — `model.Add(staff_rank[s] >= required_rank[p]).OnlyEnforceIf(x[s, p])`. No special modeling needed beyond §8 item 2's ranking approach.
- **Holiday proration ([H#a3d8f6c1]):** compute `adjusted_hours` in plain Python before the model is built, as a per-staff, per-block integer constant. This is data preprocessing, not something CP-SAT needs to reason about — don't introduce it as a solver variable or a constraint the solver has to derive.
- **`S#30c6f5ad`'s tiered run-length penalty:** since a block is only 14 days, run lengths are bounded and enumerable — this is tractable to model directly rather than needing a general-purpose "count consecutive equal values" abstraction. Suggested approach:
  1. For each staff member and each day *d* in the block, define `same[d]` = 1 if their shift on day *d* equals their shift on day *d*+1 (both actual shifts, not "unassigned") — reified off the existing assignment variables.
  2. Define `run_start[d]` = 1 if day *d* is worked and (day *d*−1 is unassigned or a different shift type) — this marks the first day of each run.
  3. For each day *d* where `run_start[d]` could be true, and each candidate run length *L* from 1 to 14, define a boolean for "a run of exactly length *L* starts at *d*" via a conjunction of `same[d..d+L-2]` all true and `same[d+L-1]` false (or end of block) — this is a small, fixed number of boolean AND constraints per staff, not a per-pair-of-days combinatorial blowup.
  4. Add the tier's penalty (0 / `0.1×W` / `1×W` / `(L-3)×W` per §-above) to the objective exactly once per run, gated on that run's length-*L* boolean — not once per day in the run, or multi-day runs get penalized multiple times.
  - Sub-labels for traceability: tag each tier's penalty variable/log line with `S#30c6f5ad·L=1`, `S#30c6f5ad·L=2`, etc. rather than inventing separate top-level constraint IDs — this keeps `weights.yaml` holding one value (the base unit `W`) while still letting the "Messages" section of the HTML output say which tier actually fired for a given staff member.
- **`S#6c1e9a4d`'s day/night run-count penalty:** reuses the same `run_start`-boolean machinery as `S#30c6f5ad` above, but categorised (day vs. night, per §5's split) rather than by exact shift type, and counting *how many runs occur* rather than measuring each run's length.
  1. For each staff member, define `category[d]` (day/night/unassigned) per day from the existing assignment variables.
  2. Reuse (or share) the `run_start[d]` pattern from `S#30c6f5ad`, but keyed on category equality between day *d* and *d*-1 instead of exact-shift-type equality.
  3. Sum `run_start[d]` booleans where `category[d] == day` to get `day_run_count`; same for night to get `night_run_count`. Since [H#f4c9b6c8] already forces an off-day at every category transition, you don't need to separately handle the "same day, different category" adjacency case — it can't occur in a feasible solution.
  4. Penalty = `(max(0, day_run_count - 2) + max(0, night_run_count - 2)) * W` — a single `max(0, ...)` reification per category is enough, no per-run-length tiering needed here (unlike `S#30c6f5ad`).

- **Casual fallback ([H#c92f5e1b]/[S#3d9a7ec1]):** for each roster position whose `required_skill_level` is `null`, add one extra boolean "filled by casual" option alongside the named-staff assignment options — no per-day/per-staff continuity variables needed, since casuals aren't tracked as individuals ([H#4ef8a2c3]) and supply is unlimited ([H#71b4d9ac]). Positions with any specific skill level requirement (Acute/Resus/Triage/Shift Coordinator) don't get this option at all. Add `S#3d9a7ec1`'s weight to the objective once per casual assignment used; because that weight is deliberately far larger than any other soft-constraint contribution, the solver will only pick it once tiers 1–2 (named staff, including the 12h flex) can't cover a position.

## 9. Testing

- Unit tests for `.py` and other core logic live in `tests/`, using `pytest`. Run with `.venv/bin/python -m pytest tests/`.
- Run the tests whenever code changes, and update tests to reflect the change.
- Tests should cover both a positive and a negative case per function.
- After the roster is produced, scan it and compare against `hard_constraints.md`/`soft_constraints.md` to confirm compliance.
- The lazy-mode "one runnable check" convention (§10 below) is for small, non-solver helper functions — it does not replace the `tests/` pytest suite for constraint/solver logic.
- **Weight-dominance sanity check:** `S#3d9a7ec1`'s weight (100000) is only correct if it exceeds the maximum possible *combined* penalty from every other soft constraint across the whole roster in a single run — not just one staff member's worst case. Add a test that computes an upper bound on that combined total (worst-case per-staff `S#30c6f5ad` penalty × staff count, plus worst-case fairness/tiebreaker penalties) and asserts it's still less than `S#3d9a7ec1`'s weight. If this ever fails (e.g. because the roster grows much larger, or another high-weight soft constraint gets added later), the casual-as-last-resort guarantee breaks silently — the solver could start preferring a casual over a valid all-named-staff solution.

## 10. Constraint Toggles (config.yaml)

During development, constraints can be selectively disabled via `config.yaml` to simplify debugging.

### How it works

- If `config.yaml` doesn't exist or has no `constraints` section → **all constraints enabled** (normal operation).
- If `constraints` exists → only constraint IDs listed under `enabled` are active. Everything else is skipped.
- Both `hard:` and `soft:` sections are supported. They're independent — you can toggle hard constraints on and soft constraints off.

### Adding a new constraint

**Every new constraint added to `constraints.py` MUST have a corresponding toggle entry in `config.yaml`** (commented out, under the appropriate `enabled` list). The config file is the single source of truth for which constraints exist in the system. If a constraint is missing from the config, it will silently be excluded from the solver.

### Testing

Tests that need specific constraints active must override the default (no-config = all enabled) by providing a `constraint_config` parameter to `RosterModel`. See `tests/test_config.py` for examples.

## 11. Agent Working Mode — "Ponytail" (lazy senior dev)

You are a lazy senior developer. Lazy means efficient, not careless. The best code is the code never written.

Before writing any code, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't rewrite it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs after you understand the problem, not instead of it: read the task and the code it touches, trace the real flow end to end, then climb.

**Bug fix = root cause, not symptom.** A report names a symptom. Grep every caller of the function you touch and fix the shared function once — one guard there is a smaller diff than one per caller, and patching only the path the ticket names leaves a sibling caller still broken.

Rules:
- No abstractions that weren't explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem. The smallest change in the wrong place isn't lazy, it's a second bug.
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Pick the edge-case-correct option when two stdlib approaches are the same size — lazy means less code, not the flimsier algorithm.
- Mark deliberate simplifications that cut a real corner with a known ceiling (global lock, O(n²) scan, naive heuristic) with a `ponytail:` comment naming the ceiling and upgrade path.

**Not lazy about**: understanding the problem (read it fully and trace the real flow before picking a rung — a small diff you don't understand is just laziness dressed up as efficiency), input validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs, anything explicitly requested. Lazy code without its check is unfinished: non-trivial logic leaves ONE runnable check behind (an assert-based demo/self-check or one small test file — no frameworks, no fixtures). Trivial one-liners need no test.

## 12. Python Coding Standards

1. **Indentation**: exactly 4 spaces, never tabs. Before adding logic, read the surrounding lines to confirm the current indentation context. Keep `if`/`for`/`while`/`def`/`class` blocks aligned with their parent scope.
2. **Spacing & style**: spaces around operators (`a = b + c`); PEP 8 naming (snake_case functions/variables, PascalCase classes); consistent vertical whitespace between method definitions.
3. **Verification**: after editing a `.py` file, verify no `IndentationError`/`SyntaxError` was introduced by running or linting the relevant script.

## 13. Python Implementation Structure

The project is structured as follows:

### Core Python Modules
- **`main.py`** - Main driver script that orchestrates the entire solution; sets up logging for the run (see §6)
- **`models.py`** - Data models for staff, shifts, and roster positions with validation
- **`constraints.py`** - Base classes for hard and soft constraint implementations
- **`solver.py`** - OR-Tools CP-SAT integration with model setup
- **`output.py`** - Builds the single `output/roster_<run_id>.html` file using a Jinja2 template (see `templates/roster.html`). `_build_context()` pre-computes matrix data, overtime info, and block breakdowns — the template does all rendering.
- **`utils.py`** - Utility functions for data loading, validation, calculations, and logging setup

## Changelog
