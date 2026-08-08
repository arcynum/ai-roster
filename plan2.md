# AI-Roster — Follow-up Audit & Repair Plan (v2)

Audit date: 2026-08-08. This supersedes the previous `plan.md` (2026-08-07), which was
mostly but not fully implemented. Method: read every changed file, then wrote isolated
CP-SAT repros for anything load-bearing rather than trusting docstrings — the same
"prove it in isolation" standard the last plan used.

**Bottom line:** the previous plan's implementation is a genuine, well-executed pass —
roughly 35 of its ~45 items are correctly done, and the test suite is far healthier
(178 passed / 1 failed / 1 skipped vs. the old 139-that-caught-nothing). But one new,
serious correctness bug was introduced while fixing the old ones, three of the twelve
user decisions (D4, D6, D10, D11) were left half-done or undone, and the two
documentation-size items (§6.2/§6.3 in v1) were essentially not attempted — which
matters directly for the context-size problem you're hitting.

Fix order: §1 (the new P0 bug — this is why tests are failing) → §2 (finish the
decisions the user already made) → §3 (project-size reduction) → §4 (small hygiene
leftovers) → §5 (execution order).

---

## 1. P0 — New correctness defect (PROVEN, this is the current test failure)

### 1.1 `ConsecutiveShiftDiscouraged`'s "same shift as yesterday" reification is backwards

`constraints.py:906-907` (shared-vars path) and `constraints.py:1091-1092` (fallback
path), identical bug in both:

```python
model.add_bool_or(and_sh_vars).only_enforce_if(same)
model.add_bool_or([av.Not() for av in and_sh_vars]).only_enforce_if(same.Not())
```

`and_sh_vars[sh]` is 1 iff shift type `sh` is worked on both day *d* and *d+1*. `same`
is meant to be `OR(and_sh_vars)` — "some shift type matched on both days." The first
line is correct. The second line is **not** the De Morgan negation of the first: `NOT
(A OR B OR ... OR H)` is `NOT A AND NOT B AND ... AND NOT H` (all eight must be 0), but
the code emits `NOT A OR NOT B OR ... OR NOT H` (only one needs to be 0). Since a staff
member works at most one shift type per day, at least 7 of the 8 `and_sh` vars are
already 0 in every real scenario — so `add_bool_or([...Not()])` is satisfied *for free*
regardless of whether the matching shift actually repeated. The solver can therefore
set `same = 0` even when the same shift demonstrably ran both days, with no penalty and
no contradiction anywhere else in the model.

**Proven in isolation:** forcing the same staff member onto the same shift type for 4
consecutive days (`weight=500`) should cost `500` (the L=4 tier). It costs `0`. This is
functionally the same failure mode as v1's §2.1/§2.2 — the tiered run-length penalty is
inert — just via a different mechanism, and it's why `S#30c6f5ad·L=4` and `·L=5+` can
never actually fire: the solver always has a free escape hatch through `same=0`.

**Fix** — the negative branch needs an AND, not an OR. Either:

```python
model.add_bool_and([av.Not() for av in and_sh_vars]).only_enforce_if(same.Not())
```

or the arithmetic equivalent (one constraint instead of eight terms):

```python
model.Add(sum(and_sh_vars) == 0).only_enforce_if(same.Not())
```

Apply to **both** occurrences — `_apply_with_shared_vars` (~line 907) and
`_apply_fallback` (~line 1092). They are separate code paths with separate copies of
the bug; fixing one does not fix the other. `DayNightRunCountPenalty`'s analogous
run-detection logic (`constraints.py:1231+`) uses `!=`/`==` reification on an `IntVar`
instead of this OR-of-booleans pattern and does **not** have this bug — worth using as
the reference implementation if this code is refactored later.

**Regression test:** this is exactly what `tests/test_soft_constraints.py::
TestConsecutiveShiftDiscouraged::test_longer_runs_incur_penalty` already checks — it's
the one currently-failing test. No new test needed, just make it pass. Add one more
directly targeting the mechanism: assert that `same` is forced to `1` (not just that
the aggregate objective is higher) when two consecutive days are hard-constrained to
the identical shift, so a future refactor can't silently reintroduce this by changing
the aggregate math while leaving the reification broken.

**Why this matters beyond the one test:** the full 42-staff run's solve quality
(whether it reaches `OPTIMAL`, how many positions go unfilled) depends on this
constraint doing real work, since it's one of the larger per-instance soft penalties in
the objective. Re-run the full `main.py` end-to-end after this fix and record the new
objective/status/solve-time/unfilled numbers against a baseline captured *before* this
fix, the same way v1 recorded `160,197,000` / `FEASIBLE` / `300s` / `25 unfilled`.

---

## 2. Finish what the user already decided (D4, D6, D10, D11)

These aren't new findings — they're `plan.md` v1 decisions the user explicitly
answered in §0.1 that didn't make it into the code. Re-litigating them isn't necessary;
implementing what was already agreed is.

### 2.1 D4 — Saturday/Sunday fairness is still whole-period, not per-block

User answered **D4: (a) per block, for consistency** with the other three fairness
constraints. `_DayOfWeekFairness.apply()` (`constraints.py:740-790`, base class for
both `SaturdayFairness` and `SundayFairness`) has no `for bi, block in enumerate
(blocks):` loop at all — it pools every Saturday (or Sunday) across the *entire*
2-block roster period into one `staff_day_hours` sum, unlike `WeekdayNightFairness`
(`constraints.py:665`) and `OvertimeDistribution`, which correctly loop per block.

**Fix:** restructure `_DayOfWeekFairness.apply()` to loop over `blocks` the same way
`WeekdayNightFairness` does — filter `day_pos_indices` to positions within each block's
date set, compute `staff_day_hours` and `fair_share_deviation(...)` per block, and sum
into a `total_deviation` IntVar across blocks. Add a regression test with a 2-block
roster where one staff works all their Saturdays in block 1 and none in block 2 (equal
over the whole period, unequal per block) — the per-block version should penalize this
and the current whole-period version should not; assert the difference.

### 2.2 D6 — `solver:` config section still doesn't exist

User answered **D6: (a) expose `solver:` in `config.yaml`**. `solver.py:464-476`
already reads `constraint_config.get("solver", {})` with sane defaults
(`max_time_in_seconds=300.0`, `num_workers=8`, `random_seed=None`) — the mechanism is
built. But `config.yaml` has no `solver:` key at all, so every run silently uses the
hard-coded defaults and the config surface the user asked for doesn't exist.

**Fix:** add to `config.yaml`:

```yaml
solver:
  max_time_in_seconds: 300
  num_workers: 8
  random_seed: 42
```

Document the keys in `config.yaml`'s header comment and in AGENTS.md §10 (one line
each — don't re-explain CP-SAT parameters). Setting an explicit `random_seed` also
closes v1 §8's "no determinism" observation for free.

### 2.3 D10 — Tooling cleanup never happened

User answered **D10: (a) `pyproject.toml` + direct deps + `ruff` + `ty`**. Nothing
changed: `requirements.txt` is still the identical unfiltered `pip freeze` — `pandas`
and `numpy` (zero source-file usages, confirmed by grep), `pyright` (not installed —
the venv has no type checker at all right now), plus transitive noise (`six`,
`python-dateutil`, `Pygments`, `nodeenv`, `protobuf`, `absl-py`). `pyrightconfig.json`
is still present and still dead.

**Fix:**
- Create `pyproject.toml` with direct runtime deps only (`ortools`, `PyYAML`,
  `jinja2`) and a `[project.optional-dependencies] dev = ["pytest", "ruff", "ty"]`.
- Add `[tool.ruff]` (line length, `E`/`F`/`I`/`UP` rule sets) and `[tool.ty]`.
- Add `[tool.pytest.ini_options]` with `addopts = "-m 'not slow'"` and register the
  `slow` marker — this also fixes the `PytestUnknownMarkWarning` currently printed on
  every test run (`tests/test_missing_coverage.py:88` uses `@pytest.mark.slow` but
  nothing registers it).
- Delete `requirements.txt` and `pyrightconfig.json`.
- Add a one-line `scripts/check.sh` (or a `Makefile` target) running
  `ruff check . && ty check . && pytest tests/`, and reference it from AGENTS.md's
  workflow section and the README.

### 2.4 D11 — `constraints.py` is still one 1537-line file

User answered **D11: (a) split into `constraints/{base,hard,soft,registry}.py`**.
This is the largest source file in the project and wasn't touched. See §3.1 below —
this is now doing double duty as both "finish D11" and "the single biggest lever on
the context-size problem," so it's covered there instead of being a separate task.

---

## 3. Project-size reduction

You mentioned running into context-size issues working on this project. Three things
are driving that, roughly in order of impact:

### 3.1 Split `constraints.py` (1537 lines) — biggest lever, and closes D11

One file currently holds the base classes, all ~15 hard/soft constraint
implementations, and the shared helpers. A future session that needs to touch one
constraint has to load all 1537 lines to find it. Split along the lines v1 already
proposed:

- `constraints/base.py` — `BaseConstraint`, `BaseHardConstraint`, `BaseSoftConstraint`,
  `_emit_compatibility_constraints`, `SHIFT_ORDER`-adjacent shared helpers (~120 lines)
- `constraints/hard.py` — all `BaseHardConstraint` subclasses (~650 lines)
- `constraints/soft.py` — all `BaseSoftConstraint` subclasses, including
  `ConsecutiveShiftDiscouraged` and `DayNightRunCountPenalty`, which are the two
  largest classes in the file at ~230 and ~280 lines respectively (~700 lines)
- `constraints/registry.py` — `HARD_CONSTRAINTS`, `SOFT_CONSTRAINTS`,
  `get_hard_constraint_ids()`, `get_soft_constraint_ids()` (~60 lines)
- `constraints/__init__.py` — re-export everything currently importable from
  `constraints` so `main.py`, `solver.py`, and all of `tests/` need zero import
  changes beyond `from constraints import X` continuing to work unmodified.

This doesn't shrink the total line count, but it means a session working on, say,
`WeekdayNightFairness` reads a ~300-line `soft.py` section instead of the full
1537-line file — a large working-context win for exactly the kind of task this project
generates. Update AGENTS.md §12 (module map) to match.

### 3.2 AGENTS.md and README were supposed to shrink and didn't

v1 §6.2 targeted trimming AGENTS.md from 4,301 to ~3,000 words by cutting historical
narrative. It's now **4,171 words** — a ~3% cut, not the ~30% that was asked for. v1
§6.3 targeted README going from 1,487 to ~600 words by deduplicating content that's
also in AGENTS.md. It's now **1,458 words** — essentially untouched. Together these
two files are larger than `constraints.py` and get loaded into context on nearly every
session since they're the orientation docs.

**Fix, concretely this time:**

- **AGENTS.md**: delete the parenthetical change-history asides (the overtime-cap
  "raised from 12.5 to 24 … reduced to 12" narrative in §7, the "previously conflated —
  now resolved" framing in §2, the "duplicate ID was found and fixed" aside in §8, the
  "everything that used to live in `result.violations.md`" phrasing in §6) — these
  describe past agent sessions, not current rules, and don't inform any decision a
  future session needs to make. State the current rule only. This alone should recover
  most of the target.
- **README**: the `staff.yaml` field reference, the shift/day-night table, and the full
  output-file spec are near-verbatim duplicates of AGENTS.md §4/§5/§6. Since README
  already says "if the two disagree, AGENTS.md wins," there's no reason to carry two
  copies. Replace each duplicated block with a one-line pointer. Keep README to: what
  the project is, how to run it, what comes out, and a link to AGENTS.md for the rest.
- Do this as one focused pass, not incrementally — word-count creep back to the
  original size is easy if trims happen piecemeal alongside unrelated changes.

### 3.3 Tests: `test_constraints.py` (1531 lines) — check for consolidation, not cutting

This file is nearly as large as `constraints.py` itself and is the largest file in the
repo. Unlike the docs, this isn't wasted content — it's real coverage, and v1's test
rebuild (real `definitions.yaml` via `conftest.py`, no more fabricated shift times) is
one of the better parts of this codebase now. Don't cut assertions to save space. But
do check for the specific pattern v1 flagged and partially fixed elsewhere: repeated
~20-30 line setup blocks (building the same 2-3 staff, same position list, same
`_make_model` call) copy-pasted across dozens of tests instead of using
`pytest.fixture` parametrization. A pass to extract shared setups into
`conftest.py`-level fixtures (parametrized over the cases that currently get their own
copy-pasted test function) would cut real duplication without losing coverage. Treat
this as lower priority than §3.1/§3.2 — it's a nice-to-have, not blocking.

### 3.4 Remove crossed-out text; compact the two constraint docs

Two lines still carry Markdown strikethrough (`~~...~~`) left over from v1's D9
resolution:

- `hard_constraints.md:23` — `~~[H#d9a8b7c6]~~ ~~Staff must be rostered on for at
  least...~~` followed by the current reclassification note
- `soft_constraints.md:36` — `~~[S#a1d6c3d5]~~ ~~Weekend hours fairness...~~` followed
  by the current replacement note

These were kept as historical breadcrumbs, but struck-through IDs and full sentences
render as visual noise in every tool that shows raw Markdown (including any agent
reading the file) and add tokens without adding usable information — the replacement
constraint IDs already make the history traceable without them.

**Fix:** replace both with a plain, compact note and drop the strikethrough markup
entirely:

```markdown
<!-- [H#d9a8b7c6] reclassified to soft [S#d9a8b7c6] — see below -->
```

```markdown
<!-- [S#a1d6c3d5] replaced by [S#s1a2t3u4] and [S#s2u3n4d5] — see below -->
```

(or delete the lines outright and rely on the `IMPLEMENTED_ELSEWHERE` pointers in
`tests/test_constraint_sync.py`, which already document exactly this — a comment is
only worth keeping if a human reading `hard_constraints.md` on its own, without the
test file open, would otherwise wonder where the ID went.) Grep confirms these are the
**only** two strikethrough spans in the project — no wider cleanup needed here.

---

## 4. Small hygiene leftovers (low priority, cheap to batch)

Everything in this section is minor and can be done in one pass; none of it is
currently causing incorrect behavior.

- **§3.5 from v1 (`ModelContext` dataclass) was never done.** `apply()` signatures are
  still 10-13 positional parameters everywhere. This is real but lower priority than
  §1/§2 above — it's a readability/maintainability issue, not a correctness or
  size issue. Worth doing in the same pass as §3.1's file split, since splitting
  `constraints.py` and introducing `ModelContext` both touch every constraint class's
  signature — combining them avoids touching each class twice.
- **The "dead `model.minimize()` else-branches" v1 §6.4 flagged for deletion are
  actually load-bearing — this needs a decision, not a deletion.** v1 assumed these
  ~9 `else: model.minimize(...)` branches (present when `objective_terms is None`) were
  unreachable dead code that would "silently clobber the objective if ever reached."
  They're not dead: the entire `tests/test_soft_constraints.py` suite calls
  `constraint.apply()` directly without `objective_terms`, relying on exactly this
  fallback to make `solver.Solve()` optimize anything. Deleting them per the original
  plan would break ~15+ passing tests. **Recommendation:** keep the fallback, but
  document it explicitly as a supported dual-mode API (used standalone by tests, used
  via `objective_terms` accumulation by the real registry) rather than leaving it an
  implicit, undocumented convention — one sentence in each constraint's docstring or a
  short note in AGENTS.md §11 is enough.
- **`config.yaml` still has no `solver:` section** — covered above in §2.2, listed here
  too since it's easy to lose in a batch pass.
- Confirm `ty check .` and `ruff check .` run clean once §2.3's `pyproject.toml` lands
  — this hasn't been checked at all yet since neither tool is currently installed.

---

## 5. Suggested execution order

1. **§1** — fix the reification bug in both `ConsecutiveShiftDiscouraged` code paths.
   This is a two-line-per-occurrence fix (4 lines total) and turns the failing test
   green. Do this first and in isolation; nothing else in this plan depends on it, but
   it's the highest-value fix available and should land before any refactor that
   touches this constraint (§4's `ModelContext` work).
2. **Re-run the full test suite** — confirm 179/179 passing, note the objective/status
   from a full `main.py` run against real data as the new baseline (replacing v1's
   `160,197,000` / `FEASIBLE` / `300s` / `25 unfilled`).
3. **§2** — D4, D6, D10 in any order (independent, small, each with its own test where
   noted). D11 is folded into §3.1.
4. **§3.1** — split `constraints.py`, and fold in §4's `ModelContext` dataclass while
   every constraint signature is already being touched. Re-run the full test suite
   after — this is a pure refactor and should not change any test outcome.
5. **§3.2** — the AGENTS.md/README trim, as one focused pass.
6. **§3.4** — the two strikethrough lines, five minutes.
7. **§3.3** — test fixture consolidation, whenever convenient; not blocking.

**Definition of done for each step:** `pytest tests/` clean (179/179, no warnings),
`ruff check . && ty check .` clean once §2.3 lands, a full `main.py` run against real
data produces zero `verify()` violations, and the objective/status numbers are recorded
against the new baseline from step 2.
