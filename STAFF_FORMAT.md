# Staff Data Format

This document explains the format and structure of staff data used by the AI-Roster system.

## Overview

The staff data defines all personnel who can be assigned to shifts, including their training levels, FTE hours, and availability constraints.

## File Format

The system uses only one format for staff data:

1. **New Format**: `staff.yaml` (recommended)

## Staff YAML Format

The `staff.yaml` file defines staff information in a structured format:

```yaml
- name: "Amanda Bartley"
  classification: "CN"
  training_levels:
    - Acute
    - Resus
    - Triage
    - Shift Coordinator
  fte_hours: 56
  red_requests: 
    - "2026-08-01"
    - "2026-08-04"
  holidays:
    - start: "2026-08-01"
      end: "2026-08-31"
    - start: "2026-10-01"
      end: "2026-10-30"

- name: "Jennifer Brodie"
  classification: "CN"
  training_levels:
    - Acute
    - Resus
    - Triage
    - Shift Coordinator
  fte_hours: 48
  red_requests: 
    - "2026-08-01"
    - "2026-08-04"
  holidays: []
```

### Structure Details

Each staff member is defined with the following fields:

- `name`: The full name of the staff member
- `classification`: The staff classification (CN = Clinical Nurse, RN = Registered Nurse, Graduate)
- `training_levels`: A list of training levels the staff member has achieved, formatted exactly like `red_requests` with each level on a separate line prefixed with a hyphen
- `fte_hours`: The full-time equivalent hours per fortnight (this is a minimum, not a ceiling)
- `red_requests`: A list of dates when the staff member cannot be scheduled (hard constraint)
- `holidays`: A list of date ranges when the staff member is unavailable (can be single dates or date ranges)

### Training Levels

The `training_levels` field contains a list of training levels, ordered from lowest to highest:
- Graduate
- Acute
- Resus
- Triage
- Shift Coordinator

This hierarchy allows higher-trained staff to fill roles requiring lower training levels, but not vice versa.

### Date Formats

- Date strings use the format `YYYY-MM-DD`
- Holiday ranges are specified with `start` and `end` fields
- Single dates in holidays are treated as ranges with same start and end dates

### Hard Constraints

- **Red Requests**: Staff members cannot be scheduled on dates listed in their red requests
- **Holidays/Sickness**: Staff members cannot be scheduled during their holiday periods

These are hard constraints that the roster solver will enforce.