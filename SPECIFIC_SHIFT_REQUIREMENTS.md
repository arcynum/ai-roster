# Shift Requirements Documentation

This document provides detailed information about shift requirements and their implementation in the AI-Roster system.

## Overview

Shift requirements define what shifts need to be filled each day of the week and specify the training requirements for each shift instance.

## Shift Instance Requirements

Each shift instance in the roster requires exactly one skill tag. This is a critical constraint that ensures proper staffing based on training levels.

### Skill Tag Types

1. **Wildcard ("*")** - Any staff member can fill this shift
2. **Specific Training Levels** - Only staff with specific training can fill:
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