# AGENTS.md — AI-Roster

This is the entry point for any agent (opencode or otherwise) working on this project. Read this file first, in full, before touching code. It is the single source of truth for how the pieces fit together — if another doc, comment, or file conflicts with what's written here, **this file wins**; flag the conflict rather than silently picking one.

---

## 🚧 0. Project Status — Work In Progress. Read before doing anything else.

**This project is not finished. Existing code is not presumed correct.**

- `build_roster.py` and `cp_solver.py` exist but their implementation is currently **known to be broken**. `result.staff.md`, `result.roster.md`, and `result.violations.md` may reflect that broken behavior.
- **The ground truth is the constraint/data files** — `hard_constraints.md`, `soft_constraints.md`, `roster.yaml`, `staff.yaml`, `definitions.yaml`, `weights.yaml`, and this document. **Code is not ground truth** until it's been verified against those files line-by-line. If code contradicts them, the code is wrong — not the other way around.
- **The existing test suite is not automatically trustworthy either.** Tests were plausibly written against the broken implementation. If a test asserts behavior that contradicts a hard/soft constraint ID, the test is the thing to fix, not the code you'd otherwise write to satisfy it.
- **You have explicit standing permission to change, rewrite, or delete existing code** in `build_roster.py`, `cp_solver.py`, and `tests/` when it conflicts with the constraint files — you do not need to ask first, and you do not need to preserve current output behavior for compatibility. There is no live consumer depending on the current (broken) behavior.
- This overrides the "reuse what's already here" step in the Ponytail ladder below (§10, step 2) specifically for `build_roster.py`/`cp_solver.py`/`tests/`: reuse is still the right instinct everywhere else in the codebase, but for these three, verify against the constraint files first — don't treat "it's already implemented this way" as a reason to keep it.
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
- **`result.staff.md`** — final roster grouped by staff member (output).
- **`result.roster.md`** — final roster grouped by date (output).
- **`result.violations.md`** — any rule violations found in the generated roster (output).
- **`build_roster.py`** — the script that builds the roster (exists, currently broken — see status note).
- **`cp_solver.py`** — the CP-SAT model itself (exists, currently broken — see status note).

**Fortnightly blocks**: rosters must span an exact multiple of 14 days. All constraints (max hours, etc.) apply *within* each discrete 14-day block, never averaged across the whole roster period. If `roster.yaml`'s date range isn't a whole multiple of 14 days, the script must error out with a clear message and refuse to build — never silently round, truncate, or prorate.

## 4. Data File Validation

`staff.yaml`, `roster.yaml`, `definitions.yaml`, `hard_constraints.md`, `soft_constraints.md` are hand-edited by humans — treat parsing them as input validation, not just data loading. If a row is malformed, missing a required field, references an undefined skill level/shift/staff member, or a date is out of range: fail loudly with a message naming the file, the row, and the problem. Never silently skip or guess a default.

### `staff.yaml`-specific rules

- **`name` must be unique across the file.** It's the identifier used to group output in `result.staff.md` and to cross-reference `red_requests`/`holidays` — a duplicate name is a data error, fail loudly rather than merging or picking one.
- **`classification` must be exactly one of `RN`, `CN`, `Graduate`.** Any other value is a data error.
- **`skill_tags` must be a contiguous prefix of the hierarchy** `Acute < Resus < Triage < Shift Coordinator` — i.e. a staff member can hold `[Acute]`, `[Acute, Resus]`, `[Acute, Resus, Triage]`, or all four, but never a level without every level below it (e.g. `[Resus]` alone, or `[Acute, Triage]` skipping `Resus`, is invalid). This matches every existing entry in `staff.yaml` and is required for the threshold-based skill check in §2/§8 to mean anything. **List order within `skill_tags` is not semantically meaningful** — determine a staff member's actual rank by looking up each tag against the hierarchy, don't rely on list position or count.
- **`contracted_hours_per_fortnight`** is a `paid_hours`-basis figure (see §5) and must be a positive number.
- **`red_requests`** is a list of `YYYY-MM-DD` date strings (may be empty). Does not reduce the contracted-hours floor (see §7 / `H#d9a8b7c6`).
- **`holidays`** is a list of `{start, end}` date-range objects, both `YYYY-MM-DD` strings (may be empty). A single-day holiday is represented as `start == end` — there is no separate scalar shorthand for a one-day holiday. `start` must not be after `end`. Holidays proportionally reduce the contracted-hours floor for the affected block.

## 5. Shift Definitions & the Day/Night Split

Shifts (from `definitions.yaml`): `D8, D12, P8, P12, L3, DISCO, N8, N12`.

- **Day shifts**: `D8, D12, P8, P12, L3, DISCO`
- **Night shifts**: `N8, N12`

**DISCO exception — read carefully:** DISCO runs 17:30→02:00 and crosses midnight, the same way N8/N12 do. Despite that, **DISCO is classified as a day shift** for all fairness/reporting purposes (weekend-hours %, night-shift-hours % in `result.staff.md`, soft-constraint fairness calcs, etc.). This is a deliberate exception, not an oversight — don't "fix" it by moving DISCO into the night bucket.

### Overnight Shift Attribution

Any shift that crosses midnight (DISCO, N8, N12) counts entirely toward the date and 14-day block **it starts on** — never the date it ends on, and never split across both. This applies consistently to hours totals, weekend-hours %, and night-shift-hours % in `result.staff.md`. (Per the exception above, DISCO's hours still land in the day-shift bucket even though the shift itself crosses midnight — attribution-by-start-date and day/night classification are two separate rules.)

### Span Hours vs. Paid Hours

Every shift's stated duration (8.5h for the 8-hour shifts, 12.5h for the 12-hour shifts) includes a **30-minute unpaid break**. `definitions.yaml` gives you both figures explicitly — never derive one from the other via a hardcoded "minus 30 minutes," always read the field:

- **`span_hours`** — wall-clock start-to-end duration, unpaid break included. Use for anything about physical presence/timing: the 11-hour rest-period gap ([H#c1f6e3f5]), the no-double-booking/overlap check ([H#e91c63ab]).
- **`paid_hours`** — `span_hours` minus the break. Use for anything measured against contracted hours: the contracted-hours floor ([H#d9a8b7c6]), the 76h absolute cap ([H#f0c5b2c4]), the 12.5h overtime cap ([H#e8f7d6c5]), and every hour total / weekend % / night % figure in `result.staff.md`.

**These are not interchangeable.** Using `span_hours` anywhere the constraint files say "hours" (contracted, cap, overtime) overcounts every shift by 30 minutes — across a 14-day block with ~10 shifts that's up to 5 hours of drift per staff member, easily enough to push someone over or under a hard cap incorrectly. If you find code computing hours-worked totals from `span_hours` (or from raw start/end time deltas) for anything contracted-hours-related, that's a bug — fix it to use `paid_hours`.

## 6. Output

- `result.*.md` files can be overwritten/replaced on disk.
- All `result.*.md` outputs should include auxiliary info like classification and skill level.
- **`result.staff.md`** (grouped by staff member) must include:
  - Summary of classification, skill level(s), and contracted hours per fortnight for the whole period.
  - A block-by-block breakdown (14-day increments): total hours worked, weekend hours + % of block total, night-shift hours + % of block total.
  - A full list of all shifts assigned during the entire period.
- **`result.roster.md`** (grouped by date) must show everyone on shift each day, their specific shift, classification, and skill level.
  - Print shifts in this fixed order: `D8, D12, P8, P12, L3, DISCO, N8, N12`.
  - Within a single shift's list of staff: order by classification first (CN before RN, or per the hierarchy in `staff.yaml`), then by skill level (highest first) within the same classification.

## 7. Operational Definitions

### Coverage Shortfalls & Overtime

`contracted_hours_per_fortnight` is a **minimum**, not a cap. If total contracted hours across all staff can't cover every shift in a 14-day block:

1. First cover the shortfall with overtime (hours above a staff member's floor), distributed **as evenly as possible** across all eligible staff — don't stack it onto the same few people.
2. All other hard constraints still apply on top of this (max hours, red requests, holidays, skill level requirements). Overtime never overrides a hard constraint.
3. If a shift still can't be covered after fair overtime distribution and respecting all hard constraints (e.g. no staff member with the required skill level is available, or covering it would breach someone's max-hours cap), record it as `UNFILLED` in the output and note which classification/skill level was required but unavailable.
4. If hard constraints make it impossible to produce **any** valid roster (e.g. a required Shift Coordinator role has zero qualified staff in the entire roster), stop and tell the user why — never produce a broken or partial file silently.

**Which hours cap actually binds:** two separate caps exist and the *lower* one always governs for a given staff member —
- Absolute ceiling: never exceed 76 hours per staff member per 14-day block ([H#f0c5b2c4]).
- Relative ceiling: never more than 12.5 hours of overtime above that person's own contracted hours in the block ([H#e8f7d6c5]).

For a staff member contracted at 76h, the relative ceiling has zero room before hitting the absolute one; for someone contracted at 40h, the relative ceiling (52.5h) binds well before the absolute one. Apply `min(76, contracted + 24)` as the effective cap per person, per block.

## 8. Technical Implementation Guide

### Environment & Execution
- CRITICAL RULE: ALWAYS use .venv/bin/python and .venv/bin/pip - NEVER bare python or pip or the system version of python.
- Python 3.x. A virtual environment is provided at `.venv/`.
- Always run python via the venv interpreter: `.venv/bin/python <script_name>.py`.

### Core Solver Logic (CP-SAT)
`cp_solver.py` uses Google OR-Tools CP-SAT. When implementing or modifying constraints:

1. **Integer arithmetic (scaling)**: CP-SAT only works with integers. All floating-point values (contracted hours like `37.5`, shift `paid_hours` like `12.0`/`8.0`) must be scaled by `self.SCALE` (= `100`). Example: contracted hours of `37.5` becomes `3750`. Note `paid_hours` values are whole/half numbers post-refactor (12.0, 8.0) — don't confuse them with `span_hours` (12.5, 8.5), a different field for a different purpose (see §5).
2. **Skill level hierarchy thresholding**: `Acute < Resus < Triage < Shift Coordinator`. Check requirements with thresholding (e.g. `SKILL_MAP[level] >= required_rank`), not exact equality — this lets higher-qualified staff fill lower roles. (Graduate is a classification, not part of this hierarchy — see §2.)
3. **Constraint lifecycle** for adding a new constraint or preference:
   - Step 1 — Variables: define decision variables (`model.NewBoolVar`, etc.)
   - Step 2 — Constraints: apply logic via `model.Add(...)` / `model.AddForbiddenAssignments(...)`
   - Step 3 — Penalties (soft only): create an integer "violation amount" variable, add to the objective multiplied by its `weights.yaml` weight.
   - Step 4 — Objective: make sure all new penalty variables are included in `model.Minimize(...)`.
4. **Linkage via IDs**: every hard/soft constraint in code must be tagged with its corresponding ID from the markdown files (e.g. `# [H#a7f2c9d1]`). **IDs must be unique** — if you're adding a new constraint, generate a fresh ID rather than reusing or copy-pasting an existing tag (a duplicate ID was found and fixed during this cleanup; don't reintroduce that pattern).

## 9. Testing

- Unit tests for `cp_solver.py` and other core logic live in `tests/`, using `pytest`. Run with `.venv/bin/python -m pytest tests/`.
- Run the tests whenever code changes, and update tests to reflect the change.
- Tests should cover both a positive and a negative case per function.
- After the roster is produced, scan it and compare against `hard_constraints.md`/`soft_constraints.md` to confirm compliance.
- The lazy-mode "one runnable check" convention (§10 below) is for small, non-solver helper functions — it does not replace the `tests/` pytest suite for constraint/solver logic.

## 10. Agent Working Mode — "Ponytail" (lazy senior dev)

You are a lazy senior developer. Lazy means efficient, not careless. The best code is the code never written.

Before writing any code, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't rewrite it. *(Exception: `build_roster.py`, `cp_solver.py`, `tests/` — see §0. Verify against the constraint files before treating existing code there as the reusable pattern.)*
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

## 11. Python Coding Standards

1. **Indentation**: exactly 4 spaces, never tabs. Before adding logic, read the surrounding lines to confirm the current indentation context. Keep `if`/`for`/`while`/`def`/`class` blocks aligned with their parent scope.
2. **Spacing & style**: spaces around operators (`a = b + c`); PEP 8 naming (snake_case functions/variables, PascalCase classes); consistent vertical whitespace between method definitions.
3. **Verification**: after editing a `.py` file, verify no `IndentationError`/`SyntaxError` was introduced by running or linting the relevant script.

---

## Changelog
