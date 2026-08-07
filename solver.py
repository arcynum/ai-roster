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
from utils import (
    NIGHT_SHIFTS,
    REST_PERIOD_SECONDS,
    SCALE,
    SHIFT_ORDER,
    build_merged_compatibility_table,
)

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
        shortfall: Dict of staff_name -> {block_key: hours under contracted floor}.
        soft_penalty: Dict of constraint_id -> total penalty incurred.
        hard_constraints: List of hard constraint records (for HTML output).
        soft_constraints: List of soft constraint records (for HTML output).
        violations: List of hard-constraint violations from the verifier.
    """
    status: str = ""
    objective_value: int = 0
    solve_time_s: float = 0.0
    assignments: list[RosterSlot] = field(default_factory=list)
    unfilled: list[dict] = field(default_factory=list)
    staff_hours: dict[str, float] = field(default_factory=dict)
    shortfall: dict[str, dict[str, float]] = field(default_factory=dict)
    soft_penalty: dict[str, float] = field(default_factory=dict)
    hard_constraints: list[dict] = field(default_factory=list)
    soft_constraints: list[dict] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)


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

    # Unfilled tier weight IDs — used by _apply_coverage_constraint.
    # These must have entries in weights.yaml (validated at startup).
    # Bracketed to match the convention used for all constraint_id attributes.
    UNFILLED_TIER_IDS: tuple[str, ...] = (
        "[S#e7f3a2b1]",  # skill-required
        "[S#f1a2b3c4]",  # Sunday, General
        "[S#a2b3c4d5]",  # Saturday, General
        "[S#b3c4d5e6]",  # weekday day, General
        "[S#c4d5e6f7]",  # weekday night, General
    )

    def __init__(
        self,
        staff_list: list["Staff"],
        positions: list[dict],
        definitions: dict,
        weights: dict[str, int],
        blocks: list[list[str]],
        constraint_config: dict | None = None,
        hard_constraints: list[dict] | None = None,
        soft_constraints: list[dict] | None = None,
    ):
        self.staff_list = staff_list
        self.positions = positions
        self.definitions = definitions
        self.weights = weights
        self.blocks = blocks
        self.constraint_config = constraint_config
        self._hard_constraints = hard_constraints or []
        self._soft_constraints = soft_constraints or []

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
        # unfilled_vars[pos_idx] -> BoolVar (populated by _create_variables)
        self._unfilled_vars: list[cp_model.IntVar] = []
        # shortfall_vars[staff_idx][block_idx] -> IntVar (populated by ContractedHoursFloorSoft)
        self._shortfall_vars: list[list[cp_model.IntVar]] = []
        # soft_penalty_vars[cid] -> IntVar for reading back penalty values
        self._soft_penalty_vars: dict[str, cp_model.IntVar] = {}
        # objective_terms — collected penalty terms for the combined objective
        self._objective_terms: list[cp_model.IntVar] = []

        # §3.1 Shared shift-type indicator variables
        # works[staff_idx][date_idx][shift_idx] -> BoolVar
        #   shift_idx 0-7 for actual shifts, 8 = "unassigned"
        self.works: list[list[cp_model.IntVar]] = []
        # works_any[staff_idx][date_idx] -> BoolVar
        self.works_any: list[list[cp_model.IntVar]] = []
        # category[staff_idx][date_idx] -> IntVar 0=day, 1=night, 2=off
        self.category: list[list[cp_model.IntVar]] = []

    def build_model(self) -> None:
        """Build the full CP-SAT model: variables, constraints, objective."""
        logger.info("Building CP-SAT model: %d staff, %d positions, %d blocks",
                    len(self.staff_list), len(self.positions), len(self.blocks))

        self._create_variables()
        self._apply_hard_constraints()
        self._apply_soft_constraints()

        # Build combined objective from all collected penalty terms
        if self._objective_terms:
            self.model.Minimize(sum(self._objective_terms))

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

        # --- Unfilled slack variables for every position ---
        # These allow positions to be left unfilled (feasible solve) rather than
        # making the model infeasible. The CoverageConstraint adds the actual
        # coverage constraint per position, incorporating unfilled vars.
        self._unfilled_vars: list[cp_model.IntVar] = []
        for pi in range(num_positions):
            unfilled = self.model.NewBoolVar(f"unfilled_{pi}")
            self._unfilled_vars.append(unfilled)

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

        # --- §3.1 Shared shift-type indicator variables ---
        # works[si][di][shift_idx] : BoolVar, 1 iff staff si works shift shift_idx on date di
        # shift_idx 0-7 maps to SHIFT_ORDER; 8 = "unassigned"
        # works_any[si][di]        : BoolVar, 1 iff staff si works any shift on date di
        # category[si][di]         : IntVar, 0=day, 1=night, 2=off

        num_shift_types = len(SHIFT_ORDER)  # 8
        UNASSIGNED = num_shift_types  # 8

        for si in range(num_staff):
            works_row: list[cp_model.IntVar] = []
            works_any_row: list[cp_model.IntVar] = []
            category_row: list[cp_model.IntVar] = []

            for di, date_str in enumerate(self.all_dates):
                pos_indices = self.positions_by_date.get(date_str, [])

                # Create BoolVars for each shift type on this date
                shift_bools: list[cp_model.IntVar] = []
                for sh_idx in range(num_shift_types):
                    # Determine which positions have this shift type on this date
                    pos_with_shift = [
                        pi for pi in pos_indices
                        if self.positions[pi]["shift"] == SHIFT_ORDER[sh_idx]
                    ]
                    if pos_with_shift:
                        # Shift BoolVar: 1 iff any assignment for this shift is 1
                        sb = self.model.NewBoolVar(
                            f"works_{self.staff_names[si]}_d{di}_s{sh_idx}"
                        )
                        shift_bools.append(sb)
                        # Channel: sb=1 iff sum(assignments for this shift) >= 1
                        assign_vars = [self._assignment_vars[si][pi] for pi in pos_with_shift]
                        self.model.Add(sum(assign_vars) >= 1).OnlyEnforceIf(sb)
                        self.model.Add(sum(assign_vars) == 0).OnlyEnforceIf(sb.Not())
                    else:
                        # No positions of this shift type on this date — always 0
                        sb = self.model.NewBoolVar(
                            f"works_{self.staff_names[si]}_d{di}_s{sh_idx}"
                        )
                        self.model.Add(sb == 0)
                        shift_bools.append(sb)

                # works_any[si][di]: 1 iff staff works any shift on this date
                wa = self.model.NewBoolVar(f"works_any_{self.staff_names[si]}_d{di}")
                self.model.Add(sum(shift_bools) >= 1).OnlyEnforceIf(wa)
                self.model.Add(sum(shift_bools) == 0).OnlyEnforceIf(wa.Not())

                # category[si][di]: IntVar 0=day, 1=night, 2=off
                cat = self.model.NewIntVar(0, 2, f"cat_{self.staff_names[si]}_d{di}")

                # Day shifts: indices 0-5 (D8, D12, P8, P12, L3, DISCO)
                day_bool = self.model.NewBoolVar(f"day_{self.staff_names[si]}_d{di}")
                day_works = shift_bools[:num_shift_types - 2]  # first 6 = day shifts
                if day_works:
                    self.model.Add(sum(day_works) >= 1).OnlyEnforceIf(day_bool)
                    self.model.Add(sum(day_works) == 0).OnlyEnforceIf(day_bool.Not())
                else:
                    self.model.Add(day_bool == 0)
                self.model.Add(cat == 0).OnlyEnforceIf(day_bool)
                self.model.Add(cat != 0).OnlyEnforceIf(day_bool.Not())

                # Night shifts: indices 6-7 (N8, N12)
                night_bool = self.model.NewBoolVar(f"night_{self.staff_names[si]}_d{di}")
                night_works = shift_bools[-2:]  # last 2 = night shifts
                if night_works:
                    self.model.Add(sum(night_works) >= 1).OnlyEnforceIf(night_bool)
                    self.model.Add(sum(night_works) == 0).OnlyEnforceIf(night_bool.Not())
                else:
                    self.model.Add(night_bool == 0)
                self.model.Add(cat == 1).OnlyEnforceIf(night_bool)
                self.model.Add(cat != 1).OnlyEnforceIf(night_bool.Not())

                # Off: neither day nor night
                self.model.Add(cat == 2).OnlyEnforceIf(day_bool.Not(), night_bool.Not())

                works_row.extend(shift_bools)
                works_any_row.append(wa)
                category_row.append(cat)

            self.works.append(works_row)
            self.works_any.append(works_any_row)
            self.category.append(category_row)

        # Store on CpModel for constraint access (same pattern as _merged_compat)
        self.model._works = self.works
        self.model._works_any = self.works_any
        self.model._category = self.category

        logger.info("Created %d assignment BoolVars, %d staff-hour IntVars",
                      num_staff * num_positions, num_staff * num_blocks)
        logger.info("Created §3.1 shared indicator vars: works (%d), works_any (%d), category (%d)",
                      num_staff * self.num_dates * num_shift_types,
                      num_staff * self.num_dates,
                      num_staff * self.num_dates)

    def _apply_hard_constraints(self) -> None:
        """Apply hard constraints to the model, filtered by config.

        §3.1: Builds the merged compatibility table (rest + night/day) once
        at startup and attaches it to the model. NoDoubleBooking is skipped
        when RestPeriodConstraint is enabled (redundant).
        """
        enabled_ids: set[str] | None = None
        if self.constraint_config is not None:
            raw = self.constraint_config.get("hard", {}).get("enabled")
            if raw is not None and len(raw) > 0:
                enabled_ids = set(raw)
            # If raw is None or empty list, enabled_ids stays None → all
            # constraints enabled (empty list = section present but no entries
            # uncommented, which should behave identically to absent section).

        # §3.1: Build merged compatibility table once at startup
        # AND-ed table of RestPeriodConstraint + NightToDayRest
        # (NoDoubleBooking is redundant with RestPeriodConstraint)
        rest_enabled = (enabled_ids is None or "[H#c1f6e3f5]" in enabled_ids)
        night_day_enabled = (enabled_ids is None or "[H#f4c9b6c8]" in enabled_ids)
        if rest_enabled and night_day_enabled:
            self.model._merged_compat = build_merged_compatibility_table(self.definitions)
            logger.debug("Built merged compatibility table (rest + night/day) for §3.1")
        elif rest_enabled:
            # Only rest period — build rest-only table (8×8, missing shifts = False)
            from datetime import datetime, timedelta
            n = len(SHIFT_ORDER)
            compat = [[True] * n for _ in range(n)]
            for a_idx, shift_a in enumerate(SHIFT_ORDER):
                for b_idx, shift_b in enumerate(SHIFT_ORDER):
                    if shift_a not in self.definitions or shift_b not in self.definitions:
                        compat[a_idx][b_idx] = False
                        continue
                    a_end_str = self.definitions[shift_a]["end"]
                    a_crosses = self.definitions[shift_a]["crosses_midnight"]
                    b_start_str = self.definitions[shift_b]["start"]
                    a_end = datetime.strptime(a_end_str, "%H:%M:%S")
                    b_start = datetime.strptime(b_start_str, "%H:%M:%S")
                    a_end_abs = a_end + timedelta(days=1 if a_crosses else 0)
                    b_start_abs = b_start + timedelta(days=1)
                    gap = (b_start_abs - a_end_abs).total_seconds()
                    compat[a_idx][b_idx] = gap >= REST_PERIOD_SECONDS
            self.model._merged_compat = compat
            logger.debug("Built rest-only compatibility table for §3.1")
        elif night_day_enabled:
            # Only night/day — build night/day-only table (8×8, missing shifts = False)
            n = len(SHIFT_ORDER)
            compat = [[True] * n for _ in range(n)]
            for a_idx, shift_a in enumerate(SHIFT_ORDER):
                for b_idx, shift_b in enumerate(SHIFT_ORDER):
                    if shift_a not in self.definitions or shift_b not in self.definitions:
                        compat[a_idx][b_idx] = False
                        continue
                    a_is_night = shift_a in NIGHT_SHIFTS
                    b_is_night = shift_b in NIGHT_SHIFTS
                    if a_is_night != b_is_night:
                        compat[a_idx][b_idx] = False
            self.model._merged_compat = compat
            logger.debug("Built night/day-only compatibility table for §3.1")
        # else: neither is enabled, no table needed

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
            result = constraint.apply(
                model=self.model,
                staff_list=self.staff_list,
                staff_by_name=self.staff_by_name,
                assignments=self._assignment_vars,
                staff_names=self.staff_names,
                definitions=self.definitions,
                all_dates=self.all_dates,
                blocks=self.blocks,
                positions=self.positions,
                staff_hours_vars=self._staff_hours_vars,
                unfilled_vars=self._unfilled_vars,
            )
            # Collect penalty terms returned by hard constraints (e.g. Coverage)
            if isinstance(result, list) and result:
                self._objective_terms.extend(result)
            applied += 1

        # Warn if 0 hard constraints were enabled (likely a config error)
        if applied == 0 and enabled_ids is not None:
            logger.warning(
                "No hard constraints enabled — this is likely a configuration error. "
                "The roster will have no safety constraints."
            )

        logger.info("Hard constraints: %d applied, %d skipped", applied, skipped)

    def _apply_soft_constraints(self) -> None:
        """Apply soft constraints as objective penalties, filtered by config."""
        enabled_ids: set[str] | None = None
        if self.constraint_config is not None:
            raw = self.constraint_config.get("soft", {}).get("enabled", [])
            if raw is not None and len(raw) > 0:
                enabled_ids = set(raw)

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
            apply_kwargs = dict(
                model=self.model,
                staff_list=self.staff_list,
                staff_by_name=self.staff_by_name,
                assignments=self._assignment_vars,
                staff_names=self.staff_names,
                definitions=self.definitions,
                all_dates=self.all_dates,
                blocks=self.blocks,
                positions=self.positions,
                staff_hours_vars=self._staff_hours_vars,
                weight=weight,
                objective_terms=self._objective_terms,
            )
            penalty_var = constraint.apply(**apply_kwargs)
            # Capture shortfall_vars from the soft floor constraint
            if hasattr(constraint, "_shortfall_vars"):
                self._shortfall_vars = constraint._shortfall_vars
            # Store returned penalty var for reading back after solve
            if penalty_var is not None:
                self._soft_penalty_vars[cid] = penalty_var
            applied += 1

        logger.info("Soft constraints: %d applied, %d skipped", applied, skipped)

    def solve(self) -> SolveResult:
        """Run the CP-SAT solver and return the result.

        Returns:
            SolveResult with status, objective, assignments, etc.
        """
        logger.info("Running CP-SAT solver...")

        # Source solver parameters from config (D6), with sensible defaults
        solver_config = (self.constraint_config or {}).get("solver", {})
        max_time = solver_config.get("max_time_in_seconds", 300.0)
        num_workers = solver_config.get("num_workers", 8)
        random_seed = solver_config.get("random_seed")

        self.solver.parameters.max_time_in_seconds = max_time
        self.solver.parameters.num_workers = num_workers
        if random_seed is not None:
            self.solver.parameters.random_seed = random_seed

        # Capture CP-SAT search log to the run log (AGENTS.md §6)
        self.solver.parameters.log_search_progress = True
        self.solver.log_callback = lambda line: logger.debug("cp-sat: %s", line)

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
        obj_val = int(self.solver.ObjectiveValue()) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0

        logger.info("Solver status: %s, objective: %d, time: %.2fs",
                    status_str, obj_val, solve_time)

        result = SolveResult(
            status=status_str,
            objective_value=obj_val,
            solve_time_s=solve_time,
            hard_constraints=self._hard_constraints,
            soft_constraints=self._soft_constraints,
        )

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self._extract_assignments(result)
        else:
            logger.error("Solver did not find a valid solution (status=%s)", status_str)

        return result

    def _extract_assignments(self, result: SolveResult) -> None:
        """Extract assignment values from the solver solution.

        Reads BoolVar values to build RosterSlot list and track unfilled positions.
        Also computes staff hours and shortfall for the result.
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
                        slot_id=pos.get("slot_id"),
                    ))
                    unfilled_set.discard(pi)

        # Build unfilled list
        for pi in unfilled_set:
            pos = self.positions[pi]
            result.unfilled.append({
                "date": pos["date"],
                "shift": pos["shift"],
                "required_skill_level": pos.get("required_skill_level"),
                "slot_id": pos.get("slot_id"),
            })

        # Compute staff hours from assignments
        for slot in result.assignments:
            paid = self.definitions[slot.shift]["paid_hours"]
            result.staff_hours[slot.staff_name] = (
                result.staff_hours.get(slot.staff_name, 0) + paid
            )

        # Read back shortfall values per staff per block
        if self._shortfall_vars:
            for si, staff in enumerate(self.staff_list):
                staff_shortfall: dict[str, float] = {}
                for bi in range(len(self.blocks)):
                    if si < len(self._shortfall_vars) and bi < len(self._shortfall_vars[si]):
                        var = self._shortfall_vars[si][bi]
                        val = self.solver.Value(var)
                        block_key = f"b{bi}"
                        staff_shortfall[block_key] = val / SCALE
                result.shortfall[staff.name] = staff_shortfall

        # Read back soft-constraint penalty values (no / SCALE — penalties are whole numbers after §2.3)
        for cid, var in self._soft_penalty_vars.items():
            result.soft_penalty[cid] = self.solver.Value(var)

        logger.info("Extracted %d assignments, %d unfilled positions",
                       len(result.assignments), len(result.unfilled))
