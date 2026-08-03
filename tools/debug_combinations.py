import datetime
from typing import List, Dict, Optional, Set, Tuple
from ortools.sat.python import cp_model
from models import (
    ShiftDefinition,
    ShiftRequirement,
    Rule,
    Preference,
    StaffMember,
    TRAINING_MAP,
    get_shift_times_helper
)

# Mocking the build process to test constraints
def test_with_constraints(disable_rest=False, disable_transition=False, disable_consecutive=False, disable_training=False, disable_max_hours=False):
    from build_roster import parse_definitions, parse_roster, parse_staff, parse_rules_and_prefs
    
    try:
        with open("definitions.md", "r") as f: defs = parse_definitions(f.read())
        with open("roster.yaml", "r") as f: 
            start_date, end_date, reqs = parse_roster_yaml(f.read())
        with open("staff.md", "r") as f: staff = parse_staff(f.read())
        with open("hard_constraints.md", "r") as f: global_rules, _ = parse_rules_and_prefs(f.read(), "")
        with open("soft_constraints.md", "r") as f: _, global_prefs = parse_rules_and_prefs("", f.read())

        model = cp_model.CpModel()
        staff_indices = range(len(staff))
        day_indices = range((end_date - start_date).days + 1)
        shift_names = list(defs.keys())
        SCALE = 100
        
        x = {}
        for s in staff_indices:
            for d in day_indices:
                for h_name in shift_names:
                    x[s, d, h_name] = model.NewBoolVar(f'x_{s}_{d}_{h_name}')

        # 1. Requirements (HARD)
        for d_idx in day_indices:
            date = start_date + datetime.timedelta(days=d_idx)
            day_name = date.strftime("%A")
            day_reqs = reqs.get(day_name, [])
            for req in day_reqs:
                model.Add(sum(x[s, d_idx, req.shift_name] for s in staff_indices) == req.count)

        # 0. One Shift Per Day (HARD)
        for s in staff_indices:
            for d in day_indices:
                model.Add(sum(x[s, d, h] for h in shift_names) <= 1)

        # Graduate Constraint (HARD)
        graduate_allowed_shifts = {"D8", "P8", "L3", "DISCO", "N8"}
        for s in staff_indices:
            if staff[s].level == "Graduate":
                for d in day_indices:
                    for h_name in shift_names:
                        if h_name not in graduate_allowed_shifts:
                            model.Add(x[s, d, h_name] == 0)

        # Training Requirements (D12/N12)
        if not disable_training:
            for d_idx in day_indices:
                date = start_date + datetime.timedelta(days=d_idx)
                day_name = date.strftime("%A")
                for target_shift in ["D12", "N12"]:
                    if any(r.shift_name == target_shift for r in reqs.get(day_name, [])):
                        model.Add(sum(x[s, d_idx, target_shift] for s in staff_indices if staff[s].level == "CN") >= 1)
                        model.Add(sum(x[s, d_idx, target_shift] for s in staff_indices if TRAINING_MAP.get(staff[s].training_level, 0) == 4) >= 1)
                        model.Add(sum(x[s, d_idx, target_shift] for s in staff_indices if TRAINING_MAP.get(staff[s].training_level, 0) == 3) >= 1)
                        model.Add(sum(x[s, d_idx, target_shift] for s in staff_indices if TRAINING_MAP.get(staff[s].training_level, 0) == 2) >= 1)

        # Max Hours (HARD)
        if not disable_max_hours:
            fortnights_in_roster = len(day_indices) / 14.0
            max_hours_limit = 76 * fortnights_in_roster
            for s in staff_indices:
                total_hours_scaled = sum(x[s, d, h] * int(defs[h].duration * SCALE) for d in day_indices for h in shift_names)
                model.Add(total_hours_scaled <= int(max_hours_limit * SCALE))

        # Red Requests / Holidays (HARD)
        for s in staff_indices:
            staff_m = staff[s]
            for d_idx in day_indices:
                date = start_date + datetime.timedelta(days=d_idx)
                if date in staff_m.red_requests:
                    for h_name in shift_names: model.Add(x[s, d_idx, h_name] == 0)
                for hs, he in staff_m.holidays:
                    if hs <= date <= he:
                        for h_name in shift_names: model.Add(x[s, d_idx, h_name] == 0)

        # Consecutive (HARD)
        if not disable_consecutive:
            for s in staff_indices:
                for h_name in shift_names:
                    for d_idx in range(len(day_indices) - 2):
                        model.Add(x[s, d_idx, h_name] + x[s, d_idx+1, h_name] + x[s, d_idx+2, h_name] <= 2)

        # Night/Day Transition (HARD)
        if not disable_transition:
            night_shifts = [h for h in shift_names if h in ["N8", "N12"]]
            day_shifts = [h for h in shift_names if h not in night_shifts]
            for s in staff_indices:
                for d_idx in range(len(day_indices) - 1):
                    for h_night in night_shifts:
                        for h_day in day_shifts:
                            model.AddForbiddenAssignments([x[s, d_idx, h_night], x[s, d_idx+1, h_day]], [(1, 1)])
                            model.AddForbiddenAssignments([x[s, d_idx, h_day], x[s, d_idx+1, h_night]], [(1, 1)])

        # Rest Period (HARD)
        if not disable_rest:
            for s in staff_indices:
                for d1_idx in day_indices:
                    date1 = start_date + datetime.timedelta(days=d1_idx)
                    for h1_name in shift_names:
                        sd1 = defs[h1_name]
                        for d2_idx in day_indices:
                            if d1_idx == d2_idx: continue
                            if abs(d1_idx - d2_idx) > 1: continue
                            date2 = start_date + datetime.timedelta(days=d2_idx)
                            for h2_name in shift_names:
                                sd2 = defs[h2_name]
                                start1 = datetime.datetime.combine(date1, sd1.start_dt)
                                end1 = datetime.datetime.combine(date1, sd1.end_dt)
                                if sd1.crosses_midnight: end1 += datetime.timedelta(days=1)
                                start2 = datetime.datetime.combine(date2, sd2.start_dt)
                                end2 = datetime.datetime.combine(date2, sd2.end_dt)
                                if sd2.crosses_midnight: end2 += datetime.timedelta(days=1)
                                
                                overlap = not (end1 <= start2 or end2 <= start1)
                                gap_seconds = 0
                                if not overlap:
                                    if start1 >= end2: gap_seconds = (start1 - end2).total_seconds()
                                    elif start2 >= end1: gap_seconds = (start2 - end1).total_seconds()
                                
                                if overlap or gap_seconds < 11 * 3600:
                                    model.AddForbiddenAssignments([x[s, d1_idx, h1_name], x[s, d2_idx, h2_name]], [(1, 1)])

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)
        return status == cp_model.OPTIMAL or status == cp_model.FEASIBLE

    except Exception as e:
        print(f"Error in test: {e}")
        return False

if __name__ == "__main__":
    print("Testing combinations:")
    print(f"All constraints: {test_with_constraints()}")
    print(f"No training/rest/transition/max_hours: {test_with_constraints(disable_rest=True, disable_transition=True, disable_training=True, disable_max_hours=True)}")
    print(f"No transition: {test_with_constraints(disable_transition=True)}")
    print(f"No rest: {test_with_constraints(disable_rest=True)}")
    print(f"No training constraints: {test_with_constraints(disable_training=True)}")
    print(f"No max hours: {test_with_constraints(disable_max_hours=True)}")
