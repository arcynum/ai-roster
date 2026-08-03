"""
Utility functions for the AI-Roster system.
Contains helper functions for data loading, validation, and calculations.
"""

import yaml
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
import os


def load_yaml_file(filename: str) -> Dict[str, Any]:
    """Load and parse a YAML file."""
    try:
        with open(filename, 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file {filename} not found")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML file {filename}: {e}")


def validate_dates(roster_data: Dict[str, Any]) -> None:
    """Validate that the roster dates are valid and span a whole number of fortnights."""
    start_date = roster_data['dates']['start']
    end_date = roster_data['dates']['end']
    
    # Handle case where dates might already be datetime.date objects
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    # Calculate the number of days between dates
    total_days = (end_date - start_date).days + 1
    
    # Check if total days is a multiple of 14 (fortnight)
    if total_days % 14 != 0:
        raise ValueError(
            f"Roster period must span a whole number of fortnights (14-day blocks). "
            f"Current period spans {total_days} days."
        )


def calculate_fortnightly_blocks(start_date_str: str, end_date_str: str) -> List[Dict[str, date]]:
    """Calculate the fortnightly blocks for a given date range."""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    blocks = []
    current_start = start_date
    
    while current_start <= end_date:
        current_end = current_start + timedelta(days=13)  # 14-day block (13 days + current day)
        if current_end > end_date:
            current_end = end_date
        blocks.append({
            'start': current_start,
            'end': current_end
        })
        current_start = current_end + timedelta(days=1)
    
    return blocks


def get_skill_level_rank(skill_level: str) -> int:
    """Convert a skill level to its rank in the hierarchy."""
    skill_hierarchy = ["Acute", "Resus", "Triage", "Shift Coordinator"]
    try:
        return skill_hierarchy.index(skill_level)
    except ValueError:
        raise ValueError(f"Unknown skill level: {skill_level}")


def is_skill_sufficient(staff_skill_tags: List[str], required_skill_level: Optional[str]) -> bool:
    """Check if a staff member's skill tags meet the required skill level."""
    if required_skill_level is None:
        return True
    
    # If staff has no skills, they can't meet any requirement
    if not staff_skill_tags:
        return False
        
    # Get the rank of required skill level
    required_rank = get_skill_level_rank(required_skill_level)
    
    # Check if any of staff's skill tags meets the requirement
    for skill_tag in staff_skill_tags:
        staff_rank = get_skill_level_rank(skill_tag)
        if staff_rank >= required_rank:
            return True
    
    return False
