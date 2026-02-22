"""
SIMS Plus - Boarding Services Package

Re-exports all boarding service classes for backward compatibility.
Existing imports like `from app.services.boarding import HouseService` continue to work.
"""

from app.services.boarding._shared import BoardingServiceError
from app.services.boarding.house_service import HouseService
from app.services.boarding.assignment_service import BoardingAssignmentService
from app.services.boarding.roll_call_service import RollCallService
from app.services.boarding.exeat_service import ExeatService
from app.services.boarding.incident_service import IncidentService
from app.services.boarding.dining_service import DiningService

__all__ = [
    "BoardingServiceError",
    "HouseService",
    "BoardingAssignmentService",
    "RollCallService",
    "ExeatService",
    "IncidentService",
    "DiningService",
]
