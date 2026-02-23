"""
SIMS Plus - School Chain Service

Business logic for managing school chains: adding schools,
assigning users to schools, querying chain-level data,
chain dashboard, and accessible school lists.

SECURITY:
- All queries filter by tenant_id (defense-in-depth on top of RLS).
- Chain operations require CHAIN_ADMIN or PLATFORM_ADMIN role.
"""

import re
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.school import School
from app.models.staff import Staff, StaffStatus
from app.models.student import Student, StudentStatus
from app.models.tenant import Tenant, TenantType
from app.models.user import User
from app.models.user_school import UserSchool

logger = structlog.get_logger()


class ChainService:
    """Service for school chain management operations."""

    class Error(Exception):
        def __init__(self, message: str, code: int = 400):
            self.message = message
            self.code = code
            super().__init__(message)

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================
    # Chain Validation
    # =========================

    async def _verify_chain_tenant(self, tenant_id: UUID) -> Tenant:
        """
        Verify that the tenant is a school_chain type.

        Raises Error if the tenant is not a chain.
        """
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise self.Error("Tenant not found", 404)
        if tenant.tenant_type != TenantType.SCHOOL_CHAIN:
            raise self.Error(
                "This operation is only available for school chain tenants",
                403,
            )
        return tenant

    @staticmethod
    def _slugify(name: str) -> str:
        """Generate a URL-safe slug from a school name."""
        slug = name.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")[:100]

    # =========================
    # School Management
    # =========================

    async def list_schools(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> dict:
        """
        List schools in a chain tenant with student/staff counts.

        Supports pagination and search by school name.
        Uses subqueries to avoid N+1: one query instead of 2N+1.
        Returns dict with items (list of dicts) and total count.
        """
        from app.utils.sanitize import escape_ilike

        # Subquery: count active students per school
        student_count_sq = (
            select(
                Student.school_id,
                func.count(Student.id).label("cnt"),
            )
            .where(Student.tenant_id == tenant_id)
            .where(Student.status == StudentStatus.ACTIVE)
            .where(Student.deleted_at.is_(None))
            .group_by(Student.school_id)
            .subquery()
        )

        # Subquery: count active staff per school
        staff_count_sq = (
            select(
                Staff.school_id,
                func.count(Staff.id).label("cnt"),
            )
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.status == StaffStatus.ACTIVE)
            .where(Staff.deleted_at.is_(None))
            .group_by(Staff.school_id)
            .subquery()
        )

        # Base query: join schools with count subqueries
        base_query = (
            select(
                School,
                func.coalesce(student_count_sq.c.cnt, 0).label("student_count"),
                func.coalesce(staff_count_sq.c.cnt, 0).label("staff_count"),
            )
            # Defense-in-depth: filter by tenant_id even though RLS handles isolation
            .outerjoin(student_count_sq, student_count_sq.c.school_id == School.id)
            .outerjoin(staff_count_sq, staff_count_sq.c.school_id == School.id)
            .where(School.tenant_id == tenant_id)
            .where(School.deleted_at.is_(None))
        )

        if search:
            safe_search = escape_ilike(search)
            base_query = base_query.where(
                School.name.ilike(f"%{safe_search}%")
            )

        # Get total count for pagination
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        result = await self.db.execute(
            base_query.order_by(School.name).offset(offset).limit(page_size)
        )

        rows = result.all()
        items = [
            {
                "school": row[0],
                "student_count": row[1],
                "staff_count": row[2],
            }
            for row in rows
        ]
        return {"items": items, "total": total}

    async def get_school_counts(
        self, school_id: UUID, tenant_id: UUID
    ) -> tuple[int, int]:
        """Get student and staff counts for a single school."""
        student_result = await self.db.execute(
            select(func.count(Student.id))
            .where(Student.school_id == school_id)
            .where(Student.tenant_id == tenant_id)
            .where(Student.deleted_at.is_(None))
        )
        student_count = student_result.scalar() or 0

        staff_result = await self.db.execute(
            select(func.count(Staff.id))
            .where(Staff.school_id == school_id)
            .where(Staff.tenant_id == tenant_id)
            .where(Staff.deleted_at.is_(None))
        )
        staff_count = staff_result.scalar() or 0

        return student_count, staff_count

    async def add_school(
        self,
        tenant_id: UUID,
        name: str,
        code: str,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        student_id_prefix: str | None = None,
    ) -> School:
        """
        Add a new school to a chain tenant.

        Raises Error if tenant is not a chain or school code already exists.
        """
        await self._verify_chain_tenant(tenant_id)

        # Check for duplicate school code within tenant
        existing = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.code == code)
            .where(School.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise self.Error(f"A school with code '{code}' already exists in this chain")

        school = School(
            tenant_id=tenant_id,
            name=name,
            slug=self._slugify(name),
            code=code,
            address=address,
            phone=phone,
            email=email,
            student_id_prefix=student_id_prefix,
        )
        self.db.add(school)
        await self.db.flush()
        await self.db.refresh(school)

        logger.info(
            "chain_school_added",
            tenant_id=str(tenant_id),
            school_id=str(school.id),
            school_name=name,
        )

        return school

    async def update_school(
        self,
        tenant_id: UUID,
        school_id: UUID,
        name: str | None = None,
        address: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        student_id_prefix: str | None = None,
    ) -> School:
        """Update a school in the chain."""
        await self._verify_chain_tenant(tenant_id)
        # Defense-in-depth: filter by tenant_id
        result = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == school_id)
            .where(School.deleted_at.is_(None))
        )
        school = result.scalar_one_or_none()
        if not school:
            raise self.Error("School not found", 404)

        if name is not None:
            school.name = name
        if address is not None:
            school.address = address
        if phone is not None:
            school.phone = phone
        if email is not None:
            school.email = email
        if student_id_prefix is not None:
            school.student_id_prefix = student_id_prefix

        await self.db.flush()
        await self.db.refresh(school)
        return school

    async def get_school(self, tenant_id: UUID, school_id: UUID) -> School:
        """Get a single school by ID within the chain tenant."""
        await self._verify_chain_tenant(tenant_id)
        result = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == school_id)
            .where(School.deleted_at.is_(None))
        )
        school = result.scalar_one_or_none()
        if not school:
            raise self.Error("School not found", 404)
        return school

    # =========================
    # Accessible Schools
    # =========================

    async def get_accessible_schools(
        self, user_id: UUID, tenant_id: UUID
    ) -> list[School]:
        """
        Get schools accessible to a user within the tenant.

        Returns lightweight school list for the school switcher dropdown.
        Ordered by primary school first, then alphabetically.
        """
        # Defense-in-depth: filter by tenant_id on both UserSchool and School
        result = await self.db.execute(
            select(School)
            .join(UserSchool, UserSchool.school_id == School.id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.is_active.is_(True))
            .where(School.tenant_id == tenant_id)
            .where(School.deleted_at.is_(None))
            .order_by(UserSchool.is_primary.desc(), School.name)
        )
        return list(result.scalars().all())

    # =========================
    # User-School Management
    # =========================

    async def assign_user_to_school(
        self,
        tenant_id: UUID,
        user_id: UUID,
        school_id: UUID,
        role_at_school: str,
        is_primary: bool = False,
    ) -> UserSchool:
        """
        Grant a user access to a school within the chain.

        Validates that both user and school belong to the tenant.
        If is_primary=True, clears the primary flag on other schools.
        """
        # Verify user belongs to tenant
        user_result = await self.db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.id == user_id)
            .where(User.deleted_at.is_(None))
        )
        if not user_result.scalar_one_or_none():
            raise self.Error("User not found", 404)

        # Verify school belongs to tenant
        school_result = await self.db.execute(
            select(School)
            .where(School.tenant_id == tenant_id)
            .where(School.id == school_id)
            .where(School.deleted_at.is_(None))
        )
        if not school_result.scalar_one_or_none():
            raise self.Error("School not found", 404)

        # Check for existing assignment
        existing = await self.db.execute(
            select(UserSchool)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.school_id == school_id)
        )
        existing_record = existing.scalar_one_or_none()
        if existing_record:
            # Reactivate if previously deactivated
            existing_record.is_active = True
            existing_record.role_at_school = role_at_school
            if is_primary:
                await self._clear_primary_flags(tenant_id, user_id)
                existing_record.is_primary = True
            await self.db.flush()
            await self.db.refresh(existing_record)
            return existing_record

        # Clear primary flags if this will be primary
        if is_primary:
            await self._clear_primary_flags(tenant_id, user_id)

        user_school = UserSchool(
            tenant_id=tenant_id,
            user_id=user_id,
            school_id=school_id,
            role_at_school=role_at_school,
            is_primary=is_primary,
            is_active=True,
        )
        self.db.add(user_school)
        await self.db.flush()
        await self.db.refresh(user_school)

        logger.info(
            "user_assigned_to_school",
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            school_id=str(school_id),
            role=role_at_school,
        )

        return user_school

    async def remove_user_from_school(
        self,
        tenant_id: UUID,
        user_id: UUID,
        school_id: UUID,
    ) -> bool:
        """
        Remove a user's access to a school (soft-disable via is_active=False).

        Returns True if the record was found and deactivated.
        """
        result = await self.db.execute(
            select(UserSchool)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.school_id == school_id)
        )
        user_school = result.scalar_one_or_none()
        if not user_school:
            raise self.Error("User-school assignment not found", 404)

        user_school.is_active = False
        await self.db.flush()
        return True

    async def list_user_schools(
        self,
        tenant_id: UUID,
        user_id: UUID,
    ) -> list[UserSchool]:
        """List all schools a user has access to."""
        result = await self.db.execute(
            select(UserSchool)
            .options(selectinload(UserSchool.school))
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.is_active.is_(True))
            .order_by(UserSchool.is_primary.desc())
        )
        return list(result.scalars().all())

    async def list_school_users(
        self,
        tenant_id: UUID,
        school_id: UUID,
    ) -> list[UserSchool]:
        """List all users assigned to a specific school."""
        result = await self.db.execute(
            select(UserSchool)
            .options(selectinload(UserSchool.user))
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.school_id == school_id)
            .where(UserSchool.is_active.is_(True))
        )
        return list(result.scalars().all())

    # =========================
    # Chain Overview
    # =========================

    async def get_chain_overview(self, tenant_id: UUID) -> dict:
        """
        Get high-level overview of the chain: total schools, students, staff.

        Fetches all schools (no pagination) for the overview aggregation.
        """
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise self.Error("Tenant not found", 404)

        # Use a large page_size to get all schools for the overview
        schools_result = await self.list_schools(tenant_id, page=1, page_size=10000)
        schools_data = schools_result["items"]

        total_students = sum(s["student_count"] for s in schools_data)
        total_staff = sum(s["staff_count"] for s in schools_data)

        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant.name,
            "total_schools": schools_result["total"],
            "total_students": total_students,
            "total_staff": total_staff,
            "schools_data": schools_data,
        }

    # =========================
    # Chain Dashboard
    # =========================

    async def get_chain_dashboard(self, tenant_id: UUID) -> dict:
        """
        Get chain dashboard with financial and attendance metrics per school.

        Returns dict ready for ChainDashboardResponse construction.
        Financial queries are batched (two grouped queries) to avoid N+1.
        They degrade gracefully if the finance module tables are not present.
        """
        await self._verify_chain_tenant(tenant_id)
        # Use a large page_size to get all schools for the dashboard
        schools_result = await self.list_schools(tenant_id, page=1, page_size=10000)
        schools_data = schools_result["items"]

        # Batch financial queries to avoid 2 SQL queries per school (N+1)
        billed_by_school: dict[UUID, float] = {}
        collected_by_school: dict[UUID, float] = {}
        try:
            from app.models.finance import Invoice, Payment, PaymentStatus

            # Batch billed amounts grouped by school
            billed_result = await self.db.execute(
                select(
                    Invoice.school_id,
                    func.coalesce(func.sum(Invoice.total_amount), 0).label("billed"),
                )
                .where(Invoice.tenant_id == tenant_id)
                .where(Invoice.deleted_at.is_(None))
                .group_by(Invoice.school_id)
            )
            for row in billed_result:
                billed_by_school[row.school_id] = float(row.billed)

            # Batch collected amounts grouped by school
            # Payment does not have SoftDeleteMixin, so no deleted_at filter
            collected_result = await self.db.execute(
                select(
                    Payment.school_id,
                    func.coalesce(func.sum(Payment.amount), 0).label("collected"),
                )
                .where(Payment.tenant_id == tenant_id)
                .where(Payment.status == PaymentStatus.COMPLETED)
                .group_by(Payment.school_id)
            )
            for row in collected_result:
                collected_by_school[row.school_id] = float(row.collected)
        except (ImportError, ProgrammingError):
            pass  # Finance module not available or tables don't exist yet
        except Exception:
            logger.warning("chain_dashboard_finance_query_failed", exc_info=True)

        school_metrics = []
        total_students = 0
        total_staff = 0
        total_revenue = 0.0
        total_outstanding = 0.0

        for sd in schools_data:
            school = sd["school"]
            s_count = sd["student_count"]
            st_count = sd["staff_count"]
            total_students += s_count
            total_staff += st_count

            # Dict lookup instead of per-school SQL queries
            billed = billed_by_school.get(school.id, 0.0)
            collected = collected_by_school.get(school.id, 0.0)
            outstanding_amt = max(billed - collected, 0)

            total_revenue += collected
            total_outstanding += outstanding_amt

            collection_rate = (collected / billed * 100) if billed > 0 else 0.0

            school_metrics.append({
                "school_id": school.id,
                "school_name": school.name,
                "school_code": school.code,
                "logo_url": school.logo_url,
                "total_students": s_count,
                "total_staff": st_count,
                "attendance_rate": 0.0,  # TODO: Calculate from attendance module
                "total_billed": billed,
                "total_collected": collected,
                "collection_rate": collection_rate,
                "outstanding": outstanding_amt,
            })

        return {
            "total_schools": len(schools_data),
            "total_students": total_students,
            "total_staff": total_staff,
            "overall_attendance_rate": 0.0,  # Placeholder until attendance integration
            "total_revenue": total_revenue,
            "total_outstanding": total_outstanding,
            "schools": school_metrics,
        }

    # =========================
    # Chain Users
    # =========================

    async def list_chain_users(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        school_id: UUID | None = None,
    ) -> dict:
        """
        List users in the chain with their school assignments.

        Supports pagination, search (name/email), and school_id filter.
        Batch-loads school accesses to avoid N+1 on user iteration.
        """
        from app.utils.sanitize import escape_ilike

        # Base query for users within tenant
        query = (
            select(User)
            .where(User.tenant_id == tenant_id)
            .where(User.deleted_at.is_(None))
        )

        if search:
            safe_search = escape_ilike(search)
            query = query.where(
                (User.email.ilike(f"%{safe_search}%"))
                | (User.first_name.ilike(f"%{safe_search}%"))
                | (User.last_name.ilike(f"%{safe_search}%"))
            )

        # Optional filter: only users assigned to a specific school
        if school_id:
            query = query.join(
                UserSchool, UserSchool.user_id == User.id
            ).where(
                UserSchool.tenant_id == tenant_id,
                UserSchool.school_id == school_id,
                UserSchool.is_active.is_(True),
            )

        # Count total matching users
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        # Paginate
        offset = (page - 1) * page_size
        result = await self.db.execute(
            query.order_by(User.last_name, User.first_name)
            .offset(offset)
            .limit(page_size)
        )
        users = result.scalars().all()

        # Batch-load school accesses for the page of users (avoid N+1)
        user_ids = [u.id for u in users]
        if user_ids:
            access_result = await self.db.execute(
                select(UserSchool)
                .options(selectinload(UserSchool.school))
                .where(UserSchool.tenant_id == tenant_id)
                .where(UserSchool.user_id.in_(user_ids))
                .where(UserSchool.is_active.is_(True))
            )
            all_accesses = access_result.scalars().all()
        else:
            all_accesses = []

        # Group accesses by user_id for O(1) lookup in the endpoint
        accesses_by_user: dict[UUID, list] = {}
        for a in all_accesses:
            accesses_by_user.setdefault(a.user_id, []).append(a)

        return {
            "users": users,
            "accesses_by_user": accesses_by_user,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    # =========================
    # Private Helpers
    # =========================

    async def _clear_primary_flags(
        self, tenant_id: UUID, user_id: UUID
    ) -> None:
        """Clear is_primary on all user-school records for this user."""
        result = await self.db.execute(
            select(UserSchool)
            .where(UserSchool.tenant_id == tenant_id)
            .where(UserSchool.user_id == user_id)
            .where(UserSchool.is_primary.is_(True))
        )
        for us in result.scalars().all():
            us.is_primary = False
        await self.db.flush()
