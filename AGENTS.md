# Agents Guide: AI-Roster
This document provides the necessary context, structure, and standards for AI agents to contribute to the `ai-roster` project.

## Project Overview
This projects purpose is to build a monthly roster for the pediatric emergency ward at TPCH.
The project contains a list of staff, list of shifts that need to be filled, and shift definitions.

## Core Architecture
- **`opencode.json`**: The definition of the model to use.
- **`definitions.md`**: The definitions for all shifts, including start time, end time, duration and whether it crosses midnight.
- **`roster.md`**: Inludes the start and end dates of the roster. The list of shifts that need to be filled each week. These shifts repeat exactly every week.
- **`rules.md`**: The list of rules that each roster needs to follow. These are not negotiable.
- **`staff.md`**: The list of all staff and their training levels and FTE hours.
- **`training.md`**: The list of the different training levels for staff.
- **`result.staff.md`**: The final roster grouped by staff member is printed here.
- **`result.roster.md`**: The final roster grouped by roster date is printed here.
- **`build_roster.py`**: The python script that actually builds the roster.

## Staff Definitions
- Each staff member has the following options.
    - **Level**: This is the staff members organisation level. RN = Registered Nurse. CN = Clinical Nurse.
    - **Training Level**: The level of training that the staff member has received. Acute < Resus < Triage < Shift Coordinator
    - **FTE Hours per Fortnight**: Hows many hours the staff member is contracted per fornight. They must be scheduled this number of hours minimum.
    - **Red Requests**: Staff members are allowed to choose a couple of days a month that they will not be roster on. These are those days. Not every staff member will make a red request each month.
    - **Holidays/Sickness**: The dates and date ranges people are on holidays. Do not schedule people on during these days.
    - **Rules**: These are the individual staff members rules. They must be followed.
    - **Preferences**: These are the preferences of the staff members - they are optional, but following it if possible.

## Output
- You can overwrite/replace the existing `results.*.md` files on disk.
- The `result.*.md` outputs should contain all of the auxillery information like level and training level.
- The final roster should be printed in multiple different formats.
    - `result.staff.md` should be grouped by the staff member and the shifts that they have in the roster. It should also summarise the amount of hours allocated.
    - `result.roster.md` should be grouped by the roster days (by date) and show all of the people that are on shift for that day, including the specific shift.
- The `result.roster.md` needs to include the the staff members level and training level.
- The `result.staff.md` needs to include the the staff members Level, Training Level and FTE Hours per Fortnight.

## Build
When I say @BUILD then proceed to build a roster for the range listed in `roster.md` based on the markdown files in this directory. If any dates provided are outside of the date range then ignore those dates. Use the existing `build_roster.py` file if it helps, otherwise you can replace it.

## Testing
After the roster has been produced, scan through it and compare it to the rules and preferences to ensure it complies.
