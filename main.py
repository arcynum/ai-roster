#!/usr/bin/env python3
"""
Main driver script for the AI-Roster system.
This orchestrates the entire rostering process using Google OR-Tools CP-SAT.
"""

import sys
import os
from typing import List

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Staff, Shift, RosterPosition
from solver import RosterSolver
from output import generate_output_files
from utils import load_yaml_file, validate_dates

def main() -> None:
    """Main entry point for the rostering system."""
    print("Starting AI-Roster system...")
    
    try:
        # Load all configuration files
        staff_data = load_yaml_file("staff.yaml")
        roster_data = load_yaml_file("roster.yaml")
        definitions_data = load_yaml_file("definitions.yaml")
        weights_data = load_yaml_file("weights.yaml")
        
        # Validate date ranges
        validate_dates(roster_data)
        
        # Create data models
        staff_list: List[Staff] = [Staff(**staff_dict) for staff_dict in staff_data]
        shifts: List[Shift] = [Shift(**shift_dict) for shift_dict in definitions_data]
        
        # Initialize solver
        solver = RosterSolver(
            staff_list=staff_list,
            shifts=shifts,
            roster_data=roster_data,
            weights_data=weights_data
        )
        
        # Solve the roster
        solution = solver.solve()
        
        # Generate output files
        generate_output_files(solution)
        
        print("Roster generation completed successfully!")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()