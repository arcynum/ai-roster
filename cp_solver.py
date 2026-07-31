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

class CPSolver:
    def __init__(self, start_date, days_count, definitions, roster_reqs, staff, rules=None, preferences=None):
        self.start_date = start_date
        self.days_count = days_count
        self.definitions = definitions
        self.roster_reqs = roster_reqs
        self.staff = staff
        self.rules = rules or []
        self.preferences = preferences or []
        self.dates = [start_date + datetime.timedelta(days=i) for i in range(days_count)]
        self.assignments = []
        
        # Scaling factor for floats to integers
        self.SCALE = 100

    def solve(self):
        model = cp_model.CpModel()
        
        # Pre-processing: mapping indices
        staff_indices = range(len(self.staff))
        day_indices = range(self.days_count)
        shift_names = list(self.definitions.keys())
        shift_indices = {name: i for i, name in enumerate(shift_names)}
        print(f"DEBUG: shift_names: {shift_names}")
        print(f"DEBUG: shift_indices: {shift_indices}")
        
        # Decision Variables: x[s, d, h] is 1 if staff s works shift h on day d
        x = {}
        for s in staff_indices:
            for d in day_indices:
                for h_name in shift_names:
                    x[s, d, h_name] = model.NewBoolVar(f'x_{s}_{d}_{h_name}')
                    
        # 1. Requirement Constraint: Sum of staff assigned to shift h on day d must match roster requirements
        for d_idx in day_indices:
            date = self.dates[d_idx]
            day_name = date.strftime("%A")
            reqs = self.roster_reqs.get(day_name, [])
            print(f"DEBUG: day: {date} ({day_name}), reqs: {reqs}")
            
            for req in reqs:
                h_name = req.shift_name
                print(f"DEBUG:   Processing req: {h_name} count {req.count}")
                if h_name in shift_indices:
                    model.Add(sum(x[s, d_idx, h_name] for s in staff_indices) == req.count)
                else:
                    # If requirement is for an unmapped shift, we can't satisfy it with x variables
                    # But in our context, it's likely an UNFILLED placeholder. 
                    # However, the input roster_reqs should only contain valid shift names.
                    print(f"DEBUG:   Warning: {h_name} not in shift_indices")
            
            # 2. One Shift Per Day Constraint
            for s in staff_indices:
                model.Add(sum(x[s, d_idx, h_name] for h_name in shift_names) <= 1)

        # 3. Training and Classification Constraints (Hard Rules)
        # We need to implement these for D12 and N12 as specified in the requirements
        for d_idx in day_indices:
            date = self.dates[d_idx]
            day_name = date.strftime("%A")
            
            # D12 requirements
            d12_reqs = [r for r in self.roster_reqs.get(day_name, []) if r.shift_name == "D12"]
            if d12_reqs:
                # At least one CN
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if self.staff[s].level == "CN") >= 1)
                # At least one Shift Coordinator
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 3) >= 1)
                # At least one Triage
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 2) >= 1)
                # At least one Resus
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 1) >= 1)

            # N12 requirements
            n12_reqs = [r for r in self.roster_reqs.get(day_name, []) if r.shift_name == "N12"]
            if n12_reqs:
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if self.staff[s].level == "CN") >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 3) >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 2) >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) == 1) >= 1)

        # 4. Rest Period Constraint (11 hours)
        # This is complex with CP. We'll use the fact that shifts have fixed times.
        # For each staff member, and every pair of shifts (s1, s2) that overlap or are too close:
        # if s1 and s2 are assigned on consecutive days (or same day), they cannot both be true.
        for s in staff_indices:
            for d1_idx in day_indices:
                date1 = self.dates[d1_idx]
                for h1_name in shift_names:
                    sd1 = self.definitions[h1_name]
                    
                    # We need to check all other assignments that would violate the 11h rule.
                    # To simplify, we check all other shifts (h2) on all days (d2)
                    for d2_idx in day_indices:
                        if d1_idx == d2_idx:
                            # Same day: can't have two shifts. Already covered by "One Shift Per Day"
                            continue
                        
                        date2 = self.dates[d2_idx]
                        # Check if d2 is within the range of possible rest period violation (d1-1, d1, d1+1)
                        if abs(d1_idx - d2_idx) > 1:
                            continue
                            
                        for h2_name in shift_names:
                            sd2 = self.definitions[h2_name]
                            
                            # Get times
                            start1 = datetime.datetime.combine(date1, sd1.start_dt)
                            end1 = datetime.datetime.combine(date1, sd1.end_dt)
                            if sd1.crosses_midnight: end1 += datetime.timedelta(days=1)
                            
                            start2 = datetime.datetime.combine(date2, sd2.start_dt)
                            end2 = datetime.datetime.combine(date2, sd2.end_dt)
                            if sd2.crosses_midnight: end2 += datetime.timedelta(days=1)
                            
                            # Check for overlap or < 11h gap
                            overlap = not (end1 <= start2 or end2 <= start1)
                            gap_too_small = False
                            if not overlap:
                                if start1 >= end2:
                                    if (start1 - end2).total_seconds() < 11 * 3600: gap_too_small = True
                                elif start2 >= end1:
                                    if (start2 - end1).total_seconds() < 11 * 3600: gap_too_small = True
                            
                            if overlap or gap_too_small:
                                model.AddForbiddenAssignments([x[s, d1_idx, h1_name], x[s, d2_idx, h2_name]], [(1, 1)])

        # 5. Consecutive Shift Constraint (max 2 in a row)
        for s in staff_indices:
            for h_name in shift_names:
                for d_idx in range(self.days_count - 2):
                    model.Add(x[s, d_idx, h_name] + x[s, d_idx+1, h_name] + x[s, d_idx+2, h_name] <= 2)

        # 6. Red Requests and Holidays
        for s in staff_indices:
            staff_m = self.staff[s]
            for d_idx in day_indices:
                date = self.dates[d_idx]
                if date in staff_m.red_requests:
                    for h_name in shift_names:
                        model.Add(x[s, d_idx, h_name] == 0)
                
                for h_s, h_e in staff_m.holidays:
                    if h_s <= date <= h_e:
                        for h_name in shift_names:
                            model.Add(x[s, d_idx, h_name] == 0)

        # 7. Max Hours Constraint (76h)
        for s in staff_indices:
            total_hours_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                     for d in day_indices for h_name in shift_names)
            model.Add(total_hours_scaled <= int(76 * self.SCALE))

        # 8. Night/Day Transition Constraint
        # If swapping between night and day, need 1 day off in between.
        night_shifts = [h for h in shift_names if h in ["N8", "N12"]]
        day_shifts = [h for h in shift_names if h not in night_shifts]
        
        for s in staff_indices:
            for d_idx in range(self.days_count - 1):
                # If s works a night shift on day d, and a day shift on day d+1, forbidden.
                for h_night in night_shifts:
                    for h_day in day_shifts:
                        model.AddForbiddenAssignments([x[s, d_idx, h_night], x[s, d_idx+1, h_day]], [(1, 1)])
                        model.AddForbiddenAssignments([x[s, d_idx, h_day], x[s, d_idx+1, h_night]], [(1, 1)])

        # --- OBJECTIVE FUNCTION ---
        # We want to minimize deviations and preference violations.
        
        # Penalties
        penalty_fte = 1000
        penalty_weekend = 100
        penalty_preference = 1
        
        # FTE Deviation
        fte_violations = []
        for s in staff_indices:
            target_fte_scaled = int(self.staff[s].fte_hours * self.SCALE)
            current_fte_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                     for d in day_indices for h_name in shift_names)
            
            # Deviation = max(0, target - current)
            # In CP-SAT, we can use an auxiliary variable for max(0, ...)
            under_fte = model.NewIntVar(0, target_fte_scaled, f'under_fte_{s}')
            model.Add(under_fte >= target_fte_scaled - current_fte_scaled)
            model.Add(under_fte >= 0)
            fte_violations.append(under_fte)

        # Weekend Deviation
        weekend_violations = []
        for s in staff_indices:
            # We want to minimize variance or deviation from a target?
            # The rule says "fair distribution". Let's aim for a target based on FTE.
            # But let's just minimize total weekend hours to keep it simple, 
            # or better, minimize deviation from a target weekend hours.
            # For now, let's just penalize high weekend hours to keep it fair.
            # Actually, the user said "most fair". Let's minimize the difference 
            # between weekend hours and a target (e.g. 20% of total FTE).
            target_weekend_scaled = int((self.staff[s].fte_hours * 0.2) * self.SCALE)
            current_weekend_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE)
                                         for d in day_indices for h_name in shift_names
                                         if self.dates[d].weekday() >= 5)
            
            weekend_under = model.NewIntVar(0, target_weekend_scaled, f'weekend_under_{s}')
            model.Add(weekend_under >= target_weekend_scaled - current_weekend_scaled)
            model.Add(weekend_under >= 0)
            weekend_violations.append(weekend_under)

        # Preference Violations
        pref_violations = []
        for s in staff_indices:
            staff_m = self.staff[s]
            for pref in staff_m.preferences:
                # This is tricky. How to model "Prefers 3 of the same shifts in a row"?
                # For now, let's just support a subset of preferences or skip them if they are too complex for this iteration.
                # For example, "Prefers morning" -> if shift is in [D8, D12, P8, P12, MD, L3, DISCO]
                pass
        
        model.Minimize(penalty_fte * sum(fte_violations) + 
                       penalty_weekend * sum(weekend_violations) +
                       penalty_preference * sum(pref_violations))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 30.0
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for d_idx in day_indices:
                date = self.dates[d_idx]
                is_weekend = date.weekday() >= 5
                for h_name in shift_names:
                    duration = self.definitions[h_name].duration
                    for s in staff_indices:
                        if solver.Value(x[s, d_idx, h_name]) == 1:
                            staff_m = self.staff[s]
                            self.assignments.append((date, h_name, staff_m))
                            staff_m.assigned_shifts.append((date, h_name))
                            staff_m.assigned_hours += duration
                            if is_weekend:
                                staff_m.weekend_hours += duration
            return self.assignments
        else:
            return []

    def get_rule_id(self, rule_id: str) -> str:
        for rule in self.rules:
            if rule.id == rule_id:
                return f"[{rule.id}] "
        return ""

    def get_pref_id(self, pref_id: str) -> str:
        for pref in self.preferences:
            if pref.id == pref_id:
                return f"[{pref.id}] "
        return ""

    def validate_roster(self) -> List[str]:
        # Use the existing validation logic but adapted for the new assignments structure
        # The logic remains largely the same
        violations = []
        daily_assignments = {}
        for date, shift_name, staff_m in self.assignments:
            if date not in daily_assignments:
                daily_assignments[date] = []
            daily_assignments[date].append((shift_name, staff_m))

        d12_cn_id = self.get_rule_id("R#a7f2c9d1")
        d12_coord_id = self.get_rule_id("R#b8e3d0e2")
        d12_triage_id = self.get_rule_id("R#c9f4e1f3")
        d12_resus_id = self.get_rule_id("R#d0a5f2a4")
        n12_cn_id = self.get_rule_id("R#e1b6a3b5")
        n12_coord_id = self.get_rule_id("R#f2c7b4c6")
        n12_triage_id = self.get_rule_id("R#a3d8c5d7")
        n12_resus_id = self.get_rule_id("R#b4e9d6e8")
        fte_id = self.get_rule_id("R#f8c3b0c2")
        max_hours_id = self.get_rule_id("R#f0c5b2c4")
        consecutive_id = self.get_rule_id("R#e3b8a5b7")
        rest_id = self.get_rule_id("R#c1f6e3f5")
        day_night_id = self.get_rule_id("R#f4c9b6c8")
        red_req_id = self.get_rule_id("R#a5d0c7d9")
        holiday_id = self.get_rule_id("R#b6e1d8e0")

        for date in self.dates:
            # Check D12 requirements
            d12_shifts = [a for a in daily_assignments.get(date, []) if a[0] == "D12" and a[1] is not None]
            if d12_shifts:
                if not any(s.level == "CN" for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_cn_id}D12 shift missing CN staff member")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 3 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_coord_id}D12 shift missing Shift Coordinator")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 2 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_triage_id}D12 shift missing Triage training")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 1 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_resus_id}D12 shift missing Resus training")

            # Check N12 requirements
            n12_shifts = [a for a in daily_assignments.get(date, []) if a[0] == "N12" and a[1] is not None]
            if n12_shifts:
                if not any(s.level == "CN" for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_cn_id}N12 shift missing CN staff member")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 3 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_coord_id}N12 shift missing Shift Coordinator")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 2 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_triage_id}N12 shift missing Triage training")
                if not any(TRAINING_MAP.get(s.training_level, 0) == 1 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_resus_id}N12 shift missing Resus training")

        # FTE and Max Hours
        for s in self.staff:
            if s.assigned_hours < s.fte_hours:
                violations.append(f"Staff {s.name} {fte_id}under FTE: {s.assigned_hours}/{s.fte_hours}")
            if s.assigned_hours > 76:
                violations.append(f"Staff {s.name} {max_hours_id}exceeded 76 hours: {s.assigned_hours}")

        # Consecutive shifts and Rest period
        for s in self.staff:
            # Consecutive shifts
            shift_history = {} # (shift_name) -> list of dates
            for d, sn, sm in self.assignments:
                if sm and sm.name == s.name:
                    if sn not in shift_history: shift_history[sn] = []
                    shift_history[sn].append(d)
            
            for sn, dates in shift_history.items():
                dates.sort()
                consecutive = 1
                for i in range(1, len(dates)):
                    if (dates[i] - dates[i-1]).days == 1:
                        consecutive += 1
                        if consecutive >= 3:
                            violations.append(f"Staff {s.name} {consecutive_id}worked {sn} for {consecutive} consecutive days ending {dates[i]}")
                            break
                    else:
                        consecutive = 1

            # Rest period and Day/Night transition
            s_assignments = []
            for d, sn, sm in self.assignments:
                if sm and sm.name == s.name:
                    s_start, s_end = get_shift_times_helper(d, sn, self.definitions)
                    is_night = sn in ["N8", "N12"]
                    s_assignments.append({'date': d, 'start': s_start, 'end': s_end, 'is_night': is_night})
            s_assignments.sort(key=lambda x: x['date'])

            for i in range(len(s_assignments)):
                curr = s_assignments[i]
                
                # Check against other assignments for rest period
                for j in range(i + 1, len(s_assignments)):
                    other = s_assignments[j]
                    if not (curr['end'] <= other['start'] or curr['start'] >= other['end']):
                        violations.append(f"Staff {s.name} has overlapping shifts on {curr['date']} and {other['date']}")
                    
                    if curr['start'] >= other['end']:
                        if (curr['start'] - other['end']).total_seconds() < 11 * 3600:
                            violations.append(f"Staff {s.name} {rest_id}has less than 11h rest between {other['end']} and {curr['start']}")
                    elif other['start'] >= curr['end']:
                        if (other['start'] - curr['end']).total_seconds() < 11 * 3600:
                            violations.append(f"Staff {s.name} {rest_id}has less than 11h rest between {curr['end']} and {other['start']}")

                # Check Day/Night transition
                if i < len(s_assignments) - 1:
                    next_as = s_assignments[i+1]
                    if curr['is_night'] != next_as['is_night']:
                        if (next_as['date'] - curr['date']).days <= 1:
                            violations.append(f"Staff {s.name} {day_night_id}swapped between day and night without a day off between {curr['date']} and {next_as['date']}")

        # Red requests and Holidays
        for s in self.staff:
            for d, sn, sm in self.assignments:
                if sm and sm.name == s.name:
                    if d in s.red_requests:
                        violations.append(f"Staff {s.name} {red_req_id}rostered on red request day {d}")
                    for hs, he in s.holidays:
                        if hs <= d <= he:
                            violations.append(f"Staff {s.name} {holiday_id}rostered during holiday {hs} to {he}")

        return violations

    def generate_results(self):
        with open("result.staff.md", "w") as f:
            f.write("# Staff Roster\n\n")
            for s in self.staff:
                f.write(f"## {s.name}\n- Level: {s.level}\n- Training Level: {s.training_level}\n- FTE Hours per Fortnight: {s.fte_hours}\n- Total Hours: {s.assigned_hours}\n- Weekend Hours: {s.weekend_hours}\n\n### Shifts\n")
                for d, sn in s.assigned_shifts: f.write(f"- {d.strftime('%Y-%m-%d')}: {sn}\n")
                f.write("\n")
        with open("result.roster.md", "w") as f:
            f.write("# Roster by Date\n\n")
            for d in self.dates:
                f.write(f"## {d.strftime('%Y-%m-%d')} ({d.strftime('%A')})\n")
                day_ass = [a for a in self.assignments if a[0] == d]
                if not day_ass: f.write("- No shifts scheduled\n")
                for date, sn, sm in day_ass:
                    if sm:
                        f.write(f"- {sn}: {sm.name} ({sm.level}, {sm.training_level})\n")
                    else:
                        f.write(f"- {sn}: UNFILLED\n")
                f.write("\n")
