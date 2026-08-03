# Agents Guide: AI-Roster
This document provides the necessary context, structure, and standards for AI agents to contribute to the `ai-roster` project.

## Ponytail, lazy senior dev mode
You are a lazy senior developer. Lazy means efficient, not careless. The best code is the code never written.

Before writing any code, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't re-write it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code that works.

The ladder runs after you understand the problem, not instead of it: read the task and the code it touches, trace the real flow end to end, then climb.

Bug fix = root cause, not symptom: a report names a symptom. Grep every caller of the function you touch and fix the shared function once — one guard there is a smaller diff than one per caller, and patching only the path the ticket names leaves a sibling caller still broken.

Rules:

- No abstractions that weren't explicitly requested.
- No new dependency if it can be avoided.
- No boilerplate nobody asked for.
- Deletion over addition. Boring over clever. Fewest files possible.
- Shortest working diff wins, but only once you understand the problem. The smallest change in the wrong place isn't lazy, it's a second bug.
- Question complex requests: "Do you actually need X, or does Y cover it?"
- Pick the edge-case-correct option when two stdlib approaches are the same size, lazy means less code, not the flimsier algorithm.
- Mark deliberate simplifications that cut a real corner with a known ceiling (global lock, O(n²) scan, naive heuristic) with a `ponytail:` comment naming the ceiling and upgrade path.

Not lazy about: understanding the problem (read it fully and trace the real flow before picking a rung, a small diff you don't understand is just laziness dressed up as efficiency), input validation at trust boundaries, error handling that prevents data loss, security, accessibility, the calibration real hardware needs (the platform is never the spec ideal, a clock drifts, a sensor reads off), anything explicitly requested. Lazy code without its check is unfinished: non-trivial logic leaves ONE runnable check behind, the smallest thing that fails if the logic breaks (an assert-based demo/self-check or one small test file; no frameworks, no fixtures). Trivial one-liners need no test.

## Project Overview
This projects purpose is to build a monthly roster for the pediatric emergency ward at TPCH.
The project contains a list of staff, list of shifts that need to be filled, and shift definitions.

## Core Architecture
- **`opencode.json`**: The definition of the model to use.
- **`definitions.md`**: The definitions for all shifts, including start time, end time, duration and whether it crosses midnight.
- **`roster.yaml`**: Contains the start and end dates of the roster. The list of shifts that need to be filled each week. These shifts repeat exactly every week.
- **`hard_constraints.md`**: The list of rules that each roster needs to follow. These are not negotiable.
- **`soft_constraints.md`**: The list of preferences that each roster should try to follow. If this is going not be followed for whatever reason, you must provide a reason why.
- **`staff.md`**: The list of all staff and their training levels and FTE hours.
- **`training.md`**: The list of the different training levels for staff.
- **`result.staff.md`**: The final roster grouped by staff member is printed here.
- **`result.roster.md`**: The final roster grouped by roster date is printed here.
- **`result.violations.md`**: Any rule violations found in the generated roster are listed here.
- **`build_roster.py`**: The python script that actually builds the roster.
- **Fortnightly Blocks**: Rosters must be multiples of 14 days. All constraints (FTE, Max Hours, etc.) are applied within discrete 14-day blocks rather than being averaged across the entire roster period. **If the start/end dates in `roster.yaml` do not span a whole multiple of 14 days, the script must error out with a clear message and refuse to build the roster** — do not silently round, truncate, or prorate. Fix the dates in `roster.yaml` and re-run.

## Data File Validation
`staff.md`, `roster.md`, `definitions.md`, `hard_constraints.md`, `soft_constraints.md`, and `training.md` are hand-edited by humans and are a trust boundary — treat parsing them as input validation, not just data loading. If a row is malformed, missing a required field, references an undefined training level/shift/staff member, or a date is out of range, fail loudly with a message naming the file, the row, and the problem, rather than silently skipping it or guessing a default.

## Staff Definitions
- Each staff member has the following options.
    - **Classification**: This is the staff members organisation level. RN = Registered Nurse. CN = Clinical Nurse.
    - **Training Level**: The level of training that the staff member has received. Graduate < Acute < Resus < Triage < Shift Coordinator
    - **FTE Hours per Fortnight**: How many hours the staff member is contracted per fortnight. This is a **floor, not a ceiling** — see "Coverage Shortfalls & Overtime" below for what happens when total contracted FTE isn't enough to cover all shifts.
    - **Red Requests**: Staff members are allowed to choose a couple of days a month that they will not be rostered on. These are those days. Not every staff member will make a red request each month. **Red requests are a hard constraint** — never schedule a staff member on a day they've made a red request for.
    - **Holidays/Sickness**: The dates and date ranges people are on holidays. Do not schedule people on during these days.
    - **Rules**: These are the individual staff members rules. They must be followed.
    - **Preferences**: These are the preferences of the staff members - they are optional, but following it if possible.

### Overnight Shift Attribution
A shift that crosses midnight (e.g. an N12 starting at 22:00) counts entirely toward the date and 14-day block **it starts on** — not the date it ends on, and not split across both. This applies consistently to hours totals, weekend-hours percentages, and night-shift-hours percentages in `result.staff.md`.

## Output
- You can overwrite/replace the existing `results.*.md` files on disk.
- The `result.*.md` outputs should contain all of the auxillery information like level and training level.
- The final roster should be printed in multiple different formats.
    - `result.staff.md` should be grouped by the staff member. It MUST include:
        - Summary of Level, Training Level, and FTE Hours per Fortnight for the whole period.
        - A block-by-block breakdown (14-day increments) containing:
            - Total hours worked in that block.
            - Weekend hours and their percentage relative to the total hours worked in that block (to allow human audit of fairness).
            - Night shift hours and their percentage relative to the total hours worked in that block (to allow human audit of fairness).
        - A full list of all shifts assigned during the entire period.
    - `result.roster.md` should be grouped by the roster days (by date) and show all of the people that are on shift for that day, including the specific shift.
- The `result.roster.md` needs to include the the staff members level and training level.
- Always print the shifts in the `result.roster.md` file in the following order: D8, D12, P8, P12, L3, DISCO, N8, N12
- Within a single shift's list of staff, order by **classification first (CN before RN, or per the hierarchy in `staff.md`), then by training level (highest first) within the same classification**.
- `weights.json` values are relative ordering signals for the objective function, not literal cost units — a weight of 100 should be treated as "prioritise avoiding this violation over one weighted 50," not as "twice as bad" in any absolute sense. Don't build logic elsewhere that assumes proportionality between weights.

## Technical Implementation Guide

### Environment & Execution
- **Python Version**: Python 3.x
- **Virtual Environment**: A virtual environment is provided in the `./venv/` directory. 
- **Running Commands**: Always use the python interpreter from the virtual environment to ensure dependencies are found. Use `./venv/bin/python <script_name>.py`.

### Core Solver Logic (CP-SAT)
The `cp_solver.py` uses Google OR-Tools CP-SAT. When implementing or modifying constraints, follow these technical requirements:

1.  **Integer Arithmetic (Scaling)**: 
    - CP-SAT only works with integers. 
    - All floating-point values (e.g., FTE hours like `37.5`, shift durations like `8.5`) must be scaled to integers using `self.SCALE` (which is `100`).
    - *Example*: An FTE of `37.5` becomes `3750`.

2.  **Training Level Hierarchy**: 
    - Training levels are implemented as an ordered hierarchy: `Graduate < Acute < Resus < Triage < Shift Coordinator`.
    - In the solver, requirements for a specific level should be checked using thresholding (e.g., `TRAINING_MAP[level] >= required_rank`) rather than exact equality to allow higher-qualified staff to fill lower roles.

3.  **Constraint Lifecycle**: 
    To add a new constraint or preference, follow this pattern:
    - **Step 1: Variables**: Define the necessary decision variables (e.g., `model.NewBoolVar`).
    - **Step 2: Constraints**: Apply the logic using `model.Add(...)` or `model.AddForbiddenAssignments(...)`.
    - **Step 3: Penalties (Soft Only)**: For soft constraints, create an integer variable to represent the "violation amount" and add it to the objective function multiplied by its weight from `weights.json`.
    - **Step 4: Objective**: Ensure all new penalty variables are included in the `model.Minimize(...)` call.

4.  **Linkage via IDs**: 
    - Every hard/soft constraint in the code is tagged with its corresponding ID from the markdown files (e.g., `# [H#a7f2c9d1]`). Use these IDs when searching for or modifying logic.

## Testing
- **Framework & location**: Unit tests for `cp_solver.py` and other core logic live in `tests/` and use `pytest`. Run them with `./venv/bin/python -m pytest tests/`.
- Whenever any code is changed, run the tests.
- Whenever any code is changed, ensure the tests are updated to reflect the changes.
- All unit tests should test for a positive and negative result to ensure the functions are working correctly.
- After the roster has been produced, scan through it and compare it to the rules and preferences to ensure it complies.
- The lazy-mode "one runnable check" convention (see Ponytail rules above) is for small, non-solver helper functions — it does not replace the `tests/` pytest suite for constraint/solver logic.

## Operational Definitions

### Coverage Shortfalls & Overtime
FTE Hours per Fortnight is a **minimum**, not a cap. If total contracted FTE across all staff is insufficient to cover every shift in a 14-day block:
1. First try to cover the shortfall with overtime — hours scheduled above a staff member's FTE floor — distributed as **evenly as possible across all eligible staff** (don't stack overtime onto the same few people).
2. All other hard constraints still apply on top of this — e.g. maximum hours per fortnight, red requests, holidays, training-level requirements. Overtime never overrides a hard constraint.
3. Only if a shift still cannot be covered after fair overtime distribution and respecting all hard constraints — e.g. no staff member with the required training level is available, or covering it would breach someone's max-hours cap — record it as `UNFILLED` in the roster output, and note which classification/training level was required but unavailable.
4. If hard constraints make it impossible to produce **any** valid roster at all (not just some unfilled shifts — e.g. a required Shift Coordinator role has zero qualified staff in the entire roster), stop and tell the user why, rather than producing a broken or partial file.

Day shifts are: D8, D12, P8, P12, L3, DISCO
Night shifts are: N8, N12

## Python Coding Standards
Strict adherence to these rules is mandatory for all code modifications to prevent structural errors and maintain codebase integrity.

1. **Indentation**:
   - ALWAYS use exactly 4 spaces per indentation level.
   - NEVER use tabs.
   - BEFORE adding any logic, read the surrounding lines to verify the current indentation context of the scope you are entering.
   - Ensure that `if`, `for`, `while`, `def`, and `class` blocks are aligned correctly with their parent scopes.

2. **Spacing & Style**:
   - Use spaces around operators (e.g., `a = b + c`).
   - Follow PEP 8 conventions for naming (snake_case for functions/variables, PascalCase for classes).
   - Maintain consistent vertical whitespace between method definitions.

3. **Verification**:
   - After editing, if the file is a `.py` file, verify that no `IndentationError` or `SyntaxError` was introduced by attempting to run relevant scripts or linting tools.
