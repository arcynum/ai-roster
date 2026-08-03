# Roster YAML Structure Documentation

This document explains the structure and usage of the `roster.yaml` file, which serves as the new source of truth for roster requirements.

## Overview

The `roster.yaml` file is the current format for defining shift requirements for each day of the week.

## File Structure

```yaml
# Roster Requirements - New Source of Truth
dates:
  start: 2026-08-03
  end: 2026-08-30

shift_requirements:
  Monday:
    - shift: D8
      required_skills: ["*"]
    - shift: D12
      required_skills: ["Shift Coordinator"]
    - shift: D12
      required_skills: ["Triage"]
    - shift: D12
      required_skills: ["Resus"]
    - shift: D12
      required_skills: ["*"]
    # ... other shifts
  Tuesday:
    # ... similar structure
  # ... other days
```

## Key Features

### 1. Shift Requirements
Each shift in the roster is defined with:
- `shift`: The shift name (e.g., "D8", "D12", "N12", etc.)
- `required_skills`: A list of required skill tags for that specific shift instance

### 2. Skill Tag System
- Each shift instance requires exactly **one** specific skill tag
- `"*"` means any skill can fill that shift
- Other values represent specific training levels required (e.g., "Shift Coordinator", "Triage", "Resus")
- The skill tag mapping will connect these requirements to staff training levels

### 3. Multiple Shifts Per Day
- Some days have multiple instances of the same shift type:
  - **Saturday and Sunday**: 2 L3 shifts each
  - **All days**: 4 D12 shifts and 4 N12 shifts
- Each of these shifts has its own specific skill requirement

### 4. Date Range
- The `dates` section defines the full roster period
- `start` and `end` are ISO date format (YYYY-MM-DD)

## Shift Instance Details

### Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
Each day contains the following shift instances:

- **D8**: 1 shift (any skill acceptable)
- **D12**: 4 shifts with different skill requirements:
  - Shift 1: "Shift Coordinator"
  - Shift 2: "Triage" 
  - Shift 3: "Resus"
  - Shift 4: "*"
- **P8**: 1 shift (any skill acceptable)
- **P12**: 1 shift (any skill acceptable)
- **L3**: 2 shifts (any skill acceptable) - only on Saturday and Sunday
- **DISCO**: 1 shift (any skill acceptable)
- **N8**: 1 shift (any skill acceptable)
- **N12**: 4 shifts with different skill requirements:
  - Shift 1: "Shift Coordinator"
  - Shift 2: "Triage"
  - Shift 3: "Resus"
  - Shift 4: "*"

## Usage in Code

The `build_roster.py` script:
1. Reads `roster.yaml` as the source of truth
2. Parses the YAML structure into `ShiftRequirement` objects with `required_skills` field
3. Uses these requirements in the constraint satisfaction solver

## Maintenance Notes

When modifying this file:
1. Each shift instance must have exactly one skill requirement
2. The skill tags should correspond to training levels defined in `training.md`
3. The number of shifts per day should match the existing requirements
4. All days must be included for complete roster coverage

This structure ensures that the roster requirements are explicit, maintainable, and clearly map to staff training requirements.