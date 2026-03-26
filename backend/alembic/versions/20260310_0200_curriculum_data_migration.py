"""Create GES Default curriculum profiles for existing tenants

Data migration for Multi-Curriculum Phase 1:

1. For each tenant: create a "GES Default" CurriculumProfile
2. Link it to the tenant's default grading scale (if any)
3. Convert existing assessment_weights rows into assessment_structures + assessment_components
4. Normalize component weights using ca_total_weight/exam_total_weight
5. Create a ReportCardConfig with GES defaults for each profile
6. If tenant has no assessment_weights, create default structure (20/10/20/50)

IMPORTANT:
- This migration does NOT modify the assessment_weights table
- It is idempotent: checks for existing "GES Default" profiles before creating
- Runs as superuser (not sims_app_user) so RLS does not apply

Revision ID: 20260310_0200
Revises: 20260310_0100
Create Date: 2026-03-10

"""

import uuid
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "20260310_0200"
down_revision: Union[str, None] = "20260310_0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Verify running as superuser (not sims_app_user which would be blocked by FORCE RLS)
    current_user = conn.execute(text("SELECT current_user")).scalar()
    assert current_user in ("postgres", "sims_admin"), (
        f"Data migration must run as superuser, not {current_user}"
    )

    # Get all tenants (tenants table has no RLS)
    tenants = conn.execute(text("SELECT id FROM tenants")).fetchall()

    for (tenant_id,) in tenants:
        tenant_id_str = str(tenant_id)

        # Check if a GES Default profile already exists (idempotent)
        existing = conn.execute(
            text("""
                SELECT id FROM curriculum_profiles
                WHERE tenant_id = CAST(:tid AS uuid)
                AND name = 'GES Default'
                AND deleted_at IS NULL
            """),
            {"tid": tenant_id_str},
        ).fetchone()

        if existing:
            continue

        # Look up a fallback school_id for this tenant
        fallback_school = conn.execute(
            text("""
                SELECT id FROM schools
                WHERE tenant_id = CAST(:tid AS uuid)
                AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT 1
            """),
            {"tid": tenant_id_str},
        ).fetchone()
        fallback_school_id = fallback_school[0] if fallback_school else None
        fallback_school_str = str(fallback_school_id) if fallback_school_id else None

        # Create GES Default curriculum profile
        profile_id = uuid.uuid4()
        profile_id_str = str(profile_id)

        conn.execute(
            text("""
                INSERT INTO curriculum_profiles
                (id, tenant_id, school_id, name, curriculum_type,
                 academic_calendar_type, periods_per_year, score_display_mode,
                 show_position, show_class_average,
                 use_gpa, use_credits, use_criterion_grading,
                 is_default, is_active, created_at, updated_at)
                VALUES
                (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                 'GES Default', 'ges',
                 'terms', 3, 'grade_and_score',
                 true, true,
                 false, false, false,
                 true, true, NOW(), NOW())
            """),
            {
                "id": profile_id_str,
                "tid": tenant_id_str,
                "sid": fallback_school_str,
            },
        )

        # Link to the tenant's default grading scale (if any)
        default_scale = conn.execute(
            text("""
                SELECT id FROM grading_scales
                WHERE tenant_id = CAST(:tid AS uuid)
                AND is_default = true AND deleted_at IS NULL
                LIMIT 1
            """),
            {"tid": tenant_id_str},
        ).fetchone()

        if default_scale:
            conn.execute(
                text("""
                    UPDATE curriculum_profiles
                    SET grading_scale_id = CAST(:sid AS uuid)
                    WHERE id = CAST(:pid AS uuid)
                """),
                {"sid": str(default_scale[0]), "pid": profile_id_str},
            )

        # Get existing assessment weights (include school_id for new tables)
        weights = conn.execute(
            text("""
                SELECT id, academic_year_id, class_work_weight, homework_weight,
                       midterm_weight, end_term_weight, school_id,
                       ca_total_weight, exam_total_weight
                FROM assessment_weights
                WHERE tenant_id = CAST(:tid AS uuid)
            """),
            {"tid": tenant_id_str},
        ).fetchall()

        # For each weight config, create assessment structure + components
        for weight_row in weights:
            (w_id, year_id, cw_w, hw_w, mid_w, end_w,
             w_school_id, ca_total, exam_total) = weight_row

            # Use school_id from assessment_weights if available, else fallback
            row_school_id = w_school_id or fallback_school_id
            row_school_str = str(row_school_id) if row_school_id else None

            ca_total_f = float(ca_total) if ca_total else 50.0
            exam_total_f = float(exam_total) if exam_total else 50.0

            # Normalize CA sub-weights: (sub_weight / ca_raw_sum) * ca_total_weight
            ca_raw = float(cw_w or 0) + float(hw_w or 0) + float(mid_w or 0)
            if ca_raw > 0:
                norm_cw = round((float(cw_w or 0) / ca_raw) * ca_total_f, 2)
                norm_hw = round((float(hw_w or 0) / ca_raw) * ca_total_f, 2)
                norm_mid = round((float(mid_w or 0) / ca_raw) * ca_total_f, 2)
            else:
                # Fallback to raw values if all CA weights are zero
                norm_cw = float(cw_w or 20)
                norm_hw = float(hw_w or 10)
                norm_mid = float(mid_w or 20)

            # Force sum to exactly 100 by absorbing rounding error into end_term
            norm_end = round(100.0 - norm_cw - norm_hw - norm_mid, 2)

            structure_id = uuid.uuid4()
            structure_id_str = str(structure_id)

            conn.execute(
                text("""
                    INSERT INTO assessment_structures
                    (id, tenant_id, school_id, curriculum_profile_id,
                     academic_year_id, name, is_active, created_at, updated_at)
                    VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                     CAST(:pid AS uuid), CAST(:yid AS uuid),
                     'GES Assessment Structure', true, NOW(), NOW())
                """),
                {
                    "id": structure_id_str,
                    "tid": tenant_id_str,
                    "sid": row_school_str,
                    "pid": profile_id_str,
                    "yid": str(year_id) if year_id else None,
                },
            )

            # Create 4 components with normalized weights
            components = [
                ("class_work", "Class Work", norm_cw, 1, True, False),
                ("homework", "Homework", norm_hw, 2, True, False),
                ("midterm", "Midterm", norm_mid, 3, True, False),
                ("end_term", "End of Term", norm_end, 4, False, True),
            ]

            for (ctype, cname, cweight, seq, to_ca, to_exam) in components:
                comp_id = uuid.uuid4()
                conn.execute(
                    text("""
                        INSERT INTO assessment_components
                        (id, tenant_id, school_id, assessment_structure_id,
                         component_type, name, weight, is_external, sequence,
                         maps_to_ca, maps_to_exam, created_at, updated_at)
                        VALUES
                        (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid2 AS uuid),
                         CAST(:sid AS uuid),
                         :ctype, :cname, :cweight, false, :seq,
                         :to_ca, :to_exam, NOW(), NOW())
                    """),
                    {
                        "id": str(comp_id),
                        "tid": tenant_id_str,
                        "sid2": row_school_str,
                        "sid": structure_id_str,
                        "ctype": ctype,
                        "cname": cname,
                        "cweight": cweight,
                        "seq": seq,
                        "to_ca": to_ca,
                        "to_exam": to_exam,
                    },
                )

        # If tenant has no assessment_weights, create default structure
        if not weights:
            structure_id = uuid.uuid4()
            structure_id_str = str(structure_id)

            conn.execute(
                text("""
                    INSERT INTO assessment_structures
                    (id, tenant_id, school_id, curriculum_profile_id,
                     name, is_active, created_at, updated_at)
                    VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                     CAST(:pid AS uuid),
                     'GES Assessment Structure', true, NOW(), NOW())
                """),
                {
                    "id": structure_id_str,
                    "tid": tenant_id_str,
                    "sid": fallback_school_str,
                    "pid": profile_id_str,
                },
            )

            defaults = [
                ("class_work", "Class Work", 20, 1, True, False),
                ("homework", "Homework", 10, 2, True, False),
                ("midterm", "Midterm", 20, 3, True, False),
                ("end_term", "End of Term", 50, 4, False, True),
            ]
            for (ctype, cname, cweight, seq, to_ca, to_exam) in defaults:
                conn.execute(
                    text("""
                        INSERT INTO assessment_components
                        (id, tenant_id, school_id, assessment_structure_id,
                         component_type, name, weight, is_external, sequence,
                         maps_to_ca, maps_to_exam, created_at, updated_at)
                        VALUES
                        (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid2 AS uuid),
                         CAST(:sid AS uuid),
                         :ct, :cn, :cw, false, :seq, :tca, :tex, NOW(), NOW())
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "tid": tenant_id_str,
                        "sid2": fallback_school_str,
                        "sid": structure_id_str,
                        "ct": ctype,
                        "cn": cname,
                        "cw": cweight,
                        "seq": seq,
                        "tca": to_ca,
                        "tex": to_exam,
                    },
                )

        # Create ReportCardConfig with GES defaults
        conn.execute(
            text("""
                INSERT INTO report_card_configs
                (id, tenant_id, school_id, curriculum_profile_id, template_key,
                 show_position, show_class_average, show_subject_position,
                 show_effort_grade, show_predicted_grades, show_gpa,
                 show_credits, show_honor_roll, show_learner_profile,
                 show_atl_skills, created_at, updated_at)
                VALUES
                (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                 CAST(:pid AS uuid), 'ges',
                 true, true, true,
                 false, false, false,
                 false, false, false,
                 false, NOW(), NOW())
            """),
            {
                "id": str(uuid.uuid4()),
                "tid": tenant_id_str,
                "sid": fallback_school_str,
                "pid": profile_id_str,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Delete all auto-created GES Default profiles and cascaded children.
    # assessment_structures, assessment_components, and report_card_configs
    # will be cascade-deleted via FK ON DELETE CASCADE.
    conn.execute(text("""
        DELETE FROM curriculum_profiles
        WHERE curriculum_type = 'ges' AND is_default = true
    """))
