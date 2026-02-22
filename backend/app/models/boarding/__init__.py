"""
SIMS Plus - Boarding Models Package

Re-exports all boarding model classes and enums for backward compatibility.
All external code can continue to use:
    from app.models.boarding import House, Dormitory, ...
"""

from .models import (
    # Enums
    HouseGender,
    DormitoryType,
    BedType,
    BedStatus,
    BoardingStatus,
    RollCallType,
    RollCallEntryStatus,
    ExeatType,
    ExeatStatus,
    IncidentType,
    IncidentSeverity,
    MealType,
    # Models
    House,
    Dormitory,
    Bed,
    StudentBoarding,
    BoardingRollCall,
    BoardingRollCallEntry,
    Exeat,
    BoardingIncident,
    DiningMeal,
)

__all__ = [
    # Enums
    "HouseGender",
    "DormitoryType",
    "BedType",
    "BedStatus",
    "BoardingStatus",
    "RollCallType",
    "RollCallEntryStatus",
    "ExeatType",
    "ExeatStatus",
    "IncidentType",
    "IncidentSeverity",
    "MealType",
    # Models
    "House",
    "Dormitory",
    "Bed",
    "StudentBoarding",
    "BoardingRollCall",
    "BoardingRollCallEntry",
    "Exeat",
    "BoardingIncident",
    "DiningMeal",
]
