#!/usr/bin/env python3
"""
ai-roster - Main driver script.

Orchestrates the full roster generation pipeline:
1. Load and validate data files
2. Build Staff objects
3. Build the CP-SAT model
4. Solve
5. Generate HTML output + log

Usage:
    .venv/bin/python main.py
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime

from constraints import get_hard_constraint_ids, get_soft_constraint_ids
from models import Classification, Staff
from solver import RosterModel, SolveResult
from utils import (
    OUTPUT_DIR,
    generate_dates,
    get_fortnight_blocks,
    load_config,
    load_definitions,
    load_hard_constraints,
    load_roster,
    load_soft_constraints,
    load_staff,
    load_weights,
    setup_logging,
    validate_roster_period,
    validate_roster_positions,
    validate_staff_records,
)


logger = logging.getLogger("ai-roster")


def main() -> None:
    """Run the full roster generation pipeline."""
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    setup_logging(run_id)
    logger.info("=" * 60)
    logger.info("AI-Roster run started (run_id=%s)", run_id)
    logger.info("=" * 60)

    try:
        _run(run_id)
    except Exception as exc:
        logger.error("Roster generation failed: %s", exc, exc_info=True)
        sys.exit(1)


def _run(run_id: str) -> None:
    """Execute the pipeline steps."""
    # Step 1: Load data files
    logger.info("Step 1: Loading data files")
    definitions = load_definitions()
    staff_records = load_staff()
    roster_data = load_roster()
    hard_constraints = load_hard_constraints()
    soft_constraints = load_soft_constraints()
    registered_hard = len(get_hard_constraint_ids())
    logger.info(
        "Hard constraints: %d documented in hard_constraints.md, %d registered as classes",
        len(hard_constraints), registered_hard,
    )
    known_hard_ids = set(get_hard_constraint_ids())
    known_soft_ids = set(get_soft_constraint_ids())
    known_unfilled_tier_ids = set(RosterModel.UNFILLED_TIER_IDS)
    weights = load_weights(
        known_soft_ids=known_soft_ids,
        known_unfilled_tier_ids=known_unfilled_tier_ids,
    )
    config = load_config(known_hard_ids=known_hard_ids, known_soft_ids=known_soft_ids)

    # Step 2: Validate data
    logger.info("Step 2: Validating data")
    roster_start, roster_end = validate_roster_period(roster_data)
    all_dates = generate_dates(roster_start, roster_end)
    validate_staff_records(staff_records, roster_dates=set(all_dates))
    blocks = get_fortnight_blocks(all_dates)
    positions = validate_roster_positions(roster_data, definitions,
                                          roster_start, roster_end)

    # Step 3: Build Staff objects
    logger.info("Step 3: Building staff models")
    staff_list = [
        Staff(
            name=rec["name"],
            classification=Classification(rec["classification"]),
            skill_tags=rec["skill_tags"],
            contracted_hours_per_fortnight=rec["contracted_hours_per_fortnight"],
            red_requests=rec.get("red_requests", []),
            holidays=rec.get("holidays", []),
        )
        for rec in staff_records
    ]

    # Step 4: Build and solve the CP-SAT model
    logger.info("Step 4: Building CP-SAT model")
    model = RosterModel(
        staff_list=staff_list,
        positions=positions,
        definitions=definitions,
        weights=weights,
        blocks=[[d.isoformat() for d in block] for block in blocks],
        constraint_config=config,
        hard_constraints=hard_constraints,
        soft_constraints=soft_constraints,
    )
    model.build_model()

    logger.info("Step 5: Solving")
    result: SolveResult = model.solve()

    # Step 5.5: Verify produced roster against hard constraints
    logger.info("Step 5.5: Verifying produced roster")
    from verify import verify as _verify
    block_strings = [[str(d) for d in block] for block in blocks]
    vr = _verify(result, staff_list, definitions, positions, block_strings)
    if vr.violations:
        for v in vr.violations:
            logger.error(
                "VERIFIER VIOLATION [%s]: %s — %s",
                v.constraint_id, v.staff_name or "(system)", v.message,
            )
        # Add violations to result for HTML Messages section
        result.violations = [
            {"constraint_id": v.constraint_id, "staff_name": v.staff_name,
             "date": v.date, "message": v.message}
            for v in vr.violations
        ]
        logger.error(
            "Verifier found %d hard constraint violation(s) — see log for details",
            len(vr.violations),
        )
    else:
        logger.info(
            "Verifier passed: %d checks, %d violations",
            vr.checks_run, len(vr.violations),
        )

    # Step 6: Generate output
    logger.info("Step 6: Generating output")
    from output import generate_html
    generate_html(result, staff_list, definitions,
                  roster_start, roster_end, blocks, run_id,
                  positions=positions,
                  hard_constraints=hard_constraints,
                  soft_constraints=soft_constraints)

    logger.info("Run complete. Output: %s", OUTPUT_DIR)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
