#!/usr/bin/env python3
"""
ai-roster - HTML roster output generation.

Produces a single self-contained HTML file per run using a Jinja2 template.
Contains:
1. Run summary (timestamp, period, solver status, objective, solve time)
2. Messages (unfilled shifts, constraint violations, soft-constraint penalties)
3. Roster tables (staff x days matrix, and by staff member with block breakdowns)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from utils import NIGHT_SHIFTS, OUTPUT_DIR, SCALE, SHIFT_ORDER, compute_adjusted_hours, is_weekend

if TYPE_CHECKING:
    from models import Staff, RosterSlot
    from solver import SolveResult

logger = logging.getLogger("ai-roster")

# Classification sort order
CLASS_ORDER = {"CN": 0, "RN": 1, "Graduate": 2}

# Shift color map (hex background colors)
SHIFT_COLORS = {
    "D8": "#E3F2FD",
    "D12": "#BBDEFB",
    "P8": "#F3E5F5",
    "P12": "#E1BEE7",
    "L3": "#FFF3E0",
    "DISCO": "#FFE0B2",
    "N8": "#E8F5E9",
    "N12": "#C8E6C9",
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]
DAY_ABBREVS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Template directory
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _day_info(d: date) -> dict:
    """Return a dict with day metadata for the matrix header."""
    wd = d.weekday()
    return {
        "date_str": d.isoformat(),
        "day": d.day,
        "abbrev": DAY_ABBREVS[wd],
        "day_name": DAY_NAMES[wd],
        "is_weekend": wd >= 5,
    }


def _overtime_info(hours: float, contracted: float) -> tuple[float, str, str, str]:
    """Compute overtime percentage and traffic-light styling.

    Returns (over_pct, light_class, badge_class, label).
    """
    if contracted <= 0:
        return 0.0, "light-green", "badge-green", "On track"
    over_pct = max(0.0, (hours - contracted) / contracted * 100)
    if over_pct <= 0:
        return over_pct, "light-green", "badge-green", "On track"
    if over_pct <= 15:
        return over_pct, "light-yellow", "badge-yellow", f"+{over_pct:.0f}%"
    return over_pct, "light-red", "badge-red", f"+{over_pct:.0f}%"


def _hours_floor_info(hours: float, adjusted: float) -> tuple[float, str, str, str]:
    """Compute hours-to-floor percentage and traffic-light styling.

    Returns (pct, light_class, badge_class, label).
    Green = at or above floor, yellow = 85-99%, red = below 85%.
    """
    if adjusted <= 0:
        return 100.0, "light-green", "badge-green", "No floor (0h)"
    pct = hours / adjusted * 100
    if pct >= 100:
        return pct, "light-green", "badge-green", f"{pct:.0f}%"
    if pct >= 85:
        return pct, "light-yellow", "badge-yellow", f"{pct:.0f}%"
    return pct, "light-red", "badge-red", f"{pct:.0f}%"


def _build_context(
    result: SolveResult,
    staff_list: list["Staff"],
    definitions: dict,
    roster_start: date,
    roster_end: date,
    blocks: list[list[date]],
    positions: list[dict] | None = None,
    hard_constraints: list[dict] | None = None,
    soft_constraints: list[dict] | None = None,
) -> dict:
    """Build the full context dict for the Jinja2 template."""
    staff_map = {s.name: s for s in staff_list}
    all_dates = []
    for i in range((roster_end - roster_start).days + 1):
        all_dates.append(_day_info(roster_start + timedelta(days=i)))
    all_date_strs = {d["date_str"] for d in all_dates}

    # Build staff_matrix: {staff_name: {date_str: shift_or_None}}
    staff_matrix: dict[str, dict[str, str | None]] = {}
    for staff in staff_list:
        staff_matrix[staff.name] = {ds: None for ds in all_date_strs}
    for slot in result.assignments:
        staff_matrix.setdefault(slot.staff_name, {})[slot.date] = slot.shift

    # Build staff_info and staff_blocks
    staff_info: dict[str, dict] = {}
    staff_blocks: dict[str, list[dict]] = {}

    for staff in staff_list:
        slots = sorted(
            [s for s in result.assignments if s.staff_name == staff.name],
            key=lambda s: s.date,
        )
        total_hours = 0.0
        weekend_hours = 0.0
        night_hours = 0.0
        shift_list = []

        for slot in slots:
            paid = definitions[slot.shift]["paid_hours"]
            total_hours += paid
            dt = date.fromisoformat(slot.date)
            if is_weekend(dt):
                weekend_hours += paid
            if slot.shift in NIGHT_SHIFTS:
                night_hours += paid
            shift_list.append({"date": slot.date, "shift": slot.shift})

        weekend_pct = (weekend_hours / total_hours * 100) if total_hours > 0 else 0.0
        night_pct = (night_hours / total_hours * 100) if total_hours > 0 else 0.0
        over_pct, light, badge, label = _overtime_info(
            total_hours, staff.contracted_hours_per_fortnight
        )

        staff_info[staff.name] = {
            "total_hours": total_hours,
            "weekend_hours": weekend_hours,
            "night_hours": night_hours,
            "weekend_pct": weekend_pct,
            "night_pct": night_pct,
            "over_pct": over_pct,
            "light_class": light,
            "badge_class": badge,
            "overtime_label": label,
            "shifts": shift_list,
        }

        # Per-block breakdown
        block_data = []
        for bi, block in enumerate(blocks):
            block_dates = set(d.isoformat() for d in block)
            block_date_strs = list(block_dates)
            block_slots = [s for s in slots if s.date in block_dates]
            b_hours = sum(definitions[s.shift]["paid_hours"] for s in block_slots)
            b_weekend = sum(
                definitions[s.shift]["paid_hours"]
                for s in block_slots
                if is_weekend(date.fromisoformat(s.date))
            )
            b_night = sum(
                definitions[s.shift]["paid_hours"]
                for s in block_slots
                if s.shift in NIGHT_SHIFTS
            )
            b_weekend_pct = (b_weekend / b_hours * 100) if b_hours > 0 else 0.0
            b_night_pct = (b_night / b_hours * 100) if b_hours > 0 else 0.0
            b_over_pct, b_light, b_badge, b_label = _overtime_info(
                b_hours, staff.contracted_hours_per_fortnight
            )
            b_adjusted_scaled = compute_adjusted_hours(
                staff.contracted_hours_per_fortnight,
                staff.holidays,
                block_date_strs,
            )
            b_adjusted = b_adjusted_scaled / SCALE
            b_floor_pct, b_floor_light, b_floor_badge, b_floor_label = _hours_floor_info(
                b_hours, b_adjusted
            )
            # Shortfall info from solver result
            shortfall = 0.0
            if hasattr(result, "shortfall") and staff.name in result.shortfall:
                block_key = f"b{bi}"
                shortfall = result.shortfall[staff.name].get(block_key, 0.0)
            shortfall_label = f"{shortfall:.1f}h under" if shortfall > 0 else "On track"
            shortfall_light = "light-red" if shortfall > 0 else "light-green"

            block_data.append({
                "block_idx": bi,
                "block_start": block[0].isoformat(),
                "block_end": block[-1].isoformat(),
                "hours": b_hours,
                "contracted": staff.contracted_hours_per_fortnight,
                "over_pct": b_over_pct,
                "light_class": b_light,
                "badge_class": b_badge,
                "overtime_label": b_label,
                "weekend_hours": b_weekend,
                "weekend_pct": b_weekend_pct,
                "night_hours": b_night,
                "night_pct": b_night_pct,
                "shift_count": len(block_slots),
                "adjusted": b_adjusted,
                "adjusted_floor_pct": b_floor_pct,
                "adjusted_light_class": b_floor_light,
                "adjusted_badge_class": b_floor_badge,
                "adjusted_label": b_floor_label,
                "shortfall": shortfall,
                "shortfall_label": shortfall_label,
                "shortfall_light_class": shortfall_light,
            })

        staff_blocks[staff.name] = block_data

    # Build shift_slot_tables: shift_type → slot_id → {date_str: staff_name_or_UNFILLED}
    all_date_str_list = sorted(all_date_strs)
    shift_slot_tables: dict[str, dict[str, dict[str, str | None]]] = {}
    positions = positions or []
    for shift_type in SHIFT_ORDER:
        slot_ids = sorted({p["slot_id"] for p in positions if p.get("shift") == shift_type})
        if not slot_ids:
            continue
        if len(slot_ids) > 15:
            logger.warning(
                "Shift %s has %d unique slots (cap 15) — truncating for display",
                shift_type, len(slot_ids),
            )
        slot_ids = slot_ids[:15]
        table: dict[str, dict[str, str | None]] = {sid: {ds: None for ds in all_date_str_list} for sid in slot_ids}
        shift_slot_tables[shift_type] = table

    # Populate from assignments
    for slot in result.assignments:
        sid = getattr(slot, "slot_id", None)
        if sid and slot.date in shift_slot_tables.get(slot.shift, {}):
            shift_slot_tables[slot.shift][sid][slot.date] = slot.staff_name

    # Populate unfilled positions
    for pos in result.unfilled:
        sid = pos.get("slot_id")
        if sid and sid in shift_slot_tables.get(pos["shift"], {}):
            shift_slot_tables[pos["shift"]][sid][pos["date"]] = "UNFILLED"

    # Compute hours summary: total required vs. staff available
    total_required_hours = sum(
        definitions[pos["shift"]]["paid_hours"] for pos in positions
    )

    hours_summary_blocks: list[dict] = []
    total_available_hours = 0.0
    for bi, block in enumerate(blocks):
        block_dates = [d.isoformat() for d in block]
        block_required = sum(
            definitions[pos["shift"]]["paid_hours"]
            for pos in positions
            if pos["date"] in block_dates
        )
        block_available = 0.0
        for staff in staff_list:
            adjusted_scaled = compute_adjusted_hours(
                staff.contracted_hours_per_fortnight,
                staff.holidays,
                block_dates,
            )
            block_available += adjusted_scaled / SCALE
        total_available_hours += block_available
        block_surplus = block_available - block_required
        block_surplus_pct = (block_surplus / block_required * 100) if block_required > 0 else 0.0
        if block_surplus_pct >= 0:
            surplus_light, surplus_badge, surplus_label = "light-green", "badge-green", f"+{block_surplus:.1f}h"
        elif block_surplus_pct >= -20:
            surplus_light, surplus_badge, surplus_label = "light-yellow", "badge-yellow", f"{block_surplus:.1f}h"
        else:
            surplus_light, surplus_badge, surplus_label = "light-red", "badge-red", f"{block_surplus:.1f}h"
        hours_summary_blocks.append({
            "block_idx": bi,
            "block_start": block[0].isoformat(),
            "block_end": block[-1].isoformat(),
            "required": block_required,
            "available": block_available,
            "surplus": block_surplus,
            "surplus_pct": block_surplus_pct,
            "surplus_light": surplus_light,
            "surplus_badge": surplus_badge,
            "surplus_label": surplus_label,
        })

    total_surplus = total_available_hours - total_required_hours
    if total_surplus >= 0:
        total_light, total_badge, total_label = "light-green", "badge-green", f"+{total_surplus:.1f}h"
    elif total_surplus >= -20:
        total_light, total_badge, total_label = "light-yellow", "badge-yellow", f"{total_surplus:.1f}h"
    else:
        total_light, total_badge, total_label = "light-red", "badge-red", f"{total_surplus:.1f}h"

    return {
        "generate_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "roster_start": roster_start.isoformat(),
        "roster_end": roster_end.isoformat(),
        "solver_status": result.status,
        "objective_value": result.objective_value,
        "assignments": result.assignments,
        "unfilled": result.unfilled,
        "staff_list": staff_list,
        "all_dates": all_dates,
        "staff_matrix": staff_matrix,
        "staff_info": staff_info,
        "staff_blocks": staff_blocks,
        "shift_slot_tables": shift_slot_tables,
        "hours_summary": {
            "total_required": total_required_hours,
            "total_available": total_available_hours,
            "total_surplus": total_surplus,
            "total_light": total_light,
            "total_badge": total_badge,
            "total_label": total_label,
            "blocks": hours_summary_blocks,
        },
        "soft_penalty": result.soft_penalty,
        "hard_constraints": result.hard_constraints,
        "soft_constraints": result.soft_constraints,
    }


def generate_html(
    result: SolveResult,
    staff_list: list["Staff"],
    definitions: dict,
    roster_start: date,
    roster_end: date,
    blocks: list[list[date]],
    run_id: str,
    positions: list[dict] | None = None,
    hard_constraints: list[dict] | None = None,
    soft_constraints: list[dict] | None = None,
) -> Path:
    """Generate the roster HTML file and write it to output/.

    Returns the path to the written file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"roster_{run_id}.html"

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
    )
    template = env.get_template("roster.html")

    context = _build_context(result, staff_list, definitions,
                               roster_start, roster_end, blocks,
                               positions=positions,
                               hard_constraints=hard_constraints,
                               soft_constraints=soft_constraints)
    html = template.render(**context)

    output_path.write_text(html, encoding="utf-8")
    logger.info("Wrote HTML roster to %s", output_path)
    return output_path
