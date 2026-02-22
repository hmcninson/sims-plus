"""
E2E tests for the complete academic cycle.

Tests the full flow: academic year -> term -> class -> section -> subject -> student enrollment.
"""

import pytest


@pytest.mark.asyncio
async def test_complete_academic_setup(auth_client, seeded_tenant):
    """Academic year -> term -> class -> section -> subject -- full happy path."""
    client = auth_client

    # 1. Create academic year
    ay_resp = await client.post("/api/v1/academic/academic-years", json={
        "name": "2025/2026",
        "start_date": "2025-09-01",
        "end_date": "2026-07-31",
        "is_current": True,
    })
    assert ay_resp.status_code == 201, f"Academic year creation failed: {ay_resp.text}"
    ay_data = ay_resp.json()
    assert ay_data["name"] == "2025/2026"
    assert ay_data["is_current"] is True
    ay_id = ay_data["id"]

    # 2. Create term within academic year
    term_resp = await client.post("/api/v1/academic/terms", json={
        "academic_year_id": ay_id,
        "name": "First Term",
        "start_date": "2025-09-01",
        "end_date": "2025-12-20",
        "sequence": 1,
    })
    assert term_resp.status_code == 201, f"Term creation failed: {term_resp.text}"
    assert term_resp.json()["name"] == "First Term"

    # 3. Create class
    class_resp = await client.post("/api/v1/academic/classes", json={
        "name": "Primary 1",
        "level": "primary",
        "sequence": 1,
    })
    assert class_resp.status_code == 201, f"Class creation failed: {class_resp.text}"
    class_data = class_resp.json()
    assert class_data["name"] == "Primary 1"
    class_id = class_data["id"]

    # 4. Create section within class
    section_resp = await client.post("/api/v1/academic/sections", json={
        "class_id": class_id,
        "name": "A",
    })
    assert section_resp.status_code == 201, f"Section creation failed: {section_resp.text}"
    assert section_resp.json()["name"] == "A"

    # 5. Create subject
    subject_resp = await client.post("/api/v1/academic/subjects", json={
        "name": "Mathematics",
        "code": "MATH",
        "category": "core",
    })
    assert subject_resp.status_code == 201, f"Subject creation failed: {subject_resp.text}"
    assert subject_resp.json()["code"] == "MATH"

    # 6. Verify list endpoints return created data
    years_resp = await client.get("/api/v1/academic/academic-years")
    assert years_resp.status_code == 200
    year_names = [y["name"] for y in years_resp.json()]
    assert "2025/2026" in year_names

    classes_resp = await client.get("/api/v1/academic/classes")
    assert classes_resp.status_code == 200


@pytest.mark.asyncio
async def test_student_enrollment_and_list(auth_client, seeded_tenant):
    """Create a class + section, enroll a student, verify student appears in list."""
    client = auth_client

    # Create class
    class_resp = await client.post("/api/v1/academic/classes", json={
        "name": "Class 2",
        "level": "primary",
        "sequence": 2,
    })
    assert class_resp.status_code == 201
    class_id = class_resp.json()["id"]

    # Create section
    section_resp = await client.post("/api/v1/academic/sections", json={
        "class_id": class_id,
        "name": "A",
    })
    assert section_resp.status_code == 201
    section_id = section_resp.json()["id"]

    # Create student enrolled in that class + section
    student_resp = await client.post("/api/v1/students", json={
        "first_name": "Ama",
        "last_name": "Serwaa",
        "date_of_birth": "2016-06-10",
        "gender": "female",
        "class_id": class_id,
        "section_id": section_id,
    })
    assert student_resp.status_code == 201, f"Student creation failed: {student_resp.text}"
    student_data = student_resp.json()
    assert student_data["first_name"] == "Ama"
    assert student_data["last_name"] == "Serwaa"
    student_id = student_data["id"]

    # Verify student appears in list
    list_resp = await client.get("/api/v1/students", params={
        "class_id": class_id,
        "page": 1,
        "page_size": 50,
    })
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    found_ids = [s["id"] for s in list_data["items"]]
    assert student_id in found_ids


@pytest.mark.asyncio
async def test_academic_year_validation(auth_client, seeded_tenant):
    """End date before start date should fail."""
    resp = await auth_client.post("/api/v1/academic/academic-years", json={
        "name": "Bad Year",
        "start_date": "2026-09-01",
        "end_date": "2025-07-31",  # Before start
    })
    assert resp.status_code == 422, "End date before start date should be rejected"


@pytest.mark.asyncio
async def test_unauthenticated_academic_rejected(unauth_client):
    """Academic endpoints should reject unauthenticated requests."""
    resp = await unauth_client.get("/api/v1/academic/academic-years")
    # Without subdomain header, middleware returns 400; with it but no auth, 401
    assert resp.status_code in (400, 401)
