"""
SIMS Plus - Transport Models

Models for transport management: vehicles, drivers, routes, stops,
student transport assignments, trip logs, and vehicle maintenance.
"""

import uuid
from datetime import date, time
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.academic import AcademicYear
    from app.models.school import School
    from app.models.staff import Staff
    from app.models.student import Student
    from app.models.user import User


# =========================
# Enums
# =========================


class VehicleType(str, Enum):
    """Type of vehicle."""

    BUS = "bus"
    MINIBUS = "minibus"
    VAN = "van"
    CAR = "car"


class VehicleStatus(str, Enum):
    """Operational status of a vehicle."""

    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class DriverStatus(str, Enum):
    """Employment status of a driver."""

    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"


class RouteType(str, Enum):
    """Type of transport route."""

    MORNING_PICKUP = "morning_pickup"
    AFTERNOON_DROPOFF = "afternoon_dropoff"
    BOTH = "both"


class TransportAssignmentStatus(str, Enum):
    """Status of a student's transport assignment."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class TripType(str, Enum):
    """Type of trip."""

    MORNING_PICKUP = "morning_pickup"
    AFTERNOON_DROPOFF = "afternoon_dropoff"
    FIELD_TRIP = "field_trip"
    OTHER = "other"


class TripStatus(str, Enum):
    """Status of a trip."""

    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MaintenanceType(str, Enum):
    """Type of vehicle maintenance."""

    ROUTINE = "routine"
    REPAIR = "repair"
    INSPECTION = "inspection"
    EMERGENCY = "emergency"


# =========================
# Vehicle Model
# =========================


class Vehicle(Base, TenantMixin, SoftDeleteMixin):
    """
    Vehicle model.

    Represents a school transport vehicle.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "registration_number",
            name="uq_vehicles_tenant_registration",
        ),
        {"extend_existing": True},
    )

    registration_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Vehicle registration/plate number",
    )
    vehicle_type: Mapped[VehicleType] = mapped_column(
        SQLEnum(
            VehicleType,
            name="vehicletype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    make: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Vehicle make, e.g., Toyota, Mercedes",
    )
    # Python attr is model_name to avoid conflict with SQLAlchemy's model
    model_name: Mapped[Optional[str]] = mapped_column(
        "model",
        String(50),
        nullable=True,
        comment="Vehicle model, e.g., Coaster, Sprinter",
    )
    year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Year of manufacture",
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum passenger capacity",
    )
    status: Mapped[VehicleStatus] = mapped_column(
        SQLEnum(
            VehicleStatus,
            name="vehiclestatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VehicleStatus.ACTIVE,
    )
    insurance_expiry: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    roadworthy_expiry: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    gps_tracker_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="GPS tracking device identifier",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    routes: Mapped[list["Route"]] = relationship(
        "Route",
        back_populates="vehicle",
        lazy="raise",
    )
    maintenance_records: Mapped[list["VehicleMaintenance"]] = relationship(
        "VehicleMaintenance",
        back_populates="vehicle",
        lazy="raise",
    )


# =========================
# Driver Model
# =========================


class Driver(Base, TenantMixin, SoftDeleteMixin):
    """
    Driver model.

    Represents a vehicle driver. May optionally be linked to a staff record.
    """

    __tablename__ = "drivers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "license_number",
            name="uq_drivers_tenant_license",
        ),
        {"extend_existing": True},
    )

    staff_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional link to staff record if driver is also a staff member",
    )
    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    license_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    license_expiry: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    license_class: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Driver license class, e.g., B, C, D",
    )
    status: Mapped[DriverStatus] = mapped_column(
        SQLEnum(
            DriverStatus,
            name="driverstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DriverStatus.ACTIVE,
    )
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    staff: Mapped[Optional["Staff"]] = relationship("Staff", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")
    routes: Mapped[list["Route"]] = relationship(
        "Route",
        back_populates="driver",
        lazy="raise",
    )

    @property
    def full_name(self) -> str:
        """Get the driver's full name."""
        return f"{self.first_name} {self.last_name}"


# =========================
# Route Model
# =========================


class Route(Base, TenantMixin, SoftDeleteMixin):
    """
    Route model.

    Represents a transport route with stops, assigned vehicle, and driver.
    """

    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "route_code",
            name="uq_routes_tenant_route_code",
        ),
        {"extend_existing": True},
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Route name, e.g., East Legon Route, Tema Route",
    )
    route_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Short code for the route, e.g., ELR, TMR",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    distance_km: Mapped[Optional[float]] = mapped_column(
        Numeric(8, 2),
        nullable=True,
        comment="Total route distance in kilometers",
    )
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated trip duration in minutes",
    )
    vehicle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    driver_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="SET NULL"),
        nullable=True,
    )
    route_type: Mapped[RouteType] = mapped_column(
        SQLEnum(
            RouteType,
            name="routetype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    transport_fee_per_term: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Transport fee per term for this route",
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle",
        back_populates="routes",
        lazy="raise",
    )
    driver: Mapped[Optional["Driver"]] = relationship(
        "Driver",
        back_populates="routes",
        lazy="raise",
    )
    school: Mapped["School"] = relationship("School", lazy="raise")
    stops: Mapped[list["RouteStop"]] = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.stop_order",
        lazy="raise",
    )
    student_assignments: Mapped[list["StudentTransport"]] = relationship(
        "StudentTransport",
        back_populates="route",
        lazy="raise",
    )


# =========================
# Route Stop Model
# =========================


class RouteStop(Base, TenantMixin):
    """
    Route Stop model.

    Individual stop on a transport route.
    TenantMixin only (no SoftDeleteMixin, no school_id -- child of route).
    """

    __tablename__ = "route_stops"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "route_id", "stop_order",
            name="uq_route_stops_tenant_route_order",
        ),
        {"extend_existing": True},
    )

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    stop_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Name of the stop, e.g., East Legon Junction, Tema Station",
    )
    stop_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Order of the stop in the route sequence",
    )
    pickup_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    dropoff_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )
    landmark: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Nearby landmark for identification",
    )

    # Relationships
    route: Mapped["Route"] = relationship(
        "Route",
        back_populates="stops",
        lazy="raise",
    )


# =========================
# Student Transport Model
# =========================


class StudentTransport(Base, TenantMixin, SoftDeleteMixin):
    """
    Student Transport model.

    Assigns a student to a transport route and stop for an academic year.
    """

    __tablename__ = "student_transport"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "student_id", "academic_year_id",
            name="uq_student_transport_tenant_student_year",
        ),
        {"extend_existing": True},
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    stop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("route_stops.id", ondelete="CASCADE"),
        nullable=False,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[TransportAssignmentStatus] = mapped_column(
        SQLEnum(
            TransportAssignmentStatus,
            name="transportassignmentstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TransportAssignmentStatus.ACTIVE,
    )
    pickup_guardian_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    special_instructions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    route: Mapped["Route"] = relationship(
        "Route",
        back_populates="student_assignments",
        lazy="raise",
    )
    stop: Mapped["RouteStop"] = relationship("RouteStop", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Trip Log Model
# =========================


class TripLog(Base, TenantMixin, SoftDeleteMixin):
    """
    Trip Log model.

    Records details of a specific trip on a route.
    """

    __tablename__ = "trip_logs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "route_id", "trip_date", "trip_type",
            name="uq_trip_logs_tenant_route_date_type",
        ),
        {"extend_existing": True},
    )

    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    driver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False,
    )
    trip_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    trip_type: Mapped[TripType] = mapped_column(
        SQLEnum(
            TripType,
            name="triptype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    departure_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    arrival_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    odometer_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    odometer_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    student_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[TripStatus] = mapped_column(
        SQLEnum(
            TripStatus,
            name="tripstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TripStatus.SCHEDULED,
    )
    incidents: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description of any incidents during the trip",
    )
    logged_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who logged the trip",
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    route: Mapped["Route"] = relationship("Route", lazy="raise")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", lazy="raise")
    driver: Mapped["Driver"] = relationship("Driver", lazy="raise")
    logged_by: Mapped["User"] = relationship("User", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Vehicle Maintenance Model
# =========================


class VehicleMaintenance(Base, TenantMixin, SoftDeleteMixin):
    """
    Vehicle Maintenance model.

    Records maintenance and service history for a vehicle.
    """

    __tablename__ = "vehicle_maintenance"

    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    maintenance_type: Mapped[MaintenanceType] = mapped_column(
        SQLEnum(
            MaintenanceType,
            name="maintenancetype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    cost: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    service_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    next_service_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    odometer_reading: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    service_provider: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )
    invoice_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    logged_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who logged the maintenance record",
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship(
        "Vehicle",
        back_populates="maintenance_records",
        lazy="raise",
    )
    logged_by: Mapped["User"] = relationship("User", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")
