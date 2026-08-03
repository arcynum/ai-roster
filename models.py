"""
Data models for the AI-Roster system.
Contains classes for staff, shifts, and roster positions.
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import date
from enum import Enum


class Classification(Enum):
    """Staff classification types."""
    RN = "RN"
    CN = "CN"
    GRADUATE = "Graduate"


@dataclass
class Staff:
    """Represents a staff member."""
    name: str
    classification: Classification
    skill_tags: List[str]
    contracted_hours_per_fortnight: float
    red_requests: List[str]  # List of YYYY-MM-DD date strings
    holidays: List[dict]    # List of {start, end} date objects
    
    def __post_init__(self):
        """Validate the staff data after initialization."""
        if self.classification not in Classification:
            raise ValueError(f"Invalid classification: {self.classification}")
        
        # Validate skill tags are in correct hierarchy
        valid_hierarchy = ["Acute", "Resus", "Triage", "Shift Coordinator"]
        if not all(tag in valid_hierarchy for tag in self.skill_tags):
            raise ValueError(f"Invalid skill tags: {self.skill_tags}")
        
        # Check that skill tags form a contiguous prefix
        found_in_hierarchy = []
        for tag in self.skill_tags:
            if tag in valid_hierarchy:
                found_in_hierarchy.append(valid_hierarchy.index(tag))
        
        if found_in_hierarchy and found_in_hierarchy != list(range(len(found_in_hierarchy))):
            raise ValueError(f"Skill tags must form a contiguous prefix: {self.skill_tags}")


@dataclass
class Shift:
    """Represents a shift definition."""
    name: str
    start_time: str
    end_time: str
    span_hours: float
    paid_hours: float
    unpaid_break_minutes: int
    crosses_midnight: bool


@dataclass
class RosterPosition:
    """Represents a required position in the roster."""
    shift: str
    required_skill_level: Optional[str]  # None means any staff can fill


@dataclass
class RosterBlock:
    """Represents a 14-day fortnightly block."""
    start_date: date
    end_date: date
    positions: List[RosterPosition]