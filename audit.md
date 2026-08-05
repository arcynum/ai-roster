# AI-Roster — Code Audit & CP-SAT Design Review

**Scope:** full repo (`main.py`, `models.py`, `constraints.py`, `solver.py`, `output.py`, `utils.py`, `tests/`, data/config files).
**Method:** read every file against `AGENTS.md`/`hard_constraints.md`/`soft_constraints.md` (the stated ground truth), then actually ran the pipeline against the shipped `staff.yaml`/`roster.yaml` to confirm findings rather than guessing from static reading alone. All "confirmed" items below were reproduced by running the code.

**Bottom line:** the test suite (151 tests) passes, but it doesn't exercise the full pipeline end-to-end, so it hasn't caught four issues that mean **the project currently cannot produce a roster at all as shipped** — one crash, one silent-no-op config, and two entangled infeasibility sources. Those are §1; §1.4 now includes a specified design fix (soft floor + shortfall reporting, decided in discussion below) rather than just a diagnosis. Everything after §1 is real but not launch-blocking.

---

## 1. Critical — the pipeline does not currently run successfully

### 1.1 `generate_html()` is called with one argument too many — crashes every run

`main.py`:
```python
generate_html(result, staff_list, positions, definitions,
              roster_start, roster_end, blocks, run_id, positions)
```
`output.py`'s signature only takes 8 positional parameters (no trailing `positions`):
```python
def generate_html(result, staff_list, positions, definitions,
                   roster_start, roster_end, blocks, run_id) -> Path:
```
Running `python3 main.py` as-is reaches the solver, solves successfully, and then crashes:
```
TypeError: generate_html() takes 8 positional arguments but 9 were given
```
Reproduced 100% of the time. **Fix:** drop the duplicate trailing `positions` argument in the `main.py` call.

### 1.2 The shipped `config.yaml` silently disables *every* constraint

Confirmed by running `main.py` unmodified:
```
Hard constraints: 0 applied, 13 skipped
Soft constraints: 0 applied, 7 skipped
Solver status: OPTIMAL, objective: 0, time: 7.26s
```
`config.yaml` ships fully commented-out, intended (per `README.md`/`AGENTS.md`) to behave identically to "no config file — all constraints enabled." But `load_config()` only returns `None` (→ all enabled) when the `constraints:` key is **absent**. The shipped file *has* a `constraints:` key with `hard: {enabled:}` / `soft: {enabled:}` present but empty (because every line under `enabled:` is commented out, YAML parses this as `enabled: null`). `load_config()` then falls through to "build the enabled list from what's there," which is empty for both hard and soft — so **zero constraints are active**, and you get a warning-riddled but "successful" `OPTIMAL` solve that has no coverage skill checks, no rest rules, no red-request/holiday honoring, nothing.

This is the most dangerous bug in the project: it fails silently and "successfully," not loudly. A user who doesn't grep the log for `WARNING config.yaml: constraints.hard.enabled is not a list` would ship a roster with **no constraints applied whatsoever** and no obvious error.

**Fix options** (pick one, but pick one):
- Treat an `enabled: null`/empty list *per kind* the same as "section absent for that kind" (i.e., default to "all enabled" unless the file has at least one real entry uncommented) — probably the least surprising fix and matches the doc's intent.
- Or, if "empty list = nothing enabled" is genuinely the desired semantics (it's a defensible reading of "only listed IDs are active"), then the *shipped default file* is wrong and should not have a `constraints:` key at all until a user actually wants to toggle something — ship it fully commented out **including the top-level `constraints:` key**, or ship no `config.yaml` at all and rely on the README's documented instructions for creating one.
- Either way, add a loud `logger.warning`/startup assertion when 0 hard constraints are enabled — that condition should never pass silently as "normal operation."

### 1.3 `_create_variables()` hard-codes `sum(staff_vars) == 1` for *every* position, which directly contradicts `CasualStaffingConstraint` — casual fallback and `UNFILLED` are structurally unreachable

In `solver.py`:
```python
# --- Exactly one staff per position ---
for pi in range(num_positions):
    staff_vars = [self._assignment_vars[si][pi] for si in range(num_staff)]
    self.model.Add(sum(staff_vars) == 1)
```
This is applied to **every** position, unconditionally, before any constraint class runs. Then `CasualStaffingConstraint` ([H#c92f5e1b]) adds, for casual-eligible (`required_skill_level: null`) positions:
```python
model.Add(sum(staff_vars) + var == 1)
```
Combine the two and CP-SAT can only satisfy both by forcing `var == 0` — **the casual variable can never be 1**. This silently defeats:
- `H#c92f5e1b`/`H#71b4d9ac`/`H#4ef8a2c3` (casual staffing as a real fallback tier),
- `S#3d9a7ec1` (casual-usage minimization — it's now optimizing a variable that's already pinned to 0, i.e. a no-op),
- the entire tiered fill-order in AGENTS.md §7 (named staff → overtime flex → casual → `UNFILLED`).

Worse: because there's also no explicit `UNFILLED`/slack boolean anywhere in the model, a position that truly can't be covered by *any* named staff (e.g. a Shift-Coordinator slot with nobody available that day) doesn't get flagged as `UNFILLED` — it makes the **whole model INFEASIBLE**, and the solver reports nothing more specific than "no valid solution." That directly contradicts AGENTS.md §7's closing requirement: *"stop and tell the user why — never produce a broken or partial file silently"* — right now it doesn't even reach "produce a file," it reports total INFEASIBLE with no diagnosis of *which* position/skill/date caused it.

**Why the test suite doesn't catch this:** `tests/test_casual.py`'s integration test (`basic_model` fixture) uses 2 staff and 10 positions sized so that named staff can trivially cover everything — casuals are never actually *needed*, so the bug (casual pinned to 0) is invisible. The unit tests for `CasualStaffingConstraint` build a bare `cp_model.CpModel()` directly and never call `RosterModel._create_variables()`, so they never see the conflicting `==1` constraint either. **Recommend adding an integration test that intentionally understaffs a skill-agnostic shift** (fewer eligible/available named staff than positions) to force casual usage, which would have caught this immediately.

**Fix:** the base coverage constraint needs to become "exactly one, where the pool of options is (named staff) ∪ (casual, if eligible) ∪ (an explicit unfilled slack var)". Concretely:
```python
for pi in range(num_positions):
    staff_vars = [self._assignment_vars[si][pi] for si in range(num_staff)]
    options = list(staff_vars)
    if self.positions[pi].get("casual_allowed"):
        options.append(casual_var[pi])          # only if built before this point, or defer this constraint until after CasualStaffingConstraint runs
    options.append(unfilled_var[pi])             # new: explicit slack, heavily penalized
    self.model.Add(sum(options) == 1)
```
and give `unfilled_var` a penalty weight in the objective *above* `S#3d9a7ec1`'s (100000) but conceptually "worse than a casual" — since `UNFILLED` is supposed to be the last-last resort per AGENTS.md §7. This also finally makes the "unfilled" reporting in `output.py`/`solver._extract_assignments()` actually reachable from a *feasible* solve instead of only from a hard failure.

### 1.4 Confirmed real infeasibility in the shipped data, independent of 1.3 — **resolution: leave absorbs the shortfall, tracked as a soft floor**

After patching 1.1 and 1.3 in a scratch copy and re-running with the real `staff.yaml`/`roster.yaml` (all 13 hard + 7 soft constraints truly enabled), the solver still returns **INFEASIBLE** after ~3 minutes. I checked why:

```
Weekly required paid hours (sum of all roster.yaml positions): 1,060.0
Per 14-day block, total position-hours available:               2,120.0
Per-block SUM of every staff member's adjusted contracted-hours floor:
  Block 1 (2026-08-03 → 2026-08-16): 2,170.28
  Block 2 (2026-08-17 → 2026-08-30): 2,152.00
```
**The sum of everyone's `H#d9a8b7c6` floor exceeds the total hours the roster actually has to give out, in both blocks** — even before accounting for skill-level restrictions, red requests, rest rules, or the day/night split.

This is expected/normal in real rostering, not a data error: staff headcount is provisioned above minimum coverage on purpose, and the gap is ordinarily absorbed by staff taking leave (which proportionally reduces their floor via the existing `H#a3d8f6c1` proration — that machinery is already correct, there's just not currently enough *booked* leave in `staff.yaml` to close the gap). So the fix isn't to shrink the floor or grow the roster — it's to (a) let the solver still produce a roster when the floor can't be fully met, distributing whatever shortfall exists as fairly as possible, and (b) surface exactly how many hours of additional leave would need to be booked to close the gap entirely, so that's a decision a human can act on rather than a mystery `INFEASIBLE`.

#### Chosen design: soft floor with a per-staff/per-block shortfall slack variable

Reclassify `H#d9a8b7c6` from a hard equality-style floor into a **soft-enforced floor**, the same way `S#3d9a7ec1` documents its own history as *"Reclassified from `H#f3c72a8d`, which was mislabeled as a hard constraint."* This needs the same explicit call-out here: **`H#d9a8b7c6`'s hard/soft status is changing, and that's a real spec change that should be reflected in `hard_constraints.md`/`soft_constraints.md`, not just quietly patched in code.** Concretely:

**`ContractedHoursFloor` (renamed conceptually to a soft constraint, keep the ID or mint a new `[S#...]` per AGENTS.md §8's "IDs must be unique" rule and cross-reference the reclassification in both `.md` files):**
```python
for si, staff in enumerate(staff_list):
    for bi, block in enumerate(blocks):
        adj = compute_adjusted_hours(staff.contracted_hours_per_fortnight, staff.holidays, block)
        shortfall = model.NewIntVar(0, adj, f"floor_shortfall_{staff_names[si]}_b{bi}")
        model.Add(shortfall >= adj - staff_hours_vars[si][bi])
        model.Add(shortfall >= 0)
        shortfall_vars.append(shortfall)

# fairness: don't dump the whole shortfall on one or two people — same
# deviation-style pattern as WeekendFairness, applied to `shortfall` itself
# rather than to raw hours, so the shortfall gets spread rather than
# concentrated on whoever the solver finds "cheapest" to shortchange.
model.Minimize(sum(shortfall_vars) * weight)
```
The **absolute ceiling** (`H#f0c5b2c4`, 76h) and the **overtime cap** (`H#e8f7d6c5`, contracted+12h) stay exactly as they are today — those are safety/wellbeing limits, not coverage-math limits, and nothing about this change touches them.

**Weight:** this needs to sit *below* `S#3d9a7ec1`'s casual weight (100000) — using more casuals never helps close a floor shortfall anyway (a casual fills a position instead of a named staff member, which can only make named-staff floor attainment *harder*, not easier, so there's no actual tension there: minimizing casual usage and minimizing floor shortfall pull in the same direction). But it should sit clearly *above* the general fairness/consecutive-shift weights (50–500) — falling short of contracted hours is a bigger deal for a named staff member than shift-pattern or weekend-load preferences. A starting point in the 700–1000 range, to be tuned once real rosters are reviewed (the same caveat `weights.yaml` already applies to `S#6c1e9a4d`'s 300). **This needs a business sign-off on the exact number, not a default I should silently pick.**

**AGENTS.md §9's weight-dominance test needs updating.** It currently asserts `S#3d9a7ec1`'s weight exceeds the *worst-case combined* penalty from every other soft constraint. Adding this new shortfall-penalty term changes that upper-bound calculation — the test (and its comment showing the worked arithmetic) needs to include the new constraint's worst case (`num_staff × max_possible_shortfall_per_block × num_blocks × new_weight`) in the sum it checks against 100000.

#### Reporting: surface the shortfall, per staff, per block

This plugs directly into the reporting gap already flagged in §3.2 — the HTML "Messages" section and each staff member's per-block table should show, e.g.:

> *Amanda Bartley — Block 1: rostered 4.0h under her 76.0h floor (insufficient total roster demand this block, not a scheduling failure).*

Practically: read back each `shortfall` variable's solved value in `solver._extract_assignments()` (same place casual usage should be tallied per §3.2), attach it to `SolveResult`, and add an `adjusted_floor_shortfall`/`shortfall_light_class` (green/amber/red, same traffic-light pattern as `_overtime_info`/`_hours_floor_info`) to each block entry in `_build_context()`'s `staff_blocks`.

#### Keep the advisory pre-check too — it's complementary, not a replacement

The previous message's `check_block_feasibility()` helper (comparing total available position-hours vs. total floor demand, per block, before the solve) is still worth adding under this design — just as **informational logging, not a hard `raise`**, since the model can now solve through a shortfall instead of needing one:

```
WARNING: Block 1 (2026-08-03–2026-08-16): contracted-hours floor exceeds
available roster hours by 50.3h. Approx. 50.3h of additional leave (in any
combination across staff) would need to be booked to fully close this gap;
otherwise the solver will distribute the shortfall as fairly as possible
across staff and report it per person in the output.
```
This gives a fast, solver-free heads-up at the top of the log (useful for anyone scanning logs before waiting on a multi-minute solve), while the soft floor + per-staff reporting in the HTML output gives the precise, post-solve picture of who actually ended up short and by how much.

---

## 2. Soft-constraint logic bugs (model builds and "solves," but not to spec)

### 2.1 `OvertimeDistribution` ([S#e9b4a1b3]) doesn't distribute anything — it minimizes the *total*, not the *spread*

```python
ot = model.NewIntVar(0, 76*SCALE, ...)
model.Add(ot >= staff_hours_vars[si][bi] - contracted_scaled)
model.Add(ot >= 0)
overtime_dev_vars.append(ot)
...
model.Add(total_ot == sum(overtime_dev_vars))
model.Minimize(total_ot * weight)
```
The docstring claims "penalizes variance... deviation-from-mean formulation," but the code just sums every staff member's overtime and minimizes that sum. Minimizing **total** overtime is a different objective from **evenly distributing** overtime — the total demand for overtime hours is largely fixed by the coverage shortfall (roughly `total position-hours − total contracted floor`), so this term does little-to-nothing to prevent all the overtime landing on the same 2–3 people, which is exactly what `soft_constraints.md` says to avoid ("ensure these extra shifts are evenly distributed between all staff").

**Fix:** mirror the `WeekendFairness` pattern already in the same file — compute a per-staff overtime value, then penalize deviation from the mean (or from each other), e.g. `dev[s] = |overtime[s] * n − total_overtime|`, minimized. The building blocks already exist elsewhere in `constraints.py`; this class just needs to use them.

### 2.2 `NightShiftFairness` ([S#d2a7f4a6]) is not computed per block, despite the spec explicitly requiring it — and has a variable-bound bug that quietly caps a person's *whole-roster* night hours at 76

```python
# built ONCE, over ALL night positions in the entire roster (not per block):
nh = model.NewIntVar(0, 76 * SCALE, f"night_h_{...}")
model.Add(nh == sum(terms))     # terms cover every night position in the whole roster period
staff_night_hours.append(nh)
...
for bi in range(num_blocks):
    dev = model.NewIntVar(...)
    model.Add(dev >= staff_night_hours[si] - expected_night)   # same `nh` reused for every block!
    ...
```
Two separate problems:
1. **Spec violation:** `soft_constraints.md` says "applied on a per-block basis." The code sums night hours across the *entire* roster period and then adds a deviation term once per block using that same whole-roster total — for a 2-block (28-day) roster like the shipped one, this double-counts the same penalty and never actually evaluates fairness within a single fortnight.
2. **Latent correctness bug:** `nh`'s domain is `[0, 76*SCALE]`. That's a reasonable bound *per block*, but here `nh` represents a staff member's night hours across the *whole* roster (could span many blocks). If a roster is long enough that a person's total night hours legitimately exceed 76h, the `IntVar` domain combined with `model.Add(nh == sum(terms))` **silently forces `sum(terms) ≤ 76*SCALE` too** — i.e., it accidentally becomes an unintended extra hard cap on total night hours across the whole roster, not per block. This is a correctness bug, not just a design mismatch.

**Fix:** rebuild `night_pos_indices`/`staff_night_hours`/`expected_night` **inside** the `for bi in range(num_blocks)` loop, filtered to `blocks[bi]`, exactly like `_create_variables()` does for `staff_hours_vars`. That also fixes the IntVar bound (each block's night hours are correctly bounded by that block's own cap).

### 2.3 `DayNightRunCountPenalty` ([S#6c1e9a4d]) is specified per-block but implemented over the whole roster

`soft_constraints.md`: *"over a 14-day block, count each staff member's separate runs of day-category and night-category shifts... only counts exceeding 2 for either category are penalised."* The implementation's `category_vars`/`cat_run_start`/`staff_day_runs`/`staff_night_runs` all iterate `for di in range(num_dates)` across the **entire** multi-block `all_dates` range with no reset at block boundaries. For the shipped 2-block roster, this means a staff member could rack up 2 day-runs + 2 night-runs *per block* (4 total, correct per spec) but the code only penalizes them once they exceed 2 **across both blocks combined** — i.e., a staff member gets to "spend" their allowance once for the whole roster instead of once per fortnight, roughly halving the intended strictness for anyone on a multi-block roster (which, per `roster.yaml`, is the normal case here — 28 days = 2 blocks).

**Fix:** run the same run-counting logic once per block (reset `cat_run_start[0]` logic at the first day of each block, and sum `staff_day_runs`/`staff_night_runs` per block, per staff), summing the resulting per-block penalties into the objective — same general shape as `ContractedHoursFloor`/`OvertimeCap`, which correctly loop `for bi in range(len(blocks))`.

### 2.4 `ConsecutiveShiftDiscouraged` ([S#30c6f5ad]) — run-length enumeration cap may silently truncate for long/multi-block rosters

```python
max_run = min(14, num_dates - di)
for L in range(1, max_run + 1):
    ...
```
`soft_constraints.md` doesn't explicitly say this one resets per block (unlike S#6c1e9a4d, which does), and AGENTS.md's modeling note ("since a block is only 14 days, run lengths are bounded and enumerable") reads as a *tractability* justification rather than a scoping rule — so treating runs as continuous across the whole roster (not resetting at block boundaries) is plausibly correct behavior here. But the hardcoded `min(14, ...)` cap means any run genuinely longer than 14 consecutive days of the same shift type (which the hours caps make unlikely but don't strictly forbid, since e.g. 14 consecutive D8 shifts = 112 paid hours split as ~9 in one block + ~5 in the next, both individually under 76h) won't get an `exact_L` boolean built for `L > 14`, so the escalating penalty tier for L≥15 is simply never modeled — it neither penalizes nor forbids such a run.
**Recommendation:** either explicitly confirm with stakeholders whether this constraint is meant to reset at block boundaries (matching S#6c1e9a4d's explicit per-block wording, for consistency), or raise `max_run` to `num_dates - di` uncapped (correctness is more important than the minor performance saving from capping at 14, and the current cap doesn't actually match a real limit anywhere else in the model).

---

## 3. Output/reporting bugs

### 3.1 DISCO is counted as a **night** shift in the HTML hours/percentage breakdowns — directly contradicts the explicit spec exception

`output.py`, both in the whole-roster staff summary and the per-block breakdown:
```python
if definitions[slot.shift]["crosses_midnight"]:
    night_hours += paid
```
and again:
```python
b_night = sum(
    definitions[s.shift]["paid_hours"]
    for s in block_slots
    if definitions[s.shift]["crosses_midnight"]
)
```
`AGENTS.md` §5 is unambiguous and calls this out by name specifically *because* it's easy to get wrong: *"DISCO... crosses midnight... Despite that, DISCO is classified as a day shift for all fairness/reporting purposes... don't 'fix' it by moving DISCO into the night bucket."* Since `DISCO.crosses_midnight == true` in `definitions.yaml`, this code does exactly the thing the spec pre-emptively warns against — every DISCO shift a staff member works gets added to their reported "night hours" and "night %" in the HTML output, which will visibly overstate night-shift load for anyone rostered onto DISCO and will make the on-screen night/day fairness numbers not match what `NightShiftFairness` is actually optimizing against internally (which correctly uses `NIGHT_SHIFTS = {"N8", "N12"}`).

**Fix:** replace both `crosses_midnight` checks with a lookup against `utils.NIGHT_SHIFTS` (i.e. `slot.shift in NIGHT_SHIFTS` / `s.shift in NIGHT_SHIFTS`), matching how `constraints.py` and `models.py` (`Shift.is_night_shift`) already do it correctly.

### 3.2 The "Messages" section is missing most of what AGENTS.md §6 requires

`AGENTS.md` §6 specifies the Messages section should include: unfilled shifts (done), hard-constraint violations (not applicable if the model stays feasible, fine), **"which soft constraints incurred a penalty and roughly how much"** (not implemented — no per-constraint penalty breakdown exists anywhere in `output.py`/`solver.py`), **overtime allocation notes** (not implemented), and **"a summary of casual usage — total casual shifts used, and which dates/shifts they filled"** (not implemented — `result.assignments` contains casual slots tagged `filled_by_casual=True`, but `_build_context()` never aggregates or surfaces them separately). Right now the template only ever renders `result.unfilled` and a generic "No violations or unfilled shifts" fallback.

**Fix:** since `casual_vars`/soft-constraint penalty variables already exist inside `RosterModel` at solve time, the cleanest place to build this is in `solver._extract_assignments()` (which already has solver access) — read back each penalty term's solved value per soft constraint and stash it on `SolveResult`, and separately tally `result.assignments` where `filled_by_casual=True` into a casual-usage summary dict, then wire both into `_build_context()`.

### 3.3 Two loaded-but-unused variables in `main.py`

```python
hard_constraints = load_hard_constraints()
soft_constraints = load_soft_constraints()
```
Both are parsed from the markdown files and then never referenced again in `_run()`. Given 3.2's gap (no constraint text ever reaches the HTML output), this looks like the intended data source for that missing feature rather than genuinely dead code — worth wiring in rather than deleting, so the "Messages" section can eventually show human-readable constraint text next to a violation/penalty, not just an ID.

---

## 4. Modeling efficiency / redundancy (not incorrect, but worth tightening)

### 4.1 `NoDoubleBooking` ([H#e91c63ab]) is fully subsumed by `RestPeriodConstraint` ([H#c1f6e3f5])

Both build near-identical 8×8 shift-pair compatibility tables and both emit `model.Add(assignments[si][pi_d] + assignments[si][pi_d1] <= 1)` for every incompatible (staff, day-pair) combination. Since the 11-hour rest requirement is strictly stronger than "don't overlap" (any pair of shifts that overlaps also fails an 11h-gap check — a negative or zero gap is always < 11h), **every constraint `NoDoubleBooking` adds is already implied by `RestPeriodConstraint`'s constraints**, whenever both are enabled (the normal case). This isn't wrong, just duplicated work — for the shipped roster (42 staff × 27 date-pairs × ~up-to-64 shift-pair combos), this roughly doubles the constraint count for this specific rule, adding avoidable model-build and presolve time. Consider either merging the two into a single compatibility-table pass, or having `RestPeriodConstraint`'s table subsume `NoDoubleBooking`'s and demoting the latter to a pure registry/documentation entry (like `CoverageConstraint`/`SkillLevelHierarchy` already are) if you want to keep the two IDs distinct for traceability.

### 4.2 Three separate, near-identical 8×8 compatibility-table builders

`NoDoubleBooking._build_compatibility_table`, `RestPeriodConstraint._build_compatibility_table`, and `NightToDayRest._build_night_day_compatibility_table` each independently re-parse `definitions.yaml`'s start/end/`crosses_midnight` fields and hand-roll the same "shift A on day *d*, shift B on day *d*+1" iteration and "at most 1" constraint-emission loop. AGENTS.md §8 explicitly recommends building this once: *"Precompute shift-pair compatibility once, don't model time arithmetic per-assignment... Build an 8×8 (plus an explicit 'unassigned' state) boolean compatibility table once at startup."* Recommend factoring the shared "for each staff, for each consecutive day pair, for each shift pair, if not compatible, add `<=1`" loop into one utility function parameterized by whichever compatibility table gets passed in, and keep the three table-builders as the only per-constraint-specific code. This isn't just style — three independent hand-written time-arithmetic implementations of the same underlying date/midnight-crossing logic is exactly the kind of duplication AGENTS.md warns is easy to get subtly wrong in one copy and not the others (e.g. if `definitions.yaml` ever adds a 9th shift type, all three `SHIFT_TYPES = [...]` literals need updating in lockstep).

### 4.3 `ConsecutiveShiftDiscouraged` builds a very large number of auxiliary variables

Roughly `O(staff × dates × 14)` reified booleans/IntVars (for the shipped data: 42 staff × 28 dates × up to 14 run-length checks ≈ tens of thousands of auxiliary variables/constraints, before counting the `shift_type_vars`/`same_vars`/`run_start_vars` machinery underneath it). This is very likely the dominant contributor to the multi-minute solve times observed. Consider: (a) capping enumerated `L` by what's actually reachable given the 76h/block cap (e.g. no staff member can work more than ~9 consecutive 8h shifts within one block anyway, so enumerating up to 14 is generating a lot of provably-infeasible-anyway booleans), and (b) profiling model-build time (`_apply_soft_constraints` alone took several seconds even before solving in the test run) separately from solve time to see how much of the multi-minute solve is presolve-absorbing redundant variables from this constraint.

---

## 5. Smaller correctness/robustness notes

- **`compute_adjusted_hours` (utils.py) double-counts overlapping holiday ranges.** It loops over every holiday entry and, for each, counts every block day inside that range — if a staff member has two holiday entries that overlap the same calendar date (nothing in `validate_staff_records` forbids this), that date gets counted twice toward `holiday_days`, understating `available_days` (and thus their floor) more than it should. Low likelihood given clean data, but cheap to fix: accumulate holiday dates into a `set()` first, then take `len(set)` before computing `available_days`.
- **No cross-validation that `red_requests`/`holidays` dates fall within the roster period.** Not required by the spec, but a typo'd year (e.g. `2025-08-01` instead of `2026-08-01`) will pass validation silently and just never bind anything — worth at least a `logger.warning` when a staff member's red-request/holiday date never appears in `all_dates`.
- **Shift-type/category constants are duplicated in five+ places** (`models.py`, `utils.py`, and separately inside `NoDoubleBooking`, `RestPeriodConstraint`, `NightToDayRest`, `NightShiftFairness`, `DayNightRunCountPenalty`, `ConsecutiveShiftDiscouraged` in `constraints.py`). They're currently consistent, but there's no single source of truth enforcing that — `utils.DAY_SHIFTS`/`NIGHT_SHIFTS`/`SHIFT_ORDER` already exist and should be imported everywhere instead of re-declared.
- **`load_config`'s unknown-ID handling is a warning-only pass-through** (an unknown ID in `enabled` is logged but still added to the enabled set, where it just has no effect since nothing matches it). Combined with §1.2, this means a typo'd constraint ID in `config.yaml` degrades silently to "did nothing," which for a debugging tool whose entire purpose is toggling constraints on/off is a footgun worth hardening (e.g. raise instead of warn, since a typo here means a constraint you *think* is enabled silently isn't).

---

## Summary table

| # | Item | Severity | Verified by running? |
|---|---|---|---|
| 1.1 | `generate_html()` called with extra arg — crashes every run | Blocking | Yes |
| 1.2 | Shipped `config.yaml` silently disables all constraints | Critical | Yes |
| 1.3 | `_create_variables()` vs `CasualStaffingConstraint` contradiction — casuals/`UNFILLED` unreachable | Critical | Yes |
| 1.4 | Sum of contracted-hour floors exceeds available roster hours per block — genuine, expected scarcity (normally absorbed by leave). **Resolution specified:** reclassify `H#d9a8b7c6` to a soft floor with a per-staff/block shortfall slack variable (fairly distributed, weighted below casual usage but above general fairness), reported per staff in the HTML output; keep an advisory (non-blocking) pre-solve log of the shortfall in hours-of-leave terms | Critical (data) — design fix specified, needs weight sign-off + `.md` file updates | Yes |
| 2.1 | `OvertimeDistribution` minimizes total, not spread — doesn't implement fairness | High | Static + reasoning |
| 2.2 | `NightShiftFairness` not per-block; latent 76h whole-roster cap bug | High | Static + reasoning |
| 2.3 | `DayNightRunCountPenalty` not per-block despite explicit spec | Medium-High | Static + reasoning |
| 2.4 | `ConsecutiveShiftDiscouraged` run-length enumeration capped at 14, possible truncation | Low-Medium | Static + reasoning |
| 3.1 | DISCO counted as night hours in HTML output — contradicts explicit spec | Medium | Static (unambiguous) |
| 3.2 | Messages section missing penalty/casual-usage summaries required by spec | Medium | Static |
| 3.3 | Unused `hard_constraints`/`soft_constraints` loads in `main.py` | Low | Static |
| 4.1–4.3 | Redundant compatibility tables / large auxiliary-variable count | Efficiency | Static + observed solve times |
| 5.x | Holiday double-counting, missing date cross-validation, duplicated constants, silent unknown-ID pass-through | Low | Static |

**Suggested order of attack:** fix 1.1 and 1.2 first (they're one-line/small fixes and currently block *any* output at all), then 1.3 (casual/coverage contradiction) and 1.4 (soft floor + shortfall reporting) together since they're entangled — 1.3's coverage-constraint rewrite and 1.4's floor-as-slack-variable both touch the same `staff_hours_vars`/coverage machinery in `solver.py`, and 1.4's per-staff shortfall reporting shares a home with 1.3's casual-usage reporting (§3.2) — then the four soft-constraint scoping bugs in §2, then the DISCO reporting bug in §3.1 (quick, high-visibility fix), then use the remaining items as a backlog.
