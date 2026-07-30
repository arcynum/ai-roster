import re
import datetime
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

@dataclass
class ShiftDefinition:
    name: str
    start_time: str
    end_time: str
    duration: int
    crosses_midnight: bool
    start_dt: datetime.time
    end_dt: datetime.time

@dataclass
class ShiftRequirement:
    shift_name: str
    count: int

@dataclass
class StaffMember:
    name: str
    level: str
    training_level: str
    fte_hours: int
    red_requests: Set[datetime.date] = field(default_factory=set)
    holidays: List[Tuple[datetime.date, datetime.date]] = field(default_factory=list)
    rules: List[str] = field(default_factory=list)
    preferences: List[str] = field(default_factory=list)
    assigned_hours: int = 0
    assigned_shifts: List[Tuple[datetime.date, str]] = field(default_factory=list)

TRAINING_LEVELS = ["Acute", "Resus", "Triage", "Shift Coordinator"]
TRAINING_MAP = {level: i for i, level in enumerate(TRAINING_LEVELS)}

def parse_definitions(content: str) -> Dict[str, ShiftDefinition]:
    definitions = {}
    # Use regex to find all # Name blocks
    pattern = r'#\s+([^\n]+)\n(.*?)(?=\n#|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        name = match.group(1).strip()
        block = match.group(2).strip()
        
        start_time_str = ""
        end_time_str = ""
        duration = 0
        
        start_match = re.search(r'\*\*Start Time\*\*:\s*(\d{2}:\d{2}:\d{2})', block)
        if start_match: start_time_str = start_match.group(1)
        
        end_match = re.search(r'\*\*End Time\*\*:\s*(\d{2}:\d{2}:\d{2})', block)
        if end_match: end_time_str = end_match.group(1)
        
        duration_match = re.search(r'\*\*Duration\*\*:\s*(\d+)', block)
        if duration_match: duration = int(duration_match.group(1))
        
        if start_time_str and end_time_str:
            try:
                start_dt = datetime.datetime.strptime(start_time_str, "%H:%M:%S").time()
                end_dt = datetime.datetime.strptime(end_time_str, "%H:%M:%S").time()
                definitions[name] = ShiftDefinition(name, start_time_str, end_time_str, duration, end_dt < start_dt, start_dt, end_dt)
            except Exception as e:
                print(f"Error parsing time for {name}: {e}")
    return definitions

def parse_roster(content: str) -> Tuple[datetime.date, datetime.date, Dict[str, List[ShiftRequirement]]]:
    start_date = None
    end_date = None
    roster = {}
    current_day = None
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('- **Roster Start Date**: '):
            start_date = datetime.datetime.strptime(line.split(': ')[1], "%Y-%m-%d").date()
        elif line.startswith('- **Roster End Date**: '):
            end_date = datetime.datetime.strptime(line.split(': ')[1], "%Y-%m-%d").date()
        elif line.startswith('## '):
            current_day = line[3:].strip()
            roster[current_day] = []
        elif line.startswith('- ') and current_day:
            m = re.match(r'- (\d+) (\w+)', line)
            if m: roster[current_day].append(ShiftRequirement(m.group(2), int(m.group(1))))
    return start_date, end_date, roster

def parse_staff(content: str) -> List[StaffMember]:
    staff = []
    pattern = r'#\s+([^\n]+)\n(.*?)(?=\n#|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        name = match.group(1).strip()
        block = match.group(2).strip()
        
        level, training, fte, red, holidays, rules, prefs = "", "", 0, set(), [], [], []
        
        # Level
        l_m = re.search(r'\*\*Level\*\*:\s*(\w+)', block)
        if l_m: level = l_m.group(1)
        
        # Training
        t_m = re.search(r'\*\*Training Level\*\*:\s*([^\n]+)', block)
        if t_m: training = t_m.group(1).strip()
        
        # FTE
        f_m = re.search(r'\*\*FTE Hours per Fortnight\*\*:\s*(\d+)', block)
        if f_m: fte = int(f_m.group(1))
        
        # Red Requests
        r_m = re.search(r'\*\*Red Requests\*\*:\s*([^\n]*)', block)
        if r_m:
            rs = r_m.group(1).strip()
            for r in rs.split(','):
                try:
                    d_str = r.strip()
                    if d_str: red.add(datetime.datetime.strptime(d_str, "%Y-%m-%d").date())
                except: pass
                
        # Holidays
        h_m = re.search(r'\*\*Holidays/Sickness\*\*:\s*([^\n]*)', block)
        if h_m:
            hs = h_m.group(1).strip()
            if hs:
                if " to " in hs:
                    try:
                        p = hs.split(" to ")
                        holidays.append((datetime.datetime.strptime(p[0].strip(), "%Y-%m-%d").date(), datetime.datetime.strptime(p[1].strip(), "%Y-%m-%d").date()))
                    except: pass
                else:
                    for r in hs.split(','):
                        try:
                            d_str = r.strip()
                            if d_str: holidays.append((datetime.datetime.strptime(d_str, "%Y-%m-%d").date(), datetime.datetime.strptime(d_str, "%Y-%m-%d").date()))
                        except: pass
                        
        # Rules and Preferences
        lines = block.split('\n')
        for i, line in enumerate(lines):
            if "- **Rules**:" in line:
                content = line.split("- **Rules**:")[1].strip()
                if content:
                    rules.append(content)
                elif i + 1 < len(lines):
                    next_l = lines[i+1].strip()
                    if next_l and not next_l.startswith("- **"):
                        rules.append(next_l)
            if "- **Preferences**:" in line:
                content = line.split("- **Preferences**:")[1].strip()
                if content:
                    prefs.append(content)
                elif i + 1 < len(lines):
                    next_l = lines[i+1].strip()
                    if next_l and not next_l.startswith("- **"):
                        prefs.append(next_l)
                    
        staff.append(StaffMember(name, level, training, fte, red, holidays, rules, prefs))
    return staff

class Solver:
    def __init__(self, start_date, days_count, definitions, roster_reqs, staff):
        self.start_date = start_date
        self.days_count = days_count
        self.definitions = definitions
        self.roster_reqs = roster_reqs
        self.staff = staff
        self.dates = [start_date + datetime.timedelta(days=i) for i in range(days_count)]
        self.assignments = []

    def get_shift_times(self, date, shift_name):
        sd = self.definitions[shift_name]
        start = datetime.datetime.combine(date, sd.start_dt)
        end = datetime.datetime.combine(date, sd.end_dt)
        if sd.crosses_midnight: end += datetime.timedelta(days=1)
        return start, end

    def is_valid(self, staff_m, date, shift_name):
        if date in staff_m.red_requests: return False
        for h_s, h_e in staff_m.holidays:
            if h_s <= date <= h_e: return False
        for rule in staff_m.rules:
            if "mondays" in rule.lower() and date.strftime("%A").lower() == "monday": return False
        for ass in self.assignments:
            if ass[0] == date and ass[2].name == staff_m.name: return False
        
        sd = self.definitions[shift_name]
        if staff_m.assigned_hours + sd.duration > 80: return False

        s_start, s_end = self.get_shift_times(date, shift_name)
        for ass_date, ass_shift, ass_m in self.assignments:
            if ass_m.name == staff_m.name:
                as_start, as_end = self.get_shift_times(ass_date, ass_shift)
                if not (s_end <= as_start or s_start >= as_end): return False
                if s_start >= as_end:
                    if (s_start - as_end).total_seconds() < 11 * 3600: return False
                elif as_start >= s_end:
                    if (as_start - s_end).total_seconds() < 11 * 3600: return False
                
                is_night = lambda sn: sn in ["N8", "N12"]
                if is_night(shift_name) != is_night(ass_shift):
                    if abs((date - ass_date).days) <= 1: return False

        same_shift_count = 0
        for ass_date, ass_shift, ass_m in self.assignments:
            if ass_m.name == staff_m.name and ass_shift == shift_name:
                if abs((date - ass_date).days) == 1: same_shift_count += 1
        if same_shift_count >= 2: return False
        return True

    def solve(self):
        for d in self.dates:
            day_name = d.strftime("%A")
            reqs = self.roster_reqs.get(day_name, [])
            reqs = sorted(reqs, key=lambda r: 0 if r.shift_name in ["D12", "N12"] else 1)
            d12_cn = d12_coord = d12_triage = d12_resus = False
            n12_cn = n12_coord = n12_triage = n12_resus = False
            for req in reqs:
                for _ in range(req.count):
                    best_staff = None
                    
                    # Rule 24: Check if anyone hasn't met FTE
                    any_under_fte = any(s.assigned_hours < s.fte_hours for s in self.staff)
                    
                    candidates = []
                    for s in self.staff:
                        if self.is_valid(s, d, req.shift_name):
                            # Rule 24: If someone has met FTE, and someone else hasn't, skip them for now
                            if any_under_fte and s.assigned_hours >= s.fte_hours:
                                continue
                            candidates.append(s)
                    
                    # Sort candidates to prioritize those who need more hours
                    # We use a combination of (has_met_fte, assigned_hours/fte_hours)
                    # But if any_under_fte is True, we only have candidates who haven't met FTE.
                    # If any_under_fte is False, we have candidates who may or may not have met FTE.
                    
                    def candidate_key(s):
                        # Priority:
                        # 1. Has not met FTE (if any_under_fte is true, this is already filtered)
                        # 2. Lower ratio of assigned/fte
                        # 3. Preference: same shift yesterday
                        # 4. Rule 18: Day/Night balance
                        met_fte = 1 if s.assigned_hours >= s.fte_hours else 0
                        ratio = s.assigned_hours / s.fte_hours
                        
                        # Preference: same shift yesterday
                        pref_score = 0 if (d - datetime.timedelta(days=1), req.shift_name) in s.assigned_shifts else 1
                        
                        # Rule 18: Day/Night balance
                        s_day_count = 0
                        s_night_count = 0
                        for ass_date, ass_shift, ass_m in self.assignments:
                            if ass_m.name == s.name:
                                if ass_shift in ["N8", "N12"]:
                                    s_night_count += 1
                                else:
                                    s_day_count += 1
                        
                        req_is_night = req.shift_name in ["N8", "N12"]
                        balance_score = 1
                        if req_is_night:
                            if s_day_count > s_night_count:
                                balance_score = 0
                        elif s_night_count > s_day_count:
                            balance_score = 0
                            
                        return (met_fte, ratio, pref_score, balance_score)

                    candidates.sort(key=candidate_key)
                    
                    # Special handling for required training/level
                    # We want to pick the BEST candidate that satisfies the requirement
                    
                    for s in candidates:
                        is_needed = False
                        if req.shift_name == "D12":
                            if not d12_cn and s.level == "CN": is_needed = True
                            elif not d12_coord and TRAINING_MAP.get(s.training_level, 0) == 3: is_needed = True
                            elif not d12_triage and TRAINING_MAP.get(s.training_level, 0) == 2: is_needed = True
                            elif not d12_resus and TRAINING_MAP.get(s.training_level, 0) == 1: is_needed = True
                        elif req.shift_name == "N12":
                            if not n12_cn and s.level == "CN": is_needed = True
                            elif not n12_coord and TRAINING_MAP.get(s.training_level, 0) == 3: is_needed = True
                            elif not n12_triage and TRAINING_MAP.get(s.training_level, 0) == 2: is_needed = True
                            elif not n12_resus and TRAINING_MAP.get(s.training_level, 0) == 1: is_needed = True
                        
                        if is_needed:
                            best_staff = s
                            if req.shift_name == "D12":
                                if s.level == "CN": d12_cn = True
                                if TRAINING_MAP.get(s.training_level, 0) == 3: d12_coord = True
                                if TRAINING_MAP.get(s.training_level, 0) == 2: d12_triage = True
                                if TRAINING_MAP.get(s.training_level, 0) == 1: d12_resus = True
                            elif req.shift_name == "N12":
                                if s.level == "CN": n12_cn = True
                                if TRAINING_MAP.get(s.training_level, 0) == 3: n12_coord = True
                                if TRAINING_MAP.get(s.training_level, 0) == 2: n12_triage = True
                                if TRAINING_MAP.get(s.training_level, 0) == 1: n12_resus = True
                            break
                    
                    if not best_staff and candidates:
                        best_staff = candidates[0]
                        # Still need to update the requirement flags if we just pick someone
                        if req.shift_name == "D12":
                            if best_staff.level == "CN": d12_cn = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 3: d12_coord = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 2: d12_triage = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 1: d12_resus = True
                        elif req.shift_name == "N12":
                            if best_staff.level == "CN": n12_cn = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 3: n12_coord = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 2: n12_triage = True
                            if TRAINING_MAP.get(best_staff.training_level, 0) == 1: n12_resus = True

                    if best_staff:
                        self.assignments.append((d, req.shift_name, best_staff))
                        best_staff.assigned_hours += self.definitions[req.shift_name].duration
                        best_staff.assigned_shifts.append((d, req.shift_name))
                    else:
                        self.assignments.append((d, f"UNFILLED {req.shift_name}", None))
        return self.assignments

    def generate_results(self):
        with open("result.staff.md", "w") as f:
            f.write("# Staff Roster\n\n")
            for s in self.staff:
                f.write(f"## {s.name}\n- Level: {s.level}\n- Training Level: {s.training_level}\n- Total Hours: {s.assigned_hours}\n\n### Shifts\n")
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

if __name__ == "__main__":
    try:
        with open("definitions.md", "r") as f: defs = parse_definitions(f.read())
        with open("roster.md", "r") as f: 
            start_date, end_date, reqs = parse_roster(f.read())
        with open("staff.md", "r") as f: staff = parse_staff(f.read())
        
        import sys
        if start_date is None:
            print("Roster start date not found in roster.md")
            sys.exit(1)
            
        if end_date is None:
            # Default to 14 days if no end date provided
            end_date = start_date + datetime.timedelta(days=13)

        days_count = (end_date - start_date).days + 1
            
        if len(sys.argv) > 1:
            try:
                start_date = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
                days_count = 14 # If user provides start date, assume 14 days as before
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD")
                sys.exit(1)
        
        solver = Solver(start_date, days_count, defs, reqs, staff)
        solver.solve()
        solver.generate_results()
        
        unfilled = [a for a in solver.assignments if "UNFILLED" in a[1]]
        if unfilled:
            print(f"Roster built, but {len(unfilled)} shifts remain UNFILLED.")
        else:
            print("Roster built successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
