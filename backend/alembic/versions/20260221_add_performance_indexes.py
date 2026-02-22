"""Add performance indexes for common query patterns

Revision ID: 20260221_0100
Revises: 20260220_0100
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260221_0100"
down_revision: Union[str, None] = "20260220_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Students: list queries filter by tenant + active + sort by last_name
    op.create_index(
        "idx_students_tenant_active",
        "students",
        ["tenant_id", "deleted_at", "last_name"],
    )

    # Invoices: student invoice lookup with status filter
    op.create_index(
        "idx_invoices_tenant_student_status",
        "invoices",
        ["tenant_id", "student_id", "status"],
    )

    # Attendance: section attendance for a given date
    op.create_index(
        "idx_attendance_tenant_section_date",
        "student_attendance",
        ["tenant_id", "section_id", "date"],
    )

    # Payments: tenant payment listing sorted by date
    op.create_index(
        "idx_payments_tenant_date",
        "payments",
        ["tenant_id", "payment_date"],
    )

    # Exam scores: lookup by exam_subject + student
    op.create_index(
        "idx_exam_scores_subject_student",
        "exam_scores",
        ["exam_subject_id", "student_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_exam_scores_subject_student", table_name="exam_scores")
    op.drop_index("idx_payments_tenant_date", table_name="payments")
    op.drop_index("idx_attendance_tenant_section_date", table_name="student_attendance")
    op.drop_index("idx_invoices_tenant_student_status", table_name="invoices")
    op.drop_index("idx_students_tenant_active", table_name="students")
