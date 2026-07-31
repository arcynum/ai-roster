import unittest
import datetime
import os
from models import (
    ShiftDefinition, 
    StaffMember, 
    ShiftRequirement, 
    Rule, 
    Preference, 
    TRAINING_MAP
)
from build_roster import parse_definitions, parse_roster, parse_staff, parse_rules_and_prefs
from cp_solver import CPSolver

class TestParsers(unittest.TestCase):
    def test_parse_definitions(self):
        content = """# D12
**Start Time**: 07:00:00
**End Time**: 19:00:00
**Duration**: 12.0

# N12
**Start Time**: 19:00:00
**End Time**: 07:00:00
**Duration**: 12.0"""
        defs = parse_definitions(content)
        self.assertIn("D12", defs)
        self.assertEqual(defs["D12"].duration, 12.0)
        self.assertFalse(defs["D12"].crosses_midnight)
        self.assertTrue(defs["N12"].crosses_midnight)

    def test_parse_roster(self):
        content = """- **Roster Start Date**: 2026-08-01
- **Roster End Date**: 2026-08-14
## 2026-08-01 (Saturday)
- 1 D12
- 1 N12"""
        start, end, roster = parse_roster(content)
        self.assertEqual(start, datetime.date(2026, 8, 1))
        self.assertEqual(end, datetime.date(2026, 8, 14))
        self.assertIn("Saturday", roster)
        self.assertEqual(len(roster["Saturday"]), 2)

    def test_parse_staff(self):
        content = """# Test Staff
**Classification**: RN
**Training Level**: Resus
**FTE Hours per Fortnight**: 48.0
**Red Requests**: 2026-08-01
**Holidays/Sickness**: 2026-08-05 to 2026-08-06
- **Rules**: [R1] Never work Monday
**Preferences**: [P1] Prefers morning"""
        staff = parse_staff(content)
        self.assertEqual(len(staff), 1)
        s = staff[0]
        self.assertEqual(s.name, "Test Staff")
        self.assertEqual(s.level, "RN")
        self.assertEqual(s.training_level, "Resus")
        self.assertEqual(s.fte_hours, 48.0)
        self.assertIn(datetime.date(2026, 8, 1), s.red_requests)
        self.assertEqual(len(s.holidays), 1)
        self.assertEqual(s.holidays[0], (datetime.date(2026, 8, 5), datetime.date(2026, 8, 6)))
        self.assertEqual(s.rules[0].id, "R1")
        self.assertEqual(s.preferences[0].id, "P1")

class TestCPSolverConstraints(unittest.TestCase):
    def setUp(self):
        self.start_date = datetime.date(2026, 8, 1)
        self.days_count = 5
        self.definitions = {
            "D12": ShiftDefinition("D12", "07:00:00", "19:00:00", 12.0, False, datetime.time(7, 0), datetime.time(19, 0)),
            "N12": ShiftDefinition("N12", "19:00:00", "07:00:00", 12.0, True, datetime.time(19, 0), datetime.time(7, 0)),
            "D8": ShiftDefinition("D8", "08:00:00", "16:00:00", 8.0, False, datetime.time(8, 0), datetime.time(16, 0)),
        }
        self.roster_reqs = {
            "Saturday": [ShiftRequirement("D12", 4)],
            "Sunday": [ShiftRequirement("D12", 4)],
            "Monday": [ShiftRequirement("D12", 4)],
            "Tuesday": [ShiftRequirement("D12", 4)],
            "Wednesday": [ShiftRequirement("D12", 4)],
        }
        self.staff = [
            StaffMember("S1", "CN", "Shift Coordinator", 72.0),
            StaffMember("S2", "RN", "Resus", 72.0),
            StaffMember("S3", "RN", "Triage", 72.0),
            StaffMember("S4", "RN", "Acute", 72.0),
        ]

    def test_coverage(self):
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        assignments = solver.solve()
        self.assertTrue(len(assignments) > 0)
        
        # Verify each day has the required shift count
        for i in range(self.days_count):
            date = self.start_date + datetime.timedelta(days=i)
            day_name = date.strftime("%A")
            req_count = sum(1 for r in self.roster_reqs[day_name] if r.shift_name == "D12")
            actual_count = sum(1 for a_date, a_name, _ in assignments if a_date == date and a_name == "D12")
            self.assertEqual(actual_count, req_count)

    def test_training_requirements(self):
        # Setup staff to specifically cover all D12 needs
        self.staff = [
            StaffMember("CN_Coord", "CN", "Shift Coordinator", 72.0), # CN + Coord
            StaffMember("RN_Triage", "RN", "Triage", 72.0),           # Triage
            StaffMember("RN_Resus", "RN", "Resus", 72.0),             # Resus
            StaffMember("RN_Extra", "RN", "Acute", 72.0),             # Extra
        ]
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        assignments = solver.solve()
        self.assertTrue(len(assignments) > 0)
        
        violations = [v for v in solver.validate_roster() if "D12" in v]
        self.assertEqual(len(violations), 0, f"Training violations found: {violations}")

    def test_rest_period(self):
        # S1 works N12 on Saturday, cannot work D12 on Sunday (less than 11h gap)
        self.staff = [StaffMember("S1", "CN", "Shift Coordinator", 72.0)]
        # This will likely fail coverage if we only have 1 staff, so we need more staff to make it feasible.
        self.staff += [
            StaffMember("S2", "RN", "Triage", 72.0),
            StaffMember("S3", "RN", "Resus", 72.0),
            StaffMember("S4", "RN", "Acute", 72.0),
        ]
        # Add enough shifts for them to potentially violate it if not careful
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        solver.solve()
        violations = [v for v in solver.validate_roster() if "less than 11h rest" in v]
        self.assertEqual(len(violations), 0)

    def test_max_hours(self):
        # Ensure no one exceeds 76 hours
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        solver.solve()
        violations = [v for v in solver.validate_roster() if "exceeded 76 hours" in v]
        self.assertEqual(len(violations), 0)

    def test_red_requests(self):
        self.staff[0].red_requests.add(self.start_date)
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        solver.solve()
        violations = [v for v in solver.validate_roster() if "red requested" in v]
        self.assertEqual(len(violations), 0)

    def test_holidays(self):
        self.staff[0].holidays.append((self.start_date, self.start_date + datetime.timedelta(days=1)))
        solver = CPSolver(self.start_date, self.days_count, self.definitions, self.roster_reqs, self.staff)
        solver.solve()
        violations = [v for v in solver.validate_roster() if "on leave" in v]
        self.assertEqual(len(violations), 0)

class TestIntegration(unittest.TestCase):
    def test_full_run(self):
        # This test uses the actual files to ensure everything works end-to-end
        # We expect it to succeed since we just verified it.
        import subprocess
        result = subprocess.run([".venv/bin/python", "build_roster.py"], capture_output=True, text=True)
        self.assertIn("Roster built successfully", result.stdout)

if __name__ == "__main__":
    unittest.main()
