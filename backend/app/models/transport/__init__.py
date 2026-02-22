"""
SIMS Plus - Transport Models Package

Re-exports all transport model classes and enums for backward compatibility.
All external code can continue to use:
    from app.models.transport import Vehicle, Route, ...
"""

from .models import (
    # Enums
    VehicleType,
    VehicleStatus,
    DriverStatus,
    RouteType,
    TransportAssignmentStatus,
    TripType,
    TripStatus,
    MaintenanceType,
    # Models
    Vehicle,
    Driver,
    Route,
    RouteStop,
    StudentTransport,
    TripLog,
    VehicleMaintenance,
)

__all__ = [
    # Enums
    "VehicleType",
    "VehicleStatus",
    "DriverStatus",
    "RouteType",
    "TransportAssignmentStatus",
    "TripType",
    "TripStatus",
    "MaintenanceType",
    # Models
    "Vehicle",
    "Driver",
    "Route",
    "RouteStop",
    "StudentTransport",
    "TripLog",
    "VehicleMaintenance",
]
