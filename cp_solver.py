import datetime
import json
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
        
        # Load weights from external config
        self.weights = {
            "S#f8c3b0c2": 1000,
            "weekend_distribution": 100,
            "preference_base": 1,
            "S#d2a7f4a6": 50,
            "S#a1d6c3d5": 50,
            "S#e9b4a1b3": 20,
            "S#f5e6d7c8": 10
        }
        try:
            with open("weights.json", "r") as f:
                self.weights.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            pass
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
                    print(f"DEBUG:   Warning: {h_name} not in shift_indices")
            
        # 2. Night Shift Fairness (S#d2a7f4a6)
        night_shift_names = [h for h in shift_names if h in ["N8", "N12"]]
        total_nights_requested = sum(req.count for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime("%A"), []) if req.shift_name in night_shift_names)
        night_fairness_violations = []
        if total_nights_requested > 0:
            total_fte_sum = sum(s.fte_hours for s in self.staff)
            for s_idx in staff_indices:
                staff_m = self.staff[s_idx]
                night_shifts_s = sum(x[s_idx, d_idx, h_name] for d_idx in day_indices for h_name in night_shift_names)
                target_nights_s = int(round((staff_m.fte_hours / total_fte_sum) * total_nights_requested)) if total_fte_sum > 0 else 0
                diff_night_s = model.NewIntVar(0, self.days_count, f'diff_night_{s_idx}')
                model.AddAbsEquality(diff_night_s, night_shifts_s - target_nights_s)
                night_fairness_violations.append(diff_night_s)

        # D12 and N12 requirements (updated indices for Graduate hierarchy)
        for d_idx in day_indices:
            date = self.dates[d_idx]
            day_name = date.strftime("%A")
            
            # D12 requirements
            d12_reqs = [r for r in self.roster_reqs.get(day_name, []) if r.shift_name == "D12"]
            if d12_reqs:
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if self.staff[s].level == "CN") >= 1)
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 4) >= 1)
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 3) >= 1)
                model.Add(sum(x[s, d_idx, "D12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 2) >= 1)

            # N12 requirements
            n12_reqs = [r for r in self.roster_reqs.get(day_name, []) if r.shift_name == "N12"]
            if n12_reqs:
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if self.staff[s].level == "CN") >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 4) >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 3) >= 1)
                model.Add(sum(x[s, d_idx, "N12"] for s in staff_indices if TRAINING_MAP.get(self.staff[s].training_level, 0) >= 2) >= 1)

        # 4. Rest Period Constraint (11 hours)
        for s in staff_indices:
            for d1_idx in day_indices:
                date1 = self.dates[d1_idx]
                for h1_name in shift_names:
                    sd1 = self.definitions[h1_name]
                    for d2_idx in day_indices:
                        if d1_idx == d2_idx: continue
                        if abs(d1_idx - d2_idx) > 1: continue
                        date2 = self.dates[d2_idx]
                        for h2_name in shift_names:
                            sd2 = self.definitions[h2_name]
                            start1 = datetime.datetime.combine(date1, sd1.start_dt)
                            end1 = datetime.datetime.combine(date1, sd1.end_dt)
                            if sd1.crosses_midnight: end1 += datetime.timedelta(days=1)
                            start2 = datetime.datetime.combine(date2, sd2.start_dt)
                            end2 = datetime.datetime.combine(date2, sd2.end_dt)
                            if sd2.crosses_midnight: end2 += datetime.timedelta(days=1)
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

        # 7. Max Hours Constraint (76h per fortnight)
        fortnights_in_roster = self.days_count / 14.0
        max_hours_limit = 76 * fortnights_in_roster
        for s in staff_indices:
            total_hours_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                     for d in day_indices for h_name in shift_names)
            model.Add(total_hours_scaled <= int(max_hours_limit * self.SCALE))

        # 0. One Shift Per Day (Hard)
        for s in staff_indices:
            for d in day_indices:
                model.Add(sum(x[s, d, h] for h in shift_names) <= 1)

        # Graduate Constraint (H#30479c74): Graduates can only work D8, P8, L3, DISCO, N8
        graduate_allowed_shifts = {"D8", "P8", "L3", "DISCO", "N8"}
        for s in staff_indices:
            if self.staff[s].training_level == "Graduate":
                for d in day_indices:
                    for h_name in shift_names:
                        if h_name not in graduate_allowed_shifts:
                            model.Add(x[s, d, h_name] == 0)

        # 8. Night/Day Transition Constraint
        night_shifts = [h for h in shift_names if h in ["N8", "N12"]]
        day_shifts = [h for h in shift_names if h not in night_shifts]
        for s in staff_indices:
            for d_idx in range(self.days_count - 1):
                for h_night in night_shifts:
                    for h_day in day_shifts:
                        model.AddForbiddenAssignments([x[s, d_idx, h_night], x[s, d_idx+1, h_day]], [(1, 1)])
                        model.AddForbiddenAssignments([x[s, d_idx, h_day], x[s, d_idx+1, h_night]], [(1, 1)])

        # --- OBJECTIVE FUNCTION ---
        penalty_fte = self.weights.get("S#f8c3b0c2", 1000)
        penalty_night_fairness = self.weights.get("S#d2a7f4a6", 50)
        penalty_weekend = self.weights.get("S#a1d6c3d5", 50)
        penalty_excess_fte = self.weights.get("S#e9b4a1b3", 20)
        penalty_preference = self.weights.get("S#f5e6d7c8", 10)

        # 1. FTE Deviation (S#f8c3b0c2): Minimize being under contracted hours.
        fte_violations = []
        for s in staff_indices:
            target_fte_scaled = int(self.staff[s].fte_hours * self.SCALE)
            current_fte_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                     for d in day_indices for h_name in shift_names)
            under_fte = model.NewIntVar(0, target_fte_scaled, f'under_fte_{s}')
            model.Add(under_fte >= target_fte_scaled - current_fte_scaled)
            model.Add(under_fte >= 0)
            fte_violations.append(under_fte)

        # 2. Night Shift Fairness (S#d2a7f4a6): Proportional distribution of night hours based on FTE.
        night_shift_names = [h for h in shift_names if h in ["N8", "N12"]]
        total_nights_hours_scaled = sum(req.count * int(self.definitions[req.shift_name].duration * self.SCALE) 
                                       for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime("%A"), []) if req.shift_name in night_shift_names)
        night_fairness_violations = []
        if total_nights_hours_scaled > 0:
            total_fte_sum = sum(s.fte_hours for s in self.staff)
            for s_idx in staff_indices:
                current_night_hours_scaled = sum(x[s_idx, d_idx, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                                 for d_idx in day_indices for h_name in night_shift_names)
                target_night_hours_scaled = int(round((self.staff[s_idx].fte_hours / total_fte_sum) * (total_nights_hours_scaled / self.SCALE))) * self.SCALE if total_fte_sum > 0 else 0
                diff_night_s = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'diff_night_{s_idx}')
                model.AddAbsEquality(diff_night_s, current_night_hours_scaled - target_night_hours_scaled)
                night_fairness_violations.append(diff_night_s)

        # 3. Weekend Deviation (S#a1d6c3d5): Proportional distribution of weekend hours based on FTE.
        total_weekend_hours_scaled = sum(req.count * int(self.definitions[req.shift_name].duration * self.SCALE) 
                                         for d_idx in day_indices for req in self.roster_reqs.get(self.dates[d_idx].strftime("%A"), []) if self.dates[d_idx].weekday() >= 5)
        weekend_violations = []
        if total_weekend_hours_scaled > 0:
            total_fte_sum = sum(s.fte_hours for s in self.staff)
            for s_idx in staff_indices:
                current_weekend_hours_scaled = sum(x[s_idx, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) 
                                                   for d in day_indices for h_name in shift_names if self.dates[d].weekday() >= 5)
                target_weekend_hours_scaled = int(round((self.staff[s_idx].fte_hours / total_fte_sum) * (total_weekend_hours_scaled / self.SCALE))) * self.SCALE if total_fte_sum > 0 else 0
                diff_weekend_s = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'diff_weekend_{s_idx}')
                model.AddAbsEquality(diff_weekend_s, current_weekend_hours_scaled - target_weekend_hours_scaled)
                weekend_violations.append(diff_weekend_s)

        # 4. Excess FTE Distribution (S#e9b4a1b3): Fairly distribute hours above FTE if requirements > staff capacity.
        excess_fte_violations = []
        total_req_hours_scaled = sum(req.count * int(self.definitions[req.shift_name].duration * self.SCALE) for d in day_indices for req in self.roster_reqs.get(self.dates[d].strftime("%A"), []))
        total_fte_hours_scaled = sum(int(s.fte_hours * self.SCALE) for s in self.staff)
        if total_req_hours_scaled > total_fte_hours_scaled:
            total_excess_scaled = total_req_hours_scaled - total_fte_hours_scaled
            num_staff = len(self.staff)
            target_excess_per_person_scaled = total_excess_scaled // num_staff
            for s in staff_indices:
                current_hours_scaled = sum(x[s, d, h_name] * int(self.definitions[h_name].duration * self.SCALE) for d in day_indices for h_name in shift_names)
                target_fte_scaled = int(self.staff[s].fte_hours * self.SCALE)
                excess_s = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'excess_{s}')
                model.AddMaxEquality(excess_s, [0, current_hours_scaled - target_fte_scaled])
                diff_excess = model.NewIntVar(0, int(24 * 31 * self.SCALE), f'diff_excess_{s}')
                model.AddAbsEquality(diff_excess, excess_s - target_excess_per_person_scaled)
                excess_fte_violations.append(diff_excess)

        # 5. Preference Violations (S#f5e6d7c8): Minimize shift type changes on consecutive days worked.
        pref_violations = []
        for s in staff_indices:
            shift_types = []
            for d in day_indices:
                st = model.NewIntVar(0, len(shift_names) - 1, f'st_{s}_{d}')
                for h_idx, h_name in enumerate(shift_names):
                    model.Add(st == h_idx).OnlyEnforceIf(x[s, d, h_name])
                shift_types.append(st)

            for d in range(self.days_count - 1):
                worked_d = model.NewBoolVar(f'w_{s}_{d}')
                worked_next = model.NewBoolVar(f'w_{s}_{d+1}')
                model.Add(sum(x[s, d, h] for h in shift_names) == 1).OnlyEnforceIf(worked_d)
                model.Add(sum(x[s, d, h] for h in shift_names) == 0).OnlyEnforceIf(worked_d.Not())
                model.Add(sum(x[s, d+1, h] for h in shift_names) == 1).OnlyEnforceIf(worked_next)
                model.Add(sum(x[s, d+1, h] for h in shift_names) == 0).OnlyEnforceIf(worked_next.Not())

                both = model.NewBoolVar(f'both_{s}_{d}')
                model.AddMultiplicationEquality(both, [worked_d, worked_next])
                
                diff_type = model.NewBoolVar(f'diff_type_{s}_{d}')
                model.Add(shift_types[d] != shift_types[d+1]).OnlyEnforceIf(diff_type)
                model.Add(shift_types[d] == shift_types[d+1]).OnlyEnforceIf(diff_type.Not())

                violation = model.NewBoolVar(f'pref_viol_{s}_{d}')
                model.AddMultiplicationEquality(violation, [both, diff_type])
                pref_violations.append(violation)

        model.Minimize(penalty_fte * sum(fte_violations) + 
                       penalty_night_fairness * sum(night_fairness_violations) +
                       penalty_weekend * sum(weekend_violations) +
                       penalty_excess_fte * sum(excess_fte_violations) +
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
        violations = []
        daily_assignments = {}
        for date, shift_name, staff_m in self.assignments:
            if date not in daily_assignments:
                daily_assignments[date] = []
            daily_assignments[date].append((shift_name, staff_m))

        d12_cn_id = self.get_rule_id("H#a7f2c9d1")
        d12_coord_id = self.get_rule_id("H#b8e3d0e2")
        d12_triage_id = self.get_rule_id("H#c9f4e1f3")
        d12_resus_id = self.get_rule_id("H#d0a5f2a4")
        n12_cn_id = self.get_rule_id("H#e1b6a3b5")
        n12_coord_id = self.get_rule_id("H#f2c7b4c6")
        n12_triage_id = self.get_rule_id("H#a3d8c5d7")
        n12_resus_id = self.get_rule_id("H#b4e9d6e8")
        fte_id = self.get_rule_id("S#f8c3b0c2")
        max_hours_id = self.get_rule_id("H#f0c5b2c4")
        consecutive_id = self.get_rule_id("H#e3b8a5b7")
        rest_id = self.get_rule_id("H#c1f6e3f5")
        day_night_id = self.get_rule_id("H#f4c9b6c8")
        red_req_id = self.get_rule_id("H#a5d0c7d9")
        holiday_id = self.get_rule_id("H#b6e1d8e0")

        for date in self.dates:
            d12_shifts = [a for a in daily_assignments.get(date, []) if a[0] == "D12" and a[1] is not None]
            if d12_shifts:
                if not any(s.level == "CN" for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_cn_id}D12 shift missing CN staff member")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 4 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_coord_id}D12 shift missing Shift Coordinator")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 3 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_triage_id}D12 shift missing Triage training")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 2 for _, s in d12_shifts):
                    violations.append(f"{date}: {d12_resus_id}D12 shift missing Resus training")

            n12_shifts = [a for a in daily_assignments.get(date, []) if a[0] == "N12" and a[1] is not None]
            if n12_shifts:
                if not any(s.level == "CN" for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_cn_id}N12 shift missing CN staff member")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 4 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_coord_id}N12 shift missing Shift Coordinator")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 3 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_triage_id}N12 shift missing Triage training")
                if not any(TRAINING_MAP.get(s.training_level, 0) >= 2 for _, s in n12_shifts):
                    violations.append(f"{date}: {n12_resus_id}N12 shift missing Resus training")

        fortnights = len(self.dates) / 14.0
        max_hours_limit = 76 * fortnights
        for s in self.staff:
            if s.assigned_hours < s.fte_hours:
                violations.append(f"Staff {s.name} {fte_id}under FTE: {s.assigned_hours}/{s.fte_hours}")
            if s.assigned_hours > max_hours_limit:
                violations.append(f"Staff {s.name} {max_hours_id}exceeded {max_hours_limit} hours: {s.assigned_hours}")

        for s in self.staff:
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

            s_assignments = []
            for d, sn, sm in self.assignments:
                if sm and sm.name == s.name:
                    s_start, s_end = get_shift_times_helper(d, sn, self.definitions)
                    is_night = sn in ["N8", "N12"]
                    s_assignments.append({'date': d, 'start': s_start, 'end': s_end, 'is_night': is_night})
            s_assignments.sort(key=lambda x: x['date'])

            for i in range(len(s_assignments)):
                curr = s_assignments[i]
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

                if i < len(s_assignments) - 1:
                    next_as = s_assignments[i+1]
                    if curr['is_night'] != next_as['is_night']:
                        if (next_as['date'] - curr['date']).days <= 1:
                            violations.append(f"Staff {s.name} {day_night_id}swapped between day and night without a day off between {curr['date']} and {next_as['date']}")

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
            shift_order = {"D8": 0, "D12": 1, "P8": 2, "P12": 3, "L3": 4, "DISCO": 5, "N8": 6, "N12": 7}
            for d in self.dates:
                f.write(f"## {d.strftime('%Y-%m-%d')} ({d.strftime('%A')})\n")
                day_ass = [a for a in self.assignments if a[0] == d]
                if not day_ass: 
                    f.write("- No shifts scheduled\n")
                else:
                    # Sort by the specified order
                    day_ass.sort(key=lambda x: shift_order.get(x[1], 99))
                    for date, sn, sm in day_ass:
                        if sm:
                            f.write(f"- {sn}: {sm.name} ({sm.level}, {sm.training_level})\n")
                        else:
                            f.write(f"- {sn}: UNFILLED\n")
                f.write("\n")
