import datetime
from build_roster import parse_definitions, parse_roster, parse_staff, parse_rules_and_prefs, Solver

def main():
    with open("definitions.md", "r") as f: defs = parse_definitions(f.read())
    with open("roster.md", "r") as f: start_date, end_date, reqs = parse_roster(f.read())
    with open("staff.md", "r") as f: staff = parse_staff(f.read())
    with open("rules.md", "r") as f: global_rules, _ = parse_rules_and_prefs(f.read(), "")
    with open("preferences.md", "r") as f: _, global_prefs = parse_rules_and_prefs("", f.read())
    
    solver = Solver(start_date, (end_date - start_date).days + 1, defs, reqs, staff, rules=global_rules, preferences=global_prefs)
    solver.solve()
    
    violations = solver.validate_roster()
    if violations:
        print(f"Found {len(violations)} violations:")
        for v in violations:
            print(f"  - {v}")
    else:
        print("No violations found!")

if __name__ == "__main__":
    main()
