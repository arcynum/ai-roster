import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple

@dataclass
class ShiftDefinition:
    name: str
    start_time: str
    end_time: str
    duration: float
    crosses_midnight: bool
    start_dt: datetime.time
    end_dt: datetime.time

def get_shift_times_helper(date, shift_name, definitions):
    sd = definitions[shift_name]
    start = datetime.datetime.combine(date, sd.start_dt)
    end = datetime.datetime.combine(date, sd.end_dt)
    if sd.crosses_midnight: end += datetime.timedelta(days=1)
    return start, end

@dataclass
class ShiftRequirement:
    shift_name: str
    count: int

@dataclass
class Rule:
    id: Optional[str]
    description: str

@dataclass
class Preference:
    id: Optional[str]
    description: str

@dataclass
class StaffMember:
    name: str
    level: str
    training_level: str
    fte_hours: float
    red_requests: Set[datetime.date] = field(default_factory=set)
    holidays: List[Tuple[datetime.date, datetime.date]] = field(default_factory=list)
    rules: List[Rule] = field(default_factory=list)
    preferences: List[Preference] = field(default_factory=list)
    assigned_hours: float = 0.0
    assigned_shifts: List[Tuple[datetime.date, str]] = field(default_factory=list)
    weekend_hours: float = 0.0

TRAINING_LEVELS = ["Acute", "Resus", "Triage", "Shift Coordinator"]
TRAINING_MAP = {level: i for i, level in enumerate(TRAINING_LEVELS)}
