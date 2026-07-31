import re
import datetime
from typing import List, Dict, Optional, Set, Tuple
from models import (
    ShiftDefinition,
    ShiftRequirement,
    Rule,
    Preference,
    StaffMember,
    TRAINING_LEVELS,
    TRAINING_MAP,
    get_shift_times_helper
)
from cp_solver import CPSolver

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
        
        duration_match = re.search(r'\*\*Duration\*\*:\s*([\d.]+)', block)
        if duration_match: duration = float(duration_match.group(1))
        
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
    current_day_name = None
    for line in content.split('\n'):
        line = line.strip()
        if not line: continue
        if line.startswith('- **Roster Start Date**: '):
            start_date = datetime.datetime.strptime(line.split(': ')[1], "%Y-%m-%d").date()
        elif line.startswith('- **Roster End Date**: '):
            end_date = datetime.datetime.strptime(line.split(': ')[1], "%Y-%m-%d").date()
        elif line.startswith('## '):
            header = line[3:].strip()
            # Match "YYYY-MM-DD (DayName)"
            match = re.search(r'(\d{4}-\d{2}-\d{2})\s+\((\w+)\)', header)
            if match:
                current_day_name = match.group(2)
            else:
                current_day_name = header
            
            if current_day_name not in roster:
                roster[current_day_name] = []
        elif line.startswith('- ') and current_day_name:
            m = re.match(r'- (\d+) (\w+)', line)
            if m: roster[current_day_name].append(ShiftRequirement(m.group(2), int(m.group(1))))
    return start_date, end_date, roster

def parse_rule_or_pref(text: str) -> Tuple[Optional[str], str]:
    match = re.match(r'\[([^\]]+)\]\s*(.*)', text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, text.strip()

def parse_rules_and_prefs(rules_content: str, prefs_content: str) -> Tuple[List[Rule], List[Preference]]:
    rules = []
    pattern = r'- \[([^\]]+)\]\s*(.*)'
    for line in rules_content.split('\n'):
        match = re.search(pattern, line)
        if match:
            rules.append(Rule(match.group(1).strip(), match.group(2).strip()))
            
    prefs = []
    for line in prefs_content.split('\n'):
        match = re.search(pattern, line)
        if match:
            prefs.append(Preference(match.group(1).strip(), match.group(2).strip()))
            
    return rules, prefs

def parse_staff(content: str) -> List[StaffMember]:
    staff = []
    pattern = r'#\s+([^\n]+)\n(.*?)(?=\n#|\Z)'
    matches = re.finditer(pattern, content, re.DOTALL)
    
    for match in matches:
        name = match.group(1).strip()
        block = match.group(2).strip()
        
        level, training, fte, red, holidays, rules, prefs = "", "", 0, set(), [], [], []
        
        # Classification
        c_m = re.search(r'\*\*Classification\*\*:\s*(\w+)', block)
        if c_m: level = c_m.group(1)
        
        # Training
        t_m = re.search(r'\*\*Training Level\*\*:\s*([^\n]+)', block)
        if t_m: training = t_m.group(1).strip()
        
        # FTE
        f_m = re.search(r'\*\*FTE Hours per Fortnight\*\*:\s*([\d.]+)', block)
        if f_m: fte = float(f_m.group(1))
        
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
            if "**Rules**:" in line:
                parts = line.split("**Rules**:")
                content_part = parts[1].strip()
                if content_part:
                    rule_id, desc = parse_rule_or_pref(content_part)
                    rules.append(Rule(rule_id, desc))
                elif i + 1 < len(lines):
                    next_l = lines[i+1].strip()
                    if next_l and not next_l.startswith("- **") and not next_l.startswith("**"):
                        rule_id, desc = parse_rule_or_pref(next_l)
                        rules.append(Rule(rule_id, desc))
            if "**Preferences**:" in line:
                parts = line.split("**Preferences**:")
                content_part = parts[1].strip()
                if content_part:
                    pref_id, desc = parse_rule_or_pref(content_part)
                    prefs.append(Preference(pref_id, desc))
                elif i + 1 < len(lines):
                    next_l = lines[i+1].strip()
                    if next_l and not next_l.startswith("- **") and not next_l.startswith("**"):
                        pref_id, desc = parse_rule_or_pref(next_l)
                        prefs.append(Preference(pref_id, desc))
                    
        staff.append(StaffMember(name, level, training, fte, red, holidays, rules, prefs))
    return staff

if __name__ == "__main__":
    try:
        with open("definitions.md", "r") as f: defs = parse_definitions(f.read())
        with open("roster.md", "r") as f: 
            start_date, end_date, reqs = parse_roster(f.read())
        with open("staff.md", "r") as f: staff = parse_staff(f.read())
        with open("hard_constraints.md", "r") as f: global_rules, _ = parse_rules_and_prefs(f.read(), "")
        with open("soft_constraints.md", "r") as f: _, global_prefs = parse_rules_and_prefs("", f.read())
        
        import sys
        if start_date is None:
            print("Roster start date not found in roster.md")
            sys.exit(1)
            
        if end_date is None:
            end_date = start_date + datetime.timedelta(days=13)
            
        days_count = (end_date - start_date).days + 1
            
        if len(sys.argv) > 1:
            try:
                start_date = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
                days_count = 14 
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD")
                sys.exit(1)
            
        solver = CPSolver(start_date, days_count, defs, reqs, staff, rules=global_rules, preferences=global_prefs)
        assignments = solver.solve()
        
        if not assignments:
            print("Failed to find a feasible roster.")
        else:
            solver.generate_results()
            violations = solver.validate_roster()
            if violations:
                print(f"Roster built, but {len(violations)} rule violations found:")
                for v in violations:
                    print(f"- {v}")
            else:
                print("Roster built successfully with no violations.")

    except Exception as e:
        import traceback
        traceback.print_exc()
