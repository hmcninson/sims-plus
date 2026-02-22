"""Add boarding house and transport management tables

Creates 16 tables (9 boarding, 7 transport) with 20 enum types.
All tables have RLS enabled and forced with hardened tenant isolation.

Boarding tables:
- houses, dormitories, beds, student_boarding, boarding_roll_call,
  boarding_roll_call_entries, exeats, boarding_incidents, dining_meals

Transport tables:
- vehicles, drivers, routes, route_stops, student_transport,
  trip_logs, vehicle_maintenance

Revision ID: 20260222_0100
Revises: 20260221_0400
Create Date: 2026-02-22

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM


revision: str = "20260222_0100"
down_revision: Union[str, None] = "20260221_0400"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# -----------------------------------------------------------------------
# All 16 new tenant-scoped tables (must be added to conftest.py too)
# -----------------------------------------------------------------------
NEW_TENANT_SCOPED_TABLES = [
    # Boarding
    "houses",
    "dormitories",
    "beds",
    "student_boarding",
    "boarding_roll_call",
    "boarding_roll_call_entries",
    "exeats",
    "boarding_incidents",
    "dining_meals",
    # Transport
    "vehicles",
    "drivers",
    "routes",
    "route_stops",
    "student_transport",
    "trip_logs",
    "vehicle_maintenance",
]

# -----------------------------------------------------------------------
# All 20 new enum types
# -----------------------------------------------------------------------
ENUM_DEFINITIONS = {
    # Boarding enums
    "housegender": ("male", "female", "mixed"),
    "dormitorytype": ("room", "hall", "cubicle"),
    "bedtype": ("single", "bunk_upper", "bunk_lower"),
    "bedstatus": ("available", "occupied", "maintenance"),
    "boardingstatus": ("active", "withdrawn", "suspended", "graduated"),
    "rollcalltype": ("morning", "evening", "lights_out", "emergency"),
    "rollcallentrystatus": ("present", "absent", "sick_bay", "exeat", "awol"),
    "exeattype": ("weekend", "medical", "emergency", "funeral", "other"),
    "exeatstatus": ("pending", "approved", "denied", "active", "returned", "overdue"),
    "incidenttype": ("disciplinary", "health", "property_damage", "missing_student", "bullying", "theft", "other"),
    "incidentseverity": ("low", "medium", "high", "critical"),
    "mealtype": ("breakfast", "lunch", "dinner", "snack"),
    # Transport enums
    "vehicletype": ("bus", "minibus", "van", "car"),
    "vehiclestatus": ("active", "maintenance", "retired"),
    "driverstatus": ("active", "on_leave", "terminated"),
    "routetype": ("morning_pickup", "afternoon_dropoff", "both"),
    "transportassignmentstatus": ("active", "suspended", "cancelled"),
    "triptype": ("morning_pickup", "afternoon_dropoff", "field_trip", "other"),
    "tripstatus": ("scheduled", "in_progress", "completed", "cancelled"),
    "maintenancetype": ("routine", "repair", "inspection", "emergency"),
}


def _enable_rls(table_name: str) -> None:
    """Enable and force RLS with hardened tenant isolation policy."""
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
            FOR ALL TO sims_app_user
            USING (tenant_id = get_current_tenant_id())
            WITH CHECK (tenant_id = get_current_tenant_id())
    """)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO sims_app_user")


def _disable_rls(table_name: str) -> None:
    """Drop RLS policy and disable RLS."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name}")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Create all enum types
    # ------------------------------------------------------------------
    for enum_name, values in ENUM_DEFINITIONS.items():
        values_str = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {enum_name} AS ENUM ({values_str})")

    # ------------------------------------------------------------------
    # Phase 2: Create boarding tables
    # ------------------------------------------------------------------

    # 1. houses
    op.create_table(
        "houses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("house_code", sa.String(20), nullable=False),
        sa.Column("gender", ENUM("male", "female", "mixed", name="housegender", create_type=False), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("house_parent_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "house_code", name="uq_houses_tenant_house_code"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_houses_tenant_name"),
    )

    # 2. dormitories
    op.create_table(
        "dormitories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("house_id", UUID(as_uuid=True), sa.ForeignKey("houses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("floor", sa.String(20), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("dormitory_type", ENUM("room", "hall", "cubicle", name="dormitorytype", create_type=False), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "house_id", "name", name="uq_dormitories_tenant_house_name"),
    )

    # 3. beds
    op.create_table(
        "beds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dormitory_id", UUID(as_uuid=True), sa.ForeignKey("dormitories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bed_number", sa.String(20), nullable=False),
        sa.Column("bed_type", ENUM("single", "bunk_upper", "bunk_lower", name="bedtype", create_type=False), nullable=False),
        sa.Column("status", ENUM("available", "occupied", "maintenance", name="bedstatus", create_type=False), nullable=False, server_default="available"),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "dormitory_id", "bed_number", name="uq_beds_tenant_dormitory_bed_number"),
    )

    # 4. student_boarding
    op.create_table(
        "student_boarding",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("house_id", UUID(as_uuid=True), sa.ForeignKey("houses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dormitory_id", UUID(as_uuid=True), sa.ForeignKey("dormitories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("bed_id", UUID(as_uuid=True), sa.ForeignKey("beds.id", ondelete="SET NULL"), nullable=True),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("boarding_status", ENUM("active", "withdrawn", "suspended", "graduated", name="boardingstatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("check_in_date", sa.Date, nullable=False),
        sa.Column("check_out_date", sa.Date, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "student_id", "academic_year_id", name="uq_student_boarding_tenant_student_year"),
        sa.UniqueConstraint("tenant_id", "bed_id", "academic_year_id", name="uq_student_boarding_tenant_bed_year"),
    )

    # 5. boarding_roll_call
    op.create_table(
        "boarding_roll_call",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("house_id", UUID(as_uuid=True), sa.ForeignKey("houses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("roll_call_type", ENUM("morning", "evening", "lights_out", "emergency", name="rollcalltype", create_type=False), nullable=False),
        sa.Column("conducted_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "house_id", "date", "roll_call_type", name="uq_boarding_roll_call_tenant_house_date_type"),
    )

    # 6. boarding_roll_call_entries (junction-style: no SoftDeleteMixin, no school_id)
    op.create_table(
        "boarding_roll_call_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("roll_call_id", UUID(as_uuid=True), sa.ForeignKey("boarding_roll_call.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", ENUM("present", "absent", "sick_bay", "exeat", "awol", name="rollcallentrystatus", create_type=False), nullable=False),
        sa.Column("notes", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "roll_call_id", "student_id", name="uq_boarding_roll_call_entries_tenant_roll_call_student"),
    )

    # 7. exeats
    op.create_table(
        "exeats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("exeat_type", ENUM("weekend", "medical", "emergency", "funeral", "other", name="exeattype", create_type=False), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("actual_return_date", sa.Date, nullable=True),
        sa.Column("status", ENUM("pending", "approved", "denied", "active", "returned", "overdue", name="exeatstatus", create_type=False), nullable=False, server_default="pending"),
        sa.Column("guardian_notified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("guardian_phone", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 8. boarding_incidents
    op.create_table(
        "boarding_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reported_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("incident_type", ENUM("disciplinary", "health", "property_damage", "missing_student", "bullying", "theft", "other", name="incidenttype", create_type=False), nullable=False),
        sa.Column("severity", ENUM("low", "medium", "high", "critical", name="incidentseverity", create_type=False), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("action_taken", sa.Text, nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("resolved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_notified", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 9. dining_meals
    op.create_table(
        "dining_meals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("meal_type", ENUM("breakfast", "lunch", "dinner", "snack", name="mealtype", create_type=False), nullable=False),
        sa.Column("menu_description", sa.Text, nullable=True),
        sa.Column("head_count", sa.Integer, nullable=True),
        sa.Column("prepared_by", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "school_id", "date", "meal_type", name="uq_dining_meals_tenant_school_date_meal"),
    )

    # ------------------------------------------------------------------
    # Phase 3: Create transport tables
    # ------------------------------------------------------------------

    # 10. vehicles
    op.create_table(
        "vehicles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("registration_number", sa.String(20), nullable=False),
        sa.Column("vehicle_type", ENUM("bus", "minibus", "van", "car", name="vehicletype", create_type=False), nullable=False),
        sa.Column("make", sa.String(50), nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("status", ENUM("active", "maintenance", "retired", name="vehiclestatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("insurance_expiry", sa.Date, nullable=True),
        sa.Column("roadworthy_expiry", sa.Date, nullable=True),
        sa.Column("gps_tracker_id", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "registration_number", name="uq_vehicles_tenant_registration"),
    )

    # 11. drivers
    op.create_table(
        "drivers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id", ondelete="SET NULL"), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("license_number", sa.String(50), nullable=False),
        sa.Column("license_expiry", sa.Date, nullable=False),
        sa.Column("license_class", sa.String(10), nullable=False),
        sa.Column("status", ENUM("active", "on_leave", "terminated", name="driverstatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("emergency_contact_name", sa.String(200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(20), nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "license_number", name="uq_drivers_tenant_license"),
    )

    # 12. routes
    op.create_table(
        "routes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("route_code", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("distance_km", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=True),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("route_type", ENUM("morning_pickup", "afternoon_dropoff", "both", name="routetype", create_type=False), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("transport_fee_per_term", sa.Numeric(10, 2), nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "route_code", name="uq_routes_tenant_route_code"),
    )

    # 13. route_stops (no SoftDeleteMixin, no school_id -- child of route)
    op.create_table(
        "route_stops",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stop_name", sa.String(200), nullable=False),
        sa.Column("stop_order", sa.Integer, nullable=False),
        sa.Column("pickup_time", sa.Time, nullable=True),
        sa.Column("dropoff_time", sa.Time, nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("landmark", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "route_id", "stop_order", name="uq_route_stops_tenant_route_order"),
    )

    # 14. student_transport
    op.create_table(
        "student_transport",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stop_id", UUID(as_uuid=True), sa.ForeignKey("route_stops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year_id", UUID(as_uuid=True), sa.ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", ENUM("active", "suspended", "cancelled", name="transportassignmentstatus", create_type=False), nullable=False, server_default="active"),
        sa.Column("pickup_guardian_phone", sa.String(20), nullable=True),
        sa.Column("special_instructions", sa.Text, nullable=True),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "student_id", "academic_year_id", name="uq_student_transport_tenant_student_year"),
    )

    # 15. trip_logs
    op.create_table(
        "trip_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("driver_id", UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trip_date", sa.Date, nullable=False),
        sa.Column("trip_type", ENUM("morning_pickup", "afternoon_dropoff", "field_trip", "other", name="triptype", create_type=False), nullable=False),
        sa.Column("departure_time", sa.Time, nullable=True),
        sa.Column("arrival_time", sa.Time, nullable=True),
        sa.Column("odometer_start", sa.Integer, nullable=True),
        sa.Column("odometer_end", sa.Integer, nullable=True),
        sa.Column("student_count", sa.Integer, nullable=False),
        sa.Column("status", ENUM("scheduled", "in_progress", "completed", "cancelled", name="tripstatus", create_type=False), nullable=False, server_default="scheduled"),
        sa.Column("incidents", sa.Text, nullable=True),
        sa.Column("logged_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "route_id", "trip_date", "trip_type", name="uq_trip_logs_tenant_route_date_type"),
    )

    # 16. vehicle_maintenance
    op.create_table(
        "vehicle_maintenance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("maintenance_type", ENUM("routine", "repair", "inspection", "emergency", name="maintenancetype", create_type=False), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("service_date", sa.Date, nullable=False),
        sa.Column("next_service_date", sa.Date, nullable=True),
        sa.Column("odometer_reading", sa.Integer, nullable=True),
        sa.Column("service_provider", sa.String(200), nullable=True),
        sa.Column("invoice_number", sa.String(50), nullable=True),
        sa.Column("logged_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", UUID(as_uuid=True), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------------
    # Phase 4: Create composite indexes
    # ------------------------------------------------------------------

    # Boarding indexes
    op.create_index("idx_houses_tenant_id", "houses", ["tenant_id"])
    op.create_index("idx_houses_tenant_school", "houses", ["tenant_id", "school_id"])
    op.create_index("idx_houses_tenant_active", "houses", ["tenant_id", "is_active"])

    op.create_index("idx_dormitories_tenant_id", "dormitories", ["tenant_id"])
    op.create_index("idx_dormitories_tenant_house", "dormitories", ["tenant_id", "house_id"])

    op.create_index("idx_beds_tenant_id", "beds", ["tenant_id"])
    op.create_index("idx_beds_tenant_dormitory", "beds", ["tenant_id", "dormitory_id"])
    op.create_index("idx_beds_tenant_status", "beds", ["tenant_id", "status"])

    op.create_index("idx_student_boarding_tenant_id", "student_boarding", ["tenant_id"])
    op.create_index("idx_student_boarding_tenant_student", "student_boarding", ["tenant_id", "student_id"])
    op.create_index("idx_student_boarding_tenant_house_year", "student_boarding", ["tenant_id", "house_id", "academic_year_id"])
    op.create_index("idx_student_boarding_tenant_status", "student_boarding", ["tenant_id", "boarding_status"])

    op.create_index("idx_boarding_roll_call_tenant_id", "boarding_roll_call", ["tenant_id"])
    op.create_index("idx_boarding_roll_call_tenant_house_date", "boarding_roll_call", ["tenant_id", "house_id", "date"])

    op.create_index("idx_boarding_roll_call_entries_tenant_id", "boarding_roll_call_entries", ["tenant_id"])
    op.create_index("idx_boarding_roll_call_entries_tenant_roll_call", "boarding_roll_call_entries", ["tenant_id", "roll_call_id"])

    op.create_index("idx_exeats_tenant_id", "exeats", ["tenant_id"])
    op.create_index("idx_exeats_tenant_student", "exeats", ["tenant_id", "student_id"])
    op.create_index("idx_exeats_tenant_status", "exeats", ["tenant_id", "status"])
    op.create_index("idx_exeats_tenant_dates", "exeats", ["tenant_id", "start_date", "end_date"])

    op.create_index("idx_boarding_incidents_tenant_id", "boarding_incidents", ["tenant_id"])
    op.create_index("idx_boarding_incidents_tenant_student", "boarding_incidents", ["tenant_id", "student_id"])
    op.create_index("idx_boarding_incidents_tenant_resolved", "boarding_incidents", ["tenant_id", "resolved"])
    op.create_index("idx_boarding_incidents_tenant_severity", "boarding_incidents", ["tenant_id", "severity"])

    op.create_index("idx_dining_meals_tenant_id", "dining_meals", ["tenant_id"])
    op.create_index("idx_dining_meals_tenant_school_date", "dining_meals", ["tenant_id", "school_id", "date"])

    # Transport indexes
    op.create_index("idx_vehicles_tenant_id", "vehicles", ["tenant_id"])
    op.create_index("idx_vehicles_tenant_school", "vehicles", ["tenant_id", "school_id"])
    op.create_index("idx_vehicles_tenant_status", "vehicles", ["tenant_id", "status"])

    op.create_index("idx_drivers_tenant_id", "drivers", ["tenant_id"])
    op.create_index("idx_drivers_tenant_school", "drivers", ["tenant_id", "school_id"])
    op.create_index("idx_drivers_tenant_status", "drivers", ["tenant_id", "status"])

    op.create_index("idx_routes_tenant_id", "routes", ["tenant_id"])
    op.create_index("idx_routes_tenant_school", "routes", ["tenant_id", "school_id"])
    op.create_index("idx_routes_tenant_active", "routes", ["tenant_id", "is_active"])

    op.create_index("idx_route_stops_tenant_id", "route_stops", ["tenant_id"])
    op.create_index("idx_route_stops_tenant_route", "route_stops", ["tenant_id", "route_id"])

    op.create_index("idx_student_transport_tenant_id", "student_transport", ["tenant_id"])
    op.create_index("idx_student_transport_tenant_student", "student_transport", ["tenant_id", "student_id"])
    op.create_index("idx_student_transport_tenant_route", "student_transport", ["tenant_id", "route_id"])
    op.create_index("idx_student_transport_tenant_status", "student_transport", ["tenant_id", "status"])

    op.create_index("idx_trip_logs_tenant_id", "trip_logs", ["tenant_id"])
    op.create_index("idx_trip_logs_tenant_route_date", "trip_logs", ["tenant_id", "route_id", "trip_date"])
    op.create_index("idx_trip_logs_tenant_date", "trip_logs", ["tenant_id", "trip_date"])

    op.create_index("idx_vehicle_maintenance_tenant_id", "vehicle_maintenance", ["tenant_id"])
    op.create_index("idx_vehicle_maintenance_tenant_vehicle", "vehicle_maintenance", ["tenant_id", "vehicle_id"])
    op.create_index("idx_vehicle_maintenance_tenant_date", "vehicle_maintenance", ["tenant_id", "service_date"])

    # ------------------------------------------------------------------
    # Phase 5: Enable RLS on all 16 tables
    # ------------------------------------------------------------------
    for table in NEW_TENANT_SCOPED_TABLES:
        _enable_rls(table)

    # Grant sequence usage for new tables
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user")


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 1: Disable RLS on all 16 tables (reverse order)
    # ------------------------------------------------------------------
    for table in reversed(NEW_TENANT_SCOPED_TABLES):
        _disable_rls(table)

    # ------------------------------------------------------------------
    # Phase 2: Drop tables in reverse dependency order
    # ------------------------------------------------------------------

    # Transport tables (reverse order)
    op.drop_table("vehicle_maintenance")
    op.drop_table("trip_logs")
    op.drop_table("student_transport")
    op.drop_table("route_stops")
    op.drop_table("routes")
    op.drop_table("drivers")
    op.drop_table("vehicles")

    # Boarding tables (reverse order)
    op.drop_table("dining_meals")
    op.drop_table("boarding_incidents")
    op.drop_table("exeats")
    op.drop_table("boarding_roll_call_entries")
    op.drop_table("boarding_roll_call")
    op.drop_table("student_boarding")
    op.drop_table("beds")
    op.drop_table("dormitories")
    op.drop_table("houses")

    # ------------------------------------------------------------------
    # Phase 3: Drop enum types
    # ------------------------------------------------------------------
    for enum_name in reversed(list(ENUM_DEFINITIONS.keys())):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
