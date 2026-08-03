# Staff Data Format

This document explains the format and structure of staff data used by the AI-Roster system.

## Overview

The staff data defines all personnel who can be assigned to shifts, including their training levels, contracted hours, and availability constraints.

## File Format

The system uses only one format for staff data:

1. **New Format**: `staff.yaml` (recommended)

## Staff YAML Format

The `staff.yaml` file defines staff information in a structured format:

```yaml
- name: "Amanda Bartley"
  classification: "CN"
  skill_tags:
    - Acute
    - Resus
    - Triage
    - Shift Coordinator
  contracted_hours_per_fortnight: 56
  red_requests: 
    - "2026-08-01"
    - "2026-08-04"
  holidays:
    - start: "2026-08-01"
      end: "2026-08-31"
    - start: "2026-10-01"
      end: "2026-10-30"
```

### Structure Details

Each staff member is defined with the following fields:

- `name`: The full name of the staff member
- `classification`: The staff classification (CN = Clinical Nurse, RN = Registered Nurse, Graduate)
- `skill_tags`: A list of skill tags the staff member has achieved.
- `contracted_hours_per_fortnight`: The contracted hours per fortnight (this is a minimum, not a ceiling)
- `red_requests`: A list of dates when the staff member cannot be scheduled (hard constraint)
- `holidays`: A list of date ranges when the staff member is unavailable (can be single dates or date ranges)

### Skill Tags

The `skill_tags` field contains a list of training levels, ordered from lowest to highest:
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
- **Holidays**: Staff members cannot be scheduled during their holiday periods

These are hard constraints that the roster solver will enforce.
