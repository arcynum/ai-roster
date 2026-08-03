# Preferences (Soft Constraints)
Everything in this file is a preference and should be followed if possible. The solver will treat these as optimization objectives.

## Staffing & Contracted Hours Optimization
- [S#e9b4a1b3] If you need to exceed a staff members contracted hours to fill the roster due to a contracted hours shortfall, ensure these extra shifts are evenly distributed between all staff. All additional contracted hours needs to be fairly distributed to keep staff safe and healthy.

## Fairness & Distribution
- [S#d2a7f4a6] All staff need to have an equal distributed number of night shifts based on their contracted hours. This is applied on a per-block basis to ensure fairness across the entire roster period. There are more day shifts than night shifts, so the balance of nights and days will not be exactly the same - but the distribution should be fair.
- [S#a1d6c3d5] Saturday and Sunday hours have extra penalty loading pay. Saturday and Sunday hours should be shared amongst different staff to keep it fair.

## Scheduling Preferences
- [S#30c6f5ad] Working the same shift type for 3 or more consecutive days is discouraged. There is no preference between 1 and 2 consecutive days of the same shift — only the 3+ case should be penalised.

## Skill Level Matching
- [S#7b4e19fc] When multiple valid roster solutions exist, prefer solutions that minimise assigning staff to roster positions below their highest held skill level (e.g. avoid rostering a Triage-qualified nurse into a wildcard slot if an Acute-only nurse could fill it instead, all else equal). This is a low-priority tiebreaker — it must never override the fairness or overtime-distribution constraints above.
