"""
E2E tests for the complete finance billing cycle.

Tests: fee type -> fee structure -> student -> invoice generation -> payment recording.
"""

import pytest


@pytest.mark.asyncio
async def test_fee_type_crud(auth_client, seeded_tenant):
    """Create, list, and verify a fee type."""
    client = auth_client

    # Create fee type
    create_resp = await client.post("/api/v1/finance/fee-types", json={
        "name": "Tuition Fee",
        "category": "tuition",
    })
    assert create_resp.status_code == 201, f"Fee type creation failed: {create_resp.text}"
    fee_type = create_resp.json()
    assert fee_type["name"] == "Tuition Fee"
    fee_type_id = fee_type["id"]

    # List fee types -- should contain the one we just created
    list_resp = await client.get("/api/v1/finance/fee-types")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(ft["id"] == fee_type_id for ft in items)

    # Get single fee type
    get_resp = await client.get(f"/api/v1/finance/fee-types/{fee_type_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Tuition Fee"


@pytest.mark.asyncio
async def test_fee_structure_with_items(auth_client, seeded_tenant):
    """Create a fee structure with line items."""
    client = auth_client

    # Prerequisites: academic year, term, class, fee type
    ay_resp = await client.post("/api/v1/academic/academic-years", json={
        "name": "FS 2025/2026",
        "start_date": "2025-09-01",
        "end_date": "2026-07-31",
        "is_current": True,
    })
    assert ay_resp.status_code == 201
    ay_id = ay_resp.json()["id"]

    term_resp = await client.post("/api/v1/academic/terms", json={
        "academic_year_id": ay_id,
        "name": "FS Term 1",
        "start_date": "2025-09-01",
        "end_date": "2025-12-20",
        "sequence": 1,
    })
    assert term_resp.status_code == 201
    term_id = term_resp.json()["term"]["id"]

    class_resp = await client.post("/api/v1/academic/classes", json={
        "name": "FS Class 1",
        "level": "primary",
        "sequence": 1,
    })
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    ft_resp = await client.post("/api/v1/finance/fee-types", json={
        "name": "FS Tuition",
        "category": "tuition",
    })
    assert ft_resp.status_code == 201
    fee_type_id = ft_resp.json()["id"]

    # Create fee structure with items
    structure_resp = await client.post("/api/v1/finance/fee-structures", json={
        "name": "Class 1 Term 1 Fees",
        "academic_year_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "items": [
            {
                "fee_type_id": fee_type_id,
                "name": "Tuition",
                "amount": 500.00,
            },
        ],
    })
    assert structure_resp.status_code == 201, f"Fee structure creation failed: {structure_resp.text}"
    structure = structure_resp.json()
    assert structure["name"] == "Class 1 Term 1 Fees"
    # The structure should have items
    assert len(structure.get("items", [])) >= 1


@pytest.mark.asyncio
async def test_complete_billing_cycle(auth_client, seeded_tenant):
    """Fee type -> structure -> student -> invoice -> verify total."""
    client = auth_client

    # 1. Academic year
    ay_resp = await client.post("/api/v1/academic/academic-years", json={
        "name": "Billing 2025/2026",
        "start_date": "2025-09-01",
        "end_date": "2026-07-31",
        "is_current": True,
    })
    assert ay_resp.status_code == 201
    ay_id = ay_resp.json()["id"]

    # 2. Term
    term_resp = await client.post("/api/v1/academic/terms", json={
        "academic_year_id": ay_id,
        "name": "Billing Term 1",
        "start_date": "2025-09-01",
        "end_date": "2025-12-20",
        "sequence": 1,
    })
    assert term_resp.status_code == 201
    term_id = term_resp.json()["term"]["id"]

    # 3. Class
    class_resp = await client.post("/api/v1/academic/classes", json={
        "name": "Billing Class 1",
        "level": "primary",
        "sequence": 1,
    })
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    # 4. Fee type
    ft_resp = await client.post("/api/v1/finance/fee-types", json={
        "name": "Billing Tuition",
        "category": "tuition",
    })
    assert ft_resp.status_code == 201
    fee_type_id = ft_resp.json()["id"]

    # 5. Fee structure
    struct_resp = await client.post("/api/v1/finance/fee-structures", json={
        "name": "Billing Structure",
        "academic_year_id": ay_id,
        "term_id": term_id,
        "class_id": class_id,
        "items": [
            {"fee_type_id": fee_type_id, "name": "Tuition", "amount": 500.00},
        ],
    })
    assert struct_resp.status_code == 201
    structure_id = struct_resp.json()["id"]

    # 6. Student
    student_resp = await client.post("/api/v1/students", json={
        "first_name": "Kofi",
        "last_name": "Mensah",
        "date_of_birth": "2015-03-15",
        "gender": "male",
        "class_id": class_id,
    })
    assert student_resp.status_code == 201, f"Student creation failed: {student_resp.text}"
    student_id = student_resp.json()["id"]

    # 7. Generate invoice
    invoice_resp = await client.post("/api/v1/finance/invoices", json={
        "student_id": student_id,
        "academic_year_id": ay_id,
        "term_id": term_id,
        "fee_structure_id": structure_id,
    })
    assert invoice_resp.status_code == 201, f"Invoice creation failed: {invoice_resp.text}"
    invoice = invoice_resp.json()
    assert float(invoice["total_amount"]) == 500.00
    assert invoice["student_id"] == student_id

    # 8. Verify invoice in list
    list_resp = await client.get("/api/v1/finance/invoices", params={
        "page": 1,
        "page_size": 10,
    })
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_invoice_list_empty(auth_client, seeded_tenant):
    """Invoice list for a new tenant should return empty."""
    resp = await auth_client.get("/api/v1/finance/invoices", params={
        "page": 1,
        "page_size": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_fee_type_duplicate_name_rejected(auth_client, seeded_tenant):
    """Creating two fee types with the same name should fail."""
    client = auth_client

    resp1 = await client.post("/api/v1/finance/fee-types", json={
        "name": "Duplicate Fee",
        "category": "tuition",
    })
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/finance/fee-types", json={
        "name": "Duplicate Fee",
        "category": "tuition",
    })
    assert resp2.status_code == 400, f"Should reject duplicate fee type name: {resp2.text}"
