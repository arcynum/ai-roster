# Rules (Hard Constraints)
Everything in this file is a rule and MUST be followed. The final roster must obey all of these rules.

## Shift Requirements
- [H#4d9f81c2] The `roster.yaml` file shall define the roster positions that must be filled for each day within the configured roster period.
- [H#7a3e5f91] Each entry within `roster.yaml` shall represent a single roster position that must be assigned to one eligible staff member.
- [H#c18b42de] Each roster position shall specify zero or one required skill level.
- [H#5e6ad8f4] A staff member shall only be assigned to a roster position where their skill level satisfies the required skill level defined for that position.
- [H#91bc3d7e] A roster position with no required skill level shall not impose a skill level restriction on the assigned staff member.
- [H#2f74e6ab] Multiple entries with the same shift type within `roster.yaml` shall represent separate roster positions that must each be independently filled.
- [H#84a1d5c9] Staff skill levels shall be hierarchical, where a staff member with a higher skill level shall also satisfy requirements for all lower skill levels.
- [H#6db3f120] The skill level hierarchy shall be ordered as follows: Acute, Resus, Triage, Shift Coordinator.
- [H#f3c72a8d] When multiple valid roster solutions exist, the rostering engine should prefer solutions that minimise assigning staff to roster positions below their highest available skill level.
- [H#b72e41fa] The `required_skill_level` for a roster position shall represent the minimum skill level required. A staff member with an equal or higher skill level shall satisfy the requirement.
- [H#6db3f120] The skill level hierarchy shall progress from lowest to highest in the following order: Acute, Resus, Triage, Shift Coordinator.
- [H#e91c63ab] A staff member shall not be assigned to more than one roster position within the same shift group or overlapping time period.
- [H#30479c74] Staff classified as Graduate shall only be assigned to the following shift types: D8, P8, L3, DISCO and N8.

## Staff Welfare and Safety
- [H#c1f6e3f5] Staff must have a minimum of 11 hours between each shift.
- [H#f4c9b6c8] When swapping between night shifts and day shifts at least 1 day off should be rostered in between to help them recover as its extremely tiring.
- [H#a5d0c7d9] Never roster any staff members on the days that they have red requested.
- [H#b6e1d8e0] Never roster any staff members on the days that they are on leave.
- [H#f0c5b2c4] Never exceed 76 hours allocated to a single staff member per discrete 14-day fortnight block.
- [H#d9a8b7c6] Staff must be rostered on for at least their FTE hours (adjusted proportionally for holidays/leave) per 14-day fortnight block. This is enforced on a per-block basis and cannot be averaged across the entire roster period.
- [H#e8f7d6c5] Staff may not work more than 12.5 additional hours beyond their FTE in any 14-day fortnight block.
