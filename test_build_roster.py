import unittest
import datetime
from build_roster import (
    parse_definitions,
    ShiftDefinition,
    StaffMember,
    parse_roster,
    parse_staff,
    Solver,
    ShiftRequirement,
    TRAINING_MAP,
    Rule,
    Preference
)

class TestParsers(unittest.TestCase):
    def test_parse_definitions(self):
        content = """
# D12
**Start Time**: 07:00:00
**End Time**: 19:00:00
**Duration**: 12

# N12
**Start Time**: 19:00:00
**End Time**: 07:00:00
**Duration**: 12
"""
        defs = parse_definitions(content)
        self.assertIn("D12", defs)
        self.assertEqual(defs["D12"].duration, 12)
        self.assertFalse(defs["D12"].crosses_midnight)
        self.assertIn("N12", defs)
        self.assertTrue(defs["N12"].crosses_midnight)

    def test_parse_roster(self):
        content = """
- **Roster Start Date**: 2026-08-01
- **Roster End Date**: 2026-08-14
## 2026-08-01 (Saturday)
- 1 D12
- 1 N12
"""
        start, end, roster = parse_roster(content)
        self.assertEqual(start, datetime.date(2026, 8, 1))
        self.assertEqual(end, datetime.date(2026, 8, 14))
        self.assertIn("Saturday", roster)
        self.assertEqual(len(roster["Saturday"]), 2)

    def test_parse_staff(self):
        content = """
# Test Staff
**Level**: RN
**Training Level**: Resus
**FTE Hours per Fortnight**: 48
**Red Requests**: 2026-08-01
**Holidays/Sickness**: 2026-08-05 to 2026-08-06
- **Rules**: [R#123] Never work monday
**Preferences**: [P#456] Prefers morning
"""
        staff = parse_staff(content)
        self.assertEqual(len(staff), 1)
        self.assertEqual(staff[0].name, "Test Staff")
        self.assertEqual(staff[0].level, "RN")
        self.assertEqual(staff[0].training_level, "Resus")
        self.assertEqual(staff[0].fte_hours, 48)
        self.assertIn(datetime.date(2026, 8, 1), staff[0].red_requests)
        self.assertEqual(staff[0].holidays[0], (datetime.date(2026, 8, 5), datetime.date(2026, 8, 6)))
        self.assertEqual(staff[0].rules[0].id, "R#123")
        self.assertEqual(staff[0].rules[0].description, "Never work monday")
        self.assertEqual(staff[0].preferences[0].id, "P#456")
        self.assertEqual(staff[0].preferences[0].description, "Prefers morning")

class TestValidation(unittest.TestCase):
    def setUp(self):
        self.start_date = datetime.date(2026, 8, 1)
        self.defs = {
            "D12": ShiftDefinition("D12", "07:00:00", "19:00:00", 12, False, datetime.time(7, 0), datetime.time(19, 0)),
            "N12": ShiftDefinition("N12", "19:00:00", "07:00:00", 12, True, datetime.time(19, 0), datetime.time(7, 0)),
            "Early": ShiftDefinition("Early", "05:00:00", "17:00:00", 12, False, datetime.time(5, 0), datetime.time(17, 0)),
        }
        self.roster_reqs = {"Saturday": [ShiftRequirement("D12", 1)]}
        self.staff_m = StaffMember("Test", "RN", "Acute", 48)
        self.solver = Solver(self.start_date, 7, self.defs, self.roster_reqs, [self.staff_m])

    def test_red_requests(self):
        self.staff_m.red_requests.add(datetime.date(2026, 8, 1))
        self.assertFalse(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))
        self.staff_m.red_requests.remove(datetime.date(2026, 8, 1))
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))

    def test_holidays(self):
        self.staff_m.holidays.append((datetime.date(2026, 8, 1), datetime.date(2026, 8, 2)))
        self.assertFalse(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 3), "D12"))

    def test_rules_monday(self):
        self.staff_m.rules.append(Rule("R#1", "Never work monday"))
        monday = datetime.date(2026, 8, 3)
        self.assertFalse(self.solver.is_valid(self.staff_m, monday, "D12"))
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))

    def test_max_hours(self):
        self.staff_m.assigned_hours = 70
        self.assertFalse(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))
        self.staff_m.assigned_hours = 60
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 1), "D12"))

    def test_rest_period(self):
        self.solver.assignments.append((datetime.date(2026, 8, 1), "D12", self.staff_m))
        self.assertFalse(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 2), "Early"))
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 2), "D12"))

    def test_consecutive_shifts(self):
        for i in range(3):
            self.solver.assignments.append((self.start_date + datetime.timedelta(days=i), "D12", self.staff_m))
            self.staff_m.assigned_hours += 12
        self.assertFalse(self.solver.is_valid(self.staff_m, self.start_date + datetime.timedelta(days=3), "D12"))
        # Clean up for next tests
        for _ in range(3):
            self.solver.assignments.pop()
            self.staff_m.assigned_hours -= 12

    def test_day_night_transition(self):
        self.solver.assignments.append((datetime.date(2026, 8, 1), "N12", self.staff_m))
        # Rule 20: at least 1 day off in between when swapping. 
        # So N on Monday, can't do D on Tuesday.
        self.assertFalse(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 2), "D12"))
        self.assertTrue(self.solver.is_valid(self.staff_m, datetime.date(2026, 8, 3), "D12"))

class TestSolver(unittest.TestCase):
    def setUp(self):
        self.start_date = datetime.date(2026, 8, 1)
        self.defs = {
            "D12": ShiftDefinition("D12", "07:00:00", "19:00:00", 12, False, datetime.time(7, 0), datetime.time(19, 0)),
            "N12": ShiftDefinition("N12", "19:00:00", "07:00:00", 12, True, datetime.time(19, 0), datetime.time(7, 0)),
        }

    def test_training_requirements(self):
        # Need enough D12 shifts to satisfy all requirements
        staff = [
            StaffMember("CN_Coord", "CN", "Shift Coordinator", 48),
            StaffMember("RN_Triage", "RN", "Triage", 48),
            StaffMember("RN_Resus", "RN", "Resus", 48)
        ]
        # 3 D12 shifts on Saturday
        reqs = {"Saturday": [ShiftRequirement("D12", 3)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        
        violations = solver.validate_roster()
        # Check that no D12 is missing anything
        d12_violations = [v for v in violations if "D12" in v]
        self.assertEqual(len(d12_violations), 0)

    def test_cn_requirement_satisfied(self):
        # 2 D12 shifts, at least one must be CN.
        staff = [
            StaffMember("CN_Staff", "CN", "Acute", 48),
            StaffMember("RN_Staff", "RN", "Acute", 48)
        ]
        reqs = {"Saturday": [ShiftRequirement("D12", 2)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        violations = solver.validate_roster()
        cn_violations = [v for v in violations if "missing CN" in v]
        # Rule: 1 of the D12 shifts must be CN. If one is CN and one is RN, it's satisfied.
        self.assertEqual(len(cn_violations), 0)

    def test_cn_requirement_failure(self):
        # No CN staff.
        staff = [
            StaffMember("RN_Staff", "RN", "Acute", 48),
        ]
        reqs = {"Saturday": [ShiftRequirement("D12", 1)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        violations = solver.validate_roster()
        cn_violations = [v for v in violations if "missing CN" in v]
        # Since no CN is available, the shift will be missing CN.
        self.assertEqual(len(cn_violations), 1)

    def test_fte_minimums(self):
        staff = [
            StaffMember("Full_Staff_1", "RN", "Acute", 12),
            StaffMember("Full_Staff_2", "RN", "Acute", 12),
        ]
        reqs = {"Saturday": [ShiftRequirement("D12", 2)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        violations = solver.validate_roster()
        fte_violations = [v for v in violations if "under FTE" in v]
        self.assertEqual(len(fte_violations), 0)

    def test_unfilled_shifts(self):
        # Not enough staff to cover 3 shifts
        staff = [
            StaffMember("Only_Staff", "RN", "Acute", 12),
        ]
        reqs = {"Saturday": [ShiftRequirement("D12", 3)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        
        unfilled = [a for a in solver.assignments if "UNFILLED" in a[1]]
        self.assertTrue(len(unfilled) > 0)

    def test_requirement_overlap(self):
        # One person is CN and Shift Coordinator. They should satisfy both.
        # To make this work, we need to provide enough shifts so that all rules are checked.
        # But we only want to check if the overlap works.
        # If we have 1 D12 shift, it's impossible to satisfy all rules.
        # So let's provide 3 D12 shifts.
        staff = [
            StaffMember("Super_Staff", "CN", "Shift Coordinator", 48),
            StaffMember("RN_Triage", "RN", "Triage", 48),
            StaffMember("RN_Resus", "RN", "Resus", 48)
        ]
        reqs = {"Saturday": [ShiftRequirement("D12", 3)]}
        solver = Solver(self.start_date, 1, self.defs, reqs, staff)
        solver.solve()
        violations = solver.validate_roster()
        d12_violations = [v for v in violations if "D12" in v]
        self.assertEqual(len(d12_violations), 0)

if __name__ == '__main__':
    unittest.main()
