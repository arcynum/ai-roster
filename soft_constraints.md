# Preferences (Soft Constraints)
Everything in this file is a preference and should be followed if possible. The solver will treat these as optimization objectives.

## Staffing & FTE Optimization
- [S#a9d4c1d3] Staff can be scheduled in for more than their FTE hours, but never less.
- [S#e9b4a1b3] If you need to exceed a staff members FTE hours to fill the roster due to a FTE shortfall, ensure these extra shifts are evenly distributed between all staff. All additional FTE needs to be fairly distributed to keep staff safe and healthy.

## Fairness & Distribution
- [S#d2a7f4a6] All staff need to have an equal distributed number of night shifts based on their FTE. This is applied on a per-block basis to ensure fairness across the entire roster period. There are more day shifts than night shifts, so the balance of nights and days will not be exactly the same - but the distribution should be fair.
- [S#a1d6c3d5] Saturday and Sunday hours have extra penalty loading pay. Saturday and Sunday hours should be shared amongst different staff to keep it fair.

## Scheduling Preferences
- [S#f5e6d7c8] For each shift, the same person should be scheduled on the same shift the next day.
- [S#30c6f5ad] Staff should ideally work the same shift type for two consecutive days (to avoid gaps), but working three or more consecutive days of the same shift is discouraged.
