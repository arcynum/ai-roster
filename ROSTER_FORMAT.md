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