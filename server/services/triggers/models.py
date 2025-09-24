"""Data models for triggers and reminders."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class TriggerType(Enum):
    """Types of triggers."""
    ONE_TIME = "one_time"
    RECURRING = "recurring"


class Reminder(BaseModel):
    """Reminder/trigger model."""
    id: Optional[str] = None
    phone_number: str
    title: str
    description: str
    scheduled_time: datetime
    trigger_type: TriggerType
    recurrence_pattern: Optional[str] = None
    specialist_name: Optional[str] = None
    created_at: Optional[datetime] = None
    completed: bool = False
    active: bool = True


class RecurrencePattern(BaseModel):
    """Recurrence pattern for recurring reminders."""
    pattern_type: str  # "daily", "weekly", "monthly"
    interval: int = 1  # Every N days/weeks/months
    days_of_week: Optional[list] = None  # For weekly patterns
    day_of_month: Optional[int] = None  # For monthly patterns