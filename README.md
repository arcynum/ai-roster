# AI-Roster System Documentation

## Overview

This project builds a monthly roster for the pediatric emergency ward at TPCH. The system uses constraint satisfaction to generate rosters that meet all hard constraints while optimizing soft constraints.

## Core Components

### Data Files

1. **`roster.yaml`** - New source of truth for roster requirements (replaces `roster.md`)
2. **`definitions.md`** - Shift definitions including start time, end time, duration, and midnight crossing
3. **`staff.yaml`** - Staff information including training levels, FTE hours, red requests, and holidays (replaces `staff.md`)
4. **`hard_constraints.md`** - Non-negotiable rules that must be followed
5. **`soft_constraints.md`** - Preferences that should be followed when possible
6. **`training.md`** - Training levels available for staff

For detailed information about the format of `staff.yaml`, see [STAFF_FORMAT.md](STAFF_FORMAT.md).

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

1. Parse all data files (`roster.yaml`, `definitions.md`, `staff.yaml`, etc.)
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

# Roster Requirements Format

This document explains the format and structure of roster requirements used by the AI-Roster system.

## Overview

The roster requirements define what shifts need to be filled each day and what skill levels are required for each shift instance.

## File Formats

The system uses only one format for roster requirements:

1. **New Format**: `roster.yaml` (recommended)

## Roster YAML Format

The `roster.yaml` file defines shift requirements in a structured format:

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
    - shift: D12
      required_skills: ["Triage"]
    - shift: D12
      required_skills: ["Resus"]
    - shift: D12
      required_skills: ["*"]
    - shift: P8
      required_skills: ["*"]
    - shift: P12
      required_skills: ["*"]
    - shift: L3
      required_skills: ["*"]
    - shift: L3
      required_skills: ["*"]
    - shift: DISCO
      required_skills: ["*"]
    - shift: N8
      required_skills: ["*"]
    - shift: N12
      required_skills: ["Shift Coordinator"]
    - shift: N12
      required_skills: ["Triage"]
    - shift: N12
      required_skills: ["Resus"]
    - shift: N12
      required_skills: ["*"]
  # ... other days
```

### Structure Details

Each day contains a list of shift instances, where each instance has:
- `shift`: The shift name (D8, D12, P8, P12, L3, DISCO, N8, N12)
- `required_skills`: A list containing exactly one skill tag that must be met

### Skill Tag Requirements

- `"*"` - Any skill can fill this shift instance
- Specific skill tags (e.g., "Shift Coordinator", "Triage", "Resus") - Only staff with that exact training level can fill this shift
- Each shift instance requires exactly one skill tag

### Shift Instance Counts

- Each day has exactly:
  - 1 D8 shift
  - 4 D12 shifts (with different skill requirements)
  - 1 P8 shift
  - 1 P12 shift
  - 2 L3 shifts (only on Saturday and Sunday)
  - 1 DISCO shift
  - 1 N8 shift
  - 4 N12 shifts (with different skill requirements)

## Roster YAML Format

The `roster.yaml` format is the only supported format for roster requirements:

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

## Integration with Staff Training

The skill tags defined in this file will be mapped to staff training levels in `staff.yaml`. The constraint solver uses these requirements to ensure that staff with the required training levels are assigned to their respective shifts.


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


# Shift Requirements Documentation

This document provides detailed information about shift requirements and their implementation in the AI-Roster system.

## Overview

Shift requirements define what shifts need to be filled each day of the week and specify the training requirements for each shift instance.

## Shift Instance Requirements

Each shift instance in the roster requires exactly one skill tag. This is a critical constraint that ensures proper staffing based on training levels.

### Skill Tag Types

1. **null** - Any staff member can fill this shift
2. **Specific Skill Tags** - Only staff with specific skill tags can fill:
   - "Shift Coordinator"
   - "Triage" 
   - "Resus"
   - "Acute"

## Shift Instance Counts by Day

### All Days (Monday through Sunday):
- 1 D8 shift
- 4 D12 shifts with different skill requirements
- 1 P8 shift
- 1 P12 shift
- 1 DISCO shift
- 1 N8 shift
- 4 N12 shifts with different skill requirements

### Special Days:
- **Saturday and Sunday**: 2 L3 shifts each (instead of 1)

## Detailed Shift Requirements

### D12 Shifts (4 instances per day)
1. "Shift Coordinator" - Requires staff with Shift Coordinator training level
2. "Triage" - Requires staff with Triage training level
3. "Resus" - Requires staff with Resus training level
4. "*" - Any staff member (wildcard)

### N12 Shifts (4 instances per day)
1. "Shift Coordinator" - Requires staff with Shift Coordinator training level
2. "Triage" - Requires staff with Triage training level
3. "Resus" - Requires staff with Resus training level
4. "*" - Any staff member (wildcard)

### L3 Shifts (2 instances on Saturday and Sunday only)
- "*" - Any staff member (wildcard)

## Implementation Details

The `ShiftRequirement` class in `models.py` was updated to include:
- `shift_name`: The name of the shift (D8, D12, etc.)
- `count`: Number of instances (always 1 for current implementation)
- `required_skills`: List of required skill tags (exactly 1 skill tag per instance)

## Validation

The constraint solver validates that:
1. Each shift instance has exactly one required skill tag
2. Staff assigned to a shift meet the required skill tag
3. The total number of shifts matches the requirements

## Migration Notes

This file replaces the previous `roster.md` format:
- All shift instances are preserved
- Skill tag requirements are maintained exactly
- The number of instances per shift type remains the same
- The structure is more explicit and easier to maintain


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
