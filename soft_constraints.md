# Preferences (Soft Constraints)
Everything in this file is a preference and should be followed if possible. The solver will treat these as optimization objectives.

## Staffing & Contracted Hours Optimization
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

## Skill Level Matching
- [S#7b4e19fc] When multiple valid roster solutions exist, prefer solutions that minimise assigning staff to roster positions below their highest held skill level (e.g. avoid rostering a Triage-qualified nurse into a wildcard slot if an Acute-only nurse could fill it instead, all else equal). This is a low-priority tiebreaker — it must never override the fairness or overtime-distribution constraints above. (Reclassified from `H#f3c72a8d`, which was mislabeled as a hard constraint.)
