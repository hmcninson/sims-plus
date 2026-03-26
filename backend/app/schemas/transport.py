"""
SIMS Plus - Transport Schemas

Pydantic schemas for transport management endpoints.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        protected_namespaces=(),
    )


# =========================
# Vehicle Schemas
# =========================


class VehicleCreate(BaseSchema):
    """Create vehicle request."""

    registration_number: str = Field(..., min_length=1, max_length=20)
    vehicle_type: str = Field(..., pattern="^(bus|minibus|van|car)$")
    make: Optional[str] = Field(None, max_length=50)
    model_name: Optional[str] = Field(None, max_length=50)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    capacity: int = Field(..., gt=0)
    status: str = Field(default="active", pattern="^(active|maintenance|retired)$")
    insurance_expiry: Optional[date] = None
    roadworthy_expiry: Optional[date] = None
    gps_tracker_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class VehicleUpdate(BaseSchema):
    """Update vehicle request."""

    registration_number: Optional[str] = Field(None, min_length=1, max_length=20)
    vehicle_type: Optional[str] = Field(None, pattern="^(bus|minibus|van|car)$")
    make: Optional[str] = Field(None, max_length=50)
    model_name: Optional[str] = Field(None, max_length=50)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    capacity: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, pattern="^(active|maintenance|retired)$")
    insurance_expiry: Optional[date] = None
    roadworthy_expiry: Optional[date] = None
    gps_tracker_id: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class VehicleResponse(BaseSchema):
    """Vehicle response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    registration_number: str
    vehicle_type: str
    make: Optional[str] = None
    model_name: Optional[str] = None
    year: Optional[int] = None
    capacity: int
    status: str
    insurance_expiry: Optional[date] = None
    roadworthy_expiry: Optional[date] = None
    gps_tracker_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VehicleDetailResponse(VehicleResponse):
    """Vehicle with route and maintenance summary."""

    active_route_count: int = 0
    last_maintenance_date: Optional[date] = None
    next_maintenance_date: Optional[date] = None


class VehicleListResponse(BaseSchema):
    """Paginated vehicle list."""

    items: list[VehicleResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Driver Schemas
# =========================


class DriverCreate(BaseSchema):
    """Create driver request."""

    staff_id: Optional[UUID] = None
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    license_number: str = Field(..., min_length=1, max_length=50)
    license_expiry: date
    license_class: str = Field(..., min_length=1, max_length=10)
    status: str = Field(default="active", pattern="^(active|on_leave|terminated)$")
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)


class DriverUpdate(BaseSchema):
    """Update driver request."""

    staff_id: Optional[UUID] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=20)
    license_number: Optional[str] = Field(None, min_length=1, max_length=50)
    license_expiry: Optional[date] = None
    license_class: Optional[str] = Field(None, min_length=1, max_length=10)
    status: Optional[str] = Field(None, pattern="^(active|on_leave|terminated)$")
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)


class DriverResponse(BaseSchema):
    """Driver response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    staff_id: Optional[UUID] = None
    first_name: str
    last_name: str
    phone: str
    license_number: str
    license_expiry: date
    license_class: str
    status: str
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @property
    def full_name(self) -> str:
        """Get the driver's full name."""
        return f"{self.first_name} {self.last_name}"


class DriverListResponse(BaseSchema):
    """Paginated driver list."""

    items: list[DriverResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Route Schemas
# =========================


class RouteStopCreate(BaseSchema):
    """Create route stop request."""

    stop_name: str = Field(..., min_length=1, max_length=200)
    stop_order: int = Field(..., ge=1)
    pickup_time: Optional[time] = None
    dropoff_time: Optional[time] = None
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    landmark: Optional[str] = Field(None, max_length=200)


class RouteStopUpdate(BaseSchema):
    """Update route stop request."""

    stop_name: Optional[str] = Field(None, min_length=1, max_length=200)
    stop_order: Optional[int] = Field(None, ge=1)
    pickup_time: Optional[time] = None
    dropoff_time: Optional[time] = None
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)
    landmark: Optional[str] = Field(None, max_length=200)


class RouteStopResponse(BaseSchema):
    """Route stop response."""

    id: UUID
    tenant_id: UUID
    route_id: UUID
    stop_name: str
    stop_order: int
    pickup_time: Optional[time] = None
    dropoff_time: Optional[time] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    landmark: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RouteCreate(BaseSchema):
    """Create route request."""

    name: str = Field(..., min_length=1, max_length=100)
    route_code: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None
    distance_km: Optional[Decimal] = Field(None, ge=0)
    estimated_duration_minutes: Optional[int] = Field(None, gt=0)
    vehicle_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    route_type: str = Field(..., pattern="^(morning_pickup|afternoon_dropoff|both)$")
    is_active: bool = True
    transport_fee_per_term: Optional[Decimal] = Field(None, ge=0)
    stops: Optional[list[RouteStopCreate]] = None


class RouteUpdate(BaseSchema):
    """Update route request."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    route_code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    distance_km: Optional[Decimal] = Field(None, ge=0)
    estimated_duration_minutes: Optional[int] = Field(None, gt=0)
    vehicle_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    route_type: Optional[str] = Field(None, pattern="^(morning_pickup|afternoon_dropoff|both)$")
    is_active: Optional[bool] = None
    transport_fee_per_term: Optional[Decimal] = Field(None, ge=0)


class RouteResponse(BaseSchema):
    """Route response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    name: str
    route_code: str
    description: Optional[str] = None
    distance_km: Optional[Decimal] = None
    estimated_duration_minutes: Optional[int] = None
    vehicle_id: Optional[UUID] = None
    driver_id: Optional[UUID] = None
    route_type: str
    is_active: bool
    transport_fee_per_term: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class RouteDetailResponse(RouteResponse):
    """Route with stops and assignment details."""

    vehicle_registration: Optional[str] = None
    driver_name: Optional[str] = None
    stops: list[RouteStopResponse] = []
    student_count: int = 0


class RouteListResponse(BaseSchema):
    """Paginated route list."""

    items: list[RouteResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Student Transport Schemas
# =========================


class StudentTransportCreate(BaseSchema):
    """Assign student to transport route."""

    student_id: UUID
    route_id: UUID
    stop_id: UUID
    academic_year_id: UUID
    status: str = Field(
        default="active",
        pattern="^(active|suspended|cancelled)$",
    )
    pickup_guardian_phone: Optional[str] = Field(None, max_length=20)
    special_instructions: Optional[str] = None


class StudentTransportUpdate(BaseSchema):
    """Update student transport assignment."""

    route_id: Optional[UUID] = None
    stop_id: Optional[UUID] = None
    status: Optional[str] = Field(None, pattern="^(active|suspended|cancelled)$")
    pickup_guardian_phone: Optional[str] = Field(None, max_length=20)
    special_instructions: Optional[str] = None


class StudentTransportResponse(BaseSchema):
    """Student transport assignment response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    student_id: UUID
    route_id: UUID
    stop_id: UUID
    academic_year_id: UUID
    status: str
    pickup_guardian_phone: Optional[str] = None
    special_instructions: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StudentTransportDetailResponse(StudentTransportResponse):
    """Student transport with nested info."""

    student_name: Optional[str] = None
    route_name: Optional[str] = None
    stop_name: Optional[str] = None
    academic_year_name: Optional[str] = None
    pickup_time: Optional[time] = None
    dropoff_time: Optional[time] = None


class StudentTransportListResponse(BaseSchema):
    """Paginated student transport list."""

    items: list[StudentTransportDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Trip Log Schemas
# =========================


class TripLogCreate(BaseSchema):
    """Create trip log request."""

    route_id: UUID
    vehicle_id: UUID
    driver_id: UUID
    trip_date: date
    trip_type: str = Field(
        ...,
        pattern="^(morning_pickup|afternoon_dropoff|field_trip|other)$",
    )
    departure_time: Optional[time] = None
    arrival_time: Optional[time] = None
    odometer_start: Optional[int] = Field(None, ge=0)
    odometer_end: Optional[int] = Field(None, ge=0)
    student_count: int = Field(..., ge=0)
    status: str = Field(
        default="scheduled",
        pattern="^(scheduled|in_progress|completed|cancelled)$",
    )
    incidents: Optional[str] = None


class TripLogUpdate(BaseSchema):
    """Update trip log request."""

    departure_time: Optional[time] = None
    arrival_time: Optional[time] = None
    odometer_start: Optional[int] = Field(None, ge=0)
    odometer_end: Optional[int] = Field(None, ge=0)
    student_count: Optional[int] = Field(None, ge=0)
    status: Optional[str] = Field(
        None,
        pattern="^(scheduled|in_progress|completed|cancelled)$",
    )
    incidents: Optional[str] = None


class TripLogResponse(BaseSchema):
    """Trip log response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    route_id: UUID
    vehicle_id: UUID
    driver_id: UUID
    trip_date: date
    trip_type: str
    departure_time: Optional[time] = None
    arrival_time: Optional[time] = None
    odometer_start: Optional[int] = None
    odometer_end: Optional[int] = None
    student_count: int
    status: str
    incidents: Optional[str] = None
    logged_by_id: UUID
    created_at: datetime
    updated_at: datetime


class TripLogDetailResponse(TripLogResponse):
    """Trip log with names."""

    route_name: Optional[str] = None
    vehicle_registration: Optional[str] = None
    driver_name: Optional[str] = None
    logged_by_name: Optional[str] = None


class TripLogListResponse(BaseSchema):
    """Paginated trip log list."""

    items: list[TripLogDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Vehicle Maintenance Schemas
# =========================


class VehicleMaintenanceCreate(BaseSchema):
    """Create vehicle maintenance record."""

    vehicle_id: UUID
    maintenance_type: str = Field(
        ...,
        pattern="^(routine|repair|inspection|emergency)$",
    )
    description: str = Field(..., min_length=1)
    cost: Optional[Decimal] = Field(None, ge=0)
    service_date: date
    next_service_date: Optional[date] = None
    odometer_reading: Optional[int] = Field(None, ge=0)
    service_provider: Optional[str] = Field(None, max_length=200)
    invoice_number: Optional[str] = Field(None, max_length=50)

    @field_validator("next_service_date")
    @classmethod
    def validate_next_service_date(cls, v: Optional[date], info) -> Optional[date]:
        """Next service date must be after service date."""
        service = info.data.get("service_date")
        if v and service and v <= service:
            raise ValueError("Next service date must be after service date")
        return v


class VehicleMaintenanceUpdate(BaseSchema):
    """Update vehicle maintenance record."""

    maintenance_type: Optional[str] = Field(
        None,
        pattern="^(routine|repair|inspection|emergency)$",
    )
    description: Optional[str] = Field(None, min_length=1)
    cost: Optional[Decimal] = Field(None, ge=0)
    service_date: Optional[date] = None
    next_service_date: Optional[date] = None
    odometer_reading: Optional[int] = Field(None, ge=0)
    service_provider: Optional[str] = Field(None, max_length=200)
    invoice_number: Optional[str] = Field(None, max_length=50)


class VehicleMaintenanceResponse(BaseSchema):
    """Vehicle maintenance response."""

    id: UUID
    tenant_id: UUID
    school_id: UUID
    vehicle_id: UUID
    maintenance_type: str
    description: str
    cost: Optional[Decimal] = None
    service_date: date
    next_service_date: Optional[date] = None
    odometer_reading: Optional[int] = None
    service_provider: Optional[str] = None
    invoice_number: Optional[str] = None
    logged_by_id: UUID
    created_at: datetime
    updated_at: datetime


class VehicleMaintenanceDetailResponse(VehicleMaintenanceResponse):
    """Maintenance with vehicle info."""

    vehicle_registration: Optional[str] = None
    logged_by_name: Optional[str] = None


class VehicleMaintenanceListResponse(BaseSchema):
    """Paginated vehicle maintenance list."""

    items: list[VehicleMaintenanceDetailResponse]
    total: int
    page: int
    page_size: int
    pages: int


# =========================
# Transport Stats Schemas
# =========================


class TransportStatsResponse(BaseSchema):
    """Transport statistics."""

    total_vehicles: int = 0
    active_vehicles: int = 0
    maintenance_vehicles: int = 0
    total_drivers: int = 0
    active_drivers: int = 0
    total_routes: int = 0
    active_routes: int = 0
    total_students_assigned: int = 0
    trips_today: int = 0
