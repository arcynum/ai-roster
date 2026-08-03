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
    ):
        self.staff_list = staff_list
        self.positions = positions
        self.definitions = definitions
        self.weights = weights
        self.blocks = blocks

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()

        # Decision variables (populated by build_model)
        self._assignment_vars: dict = {}  # (staff_name, date, shift) -> BoolVar
        self._staff_hours_vars: dict = {}  # staff_name -> IntVar (scaled hours)

    def build_model(self) -> None:
        """Build the full CP-SAT model: variables, constraints, objective."""
        logger.info("Building CP-SAT model: %d staff, %d positions, %d blocks",
                    len(self.staff_list), len(self.positions), len(self.blocks))

        self._create_variables()
        self._apply_hard_constraints()
        self._apply_soft_constraints()

    def _create_variables(self) -> None:
        """Create CP-SAT decision variables.

        For each (staff, date, shift) combination, create a boolean variable
        indicating whether that staff member is assigned to that position.
        """
        # TODO: create assignment BoolVars for all (staff, position) pairs
        pass

    def _apply_hard_constraints(self) -> None:
        """Apply all hard constraints to the model."""
        for constraint_cls in HARD_CONSTRAINTS:
            constraint = constraint_cls()
            logger.debug("Applying hard constraint %s", constraint.constraint_id)
            constraint.apply(
                model=self.model,
                staff_list=self.staff_list,
                assignments=self._assignment_vars,
                definitions=self.definitions,
            )

    def _apply_soft_constraints(self) -> None:
        """Apply all soft constraints as objective penalties."""
        for constraint_cls in SOFT_CONSTRAINTS:
            constraint = constraint_cls()
            weight = self.weights.get(constraint.constraint_id, 1)
            logger.debug("Applying soft constraint %s (weight=%d)",
                         constraint.constraint_id, weight)
            constraint.apply(
                model=self.model,
                staff_list=self.staff_list,
                assignments=self._assignment_vars,
                definitions=self.definitions,
                weight=weight,
            )

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

        solution_start = self.solver.wall_time()
        status = self.solver.Solve(self.model)
        solve_time = self.solver.wall_time() - solution_start

        status_str = status_map.get(status, f"UNKNOWN({status})")
        obj_val = self.solver.ObjectiveValue

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
        """Extract assignment values from the solver solution."""
        # TODO: read BoolVar values and build RosterSlot list
        pass
