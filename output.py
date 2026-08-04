#!/usr/bin/env python3
"""
ai-roster - HTML roster output generation.

Produces a single self-contained HTML file per run containing:
1. Run summary (timestamp, period, solver status, objective, solve time)
2. Messages (unfilled shifts, constraint violations, soft-constraint penalties)
3. Roster tables (by date and by staff member)
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from utils import OUTPUT_DIR, is_weekend, shift_span_hours

if TYPE_CHECKING:
    from models import Staff, RosterSlot
    from solver import SolveResult


logger = logging.getLogger("ai-roster")

# Shift display order for tables
SHIFT_ORDER = ["D8", "D12", "P8", "P12", "L3", "DISCO", "N8", "N12"]

# Classification sort order (highest first)
CLASS_ORDER = {"CN": 0, "RN": 1, "Graduate": 2}


def generate_html(
    result: SolveResult,
    staff_list: list["Staff"],
    positions: list,
    definitions: dict,
    roster_start: date,
    roster_end: date,
    run_id: str,
) -> Path:
    """Generate the roster HTML file and write it to output/.

    Returns the path to the written file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"roster_{run_id}.html"

    html = _build_html(result, staff_list, positions, definitions,
                       roster_start, roster_end)

    output_path.write_text(html, encoding="utf-8")
    logger.info("Wrote HTML roster to %s", output_path)
    return output_path


def _build_html(
    result: SolveResult,
    staff_list: list["Staff"],
    positions: list,
    definitions: dict,
    roster_start: date,
    roster_end: date,
) -> str:
    """Build the full HTML string."""
    summary = _render_summary(result, roster_start, roster_end)
    messages = _render_messages(result, staff_list, definitions)
    staff_map = {s.name: s for s in staff_list}
    roster_by_date = _render_roster_by_date(result, definitions, staff_map)
    roster_by_staff = _render_roster_by_staff(result, staff_list, definitions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI-Roster Report</title>
<style>{_css()}</style>
</head>
<body>
<h1>AI-Roster Report</h1>
{summary}
{messages}
{roster_by_date}
{roster_by_staff}
</body>
</html>"""


def _css() -> str:
    """Inline CSS for the HTML output."""
    return """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       margin: 2rem; color: #222; background: #fafafa; }
h1 { border-bottom: 2px solid #333; padding-bottom: 0.5rem; }
h2 { margin-top: 2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.25rem; }
h3 { margin-top: 1.5rem; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1rem;
        background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; font-size: 0.9rem; }
th { background: #f5f5f5; font-weight: 600; }
tr:nth-child(even) { background: #fafafa; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 0.75rem; margin: 1rem 0; }
.summary-card { background: #fff; border: 1px solid #ddd; border-radius: 6px;
                padding: 0.75rem 1rem; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.summary-card .label { font-size: 0.75rem; text-transform: uppercase; color: #666; }
.summary-card .value { font-size: 1.1rem; font-weight: 600; margin-top: 0.25rem; }
.optimal { color: #1a7f37; }
.feasible { color: #e37400; }
.infeasible { color: #c5221f; }
.warning { color: #c5221f; }
.staff-block { margin-bottom: 1.5rem; padding: 1rem; background: #fff;
              border: 1px solid #ddd; border-radius: 6px; }
.staff-block h3 { margin-top: 0; }
.hours-bar { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem; }
.hours-bar span { background: #e8f5e9; padding: 2px 8px; border-radius: 4px;
                  font-size: 0.8rem; }
"""


def _render_summary(result: SolveResult, start: date, end: date) -> str:
    """Render the run summary section."""
    status_class = result.status.lower()
    return f"""<h2>Run Summary</h2>
<div class="summary-grid">
  <div class="summary-card">
    <div class="label">Generated</div>
    <div class="value">{result.solve_time_s:.1f}s</div>
  </div>
  <div class="summary-card">
    <div class="label">Roster Period</div>
    <div class="value">{start.isoformat()} &ndash; {end.isoformat()}</div>
  </div>
  <div class="summary-card">
    <div class="label">Solver Status</div>
    <div class="value {status_class}">{result.status}</div>
  </div>
  <div class="summary-card">
    <div class="label">Objective Value</div>
    <div class="value">{result.objective_value}</div>
  </div>
  <div class="summary-card">
    <div class="label">Assignments</div>
    <div class="value">{len(result.assignments)}</div>
  </div>
  <div class="summary-card">
    <div class="label">Unfilled Positions</div>
    <div class="value warning">{len(result.unfilled)}</div>
  </div>
</div>"""


def _render_messages(result: SolveResult, staff_list: list["Staff"],
                     definitions: dict) -> str:
    """Render the messages/violations section."""
    parts: list[str] = []

    if result.unfilled:
        parts.append("<h3>Unfilled Shifts</h3><ul>")
        for pos in result.unfilled:
            parts.append(f"<li>{pos.get('date', '?')}: {pos.get('shift', '?')} "
                         f"(skill: {pos.get('required_skill_level', 'any')})</li>")
        parts.append("</ul>")

    if not result.unfilled and len(result.assignments) == 0:
        parts.append("<p>No violations or unfilled shifts.</p>")

    return f"""<h2>Messages</h2>
{''.join(parts)}"""


def _render_roster_by_date(result: SolveResult, definitions: dict,
                           staff_map: dict[str, "Staff"]) -> str:
    """Render the roster grouped by date."""
    # Group assignments by date
    by_date: dict[str, list[RosterSlot]] = {}
    for slot in result.assignments:
        by_date.setdefault(slot.date, []).append(slot)

    # Sort dates
    sorted_dates = sorted(by_date.keys())

    rows: list[str] = []
    for d in sorted_dates:
        slots = sorted(by_date[d], key=lambda s: (
            SHIFT_ORDER.index(s.shift) if s.shift in SHIFT_ORDER else 99,
            CLASS_ORDER.get(_classification_of(s.staff_name, staff_map), 9),
        ))
        date_str = f"<th colspan='3' style='background:#e3f2fd'>{d}</th>"
        shift_row = "<tr>" + "".join(f"<th>{s.shift}</th>" for s in slots) + "</tr>"
        staff_row = "<tr>" + "".join(f"<td>{s.staff_name}</td>" for s in slots) + "</tr>"
        rows.append(f"<table><tr>{date_str}</tr>{shift_row}{staff_row}</table>")

    return f"""<h2>Roster by Date</h2>
{''.join(rows)}"""


def _render_roster_by_staff(result: SolveResult, staff_list: list["Staff"],
                            definitions: dict) -> str:
    """Render the roster grouped by staff member."""
    # Group assignments by staff
    by_staff: dict[str, list[RosterSlot]] = {}
    for slot in result.assignments:
        by_staff.setdefault(slot.staff_name, []).append(slot)

    staff_map = {s.name: s for s in staff_list}

    parts: list[str] = []
    for staff in sorted(staff_list, key=lambda s: s.name):
        slots = sorted(by_staff.get(staff.name, []), key=lambda s: s.date)
        total_hours = sum(
            definitions[s.shift]["paid_hours"] for s in slots
        )
        weekend_hours = sum(
            definitions[s.shift]["paid_hours"]
            for s in slots
            if is_weekend(date.fromisoformat(s.date))
        )
        night_hours = sum(
            definitions[s.shift]["paid_hours"]
            for s in slots
            if definitions[s.shift]["crosses_midnight"]
        )

        shift_list = ", ".join(f"{s.date}: {s.shift}" for s in slots)

        parts.append(f"""<div class="staff-block">
  <h3>{staff.name} <small>({staff.classification.value})</small></h3>
  <p>Skills: {", ".join(staff.skill_tags) or "None"}</p>
  <p>Contracted: {staff.contracted_hours_per_fortnight}h/fortnight</p>
  <p>Assigned: {total_hours:.1f}h (weekend: {weekend_hours:.1f}h, night: {night_hours:.1f}h)</p>
  <p>Shifts: {shift_list or "None"}</p>
</div>""")

    return f"""<h2>Roster by Staff</h2>
{''.join(parts)}"""


def _classification_of(staff_name: str, staff_map: dict[str, "Staff"]) -> str:
    """Lookup classification for a staff member."""
    staff = staff_map.get(staff_name)
    if staff is None:
        return ""
    return staff.classification.value
