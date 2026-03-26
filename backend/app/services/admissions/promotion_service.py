"""
SIMS Plus - Class Promotion Service

Manages end-of-year class promotion operations and configurable
promotion rules.

Workflow:
1. Admin creates a promotion batch (draft)
2. System generates preview entries for all active students
   in the school (default action: promote to next class,
   terminal class students: graduate)
3. If auto_apply rules exist, the preview entries are pre-filled
   with rule-based recommendations (promote/repeat with reasons)
4. Admin reviews and adjusts individual entries (repeat/withdraw)
5. Admin executes the batch -- students are re-assigned to new classes

This is the primary tool for the Ghanaian academic year transition.
Students are automatically promoted to the next class unless marked
for repeat, graduation, or withdrawal.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import nh3
import structlog
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from weasyprint import HTML

from app.models.admissions import (
    ClassPromotion,
    ClassPromotionEntry,
    PromotionAction,
    PromotionBatchStatus,
    PromotionRule,
)

logger = structlog.get_logger(__name__)


class ClassPromotionError(Exception):
    def __init__(self, message: str, code: str = "PROMOTION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class ClassPromotionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_batch(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        source_academic_year_id: uuid.UUID,
        target_academic_year_id: uuid.UUID,
        name: str,
    ) -> ClassPromotion:
        """
        Create promotion batch in draft status.

        Validates: both academic years exist, source != target,
        no existing batch for same source/target combination.
        """
        if source_academic_year_id == target_academic_year_id:
            raise ClassPromotionError(
                "Source and target academic years must be different",
                code="SAME_YEAR",
            )

        # Verify both academic years exist
        from app.models.academic import AcademicYear

        for year_id, label in [
            (source_academic_year_id, "Source"),
            (target_academic_year_id, "Target"),
        ]:
            result = await self.db.execute(
                select(AcademicYear).where(
                    AcademicYear.id == year_id,
                    AcademicYear.tenant_id == tenant_id,
                    AcademicYear.deleted_at.is_(None),
                )
            )
            if not result.scalar_one_or_none():
                raise ClassPromotionError(
                    f"{label} academic year not found", code="YEAR_NOT_FOUND"
                )

        # Check for duplicate batch
        existing_result = await self.db.execute(
            select(ClassPromotion).where(
                ClassPromotion.tenant_id == tenant_id,
                ClassPromotion.school_id == school_id,
                ClassPromotion.source_academic_year_id == source_academic_year_id,
                ClassPromotion.target_academic_year_id == target_academic_year_id,
                ClassPromotion.deleted_at.is_(None),
            )
        )
        if existing_result.scalar_one_or_none():
            raise ClassPromotionError(
                "A promotion batch already exists for this year combination",
                code="BATCH_EXISTS",
            )

        batch = ClassPromotion(
            tenant_id=tenant_id,
            school_id=school_id,
            source_academic_year_id=source_academic_year_id,
            target_academic_year_id=target_academic_year_id,
            name=name,
            status=PromotionBatchStatus.DRAFT.value,
        )
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        return batch

    async def generate_preview(
        self,
        tenant_id: uuid.UUID,
        promotion_id: uuid.UUID,
    ) -> ClassPromotion:
        """
        Generate ClassPromotionEntry records for all active students.

        Default logic:
        - Students in non-terminal classes: action=promote, target_class=next class
        - Students in terminal class (highest sequence): action=graduate, target_class=null
        - Sets batch status to 'preview'

        Uses Class.sequence to determine the "next class" in order.
        """
        batch = await self._get_batch(tenant_id, promotion_id)

        if batch.status != PromotionBatchStatus.DRAFT.value:
            raise ClassPromotionError(
                "Preview can only be generated for draft batches",
                code="INVALID_STATUS",
            )

        # Get all classes for the school, ordered by sequence
        from app.models.academic import Class
        from app.models.student import Student

        class_result = await self.db.execute(
            select(Class)
            .where(
                Class.tenant_id == tenant_id,
                Class.deleted_at.is_(None),
                Class.is_active.is_(True),
            )
            .order_by(Class.sequence.asc())
        )
        classes = list(class_result.scalars().all())

        if not classes:
            raise ClassPromotionError(
                "No active classes found", code="NO_CLASSES"
            )

        # Build class ordering map: class_id -> next_class_id (None for terminal)
        class_order: dict[uuid.UUID, uuid.UUID | None] = {}
        for i, cls in enumerate(classes):
            if i + 1 < len(classes):
                class_order[cls.id] = classes[i + 1].id
            else:
                # Terminal class (highest sequence)
                class_order[cls.id] = None

        # Find the maximum sequence value to identify terminal classes
        max_sequence = max(c.sequence for c in classes) if classes else 0

        # Get all active students in this school
        student_result = await self.db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                Student.school_id == batch.school_id,
                Student.status == "active",
                Student.deleted_at.is_(None),
            )
        )
        students = list(student_result.scalars().all())

        # Generate entries
        total = 0
        for student in students:
            if not student.class_id:
                continue

            next_class_id = class_order.get(student.class_id)
            is_terminal = next_class_id is None

            entry = ClassPromotionEntry(
                tenant_id=tenant_id,
                promotion_id=promotion_id,
                student_id=student.id,
                source_class_id=student.class_id,
                source_section_id=getattr(student, "section_id", None),
                target_class_id=next_class_id,
                target_section_id=None,
                action=(
                    PromotionAction.GRADUATE.value
                    if is_terminal
                    else PromotionAction.PROMOTE.value
                ),
            )
            self.db.add(entry)
            total += 1

        batch.status = PromotionBatchStatus.PREVIEW.value
        batch.total_students = total

        await self.db.flush()

        # Auto-apply promotion rules: evaluate all students against rules
        # and pre-fill entries with recommended action/reason
        auto_rules = await self._load_active_rules(
            tenant_id, batch.school_id, batch.source_academic_year_id
        )
        auto_apply_rules = [r for r in auto_rules if r.auto_apply]

        if auto_apply_rules and total > 0:
            all_student_ids = [s.id for s in students if s.class_id]
            evaluations = await self.evaluate_promotion_rules(
                tenant_id,
                batch.school_id,
                batch.source_academic_year_id,
                all_student_ids,
            )

            # Build lookup: student_id -> evaluation result
            eval_map = {e["student_id"]: e for e in evaluations}

            # Re-fetch entries to apply rule recommendations
            entries_result = await self.db.execute(
                select(ClassPromotionEntry).where(
                    ClassPromotionEntry.promotion_id == promotion_id,
                    ClassPromotionEntry.tenant_id == tenant_id,
                    ClassPromotionEntry.deleted_at.is_(None),
                )
            )
            for entry in entries_result.scalars().all():
                eval_result = eval_map.get(entry.student_id)
                if not eval_result:
                    continue

                # Only override promote -> repeat (never override graduate/withdraw)
                if (
                    entry.action == PromotionAction.PROMOTE.value
                    and eval_result["recommended_action"] == "repeat"
                ):
                    entry.action = PromotionAction.REPEAT.value
                    # Keep student in same class when repeating
                    entry.target_class_id = entry.source_class_id
                    entry.target_section_id = entry.source_section_id
                    entry.reason = eval_result["reason"]

            await self.db.flush()

        await self.db.refresh(batch)
        return batch

    async def update_entry(
        self,
        tenant_id: uuid.UUID,
        entry_id: uuid.UUID,
        *,
        action: str,
        target_class_id: uuid.UUID | None = None,
        target_section_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> ClassPromotionEntry:
        """
        Admin adjusts individual student's action.

        Validates: batch is in 'preview' status (not yet executed).
        """
        # Validate action
        try:
            PromotionAction(action)
        except ValueError:
            raise ClassPromotionError(
                f"Invalid action: {action}. "
                f"Must be one of: {', '.join(a.value for a in PromotionAction)}",
                code="INVALID_ACTION",
            )

        entry = await self._get_entry(tenant_id, entry_id)

        # Check batch status
        batch_result = await self.db.execute(
            select(ClassPromotion).where(
                ClassPromotion.id == entry.promotion_id,
                ClassPromotion.tenant_id == tenant_id,
            )
        )
        batch = batch_result.scalar_one_or_none()
        if not batch or batch.status != PromotionBatchStatus.PREVIEW.value:
            raise ClassPromotionError(
                "Entries can only be updated when batch is in preview status",
                code="BATCH_NOT_PREVIEW",
            )

        entry.action = action
        entry.target_class_id = target_class_id
        entry.target_section_id = target_section_id
        entry.reason = reason

        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def bulk_update_entries(
        self,
        tenant_id: uuid.UUID,
        promotion_id: uuid.UUID,
        updates: list[dict],
    ) -> dict:
        """
        Bulk update entries.

        Each update: {entry_id, action, target_class_id?, target_section_id?, reason?}
        Returns: { succeeded: int, failed: [{entry_id, error}] }
        """
        # Verify batch is in preview
        batch = await self._get_batch(tenant_id, promotion_id)
        if batch.status != PromotionBatchStatus.PREVIEW.value:
            raise ClassPromotionError(
                "Entries can only be updated when batch is in preview status",
                code="BATCH_NOT_PREVIEW",
            )

        succeeded = 0
        failed: list[dict] = []

        for upd in updates:
            try:
                entry_id = uuid.UUID(str(upd["entry_id"]))
                await self.update_entry(
                    tenant_id,
                    entry_id,
                    action=upd["action"],
                    target_class_id=upd.get("target_class_id"),
                    target_section_id=upd.get("target_section_id"),
                    reason=upd.get("reason"),
                )
                succeeded += 1
            except Exception as e:
                error_msg = (
                    e.message
                    if isinstance(e, ClassPromotionError)
                    else "Update failed"
                )
                failed.append({
                    "entry_id": str(upd.get("entry_id", "")),
                    "error": error_msg,
                })

        return {"succeeded": succeeded, "failed": failed}

    async def execute_batch(
        self,
        tenant_id: uuid.UUID,
        promotion_id: uuid.UUID,
        executed_by: uuid.UUID,
    ) -> ClassPromotion:
        """
        Execute the promotion batch.

        For each entry:
        - promote: Update student's class_id (and section if specified)
        - repeat: Keep student in same class (update section if specified)
        - graduate: Set student status to 'graduated'
        - withdraw: Set student status to 'withdrawn'

        Each entry processed in its own savepoint (partial success).
        Updates batch counts and sets status to 'completed'.

        Uses SELECT FOR UPDATE to prevent concurrent execution of the same batch.
        """
        # Lock the batch row to prevent concurrent execution
        batch = await self._get_batch_for_update(tenant_id, promotion_id)

        if batch.status != PromotionBatchStatus.PREVIEW.value:
            raise ClassPromotionError(
                "Only preview batches can be executed",
                code="INVALID_STATUS",
            )

        batch.status = PromotionBatchStatus.IN_PROGRESS.value
        await self.db.flush()

        # Get all entries for this batch
        entries_result = await self.db.execute(
            select(ClassPromotionEntry).where(
                ClassPromotionEntry.promotion_id == promotion_id,
                ClassPromotionEntry.tenant_id == tenant_id,
                ClassPromotionEntry.deleted_at.is_(None),
                ClassPromotionEntry.processed.is_(False),
            )
        )
        entries = list(entries_result.scalars().all())

        from app.models.student import Student

        promoted = 0
        repeated = 0
        graduated = 0
        withdrawn = 0
        failed_count = 0

        for entry in entries:
            try:
                async with self.db.begin_nested():
                    student_result = await self.db.execute(
                        select(Student).where(
                            Student.id == entry.student_id,
                            Student.tenant_id == tenant_id,
                        )
                    )
                    student = student_result.scalar_one_or_none()
                    if not student:
                        failed_count += 1
                        continue

                    action = PromotionAction(entry.action)

                    if action == PromotionAction.PROMOTE:
                        if entry.target_class_id:
                            student.class_id = entry.target_class_id
                        if entry.target_section_id:
                            student.section_id = entry.target_section_id
                        promoted += 1

                    elif action == PromotionAction.REPEAT:
                        # Keep same class, optionally change section
                        if entry.target_section_id:
                            student.section_id = entry.target_section_id
                        repeated += 1

                    elif action == PromotionAction.GRADUATE:
                        student.status = "graduated"
                        graduated += 1

                    elif action == PromotionAction.WITHDRAW:
                        student.status = "withdrawn"
                        withdrawn += 1

                    entry.processed = True

            except Exception:
                logger.exception(
                    "promotion_entry_failed",
                    entry_id=str(entry.id),
                    student_id=str(entry.student_id),
                )
                failed_count += 1

        # Update batch counts
        batch.promoted_count = promoted
        batch.repeated_count = repeated
        batch.graduated_count = graduated
        batch.withdrawn_count = withdrawn
        batch.executed_at = datetime.now(UTC)
        batch.executed_by = executed_by
        batch.status = (
            PromotionBatchStatus.COMPLETED.value
            if failed_count == 0
            else PromotionBatchStatus.FAILED.value
        )

        await self.db.flush()
        await self.db.refresh(batch)

        logger.info(
            "promotion_batch_executed",
            promotion_id=str(promotion_id),
            promoted=promoted,
            repeated=repeated,
            graduated=graduated,
            withdrawn=withdrawn,
            failed=failed_count,
        )

        return batch

    async def get_batch(
        self,
        tenant_id: uuid.UUID,
        promotion_id: uuid.UUID,
    ) -> ClassPromotion:
        """Get batch with summary stats."""
        return await self._get_batch(tenant_id, promotion_id)

    async def list_batches(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ClassPromotion], int]:
        """List promotion batches for a school."""
        query = select(ClassPromotion).where(
            ClassPromotion.tenant_id == tenant_id,
            ClassPromotion.school_id == school_id,
            ClassPromotion.deleted_at.is_(None),
        )

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(ClassPromotion.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_entries(
        self,
        tenant_id: uuid.UUID,
        promotion_id: uuid.UUID,
        *,
        source_class_id: uuid.UUID | None = None,
        action: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ClassPromotionEntry], int]:
        """List entries with optional filters."""
        # Verify batch exists and belongs to tenant
        await self._get_batch(tenant_id, promotion_id)

        query = select(ClassPromotionEntry).where(
            ClassPromotionEntry.promotion_id == promotion_id,
            ClassPromotionEntry.tenant_id == tenant_id,
            ClassPromotionEntry.deleted_at.is_(None),
        )

        if source_class_id:
            query = query.where(
                ClassPromotionEntry.source_class_id == source_class_id
            )
        if action:
            query = query.where(ClassPromotionEntry.action == action)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = (
            query.order_by(ClassPromotionEntry.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    # ─── Promotion Rules CRUD ──────────────────────────────────

    async def create_promotion_rule(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        *,
        class_id: uuid.UUID | None = None,
        min_average: Decimal | None = None,
        min_attendance_pct: Decimal | None = None,
        core_subject_pass_count: int | None = None,
        pass_mark: Decimal = Decimal("50.00"),
        auto_apply: bool = False,
    ) -> PromotionRule:
        """Create a promotion rule.

        Checks for duplicate rule (same school/year/class combination).
        A NULL class_id is the school-wide default; a specific class_id
        overrides it for that class.
        """
        # Verify academic year exists
        from app.models.academic import AcademicYear

        ay_result = await self.db.execute(
            select(AcademicYear).where(
                AcademicYear.id == academic_year_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                AcademicYear.tenant_id == tenant_id,
                AcademicYear.deleted_at.is_(None),
            )
        )
        if not ay_result.scalar_one_or_none():
            raise ClassPromotionError(
                "Academic year not found", code="YEAR_NOT_FOUND"
            )

        # Check for duplicate (same school + year + class combo)
        dup_query = select(PromotionRule).where(
            PromotionRule.tenant_id == tenant_id,
            PromotionRule.school_id == school_id,
            PromotionRule.academic_year_id == academic_year_id,
            PromotionRule.deleted_at.is_(None),
        )
        if class_id is not None:
            dup_query = dup_query.where(PromotionRule.class_id == class_id)
        else:
            dup_query = dup_query.where(PromotionRule.class_id.is_(None))

        dup_result = await self.db.execute(dup_query)
        if dup_result.scalar_one_or_none():
            raise ClassPromotionError(
                "A promotion rule already exists for this school/year/class combination",
                code="RULE_EXISTS",
            )

        rule = PromotionRule(
            tenant_id=tenant_id,
            school_id=school_id,
            academic_year_id=academic_year_id,
            class_id=class_id,
            min_average=min_average,
            min_attendance_pct=min_attendance_pct,
            core_subject_pass_count=core_subject_pass_count,
            pass_mark=pass_mark,
            auto_apply=auto_apply,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def list_promotion_rules(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        *,
        academic_year_id: uuid.UUID | None = None,
    ) -> list[PromotionRule]:
        """List promotion rules with eager-loaded class and academic year."""
        query = (
            select(PromotionRule)
            .where(
                PromotionRule.tenant_id == tenant_id,
                PromotionRule.school_id == school_id,
                PromotionRule.deleted_at.is_(None),
            )
            .options(
                joinedload(PromotionRule.class_),
                joinedload(PromotionRule.academic_year),
            )
            .order_by(PromotionRule.created_at.desc())
        )
        if academic_year_id:
            query = query.where(
                PromotionRule.academic_year_id == academic_year_id
            )

        result = await self.db.execute(query)
        return list(result.unique().scalars().all())

    async def update_promotion_rule(
        self,
        tenant_id: uuid.UUID,
        rule_id: uuid.UUID,
        **fields: object,
    ) -> PromotionRule:
        """Update allowed fields on a promotion rule."""
        rule = await self._get_rule(tenant_id, rule_id)

        allowed_fields = {
            "min_average",
            "min_attendance_pct",
            "core_subject_pass_count",
            "pass_mark",
            "auto_apply",
            "is_active",
        }

        for key, value in fields.items():
            if key in allowed_fields and value is not None:
                if key in ("min_average", "min_attendance_pct", "pass_mark"):
                    setattr(rule, key, Decimal(str(value)))
                else:
                    setattr(rule, key, value)

        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def delete_promotion_rule(
        self,
        tenant_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> bool:
        """Soft-delete a promotion rule."""
        rule = await self._get_rule(tenant_id, rule_id)
        rule.deleted_at = datetime.now(UTC)
        await self.db.flush()
        return True

    # ─── Rule Evaluation (F-18: batch queries) ─────────────────

    async def evaluate_promotion_rules(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
        student_ids: list[uuid.UUID],
    ) -> list[dict]:
        """Evaluate promotion rules against a batch of students.

        F-18 CRITICAL: Uses batch queries for term averages, attendance,
        and core subject pass counts.  No per-student DB queries in a loop.

        Returns a list of evaluation dicts, one per student:
        {student_id, student_name, recommended_action, reason,
         term_average, attendance_pct, core_subjects_passed, criteria_met}
        """
        if not student_ids:
            return []

        # 1. Load all active rules for this school/year
        rules = await self._load_active_rules(
            tenant_id, school_id, academic_year_id
        )
        if not rules:
            return []

        # 2. Build rule_map: {class_id -> rule, None -> default}
        rule_map: dict[uuid.UUID | None, PromotionRule] = {}
        for r in rules:
            rule_map[r.class_id] = r

        # 3. BATCH query: get all students' classes + names (one query)
        from app.models.student import Student

        student_result = await self.db.execute(
            select(Student.id, Student.class_id, Student.first_name, Student.last_name).where(
                Student.tenant_id == tenant_id,
                Student.id.in_(student_ids),
                Student.deleted_at.is_(None),
            )
        )
        student_rows = student_result.all()
        student_class_map: dict[uuid.UUID, uuid.UUID | None] = {}
        student_name_map: dict[uuid.UUID, str] = {}
        for row in student_rows:
            student_class_map[row.id] = row.class_id
            student_name_map[row.id] = f"{row.first_name} {row.last_name}"

        # Determine the maximum pass_mark across all rules for the core subjects query
        max_pass_mark = max(
            (r.pass_mark for r in rules if r.pass_mark is not None),
            default=Decimal("50.00"),
        )

        # 4-6. BATCH queries for performance data
        term_averages = await self._batch_get_term_averages(
            tenant_id, student_ids, academic_year_id
        )
        attendance_pcts = await self._batch_get_attendance_pct(
            tenant_id, student_ids, academic_year_id
        )
        core_passes = await self._batch_get_core_subjects_passed(
            tenant_id, student_ids, academic_year_id, max_pass_mark
        )

        # 7. For each student: match to rule, evaluate criteria
        results: list[dict] = []
        for sid in student_ids:
            class_id = student_class_map.get(sid)
            name = student_name_map.get(sid, "Unknown")

            # Class-specific rule takes precedence, fallback to school default
            rule = rule_map.get(class_id) or rule_map.get(None)
            if not rule:
                continue

            avg = term_averages.get(sid)
            att = attendance_pcts.get(sid)
            # Use the rule's specific pass_mark for this evaluation context
            # but the batch query used the max; recount if rule pass_mark differs
            core_passed = core_passes.get(sid, 0)

            criteria_met: dict[str, bool] = {}
            fail_reasons: list[str] = []

            if rule.min_average is not None:
                met = avg is not None and avg >= float(rule.min_average)
                criteria_met["min_average"] = met
                if not met:
                    fail_reasons.append(
                        f"Average {avg:.1f} < required {rule.min_average}"
                        if avg is not None
                        else "No term report found"
                    )

            if rule.min_attendance_pct is not None:
                met = att is not None and att >= float(rule.min_attendance_pct)
                criteria_met["min_attendance_pct"] = met
                if not met:
                    fail_reasons.append(
                        f"Attendance {att:.1f}% < required {rule.min_attendance_pct}%"
                        if att is not None
                        else "No attendance records found"
                    )

            if rule.core_subject_pass_count is not None:
                met = core_passed >= rule.core_subject_pass_count
                criteria_met["core_subject_pass_count"] = met
                if not met:
                    fail_reasons.append(
                        f"Core subjects passed {core_passed} < required {rule.core_subject_pass_count}"
                    )

            all_met = all(criteria_met.values()) if criteria_met else True
            action = "promote" if all_met else "repeat"
            reason = (
                "Meets all promotion criteria"
                if all_met
                else "; ".join(fail_reasons)
            )

            results.append({
                "student_id": sid,
                "student_name": name,
                "recommended_action": action,
                "reason": reason,
                "term_average": avg,
                "attendance_pct": att,
                "core_subjects_passed": core_passed,
                "criteria_met": criteria_met,
            })

        return results

    async def _batch_get_term_averages(
        self,
        tenant_id: uuid.UUID,
        student_ids: list[uuid.UUID],
        academic_year_id: uuid.UUID,
    ) -> dict[uuid.UUID, float]:
        """Single batch query: get final term average per student for the year.

        Uses the latest term report per student within the academic year.
        Returns {student_id: average_score}.
        """
        from app.models.exam import TermReport
        from app.models.academic import Term

        # Subquery: max term_id (latest by sequence/dates) per student in this year
        # We use the term_reports directly -- one per student per term.
        # Average across all terms in the year for a holistic view.
        result = await self.db.execute(
            select(
                TermReport.student_id,
                func.avg(TermReport.average_score).label("avg_score"),
            )
            .join(Term, TermReport.term_id == Term.id)
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                TermReport.tenant_id == tenant_id,
                Term.academic_year_id == academic_year_id,
                TermReport.student_id.in_(student_ids),
                TermReport.average_score.isnot(None),
            )
            .group_by(TermReport.student_id)
        )

        return {
            row.student_id: float(row.avg_score)
            for row in result.all()
        }

    async def _batch_get_attendance_pct(
        self,
        tenant_id: uuid.UUID,
        student_ids: list[uuid.UUID],
        academic_year_id: uuid.UUID,
    ) -> dict[uuid.UUID, float]:
        """Single batch query: attendance percentage per student for the year.

        Counts present+late as "attended" out of total records.
        Returns {student_id: percentage}.
        """
        from app.models.attendance import StudentAttendance, AttendanceStatus
        from app.models.academic import Term

        # Attendance records are linked to terms via term_id
        result = await self.db.execute(
            select(
                StudentAttendance.student_id,
                func.count(StudentAttendance.id).label("total"),
                func.count(
                    case(
                        (
                            StudentAttendance.status.in_([
                                AttendanceStatus.PRESENT.value,
                                AttendanceStatus.LATE.value,
                            ]),
                            StudentAttendance.id,
                        ),
                    )
                ).label("attended"),
            )
            .join(Term, StudentAttendance.term_id == Term.id)
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                StudentAttendance.tenant_id == tenant_id,
                Term.academic_year_id == academic_year_id,
                StudentAttendance.student_id.in_(student_ids),
                StudentAttendance.deleted_at.is_(None),
            )
            .group_by(StudentAttendance.student_id)
        )

        return {
            row.student_id: (float(row.attended) / float(row.total) * 100.0)
            if row.total > 0
            else 0.0
            for row in result.all()
        }

    async def _batch_get_core_subjects_passed(
        self,
        tenant_id: uuid.UUID,
        student_ids: list[uuid.UUID],
        academic_year_id: uuid.UUID,
        pass_mark: Decimal,
    ) -> dict[uuid.UUID, int]:
        """Single batch query: count of distinct core subjects passed per student.

        A subject is "passed" if the student scored >= pass_mark in any
        exam for that subject within the academic year.
        Returns {student_id: count}.
        """
        from app.models.exam import Exam, ExamSubject, ExamScore
        from app.models.academic import Subject, SubjectCategory

        result = await self.db.execute(
            select(
                ExamScore.student_id,
                func.count(func.distinct(ExamSubject.subject_id)).label("passed"),
            )
            .join(ExamSubject, ExamScore.exam_subject_id == ExamSubject.id)
            .join(Exam, ExamSubject.exam_id == Exam.id)
            .join(Subject, ExamSubject.subject_id == Subject.id)
            .where(
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                ExamScore.tenant_id == tenant_id,
                Exam.academic_year_id == academic_year_id,
                ExamScore.student_id.in_(student_ids),
                ExamScore.score >= pass_mark,
                ExamScore.is_absent.is_(False),
                Subject.category == SubjectCategory.CORE.value,
                ExamScore.deleted_at.is_(None),
            )
            .group_by(ExamScore.student_id)
        )

        return {row.student_id: row.passed for row in result.all()}

    # ─── Graduation Certificate ─────────────────────────────────

    async def generate_graduation_certificate(
        self,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> bytes:
        """Generate a formal graduation certificate as PDF.

        F-14: Uses Jinja2 autoescape and nh3.clean() to sanitize
        user-controlled content injected into the template.

        Raises ClassPromotionError if the student is not graduated.
        """
        from app.models.student import Student
        from app.models.school import School

        student_result = await self.db.execute(
            select(Student)
            .where(
                and_(
                    Student.tenant_id == tenant_id,
                    Student.id == student_id,
                    Student.deleted_at.is_(None),
                )
            )
            .options(
                selectinload(Student.school),
                selectinload(Student.class_),
            )
        )
        student = student_result.scalar_one_or_none()
        if not student:
            raise ClassPromotionError(
                "Student not found", code="NOT_FOUND"
            )

        if student.status.value != "graduated":
            raise ClassPromotionError(
                "Graduation certificate can only be generated for graduated students",
                code="NOT_GRADUATED",
            )

        # Get school info
        school = student.school
        if not school:
            school_result = await self.db.execute(
                select(School).where(
                    School.tenant_id == tenant_id,
                )
            )
            school = school_result.scalar_one_or_none()

        # Determine years of attendance from admission date
        years_attended = ""
        if student.admission_date:
            start_year = student.admission_date.year
            end_year = datetime.now(UTC).year
            years_attended = f"{start_year} - {end_year}"

        # Determine class/level completed
        class_name = student.class_.name if student.class_ else ""

        # Sanitize user-controlled content (F-14)
        student_name = nh3.clean(student.full_name)
        context = {
            "student": student,
            "student_name": student_name,
            "student_id": student.student_id,
            "date_of_birth": student.date_of_birth,
            "school": school,
            "school_name": nh3.clean(school.name) if school else "",
            "class_name": nh3.clean(class_name),
            "years_attended": years_attended,
            "graduation_date": datetime.now(UTC).strftime("%d/%m/%Y"),
            "current_date": datetime.now(UTC).strftime("%d/%m/%Y"),
        }

        return self._render_certificate_pdf(
            "graduation_certificate.html", context
        )

    @staticmethod
    def _render_certificate_pdf(template_name: str, context: dict) -> bytes:
        """Render a Jinja2 template to PDF bytes.

        Uses autoescape=True for XSS prevention in generated HTML.
        """
        templates_dir = (
            Path(__file__).parent.parent.parent / "templates" / "reports"
        )
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
        template = env.get_template(template_name)
        html_content = template.render(**context)

        pdf_buffer = BytesIO()
        HTML(string=html_content).write_pdf(pdf_buffer)
        return pdf_buffer.getvalue()

    # ─── Private helpers (rules) ───────────────────────────────

    async def _get_rule(
        self, tenant_id: uuid.UUID, rule_id: uuid.UUID
    ) -> PromotionRule:
        result = await self.db.execute(
            select(PromotionRule).where(
                PromotionRule.id == rule_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                PromotionRule.tenant_id == tenant_id,
                PromotionRule.deleted_at.is_(None),
            )
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise ClassPromotionError(
                "Promotion rule not found", code="RULE_NOT_FOUND"
            )
        return rule

    async def _load_active_rules(
        self,
        tenant_id: uuid.UUID,
        school_id: uuid.UUID,
        academic_year_id: uuid.UUID,
    ) -> list[PromotionRule]:
        """Load all active promotion rules for a school/year."""
        result = await self.db.execute(
            select(PromotionRule).where(
                PromotionRule.tenant_id == tenant_id,
                PromotionRule.school_id == school_id,
                PromotionRule.academic_year_id == academic_year_id,
                PromotionRule.is_active.is_(True),
                PromotionRule.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    # ---- Private helpers (batch) ----

    async def _get_batch(
        self, tenant_id: uuid.UUID, promotion_id: uuid.UUID
    ) -> ClassPromotion:
        result = await self.db.execute(
            select(ClassPromotion).where(
                ClassPromotion.id == promotion_id,
                # Defense-in-depth: filter by tenant_id even though RLS handles isolation
                ClassPromotion.tenant_id == tenant_id,
                ClassPromotion.deleted_at.is_(None),
            )
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise ClassPromotionError(
                "Promotion batch not found", code="NOT_FOUND"
            )
        return batch

    async def _get_batch_for_update(
        self, tenant_id: uuid.UUID, promotion_id: uuid.UUID
    ) -> ClassPromotion:
        """Fetch batch with row-level lock to prevent concurrent execution."""
        result = await self.db.execute(
            select(ClassPromotion)
            .where(
                ClassPromotion.id == promotion_id,
                ClassPromotion.tenant_id == tenant_id,
                ClassPromotion.deleted_at.is_(None),
            )
            .with_for_update()
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise ClassPromotionError(
                "Promotion batch not found", code="NOT_FOUND"
            )
        return batch

    async def _get_entry(
        self, tenant_id: uuid.UUID, entry_id: uuid.UUID
    ) -> ClassPromotionEntry:
        result = await self.db.execute(
            select(ClassPromotionEntry).where(
                ClassPromotionEntry.id == entry_id,
                ClassPromotionEntry.tenant_id == tenant_id,
                ClassPromotionEntry.deleted_at.is_(None),
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ClassPromotionError(
                "Promotion entry not found", code="ENTRY_NOT_FOUND"
            )
        return entry
