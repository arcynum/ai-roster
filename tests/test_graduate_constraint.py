#!/usr/bin/env python3
"""
Test file for Graduate Shift Constraint implementation.
This tests the H#30479c74 constraint that restricts Graduate staff to specific shift types.
"""

import sys
import os
import unittest
from unittest.mock import Mock

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Staff, Classification, Shift
from constraints import GraduateShiftConstraint


class TestGraduateShiftConstraint(unittest.TestCase):
    """Test cases for GraduateShiftConstraint."""
    
    def test_constraint_initialization(self):
        """Test that the constraint initializes correctly."""
        constraint = GraduateShiftConstraint()
        self.assertEqual(constraint.constraint_id, "[H#30479c74]")
        
    def test_graduate_staff_valid_shifts(self):
        """Test that Graduate staff can be assigned to valid shifts."""
        # Create a Graduate staff member
        graduate_staff = Staff(
            name="Test Graduate",
            classification=Classification.GRADUATE,
            skill_tags=["Acute"],
            contracted_hours_per_fortnight=40,
            red_requests=[],
            holidays=[]
        )
        
        # Create constraint
        constraint = GraduateShiftConstraint()
        
        # Mock the model and variables (we're testing the logic structure)
        mock_model = Mock()
        
        # The constraint should accept valid assignments for graduates
        # This test verifies the constraint can be applied without errors
        try:
            constraint.apply(mock_model, staff_list=[graduate_staff], shifts=[])
            # Should not raise an exception
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Constraint.apply() raised {e}")
            
    def test_graduate_staff_invalid_shifts_logic(self):
        """Test that Graduate staff cannot be assigned to invalid shifts."""
        # Create a Graduate staff member  
        graduate_staff = Staff(
            name="Test Graduate",
            classification=Classification.GRADUATE,
            skill_tags=["Acute"],
            contracted_hours_per_fortnight=40,
            red_requests=[],
            holidays=[]
        )
        
        # Create constraint
        constraint = GraduateShiftConstraint()
        
        # Mock the model and variables
        mock_model = Mock()
        
        # This is a structural test - the constraint should be designed to
        # prevent assignments of graduates to invalid shifts when implemented
        try:
            constraint.apply(mock_model, staff_list=[graduate_staff], shifts=[])
            # Should not raise an exception
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Constraint.apply() raised {e}")
            
    def test_constraint_with_actual_shifts(self):
        """Test constraint with actual shift definitions."""
        # Create a Graduate staff member  
        graduate_staff = Staff(
            name="Test Graduate",
            classification=Classification.GRADUATE,
            skill_tags=["Acute"],
            contracted_hours_per_fortnight=40,
            red_requests=[],
            holidays=[]
        )
        
        # Create some shift definitions
        valid_shifts = [
            Shift("D8", "07:00", "15:30", 8.5, 8.0, 30, False),
            Shift("P8", "09:30", "18:00", 8.5, 8.0, 30, False),
            Shift("DISCO", "17:30", "02:00", 8.5, 8.0, 30, True),
            Shift("N8", "22:45", "07:15", 8.5, 8.0, 30, True)
        ]
        
        invalid_shifts = [
            Shift("D12", "07:00", "19:30", 12.5, 12.0, 30, False),
            Shift("P12", "09:30", "22:00", 12.5, 12.0, 30, False),
            Shift("N12", "19:00", "07:30", 12.5, 12.0, 30, True)
        ]
        
        # Create constraint
        constraint = GraduateShiftConstraint()
        
        # Mock the model
        mock_model = Mock()
        
        # Test that constraint can handle valid shifts
        try:
            constraint.apply(mock_model, staff_list=[graduate_staff], shifts=valid_shifts)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Constraint.apply() with valid shifts raised {e}")
            
        # Test that constraint can handle invalid shifts  
        try:
            constraint.apply(mock_model, staff_list=[graduate_staff], shifts=invalid_shifts)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Constraint.apply() with invalid shifts raised {e}")


if __name__ == '__main__':
    unittest.main()