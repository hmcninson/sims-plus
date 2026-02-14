"""
Seed exam demo data for testing.

This script:
1. Creates new exams
2. Adds subjects to exams for multiple classes
3. Enters random scores for all students
"""

import asyncio
import random
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.exam import Exam, ExamSubject, ExamScore
from app.models.student import Student, StudentStatus
from app.models.academic import Class, Subject, ClassSubject


# Configuration
TENANT_ID = UUID("59ebb8a9-3e35-4d08-82b4-5226e5be1c0a")
ACADEMIC_YEAR_ID = UUID("eeb79616-61fe-4772-87fe-73600a0a457f")
TERM_ID = UUID("2b5ad242-9e9e-4858-8c96-c47cb1ad3051")
CREATED_BY = UUID("3000e15c-6da9-4577-8823-15cf8cb3a353")


async def get_classes(session: AsyncSession) -> list[Class]:
    """Get all classes."""
    result = await session.execute(
        select(Class).where(Class.tenant_id == TENANT_ID, Class.is_active == True)
    )
    return list(result.scalars().all())


async def get_subjects(session: AsyncSession) -> list[Subject]:
    """Get all subjects."""
    result = await session.execute(
        select(Subject).where(Subject.tenant_id == TENANT_ID, Subject.is_active == True)
    )
    return list(result.scalars().all())


async def get_students_by_class(session: AsyncSession, class_id: UUID) -> list[Student]:
    """Get all students in a class."""
    result = await session.execute(
        select(Student).where(
            Student.tenant_id == TENANT_ID,
            Student.class_id == class_id,
            Student.status == StudentStatus.ACTIVE
        )
    )
    return list(result.scalars().all())


async def get_class_subjects(session: AsyncSession, class_id: UUID) -> list[ClassSubject]:
    """Get subjects assigned to a class."""
    result = await session.execute(
        select(ClassSubject).where(
            ClassSubject.tenant_id == TENANT_ID,
            ClassSubject.class_id == class_id,
            ClassSubject.is_active == True
        )
    )
    return list(result.scalars().all())


async def create_exam(
    session: AsyncSession,
    name: str,
    exam_type: str,
    status: str = "ongoing",
    description: str = None
) -> Exam:
    """Create a new exam."""
    exam = Exam(
        tenant_id=TENANT_ID,
        academic_year_id=ACADEMIC_YEAR_ID,
        term_id=TERM_ID,
        name=name,
        description=description or f"Demo {name}",
        exam_type=exam_type,
        status=status,
        created_by=CREATED_BY,
    )
    session.add(exam)
    await session.flush()
    print(f"Created exam: {name} ({exam.id})")
    return exam


async def add_exam_subject(
    session: AsyncSession,
    exam_id: UUID,
    subject_id: UUID,
    class_id: UUID,
    max_score: Decimal = Decimal("100.00"),
    pass_mark: Decimal = Decimal("50.00"),
) -> ExamSubject:
    """Add a subject to an exam for a class."""
    exam_subject = ExamSubject(
        tenant_id=TENANT_ID,
        exam_id=exam_id,
        subject_id=subject_id,
        class_id=class_id,
        max_score=max_score,
        pass_mark=pass_mark,
        status="pending",
    )
    session.add(exam_subject)
    await session.flush()
    return exam_subject


async def enter_score(
    session: AsyncSession,
    exam_subject_id: UUID,
    student_id: UUID,
    score: Decimal,
    is_absent: bool = False,
) -> ExamScore:
    """Enter a score for a student."""
    exam_score = ExamScore(
        tenant_id=TENANT_ID,
        exam_subject_id=exam_subject_id,
        student_id=student_id,
        score=None if is_absent else score,
        is_absent=is_absent,
    )
    session.add(exam_score)
    return exam_score


def generate_score(max_score: float = 100.0) -> Decimal:
    """Generate a realistic random score."""
    # Most scores between 40-90, with occasional outliers
    if random.random() < 0.1:  # 10% chance of low score
        score = random.uniform(20, 45)
    elif random.random() < 0.15:  # 15% chance of high score
        score = random.uniform(85, 100)
    else:  # Normal distribution around 65
        score = random.gauss(65, 12)
        score = max(25, min(95, score))  # Clamp to reasonable range

    return Decimal(str(round(score * (max_score / 100), 1)))


async def seed_exam_data():
    """Main function to seed exam data."""

    # Create async engine
    db_url = str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, echo=False)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Set tenant context
        await session.execute(text(f"SET app.current_tenant_id = '{TENANT_ID}'"))

        # Get existing data
        classes = await get_classes(session)
        subjects = await get_subjects(session)

        print(f"Found {len(classes)} classes and {len(subjects)} subjects")

        # Filter to only Primary and JHS classes (skip preschool for now)
        primary_jhs_classes = [c for c in classes if c.level.value.startswith(('primary', 'jhs'))]
        print(f"Using {len(primary_jhs_classes)} Primary/JHS classes")

        # Core subjects for Primary/JHS
        core_subject_codes = ['ENG', 'MATH', 'SCI', 'SST', 'ICT', 'RME', 'PE', 'ART']
        core_subjects = [s for s in subjects if s.code in core_subject_codes]
        print(f"Using {len(core_subjects)} core subjects")

        # --- Exam 1: End of Term 1 (for multiple classes) ---
        exam1 = await create_exam(
            session,
            name="End of Term 1 Examination",
            exam_type="end_term",
            status="ongoing",
            description="End of First Term comprehensive examination"
        )

        exam1_subjects_count = 0
        exam1_scores_count = 0

        for cls in primary_jhs_classes:
            students = await get_students_by_class(session, cls.id)
            if not students:
                print(f"  Skipping {cls.name} - no students")
                continue

            print(f"  Adding subjects for {cls.name} ({len(students)} students)")

            for subject in core_subjects:
                # Add subject to exam
                exam_subject = await add_exam_subject(
                    session, exam1.id, subject.id, cls.id
                )
                exam1_subjects_count += 1

                # Enter scores for all students
                for student in students:
                    # 5% chance of being absent
                    is_absent = random.random() < 0.05
                    score = Decimal("0") if is_absent else generate_score()
                    await enter_score(session, exam_subject.id, student.id, score, is_absent)
                    exam1_scores_count += 1

        print(f"Exam 1: {exam1_subjects_count} subjects, {exam1_scores_count} scores")

        # --- Exam 2: Weekly Quiz 1 (for a few classes) ---
        exam2 = await create_exam(
            session,
            name="Weekly Quiz 1",
            exam_type="quiz",
            status="completed",
            description="First weekly quiz"
        )

        # Only for Primary 4-6 and JHS
        quiz_classes = [c for c in primary_jhs_classes if c.level.value in ('primary_4', 'primary_5', 'primary_6', 'jhs_1', 'jhs_2', 'jhs_3')]
        quiz_subjects = [s for s in subjects if s.code in ['ENG', 'MATH', 'SCI']]

        exam2_subjects_count = 0
        exam2_scores_count = 0

        for cls in quiz_classes:
            students = await get_students_by_class(session, cls.id)
            if not students:
                continue

            print(f"  Adding quiz subjects for {cls.name} ({len(students)} students)")

            for subject in quiz_subjects:
                # Quiz has max score of 20
                exam_subject = await add_exam_subject(
                    session, exam2.id, subject.id, cls.id,
                    max_score=Decimal("20.00"),
                    pass_mark=Decimal("10.00")
                )
                exam2_subjects_count += 1

                for student in students:
                    is_absent = random.random() < 0.03
                    score = Decimal("0") if is_absent else generate_score(20.0)
                    await enter_score(session, exam_subject.id, student.id, score, is_absent)
                    exam2_scores_count += 1

        print(f"Exam 2: {exam2_subjects_count} subjects, {exam2_scores_count} scores")

        # --- Update existing Mid Term Test with more classes ---
        mid_term_id = UUID("4047a99f-a1c1-432c-92ac-f8a149527f16")

        # Get classes not yet in mid term (Primary 2-6, JHS 1-3)
        result = await session.execute(
            select(ExamSubject.class_id).where(ExamSubject.exam_id == mid_term_id).distinct()
        )
        existing_class_ids = {row[0] for row in result.all()}

        new_classes = [c for c in primary_jhs_classes if c.id not in existing_class_ids]

        mid_term_subjects_count = 0
        mid_term_scores_count = 0

        for cls in new_classes:
            students = await get_students_by_class(session, cls.id)
            if not students:
                continue

            print(f"  Adding mid-term subjects for {cls.name} ({len(students)} students)")

            for subject in core_subjects:
                exam_subject = await add_exam_subject(
                    session, mid_term_id, subject.id, cls.id
                )
                mid_term_subjects_count += 1

                for student in students:
                    is_absent = random.random() < 0.05
                    score = Decimal("0") if is_absent else generate_score()
                    await enter_score(session, exam_subject.id, student.id, score, is_absent)
                    mid_term_scores_count += 1

        print(f"Mid Term (updated): {mid_term_subjects_count} new subjects, {mid_term_scores_count} new scores")

        # Also fill in scores for existing Primary 1 subjects that don't have scores
        result = await session.execute(
            select(ExamSubject).where(
                ExamSubject.exam_id == mid_term_id,
                ExamSubject.tenant_id == TENANT_ID
            )
        )
        existing_exam_subjects = list(result.scalars().all())

        for exam_subject in existing_exam_subjects:
            # Check if scores exist
            result = await session.execute(
                select(ExamScore).where(ExamScore.exam_subject_id == exam_subject.id)
            )
            existing_scores = list(result.scalars().all())

            if len(existing_scores) == 0:
                students = await get_students_by_class(session, exam_subject.class_id)
                print(f"  Filling scores for {exam_subject.id} ({len(students)} students)")

                for student in students:
                    is_absent = random.random() < 0.05
                    score = Decimal("0") if is_absent else generate_score()
                    await enter_score(session, exam_subject.id, student.id, score, is_absent)
                    mid_term_scores_count += 1

        # Commit all changes
        await session.commit()
        print("\nAll data committed successfully!")

        # Summary
        print("\n=== Summary ===")
        print(f"Created 2 new exams")
        print(f"End of Term 1: {exam1_subjects_count} subjects, {exam1_scores_count} scores")
        print(f"Weekly Quiz 1: {exam2_subjects_count} subjects, {exam2_scores_count} scores")
        print(f"Mid Term (updated): +{mid_term_subjects_count} subjects, +{mid_term_scores_count} scores")


if __name__ == "__main__":
    asyncio.run(seed_exam_data())
