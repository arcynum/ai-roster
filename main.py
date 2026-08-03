#!/usr/bin/env python3
"""
Main driver script for the AI-Roster system.
This orchestrates the entire rostering process using Google OR-Tools CP-SAT.
"""

import sys
import os
import logging
from typing import List

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import Staff, Shift
from solver import RosterSolver
from output import generate_output_files
from utils import load_yaml_file, validate_dates

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('output/roster.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main() -> None:
    """Main entry point for the rostering system."""
    logger.info("Starting AI-Roster system")
    
    try:
        # Load all configuration files
        logger.info("Loading configuration files")
        staff_data = load_yaml_file("staff.yaml")
        roster_data = load_yaml_file("roster.yaml")
        definitions_data = load_yaml_file("definitions.yaml")
        weights_data = load_yaml_file("weights.yaml")
        
        # Validate date ranges
        logger.info("Validating date ranges")
        validate_dates(roster_data)
        
        # Create data models
        logger.info("Creating data models")
        shifts: List[Shift] = []
        for shift_name, shift_dict in definitions_data.items():
            shift = Shift(
                name=shift_name,
                start_time=shift_dict['start'],
                end_time=shift_dict['end'],
                span_hours=shift_dict['span_hours'],
                paid_hours=shift_dict['paid_hours'],
                unpaid_break_minutes=shift_dict['unpaid_break_minutes'],
                crosses_midnight=shift_dict['crosses_midnight']
            )
            shifts.append(shift)
            
        staff_list: List[Staff] = []
        for staff_dict in staff_data:
            staff = Staff(
                name=staff_dict['name'],
                classification=staff_dict['classification'],
                skill_tags=staff_dict['skill_tags'],
                contracted_hours_per_fortnight=staff_dict['contracted_hours_per_fortnight'],
                red_requests=staff_dict['red_requests'],
                holidays=staff_dict['holidays'],
            )
            staff_list.append(staff)
        
        # Initialize solver
        logger.info("Initializing solver")
        solver = RosterSolver(
            staff_list=staff_list,
            shifts=shifts,
            roster_data=roster_data,
            weights_data=weights_data
        )
        
        # Solve the roster
        logger.info("Solving roster")
        solution = solver.solve()
        
        # Generate output files
        logger.info("Generating output files")
        generate_output_files(solution)
        
        logger.info("Roster generation completed successfully!")
        print("Roster generation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error occurred: {e}")
        print(f"Error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
