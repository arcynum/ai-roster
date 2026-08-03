import re
import datetime
import yaml
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

# This script uses roster.yaml as the source of truth for roster requirements
# The YAML format provides a more structured and maintainable way to define roster requirements
# Each shift instance requires exactly one skill tag

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

def parse_roster_yaml(content: str) -> Tuple[datetime.date, datetime.date, Dict[str, List[ShiftRequirement]]]:
    """Parse roster requirements from YAML format."""
    data = yaml.safe_load(content)
    
    start_date = data['dates']['start']
    end_date = data['dates']['end']
    
    roster = {}
    for day_name, shifts in data['shift_requirements'].items():
        roster[day_name] = []
        for shift_data in shifts:
            shift_name = shift_data['shift']
            required_skills = shift_data['required_skills']
            # For now, we'll assume the count is 1 for each shift requirement
            # In the future, this could be expanded to support multiple counts
            roster[day_name].append(ShiftRequirement(shift_name, 1, required_skills))
    
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
        
        level, training_levels, fte, red, holidays, rules, prefs = "", [], 0, set(), [], [], []
        
        # Classification
        c_m = re.search(r'\*\*Classification\*\*:\s*(\w+)', block)
        if c_m: level = c_m.group(1)
        
        # Training - can be either single level or array
        t_m = re.search(r'\*\*Training Levels\*\*:\s*(\[.*\])', block)
        if t_m:
            # Handle array format
            training_str = t_m.group(1)
            try:
                import ast
                training_levels = ast.literal_eval(training_str)
            except:
                # Fallback to single level
                training_levels = [training_str.strip().strip("[]\"'")]
        else:
            # Legacy format - single training level
            t_m = re.search(r'\*\*Training Level\*\*:\s*([^\n]+)', block)
            if t_m: 
                training_levels = [t_m.group(1).strip()]
        
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
                    
        staff.append(StaffMember(name, level, training_levels, fte, red, holidays, rules, prefs))
    return staff

def generate_staff_shifts_html(solver, staff, dates, assignments=None):
    """Generate HTML table showing staff shifts."""
    
    # Define shift colors
    shift_colors = {
        'D8': '#4285F4',   # Blue
        'D12': '#34A853',  # Green
        'P8': '#FBBC05',   # Yellow
        'P12': '#673AB7',  # Purple
        'L3': '#EA4335',   # Red
        'DISCO': '#9E9E9E', # Gray
        'N8': '#00BCD4',   # Cyan
        'N12': '#E91E63'   # Pink/Magenta
    }
    
    # Check if assignments exist (feasible solution)
    has_assignments = assignments is not None and len(assignments) > 0
    
    if not has_assignments:
        # Generate HTML for infeasible case with diagnostics
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Staff Shift Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; font-weight: bold; }
        .shift-cell { min-width: 80px; }
        .shift-header { font-weight: bold; }
        .staff-header { font-weight: bold; }
        .shift-D8 { background-color: """ + shift_colors['D8'] + """; color: white; }
        .shift-D12 { background-color: """ + shift_colors['D12'] + """; color: white; }
        .shift-P8 { background-color: """ + shift_colors['P8'] + """; color: white; }
        .shift-P12 { background-color: """ + shift_colors['P12'] + """; color: white; }
        .shift-L3 { background-color: """ + shift_colors['L3'] + """; color: white; }
        .shift-DISCO { background-color: """ + shift_colors['DISCO'] + """; color: white; }
        .shift-N8 { background-color: """ + shift_colors['N8'] + """; color: white; }
        .shift-N12 { background-color: """ + shift_colors['N12'] + """; color: white; }
        .staff-info { font-size: 0.9em; }
        .training-levels { font-size: 0.8em; color: #666; }
        .note { background-color: #fff3cd; padding: 10px; border: 1px solid #ffeaa7; margin: 10px 0; }
        .error-section { background-color: #ffebee; padding: 15px; border: 1px solid #ffcdd2; margin: 10px 0; }
        .error-title { color: #c62828; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Staff Shift Schedule</h1>
    <p class="note">Roster could not be generated due to infeasibility.</p>
    
    <div class="error-section">
        <h2 class="error-title">Feasibility Analysis</h2>
        <p>The solver could not find a feasible roster that satisfies all constraints.</p>
        <p>Below are the diagnostic details explaining the infeasibility:</p>
    </div>
"""
        
        # Add the diagnostic information that was previously printed to stdout
        # This will be populated by the calling code
        html_content += """
    <div class="error-section">
        <h2>Diagnostic Information</h2>
        <p>Training level distribution: <strong>""" + str(getattr(solver, 'training_counts', {})) + """</strong></p>
        <p>Classification distribution: <strong>""" + str(getattr(solver, 'level_counts', {})) + """</strong></p>
"""
        
        if hasattr(solver, 'period_holidays') and solver.period_holidays:
            html_content += "<p>Staff on full-period holidays:</p><ul>"
            for name, start, end in solver.period_holidays:
                html_content += f"<li>- {name}: {start} to {end}</li>"
            html_content += "</ul>"
        
        html_content += """
        <p>Staffing Requirements:</p>
        <ul>
            <li>Total D12 shifts needed: """ + str(getattr(solver, 'total_d12_shifts', 0)) + """</li>
            <li>Required staff per shift: 4</li>
            <li>Total required staff-shifts: """ + str(getattr(solver, 'total_required_staff', 0)) + """</li>
        </ul>
        
        <p>Total available FTE hours: <strong>""" + str(getattr(solver, 'total_fte', 0)) + """</strong></p>
        <p>Required FTE for 14-day block: <strong>""" + str(getattr(solver, 'required_fte', 0)) + """</strong></p>
        
        <p><strong>Key Issue:</strong> The staffing levels don't meet shift requirements</p>
        <ul>
            <li>Need 1 Triage trained staff (L>=3) but only have <strong>""" + str(getattr(solver, 'training_counts', {}).get('Triage', 0)) + """</strong></li>
            <li>Need 1 Resus trained staff (L>=2) but only have <strong>""" + str(getattr(solver, 'training_counts', {}).get('Resus', 0)) + """</strong></li>
        </ul>
"""
        
        if len(staff) < 10:
            html_content += "<p><strong>WARNING:</strong> Very limited staff available - may not be enough to meet requirements</p>"
        
        html_content += """
    </div>
    
    <h2>Staff Assignment Table (Not Available - Roster Infeasible)</h2>
    <p>No staff assignments could be generated due to infeasibility.</p>
</body>
</html>
    """
        
        return html_content
    
    else:
        # Generate HTML for feasible case with assignments
        # Get assignments from solver
        assignments = solver.assignments
        
        # Create a mapping of date -> shift assignments for easier access
        assignment_map = {}
        for date, shift_name, staff_member in assignments:
            if date not in assignment_map:
                assignment_map[date] = {}
            assignment_map[date][shift_name] = staff_member
        
        # Get staff names in order
        staff_names = [s.name for s in staff]
        
        # Create HTML content
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Staff Shift Schedule</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; font-weight: bold; }
        .shift-cell { min-width: 80px; }
        .shift-header { font-weight: bold; }
        .staff-header { font-weight: bold; }
        .shift-D8 { background-color: """ + shift_colors['D8'] + """; color: white; }
        .shift-D12 { background-color: """ + shift_colors['D12'] + """; color: white; }
        .shift-P8 { background-color: """ + shift_colors['P8'] + """; color: white; }
        .shift-P12 { background-color: """ + shift_colors['P12'] + """; color: white; }
        .shift-L3 { background-color: """ + shift_colors['L3'] + """; color: white; }
        .shift-DISCO { background-color: """ + shift_colors['DISCO'] + """; color: white; }
        .shift-N8 { background-color: """ + shift_colors['N8'] + """; color: white; }
        .shift-N12 { background-color: """ + shift_colors['N12'] + """; color: white; }
        .staff-info { font-size: 0.9em; }
        .training-levels { font-size: 0.8em; color: #666; }
        .note { background-color: #fff3cd; padding: 10px; border: 1px solid #ffeaa7; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>Staff Shift Schedule</h1>
    <p class="note">This table shows staff assignments across the roster period.</p>
    
    <table>
        <thead>
            <tr>
                <th>Staff Member</th>
                <th>Classification</th>
                <th>Training Levels</th>
                """ + "".join(f"<th class='shift-header'>{date.strftime('%a %m/%d')}</th>" for date in dates) + """
            </tr>
        </thead>
        <tbody>
        """
        
        # Add staff rows
        for staff_name in staff_names:
            staff_member = next((s for s in staff if s.name == staff_name), None)
            if not staff_member:
                continue
                
            html_content += f"<tr>\n"
            # Staff info
            html_content += f"    <td class='staff-header'>{staff_member.name}</td>\n"
            html_content += f"    <td>{staff_member.level}</td>\n"
            html_content += f"    <td class='training-levels'>{', '.join(staff_member.training_levels)}</td>\n"
            
            # Add shift assignments for each date
            for date in dates:
                # Find if staff member is assigned to any shift on this date
                shift_cell_content = ""
                if date in assignment_map:
                    for shift_name, assigned_staff in assignment_map[date].items():
                        if assigned_staff.name == staff_member.name:
                            shift_cell_content = shift_name
                            break
                
                # Add cell with shift info or empty
                if shift_cell_content:
                    shift_class = f"shift-{shift_cell_content}"
                    html_content += f"    <td class='shift-cell {shift_class}'>{shift_cell_content}</td>\n"
                else:
                    html_content += f"    <td class='shift-cell'></td>\n"
            
            html_content += "</tr>\n"
        
        html_content += """
        </tbody>
    </table>
</body>
</html>
        """
        
        return html_content

if __name__ == "__main__":
    try:
        with open("definitions.md", "r") as f: defs = parse_definitions(f.read())
        # Use roster.yaml as the source of truth
        with open("roster.yaml", "r") as f: 
            start_date, end_date, reqs = parse_roster_yaml(f.read())
        with open("staff.md", "r") as f: staff = parse_staff(f.read())
        with open("hard_constraints.md", "r") as f: global_rules, _ = parse_rules_and_prefs(f.read(), "")
        with open("soft_constraints.md", "r") as f: _, global_prefs = parse_rules_and_prefs("", f.read())
        
        import sys
        if start_date is None:
            print("Roster start date not found in roster.yaml")
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
            # Enhanced diagnostics for infeasibility
            print("Failed to find a feasible roster.")
            print("\nPotential causes of infeasibility:")
            
            # Count training levels
            training_counts = {}
            level_counts = {}
            for s in staff:
                # Handle both old and new formats for compatibility
                if hasattr(s, 'training_levels'):
                    # New format: training_levels is an array
                    for level in s.training_levels:
                        training_counts[level] = training_counts.get(level, 0) + 1
                else:
                    # Old format: training_level is a string
                    level = s.training_level
                    training_counts[level] = training_counts.get(level, 0) + 1
                level_counts[s.level] = level_counts.get(s.level, 0) + 1
            
            # Store diagnostic info in solver for HTML generation
            solver.training_counts = training_counts
            solver.level_counts = level_counts
            
            print(f"Training level distribution: {training_counts}")
            print(f"Classification distribution: {level_counts}")
            
            # Show holiday conflicts
            period_holidays = []
            for s in staff:
                if s.holidays:
                    for start_date, end_date in s.holidays:
                        if start_date <= end_date:  # Valid date range
                            period_holidays.append((s.name, start_date, end_date))
            
            solver.period_holidays = period_holidays
            
            if period_holidays:
                print(f"\nStaff on full-period holidays: {len(period_holidays)}")
                for name, start, end in period_holidays:
                    print(f"  - {name}: {start} to {end}")
            
            # Show staffing requirements vs availability
            total_days = days_count
            total_d12_shifts = 4 * total_days  # 4 D12 shifts per day
            required_staff_per_d12 = 4  # CN + Shift Coordinator + Triage + Resus
            
            solver.total_d12_shifts = total_d12_shifts
            solver.total_required_staff = total_d12_shifts * required_staff_per_d12
            
            print(f"\nStaffing Requirements:")
            print(f"Total D12 shifts needed: {total_d12_shifts}")
            print(f"Required staff per shift: 4")
            print(f"Total required staff-shifts: {total_d12_shifts * required_staff_per_d12}")
            
            # Show FTE summary
            total_fte = sum(s.fte_hours for s in staff)
            solver.total_fte = total_fte
            solver.required_fte = total_d12_shifts * required_staff_per_d12 * 12.5  # Assuming ~12.5h per shift
            
            print(f"\nTotal available FTE hours: {total_fte:.1f}")
            print(f"Required FTE for 14-day block: {total_d12_shifts * required_staff_per_d12 * 12.5}")  # Assuming ~12.5h per shift
            
            # Highlight the core staffing issue
            print(f"\n⚠️  Key Issue: The staffing levels don't meet shift requirements")
            print(f"   - Need 1 Triage trained staff (L>=3) but only have {training_counts.get('Triage', 0)}")
            print(f"   - Need 1 Resus trained staff (L>=2) but only have {training_counts.get('Resus', 0)}")
            print(f"   - This is the main reason for infeasibility")
            
            # Show the core staffing problem
            if len(staff) < 10:
                print("\n⚠️  WARNING: Very limited staff available - may not be enough to meet requirements")
            
        else:
            solver.generate_results()
            violations = solver.validate_roster()
            if violations:
                with open("result.violations.md", "w") as f:
                    f.write("# Roster Rule Violations\n\n")
                    for v in violations:
                        f.write(f"- {v}\n")
                print(f"Roster built, but {len(violations)} rule violations found. See result.violations.md for details.")
            else:
                with open("result.violations.md", "w") as f:
                    f.write("# Roster Rule Violations\n\nNo violations found.\n")
                print("Roster built successfully with no violations.")
            
        # Generate HTML output
        html_content = generate_staff_shifts_html(solver, staff, solver.dates, assignments)
        with open("result.staff_shifts.html", "w") as f:
            f.write(html_content)
        print("HTML shift schedule generated: result.staff_shifts.html")

    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()