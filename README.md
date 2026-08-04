# AI-Roster

A CP-SAT–based rostering system for the pediatric emergency ward at TPCH. Given a staff list, a set of shift definitions, and hard/soft constraint rules, it generates a fortnightly roster using Google OR-Tools CP-SAT.

> 🚧 **Work in progress.** The constraint/data files (`hard_constraints.md`, `soft_constraints.md`, `roster.yaml`, `staff.yaml`) are the ground truth, not the code.

> **For coding agents**: see [`AGENTS.md`](AGENTS.md) — it's the canonical reference for terminology, file relationships, constraint IDs, and implementation conventions. This README is the human-facing overview; if the two ever disagree, `AGENTS.md` wins and should be corrected.

## What's in this project

| File | Purpose |
|---|---|
| `roster.yaml` | The roster period and required shift positions per day of the week (source of truth — see schema below) |
| `staff.yaml` | Every staff member: classification, held skill levels, contracted hours, red requests, holidays |
| `definitions.yaml` | Shift start/end times, span vs paid duration, unpaid break, and midnight-crossing flag |
| `hard_constraints.md` | Non-negotiable rules, each with a unique `[H#...]` ID |
| `soft_constraints.md` | Preferences optimized by the solver, each with a unique `[S#...]` ID |
| `weights.yaml` | Relative importance of each soft constraint, keyed by ID |
| `output/` | Generated at runtime: one `roster_<run_id>.html` + `roster_<run_id>.log` pair per run — see Output below |

## `roster.yaml` schema

This is the **actual** structure of the file — each entry is a single roster position for that day:

```yaml
dates:
  start: 2026-08-03
  end: 2026-08-30

roster_positions:
  Monday:
    - shift: D8
      required_skill_level: null
    - shift: D12
      required_skill_level: Shift Coordinator
    - shift: D12
      required_skill_level: Triage
    - shift: D12
      required_skill_level: Resus
    - shift: D12
      required_skill_level: null
    # ... remaining shifts for Monday
  Tuesday:
    # ... same structure
```

- `required_skill_level: null` — any staff member can fill this position.
- `required_skill_level: <name>` — only staff holding that skill level (or higher, per the hierarchy) can fill it.
- Multiple entries with the same `shift` value on the same day are **separate positions**, each filled independently.
- Shift counts per day (how many `D12`s, `L3`s, etc.) are **whatever `roster.yaml` currently specifies** — don't hardcode assumed counts anywhere else; read the file. Counts can differ by day of week.
- The date range must span an exact multiple of 14 days.

## `staff.yaml` schema

```yaml
- name: "Amanda Bartley"
  classification: "CN"          # RN, CN, or Graduate
  skill_tags:                    # held skill levels
    - Acute
    - Resus
    - Triage
    - Shift Coordinator
  contracted_hours_per_fortnight: 56   # a floor, not a ceiling; paid hours, not span hours
  red_requests:
    - "2026-08-01"
    - "2026-08-04"
  holidays:
    - start: "2026-08-01"
      end: "2026-08-31"
```

### Field reference

| Field | Type | Notes |
|---|---|---|
| `name` | string | Full name. **Must be unique** across the file — it's the identifier used to group the by-staff view in the HTML output and to attach red requests/holidays to a person. |
| `classification` | string enum | One of `RN`, `CN`, `Graduate`. Independent of skill level — see `AGENTS.md` §2 for why Graduate is a classification, not a skill tier. |
| `skill_tags` | list of strings | The skill levels this person holds, from the hierarchy `Acute < Resus < Triage < Shift Coordinator`. **Always a contiguous prefix from the bottom** — e.g. `[Acute, Resus]` is valid, `[Resus]` alone or `[Acute, Triage]` (skipping Resus) is not. List order isn't meaningful; a staff member's effective rank is looked up per-tag against the hierarchy. |
| `contracted_hours_per_fortnight` | number | Paid hours contracted per 14-day block — a **floor**, not a ceiling (see "Coverage Shortfalls & Overtime" in `AGENTS.md` §7). Uses the `paid_hours` basis from `definitions.yaml`, not `span_hours`. |
| `red_requests` | list of date strings (`YYYY-MM-DD`) | Dates this person must not be rostered. Hard constraint. May be empty. Does **not** reduce their contracted-hours floor (they're single days, not leave). |
| `holidays` | list of `{start, end}` objects (`YYYY-MM-DD` each) | Date ranges this person is unavailable. Hard constraint. May be empty. A single-day holiday is written as `start == end` — there's no separate one-day shorthand. Holidays **do** proportionally reduce the contracted-hours floor for the affected block. |

`red_requests` and `holidays` are both hard constraints — never scheduled on those dates. See `AGENTS.md` §4 for the full validation rules (uniqueness, enum checks, the contiguous-skill-tags rule, etc.) that any parser should enforce and fail loudly on.

## Shifts

Defined in `definitions.yaml`: `D8, D12, P8, P12, L3, DISCO, N8, N12`. Each shift's stated span (8.5h / 12.5h) includes a 30-minute unpaid break — actual paid hours are 8.0h / 12.0h. `definitions.yaml` gives both explicitly (`span_hours`, `paid_hours`); contracted-hours accounting and hour caps use `paid_hours`, rest-period/overlap rules use `span_hours`. See `AGENTS.md` §5 for the full breakdown of which figure applies where.

- **Day shifts**: D8, D12, P8, P12, L3, DISCO
- **Night shifts**: N8, N12

Note: DISCO (17:30–02:00) crosses midnight like the night shifts do, but is classified as a **day** shift for fairness/reporting purposes. This is intentional — see `AGENTS.md` §5 for the full rule, including how midnight-crossing shifts attribute their hours to a specific date/block.

## Constraint types

**Hard constraints** (`hard_constraints.md`) — must always hold, e.g.:
- FTE (contracted hours) as a floor per fortnight block, plus up to 24 additional paid hours of overtime (deliberately generous, to widen the feasible region)
- Absolute max hours per fortnight block (76h)
- Minimum 11h rest between shifts
- At least 1 day off when transitioning between night and day shifts
- Red requests and holidays honored
- Skill level requirements per shift position
- Graduate-classified staff restricted to D8, P8, L3, DISCO, N8

**Soft constraints** (`soft_constraints.md`) — optimized via the objective function, weighted by `weights.yaml`:
- Overtime distributed fairly when contracted hours can't cover demand
- Night shifts and weekend shifts distributed fairly across staff
- Working the same shift 3+ consecutive days is discouraged

Full authoritative text and IDs live in the two constraint files — this is a summary, not a substitute.

## Output

Every run writes exactly two files into `output/` (created automatically if it doesn't exist), both sharing the same timestamp so they're always pairable:

- **`output/roster_<run_id>.html`** — the single output artifact. Self-contained (inline CSS, no external dependencies), rendered from `templates/roster.html` via Jinja2. Contains, in order:
  1. **Run summary** — generated time, roster period, solver status, objective value, assignments count, unfilled positions count (displayed as responsive summary cards).
  2. **Messages** — unfilled shifts, constraint violations, soft-constraint penalties. Explicitly states when there's nothing to report.
  3. **Roster by date** — a staff×days matrix table with color-coded shift badges (D8=#E3F2FD, D12=#BBDEFB, P8=#F3E5F5, P12=#E1BEE7, L3=#FFF3E0, DISCO=#FFE0B2, N8=#E8F5E9, N12=#C8E6C9), weekend columns highlighted, sticky first column.
  4. **Roster by staff** — per staff member: classification, skills, contracted hours, total assigned hours, weekend/night breakdown, overtime traffic light (green ≤0% over, yellow 0–15% over, red >15% over), block-by-block tables with hours/overtime/weekend/night/shift count, and the full shift list with date tooltips.
- **`output/roster_<run_id>.log`** — the full log for that run: data loading, validation, solving, and output writing.

Runs are never overwritten — each one adds a new timestamped pair to `output/`. See `AGENTS.md` §6 for the complete spec.

## Running it

```bash
./.venv/bin/python main.py
./.venv/bin/python -m pytest tests/
```

Python 3.x, dependencies: Google OR-Tools (CP-SAT), PyYAML, and Jinja2 (for HTML rendering), installed in the provided `./.venv/`.

## Project Structure

The project is structured with the following Python modules:

- `main.py` - Main driver script that orchestrates the entire solution; sets up logging for the run
- `models.py` - Data models for staff, shifts, and roster positions with validation
- `constraints.py` - Base classes for hard and soft constraint implementations
- `solver.py` - OR-Tools CP-SAT integration with model setup
- `output.py` - Builds the single `output/roster_<run_id>.html` file using Jinja2 (see `templates/roster.html`)
- `utils.py` - Utility functions for data loading, validation, calculations, and logging setup
- `templates/roster.html` - Jinja2 HTML template for roster output
- `tests/test_output.py` - Unit tests for output helpers (shift colors, overtime, day info, context building)
