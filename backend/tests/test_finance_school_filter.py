"""
SIMS Plus - Finance School ID Filtering Tests

Verifies that finance list methods correctly filter by school_id.
Chain admins switching between schools must see only the selected
school's data; omitting school_id returns all tenant data.

Uses admin_session (superuser) for seeding, app_session (RLS-enforced)
for running service queries.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.finance.invoice_service import InvoiceService
from app.services.finance.payment_service import PaymentService
from app.services.finance.fee_type_service import FeeTypeService
from app.services.finance.fee_structure_service import FeeStructureService
from app.services.finance.scholarship_service import ScholarshipService
from app.services.finance.credit_note_service import CreditNoteService
from tests.conftest import (
    create_test_tenant,
    create_test_user,
    set_app_tenant_context,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_chain_tenant(session: AsyncSession) -> dict:
    """Create a school_chain tenant with 2 schools."""
    tenant_id = uuid4()
    school_a_id = uuid4()
    school_b_id = uuid4()
    sub = f"fin-chain-{uuid4().hex[:8]}"

    await session.execute(
        text("""
            INSERT INTO tenants (id, subdomain, slug, name, is_active,
                tenant_type, subscription_tier, max_students, max_staff)
            VALUES (
                CAST(:id AS uuid), :sub, :slug, :name,
                true, 'school_chain', 'enterprise', 5000, 500
            )
        """),
        {"id": str(tenant_id), "sub": sub, "slug": sub, "name": f"Chain {sub}"},
    )

    for sid, name, slug, code, prefix in [
        (school_a_id, "Finance School A", "fin-school-a", "FSA-001", "FSA"),
        (school_b_id, "Finance School B", "fin-school-b", "FSB-001", "FSB"),
    ]:
        await session.execute(
            text("""
                INSERT INTO schools (id, tenant_id, name, slug, code,
                    school_type, student_id_prefix)
                VALUES (
                    CAST(:id AS uuid), CAST(:tid AS uuid), :name, :slug,
                    :code, 'basic', :prefix
                )
            """),
            {
                "id": str(sid), "tid": str(tenant_id),
                "name": name, "slug": f"{slug}-{uuid4().hex[:6]}",
                "code": code, "prefix": prefix,
            },
        )

    await session.flush()
    return {
        "tenant_id": tenant_id,
        "school_a_id": school_a_id,
        "school_b_id": school_b_id,
        "subdomain": sub,
    }


async def _create_student(session, tenant_id, school_id) -> dict:
    """Create a student for the given school."""
    student_id = uuid4()
    sid_str = f"STU-{uuid4().hex[:6]}"
    await session.execute(
        text("""
            INSERT INTO students (
                id, tenant_id, school_id, student_id,
                first_name, last_name, date_of_birth, gender, status
            ) VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :stuid, 'Test', 'Student', '2010-01-01', 'male', 'active'
            )
        """),
        {
            "id": str(student_id), "tid": str(tenant_id),
            "sid": str(school_id), "stuid": sid_str,
        },
    )
    await session.flush()
    return {"id": student_id}


async def _create_academic_year(session, tenant_id, school_id) -> dict:
    """Create an academic year + term for the given school."""
    ay_id = uuid4()
    term_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO academic_years (id, tenant_id, school_id, name, start_date,
                end_date, status)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, '2025-09-01', '2026-07-31', 'active')
        """),
        {
            "id": str(ay_id), "tid": str(tenant_id),
            "sid": str(school_id), "name": f"AY-{uuid4().hex[:6]}",
        },
    )
    await session.execute(
        text("""
            INSERT INTO terms (id, tenant_id, school_id, academic_year_id, name,
                start_date, end_date, status)
            VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:ayid AS uuid), :name, '2025-09-01', '2025-12-20', 'active')
        """),
        {
            "id": str(term_id), "tid": str(tenant_id),
            "sid": str(school_id), "ayid": str(ay_id),
            "name": f"Term-{uuid4().hex[:6]}",
        },
    )
    await session.flush()
    return {"academic_year_id": ay_id, "term_id": term_id}


async def _create_fee_type(session, tenant_id, school_id, name=None) -> dict:
    """Create a fee type for the given school."""
    ft_id = uuid4()
    ft_name = name or f"Fee-{uuid4().hex[:6]}"
    await session.execute(
        text("""
            INSERT INTO fee_types (id, tenant_id, school_id, name, category, is_active)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, 'tuition', true
            )
        """),
        {
            "id": str(ft_id), "tid": str(tenant_id),
            "sid": str(school_id), "name": ft_name,
        },
    )
    await session.flush()
    return {"id": ft_id, "name": ft_name}


async def _create_fee_structure(session, tenant_id, school_id, ay_id, term_id) -> dict:
    """Create a fee structure for the given school."""
    fs_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO fee_structures (id, tenant_id, school_id, name,
                academic_year_id, term_id, is_active)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, CAST(:ayid AS uuid), CAST(:tid2 AS uuid), true
            )
        """),
        {
            "id": str(fs_id), "tid": str(tenant_id),
            "sid": str(school_id), "name": f"FS-{uuid4().hex[:6]}",
            "ayid": str(ay_id), "tid2": str(term_id),
        },
    )
    await session.flush()
    return {"id": fs_id}


async def _create_invoice(
    session, tenant_id, school_id, student_id, ay_id, term_id
) -> dict:
    """Create an invoice for the given school."""
    inv_id = uuid4()
    inv_num = f"INV-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO invoices (id, tenant_id, school_id, invoice_number,
                student_id, academic_year_id, term_id,
                subtotal, total_amount, amount_paid, status)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :inv_num, CAST(:stu AS uuid), CAST(:ayid AS uuid),
                CAST(:tid2 AS uuid),
                100.00, 100.00, 0.00, 'draft'
            )
        """),
        {
            "id": str(inv_id), "tid": str(tenant_id),
            "sid": str(school_id), "inv_num": inv_num,
            "stu": str(student_id), "ayid": str(ay_id),
            "tid2": str(term_id),
        },
    )
    await session.flush()
    return {"id": inv_id, "invoice_number": inv_num}


async def _create_payment(
    session, tenant_id, school_id, student_id, invoice_id
) -> dict:
    """Create a payment for the given school."""
    pay_id = uuid4()
    receipt = f"RCP-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO payments (id, tenant_id, school_id, invoice_id,
                student_id, receipt_number, amount, payment_method,
                payment_date, status, payer_name)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                CAST(:inv AS uuid), CAST(:stu AS uuid), :receipt,
                50.00, 'cash', CURRENT_DATE, 'completed', 'Test Payer'
            )
        """),
        {
            "id": str(pay_id), "tid": str(tenant_id),
            "sid": str(school_id), "inv": str(invoice_id),
            "stu": str(student_id), "receipt": receipt,
        },
    )
    await session.flush()
    return {"id": pay_id}


async def _create_scholarship(session, tenant_id, school_id, ay_id) -> dict:
    """Create a scholarship for the given school."""
    sch_id = uuid4()
    await session.execute(
        text("""
            INSERT INTO scholarships (id, tenant_id, school_id, name, code,
                academic_year_id, scholarship_type, coverage_type,
                coverage_value, max_recipients, is_active)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :name, :code, CAST(:ayid AS uuid), 'merit', 'percentage',
                50.00, 10, true
            )
        """),
        {
            "id": str(sch_id), "tid": str(tenant_id),
            "sid": str(school_id), "name": f"Sch-{uuid4().hex[:6]}",
            "code": f"SCH-{uuid4().hex[:4]}".upper(),
            "ayid": str(ay_id),
        },
    )
    await session.flush()
    return {"id": sch_id}


async def _create_credit_note(session, tenant_id, school_id, student_id) -> dict:
    """Create a credit note for the given school."""
    cn_id = uuid4()
    cn_num = f"CN-{uuid4().hex[:8]}"
    await session.execute(
        text("""
            INSERT INTO credit_notes (id, tenant_id, school_id,
                credit_note_number, student_id, credit_note_type,
                amount, status, reason)
            VALUES (
                CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid),
                :cn_num, CAST(:stu AS uuid), 'overpayment',
                25.00, 'draft', 'Test credit note'
            )
        """),
        {
            "id": str(cn_id), "tid": str(tenant_id),
            "sid": str(school_id), "cn_num": cn_num,
            "stu": str(student_id),
        },
    )
    await session.flush()
    return {"id": cn_id}


# ===========================================================================
# Invoices
# ===========================================================================


class TestInvoiceSchoolFilter:
    """Verify list_invoices filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_invoices_with_school_id_returns_only_that_school(
        self, admin_session, app_session
    ):
        """Passing school_id returns only invoices for that school."""
        data = await _create_chain_tenant(admin_session)
        stu_a = await _create_student(admin_session, data["tenant_id"], data["school_a_id"])
        stu_b = await _create_student(admin_session, data["tenant_id"], data["school_b_id"])
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        inv_a = await _create_invoice(
            admin_session, data["tenant_id"], data["school_a_id"],
            stu_a["id"], ay_a["academic_year_id"], ay_a["term_id"],
        )
        inv_b = await _create_invoice(
            admin_session, data["tenant_id"], data["school_b_id"],
            stu_b["id"], ay_b["academic_year_id"], ay_b["term_id"],
        )
        await admin_session.commit()

        tenant_id = data["tenant_id"]
        school_a_id = data["school_a_id"]
        inv_a_id = inv_a["id"]
        inv_b_id = inv_b["id"]

        await set_app_tenant_context(app_session, tenant_id)
        svc = InvoiceService(app_session)

        invoices, total = await svc.list_invoices(tenant_id, school_id=school_a_id)

        invoice_ids = [inv.id for inv in invoices]
        assert inv_a_id in invoice_ids
        assert inv_b_id not in invoice_ids
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_invoices_without_school_id_returns_all(
        self, admin_session, app_session
    ):
        """Omitting school_id returns invoices from all schools (chain admin view)."""
        data = await _create_chain_tenant(admin_session)
        stu_a = await _create_student(admin_session, data["tenant_id"], data["school_a_id"])
        stu_b = await _create_student(admin_session, data["tenant_id"], data["school_b_id"])
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        await _create_invoice(
            admin_session, data["tenant_id"], data["school_a_id"],
            stu_a["id"], ay_a["academic_year_id"], ay_a["term_id"],
        )
        await _create_invoice(
            admin_session, data["tenant_id"], data["school_b_id"],
            stu_b["id"], ay_b["academic_year_id"], ay_b["term_id"],
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = InvoiceService(app_session)

        invoices, total = await svc.list_invoices(data["tenant_id"])

        assert total == 2

    @pytest.mark.asyncio
    async def test_export_invoices_csv_with_school_id(
        self, admin_session, app_session
    ):
        """export_invoices_csv with school_id returns only that school's invoices."""
        data = await _create_chain_tenant(admin_session)
        stu_a = await _create_student(admin_session, data["tenant_id"], data["school_a_id"])
        stu_b = await _create_student(admin_session, data["tenant_id"], data["school_b_id"])
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        inv_a = await _create_invoice(
            admin_session, data["tenant_id"], data["school_a_id"],
            stu_a["id"], ay_a["academic_year_id"], ay_a["term_id"],
        )
        await _create_invoice(
            admin_session, data["tenant_id"], data["school_b_id"],
            stu_b["id"], ay_b["academic_year_id"], ay_b["term_id"],
        )
        await admin_session.commit()

        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = InvoiceService(app_session)

        rows = await svc.export_invoices_csv(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        assert len(rows) == 1
        assert rows[0]["invoice_number"] == inv_a["invoice_number"]


# ===========================================================================
# Payments
# ===========================================================================


class TestPaymentSchoolFilter:
    """Verify list_payments filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_payments_with_school_id(
        self, admin_session, app_session
    ):
        """Passing school_id returns only payments for that school."""
        data = await _create_chain_tenant(admin_session)
        stu_a = await _create_student(admin_session, data["tenant_id"], data["school_a_id"])
        stu_b = await _create_student(admin_session, data["tenant_id"], data["school_b_id"])
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        inv_a = await _create_invoice(
            admin_session, data["tenant_id"], data["school_a_id"],
            stu_a["id"], ay_a["academic_year_id"], ay_a["term_id"],
        )
        inv_b = await _create_invoice(
            admin_session, data["tenant_id"], data["school_b_id"],
            stu_b["id"], ay_b["academic_year_id"], ay_b["term_id"],
        )
        pay_a = await _create_payment(
            admin_session, data["tenant_id"], data["school_a_id"],
            stu_a["id"], inv_a["id"],
        )
        await _create_payment(
            admin_session, data["tenant_id"], data["school_b_id"],
            stu_b["id"], inv_b["id"],
        )
        await admin_session.commit()

        pay_a_id = pay_a["id"]
        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = PaymentService(app_session)

        payments, total = await svc.list_payments(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        payment_ids = [p.id for p in payments]
        assert pay_a_id in payment_ids
        assert total == 1


# ===========================================================================
# Fee Types
# ===========================================================================


class TestFeeTypeSchoolFilter:
    """Verify list_fee_types filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_fee_types_with_school_id(
        self, admin_session, app_session
    ):
        """Passing school_id returns only fee types for that school."""
        data = await _create_chain_tenant(admin_session)
        ft_a = await _create_fee_type(
            admin_session, data["tenant_id"], data["school_a_id"], "Tuition A"
        )
        ft_b = await _create_fee_type(
            admin_session, data["tenant_id"], data["school_b_id"], "Tuition B"
        )
        await admin_session.commit()

        ft_a_id = ft_a["id"]
        ft_b_id = ft_b["id"]
        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = FeeTypeService(app_session)

        fee_types, total = await svc.list_fee_types(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        ids = [ft.id for ft in fee_types]
        assert ft_a_id in ids
        assert ft_b_id not in ids
        assert total == 1


# ===========================================================================
# Fee Structures
# ===========================================================================


class TestFeeStructureSchoolFilter:
    """Verify list_fee_structures filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_fee_structures_with_school_id(
        self, admin_session, app_session
    ):
        """Passing school_id returns only fee structures for that school."""
        data = await _create_chain_tenant(admin_session)
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        fs_a = await _create_fee_structure(
            admin_session, data["tenant_id"], data["school_a_id"],
            ay_a["academic_year_id"], ay_a["term_id"],
        )
        fs_b = await _create_fee_structure(
            admin_session, data["tenant_id"], data["school_b_id"],
            ay_b["academic_year_id"], ay_b["term_id"],
        )
        await admin_session.commit()

        fs_a_id = fs_a["id"]
        fs_b_id = fs_b["id"]
        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = FeeStructureService(app_session)

        structures, total = await svc.list_fee_structures(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        ids = [fs.id for fs in structures]
        assert fs_a_id in ids
        assert fs_b_id not in ids
        assert total == 1


# ===========================================================================
# Scholarships
# ===========================================================================


class TestScholarshipSchoolFilter:
    """Verify list_scholarships filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_scholarships_with_school_id(
        self, admin_session, app_session
    ):
        """Passing school_id returns only scholarships for that school."""
        data = await _create_chain_tenant(admin_session)
        ay_a = await _create_academic_year(admin_session, data["tenant_id"], data["school_a_id"])
        ay_b = await _create_academic_year(admin_session, data["tenant_id"], data["school_b_id"])
        sch_a = await _create_scholarship(
            admin_session, data["tenant_id"], data["school_a_id"],
            ay_a["academic_year_id"],
        )
        sch_b = await _create_scholarship(
            admin_session, data["tenant_id"], data["school_b_id"],
            ay_b["academic_year_id"],
        )
        await admin_session.commit()

        sch_a_id = sch_a["id"]
        sch_b_id = sch_b["id"]
        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = ScholarshipService(app_session)

        scholarships, total = await svc.list_scholarships(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        ids = [s.id for s in scholarships]
        assert sch_a_id in ids
        assert sch_b_id not in ids
        assert total == 1


# ===========================================================================
# Credit Notes
# ===========================================================================


class TestCreditNoteSchoolFilter:
    """Verify list_credit_notes filters by school_id."""

    @pytest.mark.asyncio
    async def test_list_credit_notes_with_school_id(
        self, admin_session, app_session
    ):
        """Passing school_id returns only credit notes for that school."""
        data = await _create_chain_tenant(admin_session)
        stu_a = await _create_student(admin_session, data["tenant_id"], data["school_a_id"])
        stu_b = await _create_student(admin_session, data["tenant_id"], data["school_b_id"])
        cn_a = await _create_credit_note(
            admin_session, data["tenant_id"], data["school_a_id"], stu_a["id"]
        )
        cn_b = await _create_credit_note(
            admin_session, data["tenant_id"], data["school_b_id"], stu_b["id"]
        )
        await admin_session.commit()

        cn_a_id = cn_a["id"]
        cn_b_id = cn_b["id"]
        await set_app_tenant_context(app_session, data["tenant_id"])
        svc = CreditNoteService(app_session)

        credit_notes, total = await svc.list_credit_notes(
            data["tenant_id"], school_id=data["school_a_id"]
        )

        ids = [cn.id for cn in credit_notes]
        assert cn_a_id in ids
        assert cn_b_id not in ids
        assert total == 1
