# AI-Roster — Code Review & Implementation Plan

Audit date: 2026-08-07. Reviewed: all `.py`, `.yaml`, `.md`, `templates/`, `tests/`.
Baseline run: `FEASIBLE` (not `OPTIMAL`) after hitting the hard-coded 300 s limit;
objective `160,197,000`; 379 assignments, 25 unfilled.

**Read this whole file before editing anything.** §0 lists decisions the user must
make first — several P0 fixes depend on them. Ground truth is the constraint/data
files, not the existing code or tests (AGENTS.md §0).

---

## 0. DECISIONS REQUIRED FROM THE USER

> **User: answer these in §0.1 below before the implementing agent starts.**
> Items marked ⚠ block a P0 fix.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 ⚠ | **Objective scaling.** Fairness penalties are inflated ~n× (n=42 or 84) and total ~160M, swamping the 140k–220k unfilled tiers. See §2.3. | (a) Normalise deviations to whole hours + restate the dominance invariant as *marginal*; (b) raise unfilled tiers to ~10M; (c) both | **(a)** — (b) alone leaves the objective numerically ugly and slow |
| D2 ⚠ | **Dominance invariant.** AGENTS.md §9 demands each unfilled tier exceed the *total* worst-case soft penalty. That is structurally unachievable (shortfall alone worst-cases at ~6.4M). See §2.3. | (a) Restate as *marginal* cost of leaving one extra position unfilled; (b) keep total-bound and inflate tiers | **(a)** |
| D3 | **Run-length scope for `S#30c6f5ad`.** Code measures runs across the whole 28-day period; AGENTS.md §8 says per 14-day block. | (a) per block (matches doc, cheaper); (b) whole period (arguably more correct clinically) | **(a)** — and fix the doc if you disagree |
| D4 | **Sat/Sun fairness scope (`S#s1a2t3u4`/`S#s2u3n4d5`).** Currently whole-period. All other fairness is per block. | (a) per block; (b) whole period | **(a)** for consistency |
| D5 | **Empty `enabled:` list semantics.** Code treats `enabled: []` as *all enabled*; AGENTS.md §10, README and `config.yaml` all say *only listed IDs are active* (i.e. none). Tests rely on the code behaviour. | (a) code is right → fix docs; (b) docs are right → fix code (add explicit `enabled: all` sentinel) | **(a)** — least churn, and "all commented out" should mean "normal operation" |
| D6 | **Solve time limit / target status.** 300 s hard-coded in `solver.solve()`; run ends `FEASIBLE`. | (a) expose `solver:` section in `config.yaml` (`max_time_seconds`, `num_workers`, `random_seed`); (b) leave hard-coded | **(a)** |
| D7 | **`slot_id` scheme.** See §2.4. | (a) counter resets per date → `D8-General-1` stable across all weeks; (b) keep a per-fortnight counter and drop the "Roster by Shift" table | **(a)** |
| D8 | **No-op registry classes** (`CoverageConstraint`, `MaxHoursConstraint`, `SkillLevelHierarchy`, `ContractedHoursFloor`). Their `config.yaml` toggles do nothing. | (a) delete and move IDs to the sync allow-list; (b) make them do real work so toggles are honest | **(b)** for Coverage + MaxHours (cheap, makes toggles truthful); **(a)** for the other two |
| D9 | **`S#a1d6c3d5` contradiction.** `soft_constraints.md` lists it as live (line 10) *and* struck out as replaced (line 37). | (a) delete line 10; (b) delete line 37 and re-implement blended weekend fairness | **(a)** |
| D10 | **Tooling.** `requirements.txt` is a `pip freeze` incl. unused `pandas`/`numpy` and `pyright` (not installed — the venv has `ty`). `pyrightconfig.json` exists but is dead. | (a) `pyproject.toml` + direct deps + `ruff` + `ty`; (b) trim `requirements.txt`, pick one type checker | **(a)** |
| D11 | **Split `constraints.py`** (1266 lines) into `constraints/{base,hard,soft,registry}.py`? Requires an AGENTS.md §12 update. | (a) split; (b) keep flat | **(a)** |
| D12 | **`run_id` format.** Code emits `YYYYMMDD_<uuid6>`; AGENTS.md §6 specifies a timestamp `YYYYMMDD_HHMMSS`. | (a) match the doc; (b) keep uuid, update doc | **(a)** — sortable, and the doc already says so |

### 0.1 User answers

<!-- USER: fill in below. e.g. "D1: a  D2: a  D3: b ..." -->

```
D1:
D2:
D3:
D4:
D5:
D6:
D7:
D8:
D9:
D10:
D11:
D12:
Other notes:
```

---

## 1. Executive summary

The architecture (data files as ground truth → validated loaders → constraint
registry → CP-SAT → Jinja HTML) is sound and appropriate. The problems are in the
**CP-SAT modelling layer** and in **verification**:

- Four proven correctness defects, one of which makes a *soft* constraint behave as
  a hard one, and one of which makes the objective ignore the unfilled-penalty
  safety guarantee entirely.
- The test suite (3,875 lines, 139 tests, 1.2 s) exercises only toy models built on
  **fabricated shift times that contradict `definitions.yaml`**, and its
  weight-dominance test checks raw weights rather than realised penalties — so it
  gave a green light to every defect below.
- AGENTS.md §9's required post-solve compliance check **does not exist**. Building it
  is the single highest-value item here: it would have caught P0-1 and P0-3.

Fix order: §2 (P0 correctness) → §5 (verifier + test rebuild) → §3 (performance) →
§4 (hygiene) → §6 (docs).

---

## 2. P0 — Correctness defects

### 2.1 `S#30c6f5ad` injects a hard constraint (PROVEN)

`constraints.py:928`

```python
model.Add(same == 1).OnlyEnforceIf(not_unassigned_d, not_unassigned_d1)
```

Combined with `model.Add(s_d == s_d1).OnlyEnforceIf(same)` (line 918) this forces
**any two consecutive worked days to be the same shift type**. A soft preference is
acting as a hard rule. Reproduced in isolation: forcing `D8` on day *d* and `D12` on
day *d+1* yields `INFEASIBLE`.

This massively over-constrains the model and is a major cause of the 300 s timeout
and the 25 unfilled positions.

**Fix** — replace lines 917–929 with a proper three-way reification:

```python
eq = model.NewBoolVar(f"eq_{staff_names[si]}_d{di}")
model.Add(s_d == s_d1).OnlyEnforceIf(eq)
model.Add(s_d != s_d1).OnlyEnforceIf(eq.Not())

same = model.NewBoolVar(f"same_{staff_names[si]}_d{di}")
model.AddBoolAnd([eq, not_unassigned_d, not_unassigned_d1]).OnlyEnforceIf(same)
model.AddBoolOr([eq.Not(), not_unassigned_d.Not(), not_unassigned_d1.Not()]).OnlyEnforceIf(same.Not())
```

Note `not_unassigned_d1` is currently created fresh at each `di` with a name colliding
with the next iteration's `not_unassigned_d` — after the §3.1 refactor both should come
from a single shared `works_any[si][di]` array.

**Regression test:** two consecutive positions of different shift types must remain
satisfiable with `S#30c6f5ad` enabled.

### 2.2 `S#30c6f5ad·L=1` penalty never fires (PROVEN)

`constraints.py:971–979`. The `L == 1` branch only ever constrains `exact_L` *downward*
(`Add(exact_L == 0).OnlyEnforceIf(not_same_next.Not())`); nothing forces it to 1 when a
length-1 run actually occurs. Since it is minimised, the solver always picks 0.
Verified: a forced single isolated shift yields objective `0`, expected `50`
(`W//10`, W=500). Isolated single shifts are therefore free, contradicting
`soft_constraints.md` line 15.

**Fix** — treat `L == 1` with the same conjunction machinery as `L >= 2`; the only
difference is that `conj_bools` starts as `[rs]` with no `same[...]` terms:

```python
conj_bools = [rs]
for k in range(L - 1):
    conj_bools.append(same_vars[si][di + k])
if di + L < num_dates:
    conj_bools.append(<not_same at di+L-1>)
exact_L = model.NewBoolVar(...)
model.AddBoolAnd(conj_bools).OnlyEnforceIf(exact_L)
model.AddBoolOr([b.Not() for b in conj_bools]).OnlyEnforceIf(exact_L.Not())
```

Delete the special-cased `L == 1` block entirely. Also drop the dead
`total_penalty * 1` multiplier at line 1024.

### 2.3 Objective scaling defeats the unfilled-penalty guarantee (PROVEN) ⚠ D1/D2

Every fairness constraint uses the "multiply by *n* to avoid division" trick and
**never divides *n* back out**:

```python
model.Add(deviation >= staff_sat_hours[si] * n - total_sat)   # n = 42
```

Deviations are therefore reported in `SCALE × n` units. Realised objective on the live
data is **160,197,000**, against unfilled tiers of 140,000–220,000 — i.e. the solver
can profitably leave shifts unfilled to shave a fairness deviation. That is precisely
the failure AGENTS.md §9 exists to prevent, and `soft_constraints.md` [S#e7f3a2b1]
claims is guaranteed.

Order-of-magnitude worst cases today: Saturday fairness alone ≈ 42 × 62,400 × 50 ≈ 130M.

**Fix (per D1 option a):**

1. Add a shared helper in `constraints.py` and use it in all four fairness
   constraints (`S#e9b4a1b3`, `S#d2a7f4a6`, `S#s1a2t3u4`, `S#s2u3n4d5`):

   ```python
   def _fair_share_deviation(model, per_staff_hours, targets, prefix):
       """|hours_i - target_i| summed, in WHOLE PAID HOURS (targets are Python ints)."""
   ```

   Build `per_staff_hours` with **unscaled** whole-hour coefficients
   (`int(definitions[shift]["paid_hours"])`) — every `paid_hours` value is 8.0 or 12.0,
   so no precision is lost. `targets[i]` is a Python-side constant, so no `× n` is needed:

   ```
   target_i = round(total_pool_hours * contracted_i / sum(contracted))
   ```

2. `WeekdayNightFairness` currently computes `expected_night` as
   `contracted_scaled * len(night_pos_indices) // total_positions` (`constraints.py:688`)
   — dimensionally meaningless (hours × a *position count* ratio), and the correctly
   computed `total_night_hours_scaled` on line 681 is discarded. Replace with the
   `target_i` formula above.
3. It also reads hours from the hard-coded `utils.NIGHT_HOURS` dict
   (`constraints.py:663`) instead of `definitions[...]["paid_hours"]`, violating
   AGENTS.md §5 ("always read the field"). Delete `NIGHT_HOURS` from `utils.py`.
4. Restate the AGENTS.md §9 invariant per D2 as a **marginal** bound, and implement it
   as an automated check (see §5.2):

   > No unfilled tier weight may be less than the maximum soft-constraint penalty
   > reduction obtainable by removing a single assignment.

   After normalisation the marginal bound is ≈ 20,000 (shortfall 12h×1000 = 12,000;
   run-length ≤ 5,500; three fairness pools ≤ 600 each; day/night ≤ 600), comfortably
   under the 140,000 floor tier. Log both the marginal bound and an informational
   total worst case at `INFO` on every run.

**Expected side effect:** the objective drops from ~1.6e8 to ~1e4–1e5, which should
also let the solver reach `OPTIMAL` well inside the time limit.

### 2.4 `slot_id` collision hides half the roster (PROVEN) ⚠ D7

`utils.py:459–499`. The counter key is `(week_offset, day_name, shift, skill_label)`
and `week_offset` increments every **14** days — so the two Mondays inside one
fortnight share a key and produce `D8-General-1` and `D8-General-2` for what is the
same recurring position. Result: **30 distinct `slot_id`s instead of 16.**

`output.py:267` then silently truncates the "Roster by Shift" table at a hard-coded 15
rows (`WARNING ... 30 (cap 15) — truncating for display`), so half the roster is absent
from the HTML.

**Fix:**
- Reset the counter per date: key on `(date, shift, skill_label)`. Drop `week_offset`
  entirely. `slot_id` then means "the *n*th `<shift>`/`<skill>` position on this day",
  stable across every week.
- Delete the magic `15` cap in `output.py:267–272`. If a cap is genuinely wanted it
  must be derived from the data (`max positions of one kind on any day`), not a literal.
- Add a test asserting the distinct-`slot_id` count equals the max positions-per-day
  count derived from `roster.yaml`.

### 2.5 Constraint-markdown parser drops and invents constraints

`utils.py:253–287`.

| Defect | Evidence |
|---|---|
| Regex `[HS]#[a-f0-9]{8}` is hex-only | `[S#s1a2t3u4]` and `[S#s2u3n4d5]` are **never parsed** — Saturday/Sunday fairness are invisible to every consumer of `load_soft_constraints()` |
| `tag_re.search(line)` fires on *references* inside another constraint's body | `hard_constraints.md:31` mentions `[H#d9a8b7c6]/[H#a3d8f6c1]` → phantom records. Run log reports "20 hard constraints" for 19 real ones |
| `[H#f4c9b6c8]` is cited in `soft_constraints.md:20` | recorded as a **soft** constraint with a `H#` id |
| `assert current is not None` (line 279) | a bullet before the first tag → `AssertionError`, not a validation error |

**Fix:**
- Regex → `r"\[(?P<tag>[HS]#[A-Za-z0-9]{8})\]"`.
- Only start a new record when the tag is at the **start of the bullet**:
  `re.match(r"^-\s*(~~)?\[(?P<tag>[HS]#[A-Za-z0-9]{8})\]", stripped)`. Anything else on
  the line is body text.
- Reject a `H#` tag found in `soft_constraints.md` and vice versa — raise `ValueError`
  naming file and line (AGENTS.md §4: fail loudly).
- Raise `ValueError` instead of `assert` for a bullet with no open record.
- Detect and reject duplicate *definitions* of the same ID within a file.
- Move `import re` to module top.
- Also apply the same regex fix to `tests/test_constraint_sync.py:34`, which has the
  identical hex-only bug and therefore cannot see the two IDs above.

### 2.6 Soft-constraint penalties are never reported

`solver.py:132` declares `self._soft_penalty_vars`; **nothing ever writes to it**, so
`result.soft_penalty` is always `{}` and the template's "Soft Constraint Penalties"
block (`templates/roster.html:202–211`) never renders. AGENTS.md §6 requires the
Messages section to state "which soft constraints incurred a penalty and roughly how
much".

**Fix:**
- Give `BaseSoftConstraint` a `register_penalty(cid, var)` hook, or have `apply()`
  return its top-level penalty `IntVar`.
- In `RosterModel._apply_soft_constraints()`, store it:
  `self._soft_penalty_vars[cid] = penalty_var`.
- For `S#30c6f5ad`, additionally register the per-tier sub-totals under the documented
  sub-labels `S#30c6f5ad·L=1`, `·L=3`, `·L=4`, `·L=5+` (soft_constraints.md lines 13–17
  mandate these for the Messages section).
- `solver.py:467` divides the value by `SCALE`; after §2.3 the penalties are no longer
  scaled — remove the division.
- Report raw penalty **and** the contributing weight so the number is interpretable.

### 2.7 Whole-period overtime traffic light is always red

`output.py:146` calls `_overtime_info(total_hours, staff.contracted_hours_per_fortnight)`
where `total_hours` covers the **whole roster period** (2 blocks) but the contract is
**per fortnight**. Every staff member is reported as ~100% over.

**Fix:** compare against `contracted * len(blocks)`, or drop the period-level light and
keep only the per-block lights (which are computed correctly at line 182). Add a unit
test with a 28-day period.

### 2.8 CP-SAT search log is never captured

AGENTS.md §6: "CP-SAT's own log output should be captured here too, not just the final
status." No `log_search_progress` / `log_callback` anywhere in the codebase.

**Fix** in `solver.solve()`:

```python
self.solver.parameters.log_search_progress = True
self.solver.log_callback = lambda line: logger.debug("cp-sat: %s", line)
```

`DEBUG` keeps it out of the console but in the `.log` file, exactly as §6 specifies.
Also set `random_seed` for reproducible runs, and source `max_time_in_seconds` /
`num_workers` from config per D6.

### 2.9 `INFEASIBLE` is not treated as a failure

`solver.py:408` logs an error, then `main._run()` proceeds to render an empty HTML file
and exits `0`. AGENTS.md §7 requires the run to "stop and tell the user why" and never
"produce a broken or partial file silently".

**Fix:** still write the HTML (it usefully records the status), but log at `ERROR`, print
an explanatory console message, and `sys.exit(2)`. Note `solver.py:392` calls
`ObjectiveValue()` unconditionally — guard it behind the status check.

### 2.10 Config-toggle semantics contradict the docs ⚠ D5

`solver.py:220` treats an empty `enabled` list as "all constraints enabled". AGENTS.md
§10, README "Constraint Toggles", and `config.yaml`'s own header all say only listed IDs
are active. With everything commented out (today's state) the run log reports
`all hard, all soft constraints enabled` — correct behaviour, wrong documentation.

Related defects to fix regardless of D5:
- `config.yaml:22` lists `[H#d9a8b7c6]`, but `ContractedHoursFloor` is **not** in
  `HARD_CONSTRAINTS`; uncommenting that line raises `ValueError` from
  `load_config`. Remove the entry (the ID lives on as soft `[S#d9a8b7c6]`, already
  listed on line 26).
- Toggling `[H#4d9f81c2]` (coverage) or `[H#f0c5b2c4]` (76 h cap) off has **no effect** —
  both are enforced unconditionally in `_create_variables` / `_apply_coverage_constraint`.
  Per D8(b), move the enforcement into the constraint classes so the toggles are honest.
- `_apply_coverage_constraint` is called from inside `_apply_hard_constraints`
  (`solver.py:251`) but is not part of the registry loop — restructure so coverage is a
  normal registry entry.

---

## 3. P1 — Model efficiency and structure

### 3.1 Pairwise compatibility emission is ~765,000 constraints

`_emit_compatibility_constraints` (`constraints.py:30–61`) loops
staff × day-pairs × positions(d) × positions(d+1) ≈ 42 × 27 × 15 × 15 ≈ 255k `a+b<=1`
constraints, and is called **three times** (`NoDoubleBooking`, `RestPeriodConstraint`,
`NightToDayRest`). This is the dominant model-build cost.

Two compounding wastes:
- **`NoDoubleBooking` is fully redundant.** Its table is "gap ≥ 0"; `RestPeriodConstraint`'s
  is "gap ≥ 11 h". Every overlap pair is already a rest violation, so `[H#e91c63ab]`
  adds zero constraints beyond `[H#c1f6e3f5]`. Keep the class for traceability/toggling,
  but skip emission when the rest constraint is also enabled (log the fact).
- The tables depend only on shift **type**, yet are applied per position pair.

**Fix — introduce shared shift-type indicator variables in `RosterModel._create_variables()`:**

```python
# works[si][di][shift] : BoolVar, only for shift types present on that date
# works_any[si][di]    : BoolVar
# category[si][di]     : IntVar 0=day, 1=night, 2=off
```

Channel them to the assignment vars once (`works[si][di][sh] == 1 ⟺ Σ assignments for
that (date, shift) == 1`; the existing "at most one shift per day" constraint keeps the
sum ≤ 1). Then:

- Merge the three compatibility tables into one AND-ed 8×8 table at startup and emit
  ≤ 42 × 27 × 64 ≈ 72k clauses over `works` — a ~10× reduction, and the merge dedupes
  pairs forbidden by more than one rule.
- `ConsecutiveShiftDiscouraged` (currently rebuilds `shift_worked_vars`,
  `no_work`, `not_unassigned_*`) and `DayNightRunCountPenalty` (rebuilds `day_worked`,
  `night_worked`, `cat`) both reuse these instead of constructing their own — removing
  a third source of duplicated channelling logic and the name collisions noted in §2.1.

### 3.2 `SkillLevelRequirement` relies on an OR-Tools implementation detail

`constraints.py:186`:

```python
model.Add(staff_rank >= required_rank).OnlyEnforceIf(x)
```

Both operands are **Python ints**, so `Add()` receives a `bool`. It happens to work
(`Add(False)` → `add_bool_or([])`, which under `OnlyEnforceIf(x)` forces `x = 0`), but it
is silent, undocumented, unreadable, and creates a trivially-true constraint for every
*qualified* (staff, position) pair — ~16,000 of them on the live data.

**Fix:**

```python
for si, staff in enumerate(staff_list):
    for pi, pos in enumerate(positions):
        req = pos_required_ranks[pi]
        if req >= 0 and staff.highest_skill_rank < req:
            model.Add(assignments[si][pi] == 0)
```

Same pattern is already used correctly by `GraduateShiftConstraint` — be consistent.

### 3.3 `S#30c6f5ad` run enumeration is O(days²) per staff ⚠ D3

`constraints.py:962–1019` loops `di` over all 28 dates and `L` from 1 to `28 - di`,
creating ~33,000 booleans with conjunctions up to length 28. AGENTS.md §8 explicitly
scopes this to a 14-day block ("since a block is only 14 days, run lengths are bounded
and enumerable"). Per D3(a), loop per block and cap `L` at 14 — roughly a 4× reduction.

Also prefer `AddBoolAnd`/`AddBoolOr` over `!=` reifications on the `IntVar` encoding;
CP-SAT propagates clause form far better. With `works[si][di][sh]` from §3.1,
`same[di]` becomes `OR over sh of (works[di][sh] AND works[di+1][sh])`.

### 3.4 Duplication to extract

| Duplication | Locations | Action |
|---|---|---|
| Deviation-from-mean boilerplate (~25 lines ×4) | `constraints.py` 602–617, 692–705, 753–767, 815–829 | `_fair_share_deviation()` helper (§2.3) |
| `pos_by_date` construction | `constraints.py` 223, 310, 374, 859, 1101; `solver.py` 112 | build once in `RosterModel`, pass via context |
| `SaturdayFairness` / `SundayFairness` are byte-identical bar the day name | `constraints.py` 708–829 | one `_DayOfWeekFairness` base; subclasses set `DAY_NAME` + `constraint_id` |
| Compatibility-table builders | `constraints.py` 232, 319, 383 | one `build_compat_table(definitions, rule)` in `utils.py` |
| `logging.getLogger("ai-roster")` re-fetched | `utils.py` 93, 102, 111, 153, 198, 285 | use the module-level `logger` (line 41) |

### 3.5 `apply()` signature has outgrown itself

`BaseConstraint.apply()` (line 81) no longer matches any subclass: every one adds
`staff_hours_vars=None`, soft ones add `weight` and `objective_terms=None`, and
`ContractedHoursFloorSoft` communicates results by having the solver reach into
`constraint._shortfall_vars` (`solver.py:364`). The `# type: ignore[override]` on line 111
is a symptom.

**Fix:** define a frozen `ModelContext` dataclass in `constraints.py` (model, staff_list,
staff_by_name, assignments, works, works_any, category, staff_names, definitions,
all_dates, blocks, positions, pos_by_date, staff_hours_vars) and make the signatures
`apply(self, ctx) -> None` / `apply(self, ctx, weight) -> IntVar | None` (returning the
penalty var, per §2.6). Have `ContractedHoursFloorSoft` expose `shortfall_vars` as a
documented public attribute rather than relying on `hasattr` on a private name.

### 3.6 Other solver notes

- `solver.py:322–325` re-loops the positions already iterated at 296–320 — merge.
- `solver.py:255` `hasattr(self, "_objective_terms")` guards an attribute always set in
  `build_model()`; likewise `getattr(self, "_soft_penalty_vars")` at 465 and
  `getattr(self, "_hard_constraints", [])` at 401. Initialise in `__init__` and delete the
  defensive guards — they hide real ordering bugs.
- Unused: `is_weekend` import (`solver.py:22`), `self.position_indices` (line 117),
  `self.num_dates`/`self.date_index` (108–109).
- Consider symmetry breaking: many staff are interchangeable (identical classification,
  skill tags and contracted hours), which is hard for CP-SAT. Worth trying
  `AddDecisionStrategy` on the assignment vars, or lexicographic ordering within
  identical-staff groups, once §2.3 lands.

---

## 4. P2 — Hygiene, dead code, error handling

### 4.1 Delete

- `ContractedHoursFloor` (`constraints.py:469–486`) — no-op, **not registered**, dead.
- `SkillLevelHierarchy` (189–203) — pure no-op; move `[H#84a1d5c9]`/`[H#6db3f120]` to the
  `IMPLEMENTED_ELSEWHERE` allow-list (they already have entries there).
- `utils.NIGHT_HOURS` (line 32) — duplicates `definitions.yaml` (§2.3).
- `utils.py:12` `import os` — unused.
- `main.py:20` `from pathlib import Path` — unused.
- `models.Shift.is_night_shift` / `is_day_shift` (118–128) — unused, and both do a
  function-level `from utils import ...` to dodge a circular import that no longer
  exists. `models.skill_rank` / `satisfies_requirement` (40–50) — also unused.
- `constraints.py:1024` `total_penalty * 1`.
- Unused locals: `pos_date` (647), `num_positions` (724, 786), `max_shortfall` alias (524).

### 4.2 Move function-level imports to module top

`utils.py:258` (`re`), `constraints.py` 240, 327, 431, 507, 638, `solver.py:283`,
`main.py:127` (`from output import generate_html`). None are needed for cycle-breaking.

### 4.3 Error handling / logging

- `load_yaml` (`utils.py:84`) does not catch `FileNotFoundError` or `yaml.YAMLError`, so a
  missing/corrupt data file surfaces as a bare traceback rather than the "name the file,
  the row, and the problem" message AGENTS.md §4 requires. Wrap and re-raise as
  `ValueError` with the path.
- `load_definitions` does not validate that all eight `VALID_SHIFT_TYPES` are present or
  that each has the five required keys with correct types — a typo'd key becomes a
  `KeyError` deep in the model build. Add explicit validation.
- `load_roster` does not check for a missing `dates` key or `roster_positions` key.
- `validate_roster_positions` never checks that a `day_name` present in
  `roster.yaml` is a real weekday, so a typo'd `Mondey:` block is silently ignored —
  exactly the "silently skip" failure §4 forbids.
- `setup_logging` appends handlers to a module-level logger without clearing existing
  ones; calling it twice in one process (as tests may) duplicates every line. Clear
  `logger.handlers` first and set `logger.propagate = False`.
- `main.py` logs "Step 1, 2, 4, 5, 6, 7" — **Step 3 is missing**. Renumber.
- `main.py:44` defines a module-level `logger` that is shadowed by a local in `main()`
  (line 50). Harmless but confusing — drop the local assignment.

### 4.4 Template / output

- `output.py:447` `autoescape=False`. Staff names come from a hand-edited YAML file;
  use `select_autoescape(["html"])`. Verify `Allie O'Brien` / `Jessica O'Neill-Yee`
  still render correctly afterwards.
- `hard_constraints` and `soft_constraints` are threaded
  `main → RosterModel → SolveResult → _build_context → template` and then **never used**
  by `templates/roster.html`. Either surface the constraint text in the Messages section
  (which would make §2.6's penalty list far more readable) or remove the whole parameter
  chain — currently it is pure overhead.
- AGENTS.md §6 says the staff×days matrix shows "a red UNFILLED marker"; the template
  only shows unfilled in the separate "Roster by Shift" table. Reconcile code and doc.
- CSS class `badge` is referenced (template lines 186, 299, 317…) but never defined; only
  `badge-green/-yellow/-red` exist. Harmless, but remove or define it.
- `_hours_floor_info`'s 85 %/100 % thresholds are undocumented magic numbers — pull them
  into named module constants and mention them in the README output section.

### 4.5 Stale references

`weights.yaml` lines 9, 21, 29 and `constraints.py` lines 655, 714, 776 cite
"`plan.md §1.2`", "`§1.3a`", "`§1.3b`" — that `plan.md` was deleted (commit `6dce727`).
Replace with the constraint ID or the rationale itself. **Note for the implementing
agent: this new `plan.md` is also a working document; do not create fresh references
to it from source comments.**

### 4.6 Dependencies and tooling ⚠ D10

`requirements.txt` is an unfiltered `pip freeze`: it pins `pandas`, `numpy`, `absl-py`,
`six`, `python-dateutil`, `protobuf`, `Pygments`, `nodeenv` (all transitive or unused —
`pandas`/`numpy` appear in **zero** source files) and `pyright==1.1.411`, which is not
installed in `.venv`. The venv instead contains `ty`, which is not in
`requirements.txt`. `pyrightconfig.json` is consequently dead configuration.

Per D10(a): create `pyproject.toml` with direct runtime deps (`ortools`, `PyYAML`,
`jinja2`) and a `dev` extra (`pytest`, `ruff`, `ty`); add `[tool.ruff]` (line length,
`E`/`F`/`I`/`UP` rules) and `[tool.ty]`; delete `pyrightconfig.json`. Add a `Makefile` or
short `scripts/check.sh` running `ruff check . && ty check . && pytest tests/` so agents
have one deterministic gate. Document it in AGENTS.md §8 and README.

`ty check .` currently reports 109 diagnostics, almost all from OR-Tools' deprecated
CamelCase aliases (`model.Add` vs `model.add`). OR-Tools 9.15 exposes both. Migrating to
snake_case would silence the noise and align with the library's current API — worth
doing as a single mechanical pass **after** the P0 fixes land, not interleaved with them.

---

## 5. P3 — Verification and tests

This is where the project is weakest. 139 tests pass in 1.2 s and caught none of §2.

### 5.1 Build the post-solve compliance verifier (highest value)

AGENTS.md §9 requires "after the roster is produced, scan it and compare against
`hard_constraints.md`/`soft_constraints.md` to confirm compliance". **No such code
exists.** An independent verifier — one that never touches the CP-SAT model and derives
everything from `SolveResult` + the data files — would have caught §2.1 and §2.3.

Create `verify.py`:

```python
def verify(result, staff_list, definitions, positions, blocks) -> list[Violation]:
    """Independently re-check every hard constraint against the produced roster.

    Deliberately shares NO code with constraints.py — it must be able to disagree.
    """
```

Checks, each tagged with its ID:

| ID | Check |
|---|---|
| `H#4d9f81c2`/`H#7a3e5f91` | every position filled exactly once, or listed as unfilled |
| `H#5e6ad8f4`/`H#b72e41fa` | assignee's `highest_skill_rank >= required_skill_rank` |
| `H#e91c63ab` | absolute intervals (date + start/end + `crosses_midnight`) never overlap per staff, across the whole period |
| `H#c1f6e3f5` | ≥ 11 h wall-clock between consecutive shifts (`span_hours` basis) |
| `H#f4c9b6c8` | no night→day or day→night on adjacent days |
| `H#a5d0c7d9` / `H#b6e1d8e0` | no assignment on a red-request date / holiday range |
| `H#f0c5b2c4` | ≤ 76 `paid_hours` per staff per block |
| `H#e8f7d6c5` | ≤ `min(76, contracted + 12)` per staff per block |
| `H#30479c74` | Graduates only on D8/P8/L3/DISCO/N8 |
| `H#a3d8f6c1` | recompute `adjusted_hours` independently and cross-check the reported floor |

Wire it into `main._run()` between solve and output. Any violation → `logger.error`,
render into the HTML Messages section (AGENTS.md §6 requires reporting hard-constraint
failures rather than failing silently), and exit non-zero. Add `tests/test_verify.py`
with hand-built violating rosters — one positive and one negative per rule (AGENTS.md §9).

### 5.2 Replace the weight-dominance test

`tests/test_integration.py:177–217` compares raw `weights.yaml` numbers
(`lowest_unfilled > max_soft_weight`) — which passes trivially while the realised
objective is 160M. It does not do what AGENTS.md §9 asks ("weight × its maximum possible
per-instance penalty × instance count").

Replace with a test that builds the real model from the real data files and, per D2,
asserts the **marginal** bound: for each soft constraint, the maximum objective
reduction achievable by dropping one assignment must be below the lowest unfilled tier.
Compute it from each registered penalty variable's declared domain upper bound divided by
the number of assignments it can be affected by, and log the derivation so a human can
audit it. Fail the test if the margin is under 2×.

### 5.3 Fix the test fixtures

- **Fabricated shift definitions.** `tests/test_soft_constraints.py:61–70` defines
  `D8 07:30–16:00` and `N8 19:30–04:00`; `tests/test_integration.py:70–104` defines
  `P8 15:00–23:30`, `L3 22:00–06:00`, `N8 22:00–06:00`, `N12 21:00–09:30`. **None** of
  these match `definitions.yaml`. Rest-period and overlap tests are therefore validating
  behaviour against times that do not exist. `"span_hours"` appears 192 times in
  `test_constraints.py` alone.
  → Create `tests/conftest.py` with a `definitions` fixture that calls
  `utils.load_definitions()` on the real file, plus `staff_factory`, `position_factory`
  and `roster_model` fixtures. Delete every inline definitions dict.
- **Duck-typed staff mocks.** `tests/test_soft_constraints.py:20–43` builds staff via
  `type("Staff", (), {...})()`, including the meaningless
  `max((0 if not skill_tags else 0) for _ in [1]) or 0`. Use the real `models.Staff`
  dataclass so property changes are actually exercised.
- **Tests that claim to disable hard constraints but do not.**
  `tests/test_soft_constraints.py:75–78` passes `{"hard": {"enabled": []}}` with the
  comment "Disable hard constraints that need full shift definitions" — but per
  `solver.py:220` an empty list means *all enabled*. Every one of those tests is running
  the full hard constraint set. Once D5 is settled, make the intent explicit (either a
  sentinel value or a dedicated `disable_all=True` flag) and re-check the assertions.

### 5.4 Extend `test_constraint_sync.py`

- Fix the hex-only regex (§2.5).
- Add the reverse check: every registered `constraint_id` must appear in its markdown file.
- Add: every registered ID must appear in `config.yaml` (commented or not) — AGENTS.md §10
  makes `config.yaml` the single source of truth for which constraints exist, but nothing
  enforces it.
- Add: every registered soft ID and unfilled-tier ID must have a `weights.yaml` entry, and
  `weights.yaml` must have no *extra* keys (today's retired-ID comments are fine; live
  orphan keys are not).
- `IMPLEMENTED_ELSEWHERE["[H#7a3e5f91]"]` says "enforced by NoDoubleBooking constraint
  [H#e91c63ab] — one staff per position". Wrong: it is enforced by the coverage
  constraint in `_apply_coverage_constraint`. Correct the pointer.

### 5.5 Add missing coverage

- **End-to-end smoke test** (`@pytest.mark.slow`): real data files, `max_time_in_seconds=30`,
  assert status ∈ {OPTIMAL, FEASIBLE}, assert `verify()` returns zero violations, assert
  the HTML file is written and contains the expected section headings. Mark it slow and
  exclude from the default run via `[tool.pytest.ini_options] addopts = "-m 'not slow'"`.
- **Regression tests for each §2 defect** — these are the tests that were missing:
  1. `S#30c6f5ad` does not forbid differing shift types on consecutive days (§2.1).
  2. A forced isolated single shift incurs exactly `W//10` (§2.2).
  3. The parser returns both `S#s1a2t3u4` and `S#s2u3n4d5`, and returns exactly the
     number of *defined* IDs — no phantoms from in-body references (§2.5).
  4. Distinct `slot_id` count matches the per-day maximum from `roster.yaml` (§2.4).
  5. `result.soft_penalty` is non-empty after a solve with penalties (§2.6).
  6. A 28-day roster at exactly 2× contracted hours shows a green overtime light (§2.7).
- `main.py` has **no tests at all**. Add one covering the happy path with monkeypatched
  loaders, and one asserting non-zero exit on `INFEASIBLE` (§2.9).
- No test asserts the 14-day-multiple guard actually rejects a 21-day period end-to-end.

---

## 6. Documentation

### 6.1 Ground-truth contradictions to resolve first

These are in the files AGENTS.md §0 declares authoritative, so they must be fixed before
code is written against them.

| File | Problem |
|---|---|
| `soft_constraints.md` | `[S#a1d6c3d5]` is live at line 10 **and** struck out at line 37 (D9) |
| `soft_constraints.md:20` | cites `[H#f4c9b6c8]`, which the parser then records as a soft constraint (§2.5) |
| `hard_constraints.md:23` | `[H#d9a8b7c6]` struck out and reclassified, but AGENTS.md §5 and §7 still describe it as the hard floor, and `config.yaml:22` still lists it under `hard:` |
| `AGENTS.md §9` | states a dominance invariant that is structurally unachievable (§2.3 / D2) |
| `AGENTS.md §10` vs `solver.py` | empty `enabled` list semantics (D5) |
| `AGENTS.md §6` vs `main.py:49` | `run_id` is `YYYYMMDD_<uuid6>`, doc says timestamp (D12) |
| `AGENTS.md §6` vs template | staff×days matrix "UNFILLED marker" is not implemented there |

### 6.2 AGENTS.md — trim, don't gut

4,301 words. It is genuinely useful and mostly well-written; the waste is historical
narrative that no longer informs a decision. Target ~3,000 words by cutting:

- §7's parenthetical history of the overtime cap ("raised from 12.5 to 24 … reduced to
  12 now that…") — keep the current rule, drop the changelog.
- The casual-staffing explanation is stated three times (§7 tier 3, §7 relative ceiling,
  and again in `soft_constraints.md` [S#e7f3a2b1]) — state once in §7, cross-reference.
- §2's "previously conflated — now resolved" framing and §8's "a duplicate ID was found
  and fixed during this cleanup" — these describe past agent sessions, not current rules.
- §6's "everything that used to live in `result.violations.md`" phrasing — the files are
  gone; describe the required content directly.

**Do not cut:** §5 span vs paid hours, §8 CP-SAT modelling notes, §4 validation rules, the
DISCO exception, or the classification-vs-skill-level distinction. These are the parts
that actually prevent recurring bugs.

Add a short **§13 Development workflow**: the one check command from §4.6, the
"run the verifier before declaring done" rule, and the requirement to add a regression
test with every bug fix.

### 6.3 README — deduplicate

The `staff.yaml` field reference, the shift/day-night table and the full output spec are
near-verbatim copies of AGENTS.md §4/§5/§6. Since README itself says "if the two disagree,
AGENTS.md wins", replace the duplicated bodies with one-line summaries plus links. Keep
README as: what it is, how to run it, what comes out, where the real docs are. Target
~600 words (from 1,487). Drop the trailing `tests/test_output.py` bullet — listing one
test file in the module map is arbitrary.

### 6.4 Conventions worth documenting (currently unwritten)

The project has real conventions that only exist implicitly. Add them to AGENTS.md §11:

- Constraint classes are named for the rule, not the ID; the ID lives in `constraint_id`
  and the docstring's first line.
- Every penalty variable is named `<prefix>_<staff>_b<block>` — the HTML/message layer
  and the debug log both rely on this.
- Objective terms are appended to `_objective_terms`; **never** call `model.Minimize()`
  inside a constraint (there are five surviving `else: model.Minimize(...)` dead branches
  in `constraints.py` — lines 543, 617, 705, 767, 829, 1026, 1077, 1226 — that would
  silently clobber the objective if ever reached). Delete them and make
  `objective_terms` a required argument.
- Data loading validates and raises `ValueError`; the solver assumes valid input.

---

## 7. Suggested execution order

1. **Ground truth** — resolve §6.1 contradictions using the §0.1 answers. Nothing else
   is safe until the authoritative files agree with each other.
2. **P0 correctness** — §2.1, §2.2, §2.5, §2.4, §2.7 (independent, small, each with a
   regression test from §5.5).
3. **§2.3 objective rescaling** — the largest behavioural change; land it alone and
   compare a full run's objective, status, solve time and unfilled count against the
   `160,197,000` / `FEASIBLE` / `300 s` / `25 unfilled` baseline. Record the numbers.
4. **§5.1 verifier** — then re-run and confirm zero hard violations. Do this before the
   §3 refactors so there is an independent oracle for them.
5. **§2.6, §2.8, §2.9, §2.10** — reporting, logging, exit codes, toggles.
6. **§3 performance refactor** — §3.1 shared indicator vars first (it unblocks §3.3), then
   §3.2, §3.3, §3.4, §3.5. Verifier output must stay clean at every step.
7. **§5.3/§5.4 test rebuild**, then §4 hygiene, then §6 docs.
8. Optional: the OR-Tools snake_case migration (§4.6), as one mechanical commit.

**Definition of done for each step:** `ruff check . && ty check . && pytest tests/` clean,
a full `main.py` run produces zero verifier violations, and the summary states which
constraint ID each change addressed (AGENTS.md §0).

---

## 8. Additional observations

- **No CI.** For a repo maintained by agents, a GitHub Actions workflow running the §4.6
  check command on every push is high leverage — it is the only thing that makes "the
  tests pass" a verifiable claim rather than a self-report.
- **No changelog entries.** AGENTS.md ends with an empty `## Changelog` heading. Either
  use it (one line per behavioural change, with constraint IDs) or remove it.
- **`opencode.json` model config** points at a local homelab endpoint with three ~30B
  models and prices that look like placeholders (`Qwen3-Coder-30B` at `4.27` input vs
  `Gemma-4-26B` at `0.00000427` — a 10⁶ discrepancy that will badly skew any cost
  reporting). Worth correcting. `"plugin": ["@dietrichgebert/ponytail"]` is commented out;
  delete it if it is not coming back.
- **Determinism.** No `random_seed` is set, so two runs of the same input can produce
  different rosters. For a system whose output humans review and adjust by hand, run-to-run
  stability matters — set a seed and note it in the run summary card.
- **`output/` is gitignored** but contains committed-looking artefacts and `.DS_Store`
  files on disk. Nothing to fix in git; just noting the working tree is dirty with them.
- **Scale headroom.** 42 staff × 404 positions = 16,968 assignment booleans is modest;
  the solve time is driven by the constraint count (§3.1) and the broken objective (§2.3),
  not by problem size. Expect a large speedup from those two fixes alone, and re-evaluate
  the 300 s limit afterwards rather than raising it now.
