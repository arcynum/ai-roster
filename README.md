# AI-Roster System Documentation

## Overview

This project builds a monthly roster for the pediatric emergency ward at TPCH. The system uses constraint satisfaction to generate rosters that meet all hard constraints while optimizing soft constraints.

## Core Components

### Data Files

1. **`roster.yaml`** - New source of truth for roster requirements (replaces `roster.md`)
2. **`definitions.md`** - Shift definitions including start time, end time, duration, and midnight crossing
3. **`staff.md`** - Staff information including training levels, FTE hours, red requests, and holidays
4. **`hard_constraints.md`** - Non-negotiable rules that must be followed
5. **`soft_constraints.md`** - Preferences that should be followed when possible
6. **`training.md`** - Training levels available for staff

### Output Files

1. **`result.staff.md`** - Roster grouped by staff member
2. **`result.roster.md`** - Roster grouped by date
3. **`result.violations.md`** - Rule violations found in generated roster

## Roster YAML Structure

The `roster.yaml` file defines shift requirements with explicit skill tags:

```yaml
dates:
  start: 2026-08-03
  end: 2026-08-30

shift_requirements:
  Monday:
    - shift: D8
      required_skills: ["*"]
    - shift: D12
      required_skills: ["Shift Coordinator"]
    # ... other shifts
```

### Key Points

- Each shift instance requires exactly **one** specific skill tag
- `"*"` means any staff member can fill that shift
- Specific skill tags require staff with that exact training level
- The number of shift instances per day is fixed and documented

## Shift Instance Requirements

Each shift instance in the roster requires exactly one skill tag. This is critical for proper staffing based on training levels.

### Skill Tag Types
1. **Wildcard ("*")** - Any staff member can fill this shift
2. **Specific Training Levels** - Only staff with specific training can fill:
   - "Shift Coordinator"
   - "Triage" 
   - "Resus"
   - "Acute"

### Shift Instance Counts
- All days: 1 D8, 4 D12, 1 P8, 1 P12, 1 DISCO, 1 N8, 4 N12
- Saturday and Sunday: 2 L3 shifts each (instead of 1)

## Core Architecture

### Build Process

1. Parse all data files (`roster.yaml`, `definitions.md`, `staff.md`, etc.)
2. Create constraint satisfaction model using Google OR-Tools CP-SAT
3. Apply all hard constraints
4. Apply soft constraints with penalties in objective function
5. Solve the model
6. Generate output files with results and violations

### Constraint Types

#### Hard Constraints (Must be satisfied)
- FTE requirements per fortnight block
- Maximum hours per fortnight block (76h)
- Rest period between shifts (minimum 11h)
- Consecutive shift limit (maximum 2 shifts per day)
- Red requests and holidays
- Training requirements for D12/N12 shifts
- Day/night transition rules

#### Soft Constraints (Should be satisfied)
- Night shift fairness
- Weekend distribution
- Shift pattern optimization
- Preference satisfaction

## Technical Implementation

### Python Version
- Python 3.x

### Virtual Environment
- Uses `./venv/` directory

### Dependencies
- Google OR-Tools CP-SAT
- PyYAML

### Roster Duration
- Must be a multiple of 14 days (fortnightly blocks)
- All constraints applied within discrete 14-day blocks

## Output Format

### Staff Roster (`result.staff.md`)
- Grouped by staff member
- Includes level, training level, and FTE hours
- Block-by-block breakdown with hours worked, weekend hours, and night shift hours
- Full list of assigned shifts

### Roster by Date (`result.roster.md`)
- Grouped by date
- Shows all staff on shift for each day
- Includes staff level and training level
- Shifts ordered as: D8, D12, P8, P12, L3, DISCO, N8, N12
- Within each shift, ordered by classification (CN before RN) then by training level (highest first)

### Violations (`result.violations.md`)
- Lists any rule violations found in the generated roster