# AI-Roster — Update Plan v2 (Desirability Correction, Unified Shift Table, Consecutive-Run Bug, Hours Breakdown)

**Method, as before:** re-read the current codebase against `AI-Roster-Update-Plan.md` (the last plan) and the two prior audits, then verified rather than assumed — ran the pipeline, parsed the shipped output HTML you left in place, and diffed `weights.yaml`'s keys against the actual runtime lookup code. That last check turned up the real root cause of item 3 below, so read that section first — it changes how you should prioritize the rest of this plan.

---

## 0. Re-audit — confirming last plan's work landed

Good news: **the entire previous plan (casual purge, unfilled-first coverage, the tiered unfilled mechanism, the soft-floor reclassification) is implemented.** `grep -ri casual` across the repo now only turns up the deliberate historical notes explaining *why* casual sourcing moved outside the system (`AGENTS.md`, `hard_constraints.md`'s `[H#e8f7d6c5]` history note, `soft_constraints.md`'s `[S#e7f3a2b1]` entry) — no leftover casual code, config, or tests. `tests/test_casual.py` is gone, replaced by `tests/test_integration.py` which specifically tests the unfilled-first workflow. Confirmed by running the pipeline: it completes and produces `result.unfilled` correctly.

One thing worth naming up front, because it explains a lot of what follows: **the shipped `output/roster_20260807_f1dd56.html` you pointed me at was generated with every soft-constraint weight silently collapsed to `1`** (see §3 — the run's own log file literally shows `weight=1` for every single soft constraint, including the ones meant to be weighted 20–1000). So the roster you're looking at doesn't reflect the tuning already recorded in `weights.yaml` at all. That's good news in one sense — the weight design from the last plan is probably fine, it just never actually ran.

---

## 1. Preference/desirability model — align with real EB12 penalty rates

Thanks for the actual award context — the model's current "desirability" ranking is backwards in an important way, and it's worth fixing at the source (the ranking logic) rather than just retuning numbers around a wrong mental model.

### 1.1 What the current code assumes vs. what you've told me is true

`solver.py`'s unfilled-tier logic (`_apply_coverage_constraint`) currently ranks desirability as: **weekday > weekend**, and treats weekend-night as the *least* desirable/first-to-go-unfilled category. Per the EB12 rates you provided, that's inverted — Sunday (200%) and Saturday (150%) are the two most desirable categories precisely because of the loading, and weekday night (120%, "not enough to offset dislike," your words) is the *least* desirable, not the most protected. Concretely, today:
```python
elif is_wknd and is_night:
    weight = tier_general_weekend_night   # 140000 — CURRENTLY the lowest, i.e. "first to go unfilled"
```
That's exactly the category that should be *protected*, not sacrificed.

### 1.2 Revised tier design

Two independent dimensions, same structure as before, reordered:

**Dimension 1 — skill criticality (unchanged, still dominates).** Skill-required positions (`Shift Coordinator`/`Triage`/`Resus`) stay the top-protected tier regardless of day — a clinical coverage gap is a different kind of problem than a preference-optimization one, and nothing in the new information changes that.

**Dimension 2 — desirability, now correctly ordered** (within the `General`/wildcard-skill pool only, same scoping principle as before):

| Tier (most → least protected) | Category | Basis |
|---|---|---|
| 1 | Skill-required, any day | Clinical coverage (unchanged) |
| 2 | Sunday, any shift | 200% — most desirable, protect it so staff get the opportunity |
| 3 | Saturday, any shift | 150% — desirable, protect it |
| 4 | Weekday day/afternoon (`D8`/`D12`/`P8`/`P12`/`L3`/`DISCO`) | 100–112.5% — neutral, no strong pull either way |
| 5 | Weekday night (`N8`/`N12`) | 120% loading isn't enough to offset the dislike — the least desirable shift, and per your instruction this (along with tier 4) is where gaps should land first |

This directly implements *"unskilled weekday shifts are the shifts the model should leave unfilled if necessary"* (tiers 4–5) while protecting weekend shifts (tiers 2–3) from ever being the ones sacrificed, and gives weekday night the extra push down (tier 5, below weekday day) since you specifically called it out as "the most hated shifts." Illustrative weight values — same "starting point, recalibrate after reviewing a real roster" caveat as last time, and this time you'll actually be able to see it work since §3 fixes the bug that was silently defeating tuning entirely:

| ID | Category | Suggested weight |
|---|---|---|
| `S#e7f3a2b1` | Skill-required | 220000 (unchanged) |
| *(new ID)* | Sunday, General | 210000 |
| *(new ID)* | Saturday, General | 200000 |
| *(new ID)* | Weekday day/afternoon, General | 160000 |
| *(new ID)* | Weekday night, General | 140000 |

**Implementation:** rewrite `_apply_coverage_constraint`'s tier-selection branch to check `is_sunday` / `is_saturday` (not a blended `is_weekend`) before `is_night`, in that priority order. The four sub-tier IDs need new names/IDs since their *meaning* is changing, not just their weight — reusing `S#d8f2c3a4`/`S#c9e1d4b5`/`S#b0d3e5c6`/`S#a1c4f6d7` for an inverted concept under the same ID would make the git history and `soft_constraints.md` (§6 below) confusing; mint four new IDs and retire the old ones with a note explaining the correction, same pattern already used for `[H#e8f7d6c5]`'s history note.

### 1.3 Fix the fairness constraints to match the same mental model

Two concrete bugs/gaps found while checking this, both worth fixing alongside the tier reorder since they're the same underlying confusion:

**`NightShiftFairness` (`[S#d2a7f4a6]`) currently includes weekend nights in its "night hours" total** — it filters purely on `pos["shift"] in NIGHT_SHIFTS`, with no exclusion for Saturday/Sunday. Per the EB12 rules you sent, weekend penalties *replace* the night loading entirely ("weekend penalties do not stack with... night loadings") — a Saturday night shift is a *weekend* shift for pay/desirability purposes, not a *night* shift. Right now a weekend `N12` gets counted into **both** `NightShiftFairness` and `WeekendFairness` simultaneously, which muddies both signals and doesn't match the "weekday night is its own hated category" framing you've now given. **Fix:** add `and not is_weekend(date)` to `NightShiftFairness`'s position filter, so it only tracks Monday–Friday night hours — the true "most hated shift" pool that needs fair distribution.

**`WeekendFairness` (`[S#a1d6c3d5]`) currently blends Saturday and Sunday into one pooled "weekend hours" figure.** Given you've drawn an explicit distinction between them (200% vs. 150%, "most desirable" vs. "desirable... not as much"), a person could hit their "fair share" of weekend hours entirely via Saturdays and never get a Sunday shift (or vice versa), which doesn't actually deliver equitable access to the *specific* thing that's most valuable. **Recommend splitting into two separate fairness pools** — `SundayFairness` and `SaturdayFairness` — mirroring the existing deviation-from-mean pattern. This is a judgment call on how much precision you want here versus the added model complexity (two more IntVars/deviation terms per staff per block); flagging it as a recommendation rather than assuming you want the extra granularity — let me know if you'd rather keep it blended.

### 1.4 One classification question worth confirming, not silently resolving

`DISCO` (17:30–02:00) doesn't cleanly fit the EB12 categories as given: it starts before 6pm (17:30), so it misses the standard night-shift threshold, but it satisfies the *"Nurse Grades 3–7"* exception (starts ≥5pm **and** continues beyond midnight) — meaning some staff working DISCO may actually attract night-equivalent loading (120%) under the award, while others might not depending on grade. Separately, `AGENTS.md` already has an established, deliberate rule that DISCO is bucketed as a **day** shift for fairness/night% *reporting* purposes (unrelated to pay — this system doesn't model dollar amounts at all, only relative desirability). For the new desirability tiering, I'd recommend keeping DISCO in the "weekday day/afternoon" tier (4) rather than the "weekday night" tier (5), since it's not clearly a night shift under the general rule and the existing reporting convention already treats it as day-bucket — but this is worth a quick confirm given the grade-dependent nuance in the rule you sent, since the system doesn't currently track staff grade for this purpose at all.

---

## 2. Single unified "Roster by Shift" table (not one table per shift type)

Confirmed the current implementation builds one separate `<table>` per shift type (`output.py`'s `shift_slot_tables` grouped by `shift_type`, one full sub-table each in the template). That's not what you asked for last time and isn't what you want now — it should be **one table**, 15 rows total across every shift type combined, one header row.

I checked this against your actual `roster.yaml`, and the numbers work out exactly: the busiest days (Monday, Saturday, Sunday) each have exactly **15 distinct position slots** — `D8` (1), `D12` (4: Coordinator/Triage/Resus/General), `P8` (1), `P12` (1), `L3` (2), `DISCO` (1), `N8` (1), `N12` (4: Coordinator/Triage/Resus/General) = 15. That's not a coincidence you need to engineer around — the 15-row cap fits the data precisely as-is. On Tuesday–Friday, `L3` only has 1 position instead of 2 (confirmed directly in `roster.yaml`), which matches exactly what you described — the second `L3` slot only exists Saturday/Sunday/Monday and should render empty/greyed on the other five days.

### 2.1 Fix

- **`output.py`**: replace the per-shift-type grouping with a single flat structure — one ordered list of (at most) 15 `slot_id`s spanning every shift type (e.g. `D8-General-1`, `D12-Coordinator-1`, `D12-Triage-1`, `D12-Resus-1`, `D12-General-1`, `P8-General-1`, `P12-General-1`, `L3-General-1`, `L3-General-2`, `DISCO-General-1`, `N8-General-1`, `N12-Coordinator-1`, `N12-Triage-1`, `N12-Resus-1`, `N12-General-1`), each mapped to `{date_str: staff_name | "UNFILLED" | None}`. `None` (or a dedicated marker) for dates where that slot doesn't exist in `roster_positions` that day — e.g. `L3-General-2` on any Tuesday–Friday — rendered as an empty/greyed cell, not blank ambiguity between "off" and "doesn't apply."
- **`templates/roster.html`**: replace the `{% for shift_type, slots in shift_slot_tables.items() %}` loop (which currently produces N separate tables) with a single table over the flat 15-row list. Keep the existing `matrix-table`/weekend-column styling for consistency, and reuse the `.cell-unfilled` highlight already added for the previous "Roster by Shift" work.
- If a future roster configuration ever needs more than 15 total distinct daily slots, keep the existing "log a warning and truncate" safeguard rather than silently growing the table — but no action needed for the current data, since it fits exactly.

---

## 3. Root cause of the 5–9 day identical-shift runs — this is a real bug, not a tuning problem

I parsed `output/roster_20260807_f1dd56.html` directly rather than eyeballing it: **Irina Ovsyankina was rostered `DISCO` for 9 consecutive days, then `N12` for 5 consecutive days**, in the roster you left in place. That's a dramatic, concrete confirmation of what you're describing. I traced it to a specific, high-confidence root cause — not a matter of retuning weights.

### 3.1 The bug

`output/roster_20260807_f1dd56.log` (the log file from that exact run) shows this, for **every single soft constraint**:
```
Applying soft constraint [S#d9a8b7c6] (weight=1)
Applying soft constraint [S#e9b4a1b3] (weight=1)
Applying soft constraint [S#d2a7f4a6] (weight=1)
Applying soft constraint [S#a1d6c3d5] (weight=1)
Applying soft constraint [S#30c6f5ad] (weight=1)
Applying soft constraint [S#6c1e9a4d] (weight=1)
Applying soft constraint [S#7b4e19fc] (weight=1)
```
Every one of those is supposed to carry a different weight per `weights.yaml` (1000, 20, 50, 50, **500**, 300, 5 respectively) — `[S#30c6f5ad]` is `ConsecutiveShiftDiscouraged`, the exact constraint meant to prevent long same-shift-type runs, and its intended weight of 500 (deliberately set *above* the fairness constraints' 50, per `weights.yaml`'s own comment) is being silently replaced with `1` — the same flat value as everything else. That completely destroys the intended relative priority scheme; the constraint is still technically "applied" (it still contributes *something* to the objective), but at a magnitude with no meaningful precedence over anything else, so the solver has essentially no incentive to avoid a 9-day run if doing so helps it save even a small amount elsewhere.

**Why:** `solver.py`'s `_apply_soft_constraints()` does `weight = self.weights.get(cid, 1)`, where `cid = constraint_cls.constraint_id`. Every `constraint_id` in `constraints.py` is written **with square brackets**, e.g. `constraint_id = "[S#30c6f5ad]"`. But `weights.yaml`'s keys are written **without brackets**: `"S#30c6f5ad": 500`. The dictionary lookup `self.weights.get("[S#30c6f5ad]", 1)` can never match a key stored as `"S#30c6f5ad"` — it silently falls through to the default of `1`, every time, for every constraint, with no error or warning. Confirmed by reading `load_weights()` in `utils.py` — it does no key normalization at all, just returns the raw parsed YAML dict as-is.

Note this affects only `weights.yaml` — `config.yaml` uses bracketed IDs consistently (`"[H#4d9f81c2]"` etc.) and its enable/disable toggling isn't affected; this is purely a `weights.yaml` lookup mismatch.

### 3.2 The fix, and why it needs a permanent safeguard, not just a one-line patch

**Fix the mismatch** — simplest, least invasive option: change every key in `weights.yaml` to include the brackets, matching the convention already used everywhere else in the codebase (`config.yaml`, `constraint_id` class attributes, the `.md` files). Don't fix it the other way (stripping brackets in `solver.py`) — brackets are already the established convention for referencing an ID everywhere else in this codebase, `weights.yaml` is the outlier.

**Add a startup validation** so this can never silently regress again: when `RosterModel` builds (or in `load_weights()` itself), assert that every `constraint_id` in `HARD_CONSTRAINTS`/`SOFT_CONSTRAINTS`, plus the five unfilled-tier IDs, has a corresponding entry in the loaded weights dict — and **raise**, not warn, if any are missing. This bug produced zero errors and zero warnings for what was probably the single highest-impact miscalibration in the whole model; it should be structurally impossible to reintroduce.

### 3.3 Why the existing test suite didn't catch this

`tests/test_integration.py::test_weight_dominance_with_actual_weights_file` already exists and is supposed to guard exactly this kind of thing — but it loads `weights.yaml` directly with `yaml.safe_load()` and indexes it with hand-typed unbracketed strings (`actual_weights["S#a1c4f6d7"]`), which means it validates that the **file's own contents** are internally consistent, without ever exercising the actual runtime lookup path (`RosterModel._apply_soft_constraints`'s `self.weights.get(cid, 1)`, where `cid` comes from the real `constraint_id` class attributes). The test and the bug made the *same* unbracketed-key assumption independently, so the test could pass while the real code silently used the wrong value. **Fix the test to go through the real path**: instantiate the actual constraint classes (or at least iterate `get_soft_constraint_ids()`/the unfilled tier IDs as defined in code) and look each one up in the loaded weights dict using exactly the string the runtime code would use — that would have caught this immediately, and prevents the same category of "test duplicates the assumption instead of exercising the code" bug from recurring elsewhere.

### 3.4 After the fix — re-tune with real data, and note the interaction with run-*count* vs. run-*length*

Once weights actually flow through correctly, regenerate a roster and re-check for long runs. Two things worth knowing going in:
- `DayNightRunCountPenalty` (`[S#6c1e9a4d]`) — the *other* run-related constraint — only penalizes the **number** of separate day/night-category runs exceeding 2 per block; it does **not** penalize a single very long run at all (one 9-day run is just "1 run," well under its threshold). So `ConsecutiveShiftDiscouraged`'s run-*length* tiering was always the only thing standing between the model and exactly this failure mode — worth knowing so nobody's surprised that fixing the weight bug is the actual fix, not an additional constraint.
- Since every weight in this system was actually running at a flattened `1` for at least this shipped example, **treat all the "recalibrate once you've reviewed a real roster" caveats already scattered through `weights.yaml`/`AGENTS.md` as now genuinely un-tested** — the relative magnitudes were designed thoughtfully but have never actually been observed doing their job. Budget time to review a freshly-generated roster against the intended priority ordering once §3.2's fix lands, not just assume the existing numbers are correct because they look reasonable on paper.

---

## 4. Hours summary — split "available" into strict-contracted vs. with-overtime

Checked `output.py`'s current `hours_summary` — it already computes `total_available_hours` using `compute_adjusted_hours()`, which is genuinely the **contracted-only, no-overtime** figure (good, that part's already correct) — it's just not labeled that way, and there's no second figure showing what's achievable once the 12h overtime allowance is factored in. That's exactly the ambiguity you're describing: right now there's no way to tell, from the summary alone, whether a small `unfilled` count reflects genuinely adequate staffing or is being propped up by everyone being pushed toward their overtime ceiling.

### 4.1 Add the second figure

Compute, alongside the existing contracted-only total, a **with-overtime** total per block: `sum(min(76, raw_contracted_hours_per_fortnight + 12))` across staff — i.e. exactly what `[H#e8f7d6c5]`'s cap actually allows, per person, summed. Note this is a theoretical ceiling that doesn't discount for holiday days the way the contracted-only figure does (per `[H#e8f7d6c5]`'s own already-documented behavior — the overtime cap uses the *raw*, unadjusted contracted figure, not the holiday-prorated one) — worth a small caveat/tooltip on the card itself ("ceiling; may not be fully achievable if the person is also on leave this block") rather than building a more elaborate proration heuristic that doesn't correspond to any real constraint in the model.

### 4.2 Report both figures, per block and combined, each with their own surplus/shortfall

Extend `hours_summary_blocks` (and the combined totals) with a second parallel set of fields — `available_no_overtime` (rename the existing `available`), `available_with_overtime`, and **two** surplus figures (`surplus_no_overtime`, `surplus_with_overtime`), each with its own traffic-light styling. In `templates/roster.html`'s Run Summary card grid, show both clearly labeled, e.g.:

- **Hours Required**
- **Available (contracted only)** → **Surplus/Shortfall (no overtime)**
- **Available (with overtime allowed)** → **Surplus/Shortfall (with overtime)**

This gives exactly the signal you asked for: if the no-overtime surplus is deeply negative but the with-overtime surplus is close to zero, that's an immediate, legible "the low unfilled count is coming from overtime, not genuine headroom" signal, without anyone having to dig through individual staff rows to piece it together.

---

## 5. Reconcile every constraint ID across code, config, weights, and the markdown files

Did a full cross-reference of `[H#...]`/`[S#...]` IDs across `constraints.py`'s registries, `weights.yaml`, `config.yaml`, and both `.md` files. Two concrete gaps:

### 5.1 The four unfilled desirability sub-tier IDs have no entry in `soft_constraints.md`

`S#d8f2c3a4`, `S#c9e1d4b5`, `S#b0d3e5c6`, `S#a1c4f6d7` exist in `weights.yaml` and are referenced in `solver.py` and briefly in `AGENTS.md`, but **`soft_constraints.md` only documents the parent `[S#e7f3a2b1]`** — the four sub-tiers themselves are undocumented in the one file that's supposed to be the readable source of truth for what each ID means. Since §1.2 above is already replacing these four with newly-meaning IDs, **write proper entries for the new set while you're in there** — each sub-tier gets its own bullet in `soft_constraints.md`, clearly stating the category it covers and its place in the ordering, not just a weights.yaml code comment.

### 5.2 `hard_constraints.md` documents more IDs than `constraints.py` implements as standalone classes

`hard_constraints.md` contains 19 distinct `[H#...]` IDs; `HARD_CONSTRAINTS` in `constraints.py` only has 11 classes. Some of the extra IDs are legitimately **implemented indirectly** rather than as their own CP-SAT constraint class (e.g. holiday-hours proration logic that's folded into `compute_adjusted_hours()` rather than being a standalone constraint) — that's a fine design choice, but right now nothing in the document distinguishes "documented and implemented as its own class" from "documented and implemented, just folded into another constraint's code" from "documented but not actually implemented anywhere." **Do a full pass**: for every ID in both `.md` files, confirm it's either (a) a registered class in `HARD_CONSTRAINTS`/`SOFT_CONSTRAINTS`, (b) explicitly annotated as "implemented as part of `<ConstraintClass>`'s logic, not a standalone constraint" with a pointer to where, or (c) removed if it's genuinely obsolete/superseded. Same exercise for `soft_constraints.md` against `SOFT_CONSTRAINTS` (this side is already clean — 8 documented IDs against 7 classes + `[S#e7f3a2b1]`'s solver-level implementation, already correctly annotated — use that entry as the template for how to annotate the hard-constraint gaps).

### 5.3 Add an automated sync check

This is the same category of "silent drift" problem as §3's weight bug — add a test that parses both `.md` files for every `[H#...]`/`[S#...]` token and asserts each one is either a registered `constraint_id` or appears in an explicit allow-list of "implemented elsewhere" IDs (maintained alongside the constraint registries) — so a future ID typo or an implemented-but-undocumented constraint gets caught by CI instead of a manual grep during a review like this one.

### 5.4 Wording pass

Once the IDs are reconciled, do a read-through of both files for clarity/concision against actual intent — a few worth specifically checking while you're there: `[S#e7f3a2b1]`'s entry needs updating regardless (its current text describes the *old*, incorrect weekend-first ordering — see §1.2); anywhere phrasing still contrasts "named staff" against a casual alternative that no longer exists (leftover from before the casual purge, worth a final grep now that this file's getting touched anyway); and the `[H#e8f7d6c5]` history note, which is accurate but dense — could be tightened now that the casual-removal context is settled rather than being a live decision.

---

## 6. Other issues found in this pass

- **`hard_constraints.md`'s parsed-vs-applied count is confusing in the log**, and now has a documented reason (§5.2): `"Parsed 20 hard constraints from hard_constraints.md"` followed later by `"Hard constraints: 11 applied, 0 skipped"` reads like 9 constraints silently failed to load, when really most of that gap is IDs that were never meant to be standalone applied constraints in the first place. Once §5.2's reconciliation is done, consider having the startup log distinguish "N documented" from "M implemented as constraints" so this doesn't read as an error to whoever's watching the log next time (worth doing alongside the §3.2 loud-validation work, since both are about making the startup log trustworthy rather than something you have to manually cross-check).
- **`AGENTS.md`'s §7 fill-order description and §9 weight-dominance section both reference the old (incorrect) tier ordering** (*"weekend-night General shifts go unfilled before weekday-day"*) — needs rewriting to match §1.2's corrected ordering once that's implemented, including updating the specific ID/weight cited in §9's worked example (currently points at `S#a1c4f6d7`/140000 as "the lowest tier," which will be a different ID and category after this change).
- **`README.md`**: quick pass once the above lands — confirm nothing there still describes the single-flat-unfilled-weight model or the per-shift-type Roster-by-Shift tables from before this plan.
- **Consider whether `NightShiftFairness` needs renaming** once §1.3 scopes it to weekdays-only — `NightShiftFairness` as a name no longer quite captures "weekday night fairness" now that weekend nights are deliberately excluded and tracked elsewhere; not required, but worth a thought since the class/ID's docstring will need updating regardless and a clearer name avoids future confusion about scope.

---

## Suggested execution order

1. **§3.2** (weights.yaml bracket fix + startup validation) first, on its own — it's a two-line code fix plus a validation guard, it's the actual root cause of the visible roster-quality problem, and every other tuning decision in this plan is only meaningful once weights genuinely flow through.
2. **§1** (desirability reorder + fairness scoping fixes) next — these depend on §3.2 being fixed to actually be observable/testable in a real solve.
3. **§5** (doc/ID reconciliation) alongside §1, since §1.2 is already minting new IDs and retiring old ones — do the full reconciliation pass in the same sitting rather than touching `soft_constraints.md`/`hard_constraints.md` twice.
4. **§2** (single unified shift table) — independent of the above, can be done in parallel or any time after.
5. **§4** (hours summary split) — independent, smallest scope, can go last.
6. **Regenerate a roster and manually review it** (§3.4) after §3.2 + §1 land — this is the first time the intended weight design will have actually run, so it's worth a real look rather than assuming the numbers are right because they were thoughtfully chosen on paper.
7. **§1.4** (DISCO classification) and **§1.3's Sat/Sun fairness split** are the two items in this plan worth a quick confirm with you specifically before implementation, same as the overtime-cap decision last time — flagging rather than silently picking.
