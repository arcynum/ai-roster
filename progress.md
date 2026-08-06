# Progress — Audit Fixes

## Completed

- [x] **1.1** `generate_html()` extra `positions` arg in `main.py` — dropped duplicate arg
- [x] **1.2** `load_config()` treats `enabled: null`/empty as "all enabled" for that kind; warns when 0 hard constraints enabled
- [x] **1.3** Coverage contradiction resolved — unfilled slack vars added, coverage constraint rewritten to include casual+unfilled options
- [x] **1.4** `H#d9a8b7c6` reclassified from hard to soft (ContractedHoursFloorSoft) — minimizes shortfall fairly; `SolveResult` tracks shortfall per staff/block
- [x] **2.1** `OvertimeDistribution` now uses deviation-from-mean formulation (like `WeekendFairness`) instead of minimizing total
- [x] **2.2** `NightShiftFairness` rebuilt per-block; IntVar bounds fixed
- [x] **2.3** `DayNightRunCountPenalty` rebuilt per-block
- [x] **3.1** DISCO night hours in HTML — replaced `crosses_midnight` with `NIGHT_SHIFTS` lookup
- [x] **3.2** Messages section — `SolveResult` tracks soft-constraint penalties and casual usage; `_build_context` passes them through
- [x] **3.3** Unused `hard_constraints`/`soft_constraints` loads in `main.py` — wired into output context
- [x] **5.x** `compute_adjusted_hours` holiday double-counting — uses `set()` for deduplication
- [x] **5.x** Red request/holiday date cross-validation against roster period (warns when dates fall outside)
- [x] **5.x** Unknown ID hardening — raises `ValueError` instead of warning
- [x] **5.x** Duplicated shift-type constants — removed dead `SHIFT_ORDER` from `output.py`; `test_output.py` imports `SHIFT_ORDER` from `utils`
- [x] **5.x** `SHIFT_TYPES` class attributes added to `NoDoubleBooking`, `RestPeriodConstraint`, `NightToDayRest` (fixed 30 test failures)
- [x] **4.1–4.3** Redundant compatibility tables — extracted shared `_emit_compatibility_constraints()` utility; three `apply()` methods now use it
- [x] Constraint docs updated — `H#d9a8b7c6` moved to soft_constraints.md with reclassification note; config.yaml commented-out entries updated
- [x] `weights.yaml` updated — added soft floor weight (1000)
- [x] Run tests and verify all fixes work — 145/145 pass

## Pending

*(None — all audit items addressed)*
