# Roster by Shift Table

## Overview

Add a new table to the HTML roster output that shows shifts down the Y-axis and staff names in cells, transposed from the existing "Roster by Date" view.

## Structure

15 fixed rows matching the roster's shift positions (Monday's 15 as the template), columns = dates:

```
        03 Aug  04 Aug  05 Aug  ...
D8       Alice   Bob     Alice
D12 #1   ...     ...     ...
D12 #2
D12 #3
D12 #4
P8
P12
L3 #1
L3 #2
DISCO
N8
N12 #1
N12 #2
N12 #3
N12 #4
```

Row labels: `D8`, `D12`, `P8`, `P12`, `L3`, `DISCO`, `N8`, `N12`. Duplicate shift types (D12, L3, N12) get ordinal suffixes: `D12 #1`, `D12 #2`, etc.

Identical shifts on the same day (both L3 #1 and L3 #2 on Monday) share the same staff names since the solver treats them as interchangeable null-skill slots.

On days with fewer shifts than the 15-row template (e.g. Tuesday has 1 L3, not 2), the extra row's cell is empty.

Unfilled positions show red `UNFILLED` text.

Casual-filled shifts show `Casual` in the cell.

## Changes

### 1. `main.py:119-121` — Pass `positions` to `generate_html()`

Pass the `positions` list as an additional parameter so `_build_context()` can derive row labels.

### 2. `output.py` — Two changes

**`generate_html()` signature**: add `positions` parameter, pass to `_build_context()`.

**`_build_context()`**: build two new context values:
- `shift_rows`: list of row labels from the first week's positions (deduplicated by shift type, preserving order)
- `shift_matrix`: `{row_label: {date_str: [staff_names]}}` built by iterating `result.assignments` and grouping by `(shift, date)`

### 3. `templates/roster.html` — New section

Add `<h2>Roster by Shift</h2>` section between "Roster by Date" and "Roster by Staff". Uses same `.matrix-table` CSS. Cells render comma-separated staff names; empty cells for missing shifts; `UNFILLED` in red.

### 4. `tests/test_output.py` — Tests

- `test_shift_rows_count` — 15 rows for the period
- `test_shift_rows_labels` — correct labels ("D8", "D12", "L3", etc.)
- `test_shift_matrix_has_key` — `shift_matrix` present in context
- `test_shift_matrix_multi_staff_cell` — 2 L3 shifts shows 2 names
- `test_shift_matrix_casual_included` — casual appears in cell
- `test_shift_matrix_empty_for_missing_shift` — Tuesday L3 #2 is empty
