# AI-Roster — Update Plan (Casual Removal, Unfilled-First Workflow, Shift-View Table, Hours Summary)

**Purpose:** an execution plan for a coding agent, based on re-reviewing the current codebase against `AI-Roster-Audit.md` and the four new feature requests. I re-ran the full pipeline against this codebase to confirm status before writing this plan — see §0.

---

## 0. Audit re-check — what's already fixed

Good news first: **every §1 (blocking) item from the original audit is fixed**, and most of §2/§3 as well. I re-ran `python3 main.py` end-to-end against the shipped data and it now completes successfully (`FEASIBLE`, 387 assignments, 73 casual, 17 unfilled, HTML written) instead of crashing or reporting `INFEASIBLE`. Confirmed fixed:

| Audit item | Status |
|---|---|
| 1.1 `generate_html()` extra-argument crash | **Fixed** — call site and signature match |
| 1.2 Shipped `config.yaml` silently disabling all constraints | **Fixed** — empty/commented `enabled:` now correctly means "all enabled," logged clearly |
| 1.3 Coverage `==1` vs. `CasualStaffingConstraint` contradiction | **Fixed** — coverage constraint now correctly composes staff + casual + a new `unfilled` slack var, in the right order |
| 1.4 Contracted-hours floor infeasibility | **Fixed as agreed** — `H#d9a8b7c6` reclassified to `[S#d9a8b7c6]`, shortfall slack variable added, fairly distributed, weight 1000, reported per staff/block, `.md` files updated to match |
| 2.1 `OvertimeDistribution` minimizing total instead of spread | **Fixed** — now uses the deviation-from-mean pattern |
| 2.2 `NightShiftFairness` not scoped per block | **Fixed** — rebuilt inside the per-block loop |
| 2.3 `DayNightRunCountPenalty` not scoped per block | **Fixed** — rebuilt inside the per-block loop |
| 2.4 `ConsecutiveShiftDiscouraged` run-length cap at 14 | **Fixed** — cap removed, now `num_dates - di` |
| 3.1 DISCO counted as night hours in HTML output | **Fixed** — now uses `NIGHT_SHIFTS` set, not `crosses_midnight` |
| 3.2 Messages section missing penalty/casual-usage summaries | **Partially fixed** — `result.soft_penalty` and `result.casual_usage` now exist and are passed into the Jinja context, **but `templates/roster.html` never actually renders either of them** — the Messages section still only loops over `unfilled`. This is now folded into this plan (§5). |
| 3.3 Unused `hard_constraints`/`soft_constraints` loads in `main.py` | **Fixed** — now passed into `generate_html()` |
| Date-outside-roster-period validation (audit §5) | **Fixed** — `staff.yaml` red-request/holiday dates outside the period now log a warning |
| Advisory pre-solve leave/feasibility check (discussed in chat, not yet in the original written audit) | **Not implemented yet** — folds directly into new requirement #4 below, see §4 |

Still open from the original audit, not touched by this plan unless noted: §4.1/4.2 (redundant `NoDoubleBooking`/`RestPeriodConstraint` compatibility tables), §4.3 (large auxiliary-variable count in `ConsecutiveShiftDiscouraged`), §5 minor items (holiday double-counting, unknown-ID silent pass-through). **Worth flagging now: the confirmed run above took 301s and hit the solver's 300s time limit without proving optimality (`FEASIBLE`, not `OPTIMAL`).** Removing casual variables (§1 below) will shrink the model somewhat, but the real cost driver is almost certainly `ConsecutiveShiftDiscouraged`'s variable count (audit §4.3). Recommend treating that as a fast-follow after this plan, not bundling it in now.

---

## 1. Remove casual staffing entirely

Casual staffing touches code, data, config, docs, and tests. Go file by file — nothing should reference "casual" anywhere in the repo when this is done (`grep -ri casual .` should return zero results outside a changelog note, if you choose to keep one).

### 1.1 `constraints.py`
- Delete the `CasualStaffingConstraint` class (`[H#c92f5e1b]`/`[H#71b4d9ac]`/`[H#4ef8a2c3]`) in full.
- Delete the `CasualUsageMinimization` class (`[S#3d9a7ec1]`) in full.
- Remove both from the constraint registry lists at the bottom of the file.

### 1.2 `solver.py`
- Remove `self.casual_vars` (declaration + the `hasattr(constraint, "casual_vars")` capture block).
- Remove `casual_usage` from `SolveResult` (the field, and the block in `_extract_assignments()` that appends to it and sets `staff_name="Casual"` / `filled_by_casual=True`).
- Simplify the coverage-constraint builder: it currently branches on `positions[pi].get("casual_allowed")` to decide whether to add a casual option. After removal, **every** position's coverage constraint is simply `sum(staff_vars) + unfilled_var == 1`, no branching needed. Delete the `casual_allowed` branch entirely — this also means the ordering dependency ("coverage constraint must run after `CasualStaffingConstraint`") goes away, which should simplify `build_model()`'s call order.
- Remove `apply_kwargs["casual_vars"] = self.casual_vars` and the corresponding parameter from any soft constraint's `apply()` signature that still accepts `casual_vars=None` (should just be the now-deleted `CasualUsageMinimization`, but double check nothing else picked up the kwarg defensively).
- Update the log line `"Extracted %d assignments (%d casual), %d unfilled positions"` to drop the casual count.
- **Keep `unfilled_var` and `UNFILLED_PENALTY_WEIGHT` exactly as they are** — that mechanism is what requirement #2 below relies on, and it's already correct. Consider moving `UNFILLED_PENALTY_WEIGHT` out of the hardcoded `200000` in `solver.py` and into `weights.yaml` for consistency with every other weight in the system (nice-to-have, not required).

### 1.3 `models.py`
- Remove `filled_by_casual: bool = False` from `RosterSlot`.

### 1.4 `utils.py`
- Remove the `"casual_allowed": required_skill is None` key from wherever positions are built (it becomes a dead field once nothing reads it — confirm nothing else consumes it before deleting, but as of this review only the two deleted constraint classes and the deleted coverage-constraint branch read it).

### 1.5 `output.py`
- Remove `"casual_usage": result.casual_usage` from the context dict in `_build_context()`.

### 1.6 `templates/roster.html`
- No direct casual references currently exist here (confirmed), but double-check after the above changes that nothing in the Messages section or summary cards silently breaks from the removed context key.

### 1.7 `weights.yaml`
- Delete the `"S#3d9a7ec1": 100000` line and its comment.
- **Update `"S#d9a8b7c6"`'s comment** — it currently says "Sits below casual (100000) but above fairness weights (50-500)." With casual gone, the top of the weight hierarchy is now `UNFILLED_PENALTY_WEIGHT` (200000, in `solver.py`, not `weights.yaml` — see §1.2's nice-to-have). Reword to reference that instead.

### 1.8 `config.yaml`
- Delete the three commented casual hard-constraint lines (`[H#c92f5e1b]`, `[H#71b4d9ac]`, `[H#4ef8a2c3]`) and the commented `[S#3d9a7ec1]` soft line.

### 1.9 `hard_constraints.md`
- Delete lines for `[H#c92f5e1b]`, `[H#71b4d9ac]`, `[H#4ef8a2c3]` in full.
- `[H#4ef8a2c3]`'s deletion removes the *only* place that documents "these constraints don't apply cross-individual to casuals" — that's fine, since there are no casuals left to be exempt from anything, but **grep the rest of the file for any other constraint text that mentions "named staff" as if distinguishing them from casuals** (e.g. phrasing like "for named staff" that only made sense in contrast to a casual option) and simplify that language back to plain "staff."

### 1.10 `soft_constraints.md`
- Delete the `[S#3d9a7ec1]` entry in full.
- `[S#d9a8b7c6]`'s entry references "Weight should sit below casual usage (100000)" — reword to reference `UNFILLED_PENALTY_WEIGHT` instead.

### 1.11 `AGENTS.md` — the biggest doc change
This file has the most casual-specific content and needs careful editing, not just deletion, since several other sections logically depend on it:
- **§6 (Messages)**: remove "a summary of casual usage — total casual shifts used, and which dates/shifts they filled."
- **§7 (fill order)**: currently a 4-tier list (named staff → overtime flex → casual → `UNFILLED`). Collapse to 2 tiers (named staff, including the 12h flex → `UNFILLED`). Delete tier 3 (casual) entirely. Rewrite tier 4 (`UNFILLED`) so it no longer says "reachable only when neither named staff (even flexed) nor a casual can cover a position" — it's now reachable whenever no eligible named staff can cover a position, full stop.
- **§7/§9 overtime-cap rationale — decided, update the text.** The relative overtime ceiling **stays at 12h** — `[H#e8f7d6c5]`'s value in `hard_constraints.md`/the code does not change. But the *rationale* text needs rewriting: it currently says the ceiling was *"raised to 24 before casual staffing existed in this model, reduced back down to 12 now that casuals can absorb the rest of a coverage gap instead of stretching named staff further."* That's no longer accurate, since this system no longer models casuals at all. Replace it with the real reasoning: casual staff still exist operationally, but sourcing them is now entirely outside this system — the roster builder reviews `UNFILLED` positions in the output and arranges casual cover manually. The 12h ceiling stays because it's a named-staff wellbeing limit in its own right (not because something else was going to absorb the rest of the gap), and gaps beyond what named staff can safely absorb are expected to surface as `UNFILLED` and be resolved outside the model. This also means **`UNFILLED` is no longer a rare edge case — it's an expected, routine output** whenever named-staff capacity falls short of total demand (the same structural gap already identified in §1.4/§4: total contracted-hours floor already exceeds available roster hours in the shipped data even before accounting for hard caps). That reframing is important context for §6 below.
- **§8 (modeling notes)**: remove the "Casual fallback" bullet describing how it was modeled.
- **§9 (weight-dominance sanity check)**: currently anchored to `S#3d9a7ec1`'s weight (100000) needing to exceed every other soft constraint's worst-case combined penalty. **This check's entire purpose (guaranteeing a last-resort tier is never displaced by lower-priority preferences) now belongs to `UNFILLED_PENALTY_WEIGHT` (200000)**, not a soft constraint at all — reframe this section to describe validating that `UNFILLED_PENALTY_WEIGHT` exceeds the worst-case combined penalty from *all* soft constraints (including `[S#d9a8b7c6]`'s shortfall penalty, which itself needs to stay below `UNFILLED_PENALTY_WEIGHT` but is otherwise unaffected). If there's an actual test implementing this sanity check (check `tests/` — audit didn't find one yet, worth adding per the original audit's recommendation either way), update/add it to reference `UNFILLED_PENALTY_WEIGHT`.

### 1.12 `README.md`
- Remove the three casual-related bullets identified in review (casual wildcard-only coverage, unlimited supply/exemption from individual constraints, casual usage minimized as last resort).
- Update the Messages-section bullet to drop "and a summary of casual usage."

### 1.13 Tests
- Delete `tests/test_casual.py` entirely.
- Search `tests/test_constraints.py` and `tests/test_soft_constraints.py` for any fixtures or test functions that build a `constraint_config` enabling `[H#c92f5e1b]`/`[H#71b4d9ac]`/`[H#4ef8a2c3]`/`[S#3d9a7ec1]`, or that assert on `result.casual_usage`/`filled_by_casual` — remove those tests (confirmed via grep that no other test file currently references "Casual" by name, but re-check after the constraint IDs are gone since some tests may reference the IDs as bare strings rather than class names).
- **Add a new integration test** (this was already recommended in the original audit, §1.3, as the gap that let the casual bug go undetected — now repurpose it): build a scenario with more positions than eligible/available named staff can cover (e.g. more skill-restricted positions on a day than qualified staff), run the full model, and assert the shortfall shows up as `result.unfilled` entries rather than the model going `INFEASIBLE`. This is the regression test that protects requirement #2 below.

---

## 2. Let the engine leave shifts unfilled when there's a staff deficit

Structurally, **this is already done** — `solver.py`'s coverage constraint already includes `unfilled_var` per position, weighted at `UNFILLED_PENALTY_WEIGHT = 200000` (the highest weight in the model), and `result.unfilled` is already populated and rendered in the Messages section. The only remaining work here is what §1 already covers: once casual removal (§1.2) simplifies the coverage constraint to `sum(staff_vars) + unfilled_var == 1` for every position (no more `casual_allowed` branching), the "unfilled when short-staffed" behavior becomes the sole fallback path, exactly as requested. No additional modeling work needed beyond §1's cleanup — just make sure the new integration test from §1.13 passes afterward.

One thing worth double-checking once casuals are gone: currently `UNFILLED_PENALTY_WEIGHT` (200000) only had to dominate the casual weight (100000) plus every soft constraint. With casual gone, re-verify (or newly implement, per §1.11's §9 update) that 200000 still comfortably exceeds the worst-case combined soft-constraint penalty on its own.

---

## 3. New "Roster by Shift" table (shifts on the Y axis, dates on the X axis, capped at 15 rows per shift type)

This is genuinely new modeling work, not a bug fix — the engine currently has no concept of a stable, per-slot identity for "the 2nd L3 position on a Tuesday" vs. "the 1st." Positions are only distinguished by `(date, shift, required_skill_level)`, and where more than one position shares all three (e.g. the two `null`-skill `L3` slots on a Monday), they're currently interchangeable and untracked as individuals — which is fine for solving, but not for rendering a stable table where each row means the same thing every day.

### 3.1 Design: a stable `slot_id` per position

Add a `slot_id` to every roster position, assigned once when positions are generated from `roster_positions` in `roster.yaml` (wherever that currently happens — `utils.py`'s position-building function). Recommended scheme, since it keeps the skill context visible (useful to the roster builder, not just a bare number) while still uniquely numbering true duplicates:

```
slot_id = f"{shift}-{skill_label}-{n}"
```
where `skill_label` is the `required_skill_level` (e.g. `Triage`, `Coordinator`, `Resus`) or `General` for `null`-skill positions, and `n` is a 1-based counter *within that (shift, skill_label) group, per day-of-week template* — i.e. counted the same way `roster_positions` repeats weekly, so the same `slot_id` refers to "the same slot" across every week of the roster (e.g. `D12-General-1` on every Monday is the same row). Examples from the current `roster.yaml`: `D12-Coordinator-1`, `D12-Triage-1`, `D12-Resus-1`, `D12-General-1` (four separate D12 rows), `L3-General-1` and `L3-General-2` (the two interchangeable L3 wildcard slots).

I checked the current data: the highest same-(shift, skill) count on any single day is 4 (`D12`, `N12`), well under the requested 15-row cap — 15 rows gives real headroom for the roster to grow, so no data changes needed for this to fit as specified.

### 3.2 Threading `slot_id` through the engine

- **`models.py`**: add `slot_id: str` to `RosterPosition`, and add `slot_id: str` to `RosterSlot` (the solver-output assignment record) so a finished assignment can be traced back to its slot.
- **`utils.py`** (position generation): assign `slot_id` per the scheme above when building the positions list.
- **`solver.py`** (`_extract_assignments()`): when building each `RosterSlot`, carry the source position's `slot_id` through. When a position ends up in `result.unfilled` instead, make sure `slot_id` is attached there too (however `unfilled` positions are currently represented) so the new table can show "UNFILLED" in the right row/column.
- No constraint logic needs to know about `slot_id` — it's purely a reporting/identity concern, doesn't change coverage math (the coverage constraint continues to operate per-position as it does today; `slot_id` is just a label on top).

### 3.3 Building the new context in `output.py`

Add a new structure to `_build_context()`, grouped by shift type, each shift type mapping to a fixed-height (≤15) table of `slot_id → {date_str: staff_name_or_"UNFILLED"}`:

```python
shift_slot_tables: dict[str, dict[str, dict[str, str]]] = {}
for shift_type in SHIFT_ORDER:   # existing constant already used elsewhere for consistent ordering
    slot_ids = sorted({p["slot_id"] for p in positions if p["shift"] == shift_type})
    # cap at 15 — if this ever trips, it's a signal the roster has grown
    # beyond what this table format can show; log a warning rather than
    # truncating silently
    table = {sid: {ds: None for ds in all_date_strs} for sid in slot_ids[:15]}
    shift_slot_tables[shift_type] = table

for slot in result.assignments:
    if slot.slot_id in shift_slot_tables.get(slot.shift, {}):
        shift_slot_tables[slot.shift][slot.slot_id][slot.date] = slot.staff_name

for pos in result.unfilled:
    if pos["slot_id"] in shift_slot_tables.get(pos["shift"], {}):
        shift_slot_tables[pos["shift"]][pos["slot_id"]][pos["date"]] = "UNFILLED"
```
Pass `shift_slot_tables` into the template context.

### 3.4 Template: `templates/roster.html`

Add a new section (e.g. "Roster by Shift") after the existing "Roster by Date" table, following the same `matrix-table`/`matrix-container` pattern already used for the staff-by-date table for visual consistency. One sub-table per shift type, each with the mandated shape (dates as columns/header row, up to 15 slot rows):

```html
<h2>Roster by Shift</h2>
{% for shift_type, slots in shift_slot_tables.items() %}
<h3>{{ shift_type }}</h3>
<div class="matrix-container">
<table class="matrix-table">
<thead>
<tr>
  <th>Slot</th>
  {% for d in all_dates %}
    <th class="{{ 'weekend-col' if d.is_weekend else '' }}" title="{{ d.day_name }}">
      {{ d.day }}<br>{{ d.abbrev }}
    </th>
  {% endfor %}
</tr>
</thead>
<tbody>
{% for slot_id, by_date in slots.items() %}
  <tr>
    <td>{{ slot_id }}</td>
    {% for d in all_dates %}
      {% set who = by_date[d.date_str] %}
      <td class="{{ 'weekend-col' if d.is_weekend else '' }} {{ 'cell-unfilled' if who == 'UNFILLED' else '' }}">
        {{ who or '' }}
      </td>
    {% endfor %}
  </tr>
{% endfor %}
</tbody>
</table>
</div>
{% endfor %}
```
Add a `.cell-unfilled` CSS rule (in the `<style>` block at the top of the template, alongside the existing `.warning`/`weekend-col` styling) with a distinct highlight color — something that reads clearly as "needs attention" but doesn't clash with the existing weekend-column shading or shift-badge palette (e.g. a solid warm background rather than just a text color, since this needs to be scannable at a glance across a wide table).

---

## 4. Run Summary: total required hours vs. total staff available hours

This directly implements the advisory pre-check discussed earlier in this conversation, but as a first-class part of the shipped HTML output rather than just a log line — and ties directly into requirement #2 and #3: this is the "why are there unfilled shifts" answer, right at the top of the report, before the roster builder even scrolls down to the tables.

### 4.1 Compute both figures

- **Total roster hours required**: sum of `definitions[shift]["paid_hours"]` across every position in `roster.yaml` for the full roster period (all blocks) — this is exactly the `weekly_hours * num_weeks` calculation already used ad hoc during this review (`1,060h/week` in the current data).
- **Total staff available hours**: sum of every staff member's *adjusted* contracted hours (via the existing `compute_adjusted_hours()`, which already accounts for booked leave/holidays) across the full roster period.
- **Report both the whole-roster totals and the per-block breakdown.** The per-block figures are what's actually actionable (`H#a3d8f6c1`'s proration and `[S#d9a8b7c6]`'s shortfall constraint both operate per 14-day block, so "block 1 is short 50h, block 2 is short 32h" is a more useful instruction to management than one combined number for the whole roster).

### 4.2 Where this lives

- Add the computation to `solver.py` or `output.py`'s `_build_context()` (either is fine — `solver.py` has more natural access to `blocks`/`staff_list`/`positions` already, so probably cleanest there, attached to `SolveResult` alongside the existing `shortfall` field it already computes per staff/block from the same underlying numbers).
- Add new summary cards to the `Run Summary` section in `templates/roster.html`, alongside the existing `Assignments`/`Unfilled Positions` cards: **Total Hours Required**, **Total Staff Hours Available**, and a derived **Hours Surplus/Shortfall** card (available − required; negative/red when short, positive/green when there's headroom) — per block, and optionally a combined roster-total row underneath. Since management's actual question is "how many hours of leave do we need staff to take," consider phrasing the shortfall card directly in those terms when it's negative, e.g. *"Approx. Xh of additional leave needed this block to fully close the gap"* — the same framing already used for the advisory log-line concept discussed earlier, now surfaced where the roster builder will actually see it.
- This is independent of, but complements, the existing per-staff `[S#d9a8b7c6]` shortfall reporting already in the staff-by-block tables (§0) — that shows *who* ended up short after the solve; this new summary shows the *aggregate* picture *before* anyone reads a single staff row, which is what's needed to actually go plan leave.

---

## 5. Other issues identified in this review

- **`soft_penalty` is computed and passed into the template context but never rendered anywhere in `templates/roster.html`.** This was flagged as "partially fixed" in §0 — the Messages section needs a new block listing each soft constraint ID with its total incurred penalty (skip entries with 0), the same way `unfilled` is currently listed. Do this alongside §1's casual-removal pass through the Messages section, since you'll already be touching that section to remove the (now-empty) casual-usage listing plan.
- **Confirm the weight-dominance sanity check actually exists as a test**, not just as documentation. The original audit recommended adding one; this review didn't find one in `tests/`. Now is a good time to add it (§1.11's §9 update depends on it existing and being correct), asserting `UNFILLED_PENALTY_WEIGHT` exceeds the worst-case combined soft-constraint penalty (sum of every constraint's weight × its maximum possible per-instance penalty × instance count).
- **Performance**: the confirmed run in §0 hit the solver's 300s time limit at `FEASIBLE`, not `OPTIMAL`. This plan doesn't change the model's fundamental size much (casual variables were a modest fraction of the 16,968 assignment BoolVars), so this will likely persist. The original audit's §4.1–4.3 (redundant compatibility tables between `NoDoubleBooking`/`RestPeriodConstraint`, and `ConsecutiveShiftDiscouraged`'s large auxiliary-variable count) remain the most likely levers — recommend as an immediate fast-follow once this plan lands, not bundled into it, so this update can be reviewed and tested in isolation first.
- **`hard_constraints.md`'s "Parsed 23 hard constraints" vs. the ~13 actual enforced ones** — worth a quick sanity pass once casual removal drops the count further, to make sure the markdown file's constraint count and the registry in `constraints.py` stay in sync (no orphaned doc entries for constraints that no longer exist in code, and vice versa).
- **Minor items carried over from the original audit, still unaddressed, low priority, no action required in this pass**: holiday-range double-counting in `compute_adjusted_hours()` (audit §5), and `load_config()`'s silent pass-through of unknown constraint IDs (audit §5) — both still worth doing eventually, neither blocks anything in this plan.

---

## 6. Make `UNFILLED` desirability-weighted, not just a flat last resort

This is the most substantial design change in this plan, and it changes the *purpose* of `UNFILLED` in the model. Up to now (§0/§2), `UNFILLED` has been treated purely as a rare safety valve: `UNFILLED_PENALTY_WEIGHT` (200000) is a single flat constant, deliberately set high enough to dominate every other soft constraint combined, so the solver only ever leaves a position unfilled when there's truly no other way to satisfy the hard constraints. Per the discussion above, that's no longer the right mental model: **since casuals are now sourced entirely outside the system, `UNFILLED` is the expected, routine way this system reports a structural staffing gap** — and you've asked for something more specific than "minimize how often this happens": when positions *do* have to go unfilled, the model should actively prefer to leave the **least desirable** shifts open, so that the staff-hours capacity that's genuinely available gets spent on giving named staff the best possible roster rather than being spread thin trying to hit 100% coverage indiscriminately.

### 6.1 Why a flat weight can't do this, and why tiering it still keeps the existing safety guarantee

The reasoning that made 200000 "dominate everything" still needs to hold — you don't want the solver leaving a shift unfilled just to dodge a minor fairness penalty when full coverage is genuinely achievable. The fix isn't to lower the weight; it's to **replace the single constant with a small set of tiered weights**, one per "how bad is it to leave this specific position unfilled," where **every tier still individually exceeds the worst-case combined soft-constraint penalty** (the same invariant §1.11/§9 already requires — it just now needs to hold for the *lowest* tier, not a single number). That preserves the existing guarantee ("never sacrifice real coverage to save a soft-constraint penalty") while giving the solver a genuine, ordered *choice* about *which* positions to leave unfilled whenever the total achievable coverage is capped below total demand by hard constraints (max hours per person, rest rules, etc.) — which, per §0/§4, is expected to happen routinely with the current staffing data.

### 6.2 Two independent dimensions to the tiering — don't conflate them

**Dimension 1 — skill criticality (should dominate the ordering).** A gap in a `Shift Coordinator`/`Triage`/`Resus` position is a clinical coverage problem, not a preference-optimization problem — these should almost never be the ones left open just because a night/weekend slot would be "more convenient" to leave unfilled instead. Recommend: skill-required positions keep the highest unfilled weight tier (effectively unchanged from today's behavior — still the closest thing to "last resort"), and the desirability-based tiering in Dimension 2 applies primarily *within* the `null`-skill ("General"/wildcard) position pool, where leaving a gap doesn't compromise a specific clinical competency on the floor.

**Dimension 2 — shift desirability (the actual "least desirable" ranking you asked for).** Within a skill tier (most usefully, within `General`), rank position types by how undesirable they already are by the model's own existing signals — you don't need to invent a new preference score, the existing fairness constraints already encode what's undesirable:
- Night shifts (`N8`/`N12`, via `NIGHT_SHIFTS`) — already the subject of `[S#d2a7f4a6]`'s fairness constraint.
- Weekend shifts (via `is_weekend()`) — already the subject of `[S#a1d6c3d5]`'s fairness constraint.
- Combined weekend-night positions are the most undesirable of all.

Recommended tier structure (illustrative starting values — like every other weight in this system, these are a starting point to recalibrate once real rosters are reviewed, not a number to lock in without review):

| Tier | Example | Relative unfilled weight |
|---|---|---|
| Skill-required (`Coordinator`/`Triage`/`Resus`) | any date/shift | Highest — e.g. `220000` |
| `General`, weekday, day-category | e.g. Tuesday `D8` | High — e.g. `200000` |
| `General`, weekday, night-category | e.g. Tuesday `N12` | Medium — e.g. `170000` |
| `General`, weekend, day-category | e.g. Saturday `D8` | Medium-low — e.g. `160000` |
| `General`, weekend, night-category | e.g. Saturday `N12` | Lowest — e.g. `140000` |

Every tier must still be re-verified against the weight-dominance sanity check from §1.11/§9 — the *lowest* tier (weekend-night General, above) is the one that actually has to clear the bar, since it's the cheapest place for the solver to "spend" an unfilled position.

### 6.3 Implementation

- **`solver.py`**: replace the single `UNFILLED_PENALTY_WEIGHT` constant with a small function (or lookup table) that computes the tier weight for a given position — inputs are just `required_skill_level`, `shift` (via `NIGHT_SHIFTS`), and `date` (via `is_weekend()`), all of which are already available where `unfilled_var`'s penalty term is built. Move these tier values into `weights.yaml` alongside every other weight, rather than leaving them hardcoded in `solver.py` (this was already flagged as a nice-to-have in §1.2 for the single-constant version — now that it's a small table, it belongs in `weights.yaml` even more clearly).
- **Documentation**: this is a substantive, designed piece of model behavior now, not just an implementation detail of the coverage constraint — it deserves the same treatment as every other constraint in this system per `AGENTS.md`'s own convention ("every constraint added to `constraints.py` MUST have a corresponding toggle"). Recommend giving it a real ID (e.g. a new `[S#...]` entry in `soft_constraints.md`, something like *"Unfilled positions, when unavoidable, should be concentrated on the least clinically-critical and least desirable shifts — protecting skill-required coverage first, then weekday/day shifts, leaving weekend-night General shifts as the first to go unfilled"*) and a corresponding toggle in `config.yaml`, even though mechanically it's implemented as a weighting on the existing `unfilled_var` rather than a new standalone constraint class. Update `AGENTS.md` §7 (fill order) to describe this tiering explicitly, and §9's weight-dominance check description to reference "the lowest unfilled tier" rather than a single number.
- **Testing**: extend the integration test from §1.13 (deliberately understaffed scenario) to assert the tiering actually works as intended — construct a scenario where total capacity is short by a known amount, and assert that the resulting `result.unfilled` set skews toward `General`/night/weekend positions rather than skill-required or weekday-day positions, and that skill-required positions remain fully covered whenever hard-constraint-feasible. This is the regression test that protects the actual feature you asked for, not just the mechanism.
- **Reporting**: no changes needed to §3's new "Roster by Shift" table or §4's hours-summary cards — both already surface `UNFILLED` wherever it occurs, and will now visibly show it concentrated in the expected places (weekend nights, general shifts) once this lands, which is a good manual sanity check that the tiering is behaving as intended on a real roster.

---

## Suggested execution order

1. **§1** (casual removal) end-to-end first — it's the largest, most mechanical change, and §2 falls out of it almost for free.
2. **§2** — verify (via the new integration test) rather than build; should need near-zero extra work once §1 is done.
3. **§5's `soft_penalty` template gap** — small, and you'll already be in `templates/roster.html` for §1's Messages-section cleanup, so do it in the same pass.
4. **§6** (desirability-weighted unfilled tiers) — do this right after §1/§2, before §3/§4, since it changes *which* positions end up unfilled, and you want the new reporting features (§3/§4) to be validated against final unfilled behavior rather than the old flat-weight behavior.
5. **§3** (new Roster by Shift table) — do it after §1/§2/§6 so `slot_id`, the coverage/unfilled plumbing, and the tiered unfilled weighting it will visibly display are all stable.
6. **§4** (Run Summary hours) — smallest of the four new features, can go last, and benefits from `slot_id`/unfilled/tiering work already being in place for a coherent story across the whole report.
7. The **§6.2 tier weight values** (the illustrative table) are the one item in this plan that's worth a quick sanity check with whoever reviews the first real roster output — they're a reasonable starting point, not a number to lock in without seeing it play out on actual data.
