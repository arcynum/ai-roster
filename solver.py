#!/usr/bin/env python3
"""
ai-roster - OR-Tools CP-SAT model builder.

Provides:
- RosterModel: builds the CP-SAT model with variables, constraints, and
  the weighted objective function.
- SolveResult: holds solver output (status, objective value, assignments).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from constraints import HARD_CONSTRAINTS, SOFT_CONSTRAINTS
from models import RosterSlot
from utils import SCALE

if TYPE_CHECKING:
    from models import Staff, RosterPosition


logger = logging.getLogger("ai-roster")


@dataclass
class SolveResult:
    """Result from running the CP-SAT solver.

    Attributes:
        status: CP-SAT solver status string.
        objective_value: Value of the objective function.
        solve_time_s: Time spent solving (seconds).
        assignments: List of resolved RosterSlot assignments.
        unfilled: List of positions that could not be filled.
        staff_hours: Dict of staff_name -> total paid hours for the period.
    """
    status: str = ""
    objective_value: int = 0
    solve_time_s: float = 0.0
    assignments: list[RosterSlot] = field(default_factory=list)
    unfilled: list[dict] = field(default_factory=list)
    staff_hours: dict[str, float] = field(default_factory=dict)


class RosterModel:
    """Builds and solves the CP-SAT roster model.

    Attributes:
        model: The CP-SAT CpModel instance.
        solver: The CpSolver instance.
        staff_list: All staff members.
        positions: All roster positions across the period.
        definitions: Shift definitions.
        weights: Soft constraint weights.
        blocks: 14-day date blocks.
    """

    def __init__(
        self,
        staff_list: list["Staff"],
        positions: list[dict],
        definitions: dict,
        weights: dict[str, int],
        blocks: list[list[str]],
        constraint_config: dict | None = None,
    ):
        self.staff_list = staff_list
        self.positions = positions
        self.definitions = definitions
        self.weights = weights
        self.blocks = blocks
        self.constraint_config = constraint_config

        # Derived lookups
        self.staff_by_name: dict[str, Staff] = {s.name: s for s in staff_list}
        self.staff_names: list[str] = [s.name for s in staff_list]
        self.staff_index: dict[str, int] = {name: i for i, name in enumerate(self.staff_names)}
        self.all_dates: list[str] = sorted(set(p["date"] for p in positions))
        self.num_dates = len(self.all_dates)
        self.date_index: dict[str, int] = {d: i for i, d in enumerate(self.all_dates)}

        # Positions grouped by date
        self.positions_by_date: dict[str, list[int]] = {}
        for i, pos in enumerate(positions):
            self.positions_by_date.setdefault(pos["date"], []).append(i)

        # For each date, the list of position indices (for "at most one shift per day")
        self.position_indices: list[int] = list(range(len(positions)))

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Decision variables (populated by build_model)
        # assignments[staff_idx][pos_idx] -> BoolVar
        self._assignment_vars: list[list[cp_model.IntVar]] = []
        # staff_hours_vars[staff_idx][block_idx] -> IntVar (scaled hours)
        self._staff_hours_vars: list[list[cp_model.IntVar]] = []

    def build_model(self) -> None:
        """Build the full CP-SAT model: variables, constraints, objective."""
        logger.info("Building CP-SAT model: %d staff, %d positions, %d blocks",
                    len(self.staff_list), len(self.positions), len(self.blocks))

        self._create_variables()
        self._apply_hard_constraints()
        self._apply_soft_constraints()

    def _create_variables(self) -> None:
        """Create CP-SAT decision variables.

        For each (staff, position) pair, create a boolean variable indicating
        whether that staff member is assigned to that position.

        For each (staff, block), create an integer variable for total paid hours.
        """
        num_staff = len(self.staff_names)
        num_positions = len(self.positions)
        num_blocks = len(self.blocks)

        # --- Assignment BoolVars ---
        # _assignment_vars[staff_idx][pos_idx] = BoolVar
        for si in range(num_staff):
            row: list[cp_model.IntVar] = []
            for pi in range(num_positions):
                var = self.model.NewBoolVar(f"x_{self.staff_names[si]}_{pi}")
                row.append(var)
            self._assignment_vars.append(row)

        # --- Exactly one staff per position ---
        for pi in range(num_positions):
            staff_vars = [self._assignment_vars[si][pi] for si in range(num_staff)]
            self.model.Add(sum(staff_vars) == 1)

        # --- At most one shift per staff per date ---
        for si in range(num_staff):
            for date_str in self.all_dates:
                pos_indices = self.positions_by_date.get(date_str, [])
                if pos_indices:
                    day_vars = [self._assignment_vars[si][pi] for pi in pos_indices]
                    self.model.Add(sum(day_vars) <= 1)

        # --- Staff hours per block (scaled integers) ---
        for si in range(num_staff):
            block_vars: list[cp_model.IntVar] = []
            for bi in range(num_blocks):
                block_dates = set(self.blocks[bi])
                # Sum paid_hours (scaled) for all positions this staff could take in this block
                hour_vars = []
                for pi, pos in enumerate(self.positions):
                    if pos["date"] in block_dates:
                        shift_paid = self.definitions[pos["shift"]]["paid_hours"]
                        scaled_paid = int(round(shift_paid * SCALE))
                        hour_vars.append(scaled_paid * self._assignment_vars[si][pi])
                if hour_vars:
                    total = self.model.NewIntVar(0, 76 * SCALE, f"hours_{self.staff_names[si]}_b{bi}")
                    self.model.Add(total == sum(hour_vars))
                    block_vars.append(total)
                else:
                    zero = self.model.NewIntVar(0, 0, f"hours_{self.staff_names[si]}_b{bi}")
                    block_vars.append(zero)
            self._staff_hours_vars.append(block_vars)

        logger.info("Created %d assignment BoolVars, %d staff-hour IntVars",
                     num_staff * num_positions, num_staff * num_blocks)

    def _apply_hard_constraints(self) -> None:
        """Apply hard constraints to the model, filtered by config."""
        enabled_ids: set[str] | None = None
        if self.constraint_config is not None:
            enabled_ids = set(self.constraint_config.get("hard", {}).get("enabled", []))

        applied = 0
        skipped = 0
        for constraint_cls in HARD_CONSTRAINTS:
            cid = constraint_cls.constraint_id
            if enabled_ids is not None and cid not in enabled_ids:
                logger.debug("Skipping disabled hard constraint %s", cid)
                skipped += 1
                continue
            constraint = constraint_cls()
            logger.debug("Applying hard constraint %s", cid)
            constraint.apply(
                model=self.model,
                staff_list=self.staff_list,
                staff_by_name=self.staff_by_name,
                assignments=self._assignment_vars,
                staff_names=self.staff_names,
                definitions=self.definitions,
                all_dates=self.all_dates,
                blocks=self.blocks,
                positions=self.positions,
            )
            applied += 1

        logger.info("Hard constraints: %d applied, %d skipped", applied, skipped)

    def _apply_soft_constraints(self) -> None:
        """Apply soft constraints as objective penalties, filtered by config."""
        enabled_ids: set[str] | None = None
        if self.constraint_config is not None:
            enabled_ids = set(self.constraint_config.get("soft", {}).get("enabled", []))

        applied = 0
        skipped = 0
        for constraint_cls in SOFT_CONSTRAINTS:
            cid = constraint_cls.constraint_id
            if enabled_ids is not None and cid not in enabled_ids:
                logger.debug("Skipping disabled soft constraint %s", cid)
                skipped += 1
                continue
            constraint = constraint_cls()
            weight = self.weights.get(cid, 1)
            logger.debug("Applying soft constraint %s (weight=%d)", cid, weight)
            constraint.apply(
                model=self.model,
                staff_list=self.staff_list,
                staff_by_name=self.staff_by_name,
                assignments=self._assignment_vars,
                staff_names=self.staff_names,
                definitions=self.definitions,
                all_dates=self.all_dates,
                blocks=self.blocks,
                positions=self.positions,
                weight=weight,
            )
            applied += 1

        logger.info("Soft constraints: %d applied, %d skipped", applied, skipped)

    def solve(self) -> SolveResult:
        """Run the CP-SAT solver and return the result.

        Returns:
            SolveResult with status, objective, assignments, etc.
        """
        logger.info("Running CP-SAT solver...")
        self.solver.parameters.max_time_in_seconds = 300.0  # 5 minute limit
        self.solver.parameters.num_workers = 8

        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "MODEL_INVALID",
        }

        solve_start = time.perf_counter()
        status = self.solver.Solve(self.model)
        solve_time = time.perf_counter() - solve_start

        status_str = status_map.get(status, f"UNKNOWN({status})")
        obj_val = int(self.solver.ObjectiveValue())

        logger.info("Solver status: %s, objective: %d, time: %.2fs",
                    status_str, obj_val, solve_time)

        result = SolveResult(
            status=status_str,
            objective_value=obj_val,
            solve_time_s=solve_time,
        )

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self._extract_assignments(result)
        else:
            logger.error("Solver did not find a valid solution")

        return result

    def _extract_assignments(self, result: SolveResult) -> None:
        """Extract assignment values from the solver solution.

        Reads BoolVar values to build RosterSlot list and track unfilled positions.
        Also computes staff hours for the result.
        """
        num_positions = len(self.positions)
        num_staff = len(self.staff_names)
        unfilled_set: set[int] = set(range(num_positions))

        for si in range(num_staff):
            for pi in range(num_positions):
                if self.solver.Value(self._assignment_vars[si][pi]) == 1:
                    pos = self.positions[pi]
                    result.assignments.append(RosterSlot(
                        staff_name=self.staff_names[si],
                        date=pos["date"],
                        shift=pos["shift"],
                        required_skill_level=pos.get("required_skill_level"),
                    ))
                    unfilled_set.discard(pi)

        # Build unfilled list
        for pi in unfilled_set:
            pos = self.positions[pi]
            result.unfilled.append({
                "date": pos["date"],
                "shift": pos["shift"],
                "required_skill_level": pos.get("required_skill_level"),
            })

        # Compute staff hours from assignments
        for slot in result.assignments:
            paid = self.definitions[slot.shift]["paid_hours"]
            result.staff_hours[slot.staff_name] = (
                result.staff_hours.get(slot.staff_name, 0) + paid
            )

        logger.info("Extracted %d assignments, %d unfilled positions",
                     len(result.assignments), len(result.unfilled))
