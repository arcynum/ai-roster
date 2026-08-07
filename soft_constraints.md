# Preferences (Soft Constraints)
Everything in this file is a preference and should be followed if possible. The solver will treat these as optimization objectives.

## Staffing & Contracted Hours Optimization
- [S#d9a8b7c6] **Soft contracted-hours floor.** Reclassified from hard constraint H#d9a8b7c6. In real rostering, staff headcount is provisioned above minimum coverage, so the sum of all staff contracted-hours floors often exceeds total roster demand. Rather than making the model infeasible, this constraint minimizes the shortfall (adjusted contracted hours − actual assigned hours) fairly across all staff per block. Weight should sit below the unfilled penalty (200000) but above general fairness weights (50–500).
- [S#e9b4a1b3] If you need to exceed a staff members contracted hours to fill the roster due to a contracted hours shortfall, ensure these extra shifts are evenly distributed between all staff. All additional contracted hours needs to be fairly distributed to keep staff safe and healthy.

## Fairness & Distribution
- [S#d2a7f4a6] All staff need to have an equal distributed number of night shifts based on their contracted hours. This is applied on a per-block basis to ensure fairness across the entire roster period. There are more day shifts than night shifts, so the balance of nights and days will not be exactly the same - but the distribution should be fair.
- [S#a1d6c3d5] Saturday and Sunday hours have extra penalty loading pay. Saturday and Sunday hours should be shared amongst different staff to keep it fair.

## Scheduling Preferences
- [S#30c6f5ad] For each staff member, look at their maximal runs of consecutive days working the same shift type. Penalise by run length, using this constraint's `weights.yaml` value as the base unit (`W`). Each tier below has a sub-label (`S#30c6f5ad·L=n`) for use in code comments, log messages, and the HTML output's "Messages" section — these are traceability tags only, not separate constraint IDs; there is one weight (`W`) for the whole constraint, not one per tier.
  - **`S#30c6f5ad·L=2` — ideal.** No penalty. This is the preferred outcome whenever it doesn't conflict with a hard constraint.
  - **`S#30c6f5ad·L=1`** / **`S#30c6f5ad·L=3`** — mildly discouraged. Penalty = `0.1 × W`. Both a single isolated shift and a 3-in-a-row are allowed and only lightly penalised — neither is as good as a clean pair, but neither is a real problem.
  - **`S#30c6f5ad·L=4` — strongly discouraged.** Penalty = `1 × W` (10× the 1/3 tier), making it possible but unlikely.
  - **`S#30c6f5ad·L=5+` — escalating.** Penalty = `(run_length - 3) × W`, i.e. it keeps climbing by another full `W` for every additional day past 4 (run length 5 → `2 × W`, 6 → `3 × W`, etc.), so longer runs become progressively less likely rather than hitting a flat ceiling.

## Shift Category Grouping
- [S#6c1e9a4d] Swapping between night shifts (N8/N12) and day shifts (everything else, per the day/night split in `AGENTS.md` §5 — DISCO counts as day here too) is extremely fatiguing — repeatedly "flapping" back and forth between day and night sleep patterns is the specific problem this constraint exists to prevent, not the transitions themselves (those are already governed by the hard day-off requirement, [H#f4c9b6c8]). A whole fortnight of days followed by one clean block of nights is the ideal case; a single day-run plus a single night-run is just as good. Repeatedly alternating (day-run, night-run, day-run, night-run, day-run, night-run...) is exactly the pattern this constraint is meant to discourage.

  Mechanically: over a 14-day block, count each staff member's separate **runs** of day-category and night-category shifts — a run being a maximal stretch of consecutive worked days all in the same category. (Runs are always naturally separated by the mandatory day-off at every category transition, [H#f4c9b6c8] — this constraint is about *how many* such runs occur, not the transition itself.) There is no target below the cap: 1 day-run and 0 night-runs (all days), or 1 clean day-run plus 1 clean night-run, both have zero penalty. Only counts **exceeding 2** for either category are penalised: penalty = `(max(0, day_run_count − 2) + max(0, night_run_count − 2)) × W`, using this constraint's `weights.yaml` value as `W` — so the "flapping" example above (3 day-runs, 3 night-runs) would incur `(1 + 1) × W`. This is distinct from `S#30c6f5ad`: that constraint tracks runs of one exact shift type (e.g. D8 specifically); this one tracks runs of the broader day/night category regardless of which specific day-shift type is worked on any given day within the run.

## Unfilled Position Desirability
- [S#e7f3a2b1] **Unfilled positions, when unavoidable, should be concentrated on the least clinically-critical and least desirable shifts** — protecting skill-required coverage first, then weekday/day shifts, leaving weekend-night General shifts as the first to go unfilled. Since casual staff are now sourced entirely outside this system, `UNFILLED` is the expected, routine way this system reports a structural staffing gap. Rather than treating every unfilled position equally, the model uses a tiered penalty system where each tier corresponds to a position's "undesirability" (combining skill criticality and shift timing). Every tier's weight exceeds the worst-case combined soft-constraint penalty, preserving the safety guarantee that the solver never leaves a position unfilled just to save a soft-constraint penalty.

  The tier weights are defined in `weights.yaml` under this constraint ID, keyed by position characteristics:
  - **Tier 1 (skill-required)** — any position with a non-null `required_skill_level` (Coordinator/Triage/Resus). Weight: 220000. Clinical coverage is paramount.
  - **Tier 2 (General, weekday, day-shift)** — wildcard positions on weekday day-shifts (D8/D12/P8/P12/L3/DISCO). Weight: 200000.
  - **Tier 3 (General, weekday, night-shift)** — wildcard positions on weekday night-shifts (N8/N12). Weight: 170000.
  - **Tier 4 (General, weekend, day-shift)** — wildcard positions on weekend day-shifts. Weight: 160000.
  - **Tier 5 (General, weekend, night-shift)** — wildcard positions on weekend night-shifts. Weight: 140000. First to go unfilled.

  The solver uses the tier weight as the unfilled penalty for each position. Higher penalty = less likely to be left unfilled. This means the solver will preferentially leave weekend-night General shifts open when total capacity is short, while protecting skill-required positions and weekday day-shifts.

## Skill Level Matching
- [S#7b4e19fc] When multiple valid roster solutions exist, prefer solutions that minimise assigning staff to roster positions below their highest held skill level (e.g. avoid rostering a Triage-qualified nurse into a wildcard slot if an Acute-only nurse could fill it instead, all else equal). This is a low-priority tiebreaker — it must never override the fairness or overtime-distribution constraints above.


