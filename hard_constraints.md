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
- [H#b72e41fa] The `required_skill_level` for a roster position shall represent the minimum skill level required. A staff member with an equal or higher skill level shall satisfy the requirement.
- [H#e91c63ab] A staff member's assigned shifts must not overlap in wall-clock time. Compute each assigned shift's absolute start/end (specific date + `definitions.yaml`'s `start`/`end`, carrying `crosses_midnight` shifts into the next calendar day) and require zero overlap between any two intervals for the same staff member across the whole roster period — not just within a single day. This catches the boundary case where a night shift's `span_hours` end time lands after a day shift's start time on the following calendar day (e.g. N8 ending 07:15 vs. a D8 starting 07:00 the same day is a 15-minute overlap and must be rejected, even though the two shifts are on "different shift instances"). Implementation note: since every shift type's duration is fixed, this reduces to a static, precomputable table of which (shift on day *d*, shift on day *d*+1) pairs are incompatible — see AGENTS.md §8 "CP-SAT Modeling Notes."
- [H#30479c74] Staff classified as Graduate (a **classification**, distinct from the skill level hierarchy above — see AGENTS.md "Classification vs. Skill Level") shall only be assigned to the following shift types: D8, P8, L3, DISCO and N8.

## Staff Welfare and Safety
- [H#c1f6e3f5] Staff must have a minimum of 11 hours between each shift. This is measured wall-clock, end-of-shift to start-of-next-shift (i.e. using each shift's `span_hours`/start-end times from `definitions.yaml`, not `paid_hours` — the person is physically present for the full span, unpaid break included).
- [H#f4c9b6c8] If a staff member works a night shift (N8/N12) on day *d*, they must not be assigned any day shift (D8/D12/P8/P12/L3/DISCO) on day *d*+1 — day *d*+1 must either be a night shift or fully unassigned (no shift of any kind — a red request or holiday on that day satisfies "unassigned" for this purpose). The same rule applies in reverse: a day shift on day *d* forbids any night shift on day *d*+1. This is mandatory, not a preference — do not treat the "should" wording sometimes seen elsewhere as optional. Note this is stricter than the 11-hour rest rule ([H#c1f6e3f5]) specifically for night↔day transitions: some such transitions would technically clear 11 hours of rest but are still forbidden by this rule.
- [H#a5d0c7d9] Never roster any staff members on the days that they have red requested.
- [H#b6e1d8e0] Never roster any staff members on the days that they are on leave.
- [H#f0c5b2c4] Never exceed 76 **paid** hours (per `definitions.yaml`'s `paid_hours` field, not `span_hours`) allocated to a single staff member per discrete 14-day fortnight block.
- ~~[H#d9a8b7c6]~~ ~~Staff must be rostered on for at least their **adjusted contracted paid hours** (see [H#a3d8f6c1] for how this figure is calculated) per 14-day fortnight block.~~ **Reclassified to soft constraint [S#d9a8b7c6].** When total contracted-hours demand exceeds total roster hours (a normal situation when headcount > minimum coverage), the shortfall is distributed fairly across staff rather than making the model infeasible.
- [H#a3d8f6c1] **Holiday proration formula.** A staff member's adjusted contracted paid hours for a given 14-day block is calculated as a precomputed constant, before the CP-SAT model is built (not a solver decision variable):

  ```
  available_days   = 14 - (count of calendar days in this block that fall within any of the staff member's holiday date ranges, clipped to the block's own start/end)
  adjusted_hours   = floor(contracted_hours_per_fortnight * available_days / 14)
  ```

  Use integer floor division throughout (working in the same `SCALE`-d integer units as everywhere else in the model — see §8) to avoid floating point. Red requests never factor into this calculation ([H#d9a8b7c6]/[H#a3d8f6c1] both apply to holidays only). A staff member with no holidays in the block has `available_days = 14` and `adjusted_hours = contracted_hours_per_fortnight` unchanged.
- [H#e8f7d6c5] Staff may not work more than 12 additional **paid** hours (per `definitions.yaml`'s `paid_hours` field) beyond their **raw `contracted_hours_per_fortnight`** (not the holiday-adjusted `adjusted_hours` from [H#a3d8f6c1] — this cap uses the staff member's unadjusted contract figure regardless of any holiday in the block) in any 14-day fortnight block. (History: raised from 12.5 to 24 to widen the feasible region before casual staffing existed in this model; reduced to 12 now that coverage gaps can only be closed by named staff flexing or left unfilled. This is a business/wellbeing decision, not a fatigue/safety limit like the 76h absolute cap below, **which this reduction does not change in any way** — 76h remains the hard ceiling regardless of overtime.)
