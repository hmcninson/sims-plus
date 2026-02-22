"""
SIMS Plus - Transport Services Package

Re-exports all transport service classes for backward compatibility.
Existing imports like `from app.services.transport import VehicleService` continue to work.
"""

from app.services.transport._shared import TransportServiceError
from app.services.transport.vehicle_service import VehicleService
from app.services.transport.driver_service import DriverService
from app.services.transport.route_service import RouteService
from app.services.transport.assignment_service import TransportAssignmentService
from app.services.transport.trip_service import TripService

__all__ = [
    "TransportServiceError",
    "VehicleService",
    "DriverService",
    "RouteService",
    "TransportAssignmentService",
    "TripService",
]
