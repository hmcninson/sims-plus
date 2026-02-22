"""
SIMS Plus - Boarding House Models

Models for boarding house management: houses, dormitories, beds,
student boarding assignments, roll calls, exeats, incidents, and dining.
"""

import uuid
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TenantMixin

if TYPE_CHECKING:
    from app.models.school import School
    from app.models.staff import Staff
    from app.models.student import Student
    from app.models.user import User
    from app.models.academic import AcademicYear


# =========================
# Enums
# =========================


class HouseGender(str, Enum):
    """Gender assignment for a house."""

    MALE = "male"
    FEMALE = "female"
    MIXED = "mixed"


class DormitoryType(str, Enum):
    """Type of dormitory layout."""

    ROOM = "room"
    HALL = "hall"
    CUBICLE = "cubicle"


class BedType(str, Enum):
    """Type of bed."""

    SINGLE = "single"
    BUNK_UPPER = "bunk_upper"
    BUNK_LOWER = "bunk_lower"


class BedStatus(str, Enum):
    """Current status of a bed."""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"


class BoardingStatus(str, Enum):
    """Boarding assignment status for a student."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"
    GRADUATED = "graduated"


class RollCallType(str, Enum):
    """Type of roll call."""

    MORNING = "morning"
    EVENING = "evening"
    LIGHTS_OUT = "lights_out"
    EMERGENCY = "emergency"


class RollCallEntryStatus(str, Enum):
    """Student status during a roll call."""

    PRESENT = "present"
    ABSENT = "absent"
    SICK_BAY = "sick_bay"
    EXEAT = "exeat"
    AWOL = "awol"


class ExeatType(str, Enum):
    """Type of exeat request."""

    WEEKEND = "weekend"
    MEDICAL = "medical"
    EMERGENCY = "emergency"
    FUNERAL = "funeral"
    OTHER = "other"


class ExeatStatus(str, Enum):
    """Status of an exeat request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    ACTIVE = "active"
    RETURNED = "returned"
    OVERDUE = "overdue"


class IncidentType(str, Enum):
    """Type of boarding incident."""

    DISCIPLINARY = "disciplinary"
    HEALTH = "health"
    PROPERTY_DAMAGE = "property_damage"
    MISSING_STUDENT = "missing_student"
    BULLYING = "bullying"
    THEFT = "theft"
    OTHER = "other"


class IncidentSeverity(str, Enum):
    """Severity of a boarding incident."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MealType(str, Enum):
    """Type of meal."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


# =========================
# House Model
# =========================


class House(Base, TenantMixin, SoftDeleteMixin):
    """
    House model.

    Represents a boarding house within a school (e.g., "Eagle House").
    Each house may have a house parent (staff member) and multiple dormitories.
    """

    __tablename__ = "houses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "house_code", name="uq_houses_tenant_house_code"),
        UniqueConstraint("tenant_id", "name", name="uq_houses_tenant_name"),
        {"extend_existing": True},
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="House name, e.g., Eagle House, Lion House",
    )
    house_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Short code for the house, e.g., EGL, LIO",
    )
    gender: Mapped[HouseGender] = mapped_column(
        SQLEnum(
            HouseGender,
            name="housegender",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum number of students the house can hold",
    )
    house_parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member who is the house parent",
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    school: Mapped["School"] = relationship("School", lazy="raise")
    house_parent: Mapped[Optional["Staff"]] = relationship("Staff", lazy="raise")
    dormitories: Mapped[list["Dormitory"]] = relationship(
        "Dormitory",
        back_populates="house",
        cascade="all, delete-orphan",
        lazy="raise",
    )
    student_boardings: Mapped[list["StudentBoarding"]] = relationship(
        "StudentBoarding",
        back_populates="house",
        lazy="raise",
    )


# =========================
# Dormitory Model
# =========================


class Dormitory(Base, TenantMixin, SoftDeleteMixin):
    """
    Dormitory model.

    Represents a dormitory room/hall within a house.
    """

    __tablename__ = "dormitories"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "house_id", "name",
            name="uq_dormitories_tenant_house_name",
        ),
        {"extend_existing": True},
    )

    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Dormitory name, e.g., Room A1, Hall 3",
    )
    floor: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Floor or level, e.g., Ground, 1st, 2nd",
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Maximum number of beds/students",
    )
    dormitory_type: Mapped[DormitoryType] = mapped_column(
        SQLEnum(
            DormitoryType,
            name="dormitorytype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    house: Mapped["House"] = relationship(
        "House",
        back_populates="dormitories",
        lazy="raise",
    )
    school: Mapped["School"] = relationship("School", lazy="raise")
    beds: Mapped[list["Bed"]] = relationship(
        "Bed",
        back_populates="dormitory",
        cascade="all, delete-orphan",
        lazy="raise",
    )


# =========================
# Bed Model
# =========================


class Bed(Base, TenantMixin, SoftDeleteMixin):
    """
    Bed model.

    Represents a single bed within a dormitory.
    """

    __tablename__ = "beds"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "dormitory_id", "bed_number",
            name="uq_beds_tenant_dormitory_bed_number",
        ),
        {"extend_existing": True},
    )

    dormitory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dormitories.id", ondelete="CASCADE"),
        nullable=False,
    )
    bed_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Bed identifier, e.g., A1-01, B2-03",
    )
    bed_type: Mapped[BedType] = mapped_column(
        SQLEnum(
            BedType,
            name="bedtype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status: Mapped[BedStatus] = mapped_column(
        SQLEnum(
            BedStatus,
            name="bedstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BedStatus.AVAILABLE,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    dormitory: Mapped["Dormitory"] = relationship(
        "Dormitory",
        back_populates="beds",
        lazy="raise",
    )
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Student Boarding Model
# =========================


class StudentBoarding(Base, TenantMixin, SoftDeleteMixin):
    """
    Student Boarding model.

    Assigns a student to a house, dormitory, and bed for an academic year.
    """

    __tablename__ = "student_boarding"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "student_id", "academic_year_id",
            name="uq_student_boarding_tenant_student_year",
        ),
        UniqueConstraint(
            "tenant_id", "bed_id", "academic_year_id",
            name="uq_student_boarding_tenant_bed_year",
        ),
        {"extend_existing": True},
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
    )
    dormitory_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dormitories.id", ondelete="SET NULL"),
        nullable=True,
    )
    bed_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False,
    )
    boarding_status: Mapped[BoardingStatus] = mapped_column(
        SQLEnum(
            BoardingStatus,
            name="boardingstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BoardingStatus.ACTIVE,
    )
    check_in_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    check_out_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    house: Mapped["House"] = relationship(
        "House",
        back_populates="student_boardings",
        lazy="raise",
    )
    dormitory: Mapped[Optional["Dormitory"]] = relationship("Dormitory", lazy="raise")
    bed: Mapped[Optional["Bed"]] = relationship("Bed", lazy="raise")
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Boarding Roll Call Model
# =========================


class BoardingRollCall(Base, TenantMixin, SoftDeleteMixin):
    """
    Boarding Roll Call model.

    Records a roll call event for a house on a specific date and time.
    """

    __tablename__ = "boarding_roll_call"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "house_id", "date", "roll_call_type",
            name="uq_boarding_roll_call_tenant_house_date_type",
        ),
        {"extend_existing": True},
    )

    house_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("houses.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    roll_call_type: Mapped[RollCallType] = mapped_column(
        SQLEnum(
            RollCallType,
            name="rollcalltype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    conducted_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who conducted the roll call",
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
    house: Mapped["House"] = relationship("House", lazy="raise")
    conducted_by: Mapped["User"] = relationship("User", lazy="raise")
    school: Mapped["School"] = relationship("School", lazy="raise")
    entries: Mapped[list["BoardingRollCallEntry"]] = relationship(
        "BoardingRollCallEntry",
        back_populates="roll_call",
        cascade="all, delete-orphan",
        lazy="raise",
    )


# =========================
# Boarding Roll Call Entry Model
# =========================


class BoardingRollCallEntry(Base, TenantMixin):
    """
    Boarding Roll Call Entry model.

    Records the status of a single student during a roll call.
    Junction-style table: TenantMixin only (no SoftDeleteMixin, no school_id).
    Uses hard delete.
    """

    __tablename__ = "boarding_roll_call_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "roll_call_id", "student_id",
            name="uq_boarding_roll_call_entries_tenant_roll_call_student",
        ),
        {"extend_existing": True},
    )

    roll_call_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("boarding_roll_call.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[RollCallEntryStatus] = mapped_column(
        SQLEnum(
            RollCallEntryStatus,
            name="rollcallentrystatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    # Relationships
    roll_call: Mapped["BoardingRollCall"] = relationship(
        "BoardingRollCall",
        back_populates="entries",
        lazy="raise",
    )
    student: Mapped["Student"] = relationship("Student", lazy="raise")


# =========================
# Exeat Model
# =========================


class Exeat(Base, TenantMixin, SoftDeleteMixin):
    """
    Exeat model.

    Records a student's leave of absence from the boarding house.
    """

    __tablename__ = "exeats"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who submitted the exeat request",
    )
    approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved/denied the exeat",
    )
    exeat_type: Mapped[ExeatType] = mapped_column(
        SQLEnum(
            ExeatType,
            name="exeattype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    end_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    actual_return_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    status: Mapped[ExeatStatus] = mapped_column(
        SQLEnum(
            ExeatStatus,
            name="exeatstatus",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExeatStatus.PENDING,
    )
    guardian_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    guardian_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
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
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    requested_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[requested_by_id],
        lazy="raise",
    )
    approved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by_id],
        lazy="raise",
    )
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Boarding Incident Model
# =========================


class BoardingIncident(Base, TenantMixin, SoftDeleteMixin):
    """
    Boarding Incident model.

    Records incidents involving boarding students.
    """

    __tablename__ = "boarding_incidents"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    reported_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who reported the incident",
    )
    incident_type: Mapped[IncidentType] = mapped_column(
        SQLEnum(
            IncidentType,
            name="incidenttype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        SQLEnum(
            IncidentSeverity,
            name="incidentseverity",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    action_taken: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    resolved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parent_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", lazy="raise")
    reported_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[reported_by_id],
        lazy="raise",
    )
    resolved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_id],
        lazy="raise",
    )
    school: Mapped["School"] = relationship("School", lazy="raise")


# =========================
# Dining Meal Model
# =========================


class DiningMeal(Base, TenantMixin, SoftDeleteMixin):
    """
    Dining Meal model.

    Records meal information for the boarding dining hall.
    """

    __tablename__ = "dining_meals"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "school_id", "date", "meal_type",
            name="uq_dining_meals_tenant_school_date_meal",
        ),
        {"extend_existing": True},
    )

    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    meal_type: Mapped[MealType] = mapped_column(
        SQLEnum(
            MealType,
            name="mealtype",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    menu_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    head_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    prepared_by: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Name of person/team who prepared the meal",
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
