# Phase 1: Testing

**Sprint:** 20.5
**Depends on:** Phase 1 Models, Schemas & Endpoints (docs 01–02)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 4.1 | Incident CRUD tests | `backend/tests/test_preschool_incidents.py` | 0.3d |
| 4.2 | Pickup authorization tests | `backend/tests/test_preschool_pickups.py` | 0.3d |
| 4.3 | Allergy alert tests | `backend/tests/test_preschool_allergy_alerts.py` | 0.15d |
| 4.4 | Session-based fee tests | `backend/tests/test_preschool_session_fees.py` | 0.15d |
| 4.5 | RLS isolation tests | `backend/tests/test_preschool_phase1_rls.py` | 0.2d |

---

## Test Infrastructure

All tests follow the existing two-engine pattern from `conftest.py`:
- **admin_session:** Superuser for DDL and raw SQL seeding (bypasses RLS)
- **app_session:** Non-superuser `sims_app_user` with RLS enforced

### Common Seed Helper

All Phase 1 test files should use a shared seed helper:

```python
async def _seed_preschool_phase1_env(admin_session):
    """
    Seed a complete test environment for Phase 1 preschool tests.

    Creates: tenant, school, academic_year, term, class (KG1), 2 students,
    1 user (teacher), 2 guardians linked to student 1.

    Returns dict with all created IDs.
    """
    tenant_id = uuid.uuid4()
    school_id = uuid.uuid4()
    year_id = uuid.uuid4()
    term_id = uuid.uuid4()
    class_id = uuid.uuid4()
    student_1_id = uuid.uuid4()
    student_2_id = uuid.uuid4()
    user_id = uuid.uuid4()
    guardian_1_id = uuid.uuid4()
    guardian_2_id = uuid.uuid4()

    # Insert tenant (all NOT NULL columns required)
    await admin_session.execute(text("""
        INSERT INTO tenants (id, subdomain, slug, name, tenant_type, subscription_tier, status, max_students, max_staff)
        VALUES (CAST(:id AS uuid), :subdomain, :slug, :name, 'single_school', 'professional', 'active', 300, 50)
    """), {"id": str(tenant_id), "subdomain": "testpreschool", "slug": "testpreschool", "name": "Test Preschool"})

    # Insert school
    await admin_session.execute(text("""
        INSERT INTO schools (id, tenant_id, name, slug, school_type, status)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), 'Test Preschool School', 'test-preschool', 'preschool', 'active')
    """), {"id": str(school_id), "tid": str(tenant_id)})

    # ... (academic_year, term, class with level='kg_1', students, user, guardians, student_guardians)
    # Follow exact pattern from existing test_preschool.py

    return {
        "tenant_id": tenant_id,
        "school_id": school_id,
        "year_id": year_id,
        "term_id": term_id,
        "class_id": class_id,
        "student_1_id": student_1_id,
        "student_2_id": student_2_id,
        "user_id": user_id,
        "guardian_1_id": guardian_1_id,
        "guardian_2_id": guardian_2_id,
    }
```

**Important raw SQL conventions:**
- Always `CAST(:param AS uuid)` for UUID bind params
- All enum values MUST be **lowercase** (e.g., `'active'` not `'ACTIVE'`)
- Include ALL NOT NULL columns (especially `email_verified`, `mfa_enabled`, `failed_login_attempts`, `timezone` for users)
- Set tenant context: `SELECT set_config('app.current_tenant_id', :tid, true)` before app_session queries

---

## 4.1 Incident CRUD Tests

**File:** `backend/tests/test_preschool_incidents.py`

### Test Cases

```python
class TestPreschoolIncidents:
    """Test incident CRUD and workflow."""

    async def test_create_incident_success(self, app_session, env):
        """Create a basic incident report."""
        # Set tenant context
        # Call service.create_incident(...)
        # Assert: incident created with status='reported'
        # Assert: reported_by set correctly
        # Assert: school_id auto-set from student

    async def test_create_incident_student_not_found(self, app_session, env):
        """Verify error when student_id doesn't belong to tenant."""
        # Use random UUID for student_id
        # Assert: raises PreschoolServiceError with STUDENT_NOT_FOUND

    async def test_list_incidents_filter_by_student(self, app_session, env):
        """List incidents filtered by student_id."""
        # Create 2 incidents for student_1, 1 for student_2
        # Filter by student_1 → assert 2 results
        # Filter by student_2 → assert 1 result

    async def test_list_incidents_filter_by_status(self, app_session, env):
        """List incidents filtered by status."""
        # Create incident, then transition to 'reviewed'
        # Filter by status='reported' → 0 results
        # Filter by status='reviewed' → 1 result

    async def test_list_incidents_filter_by_severity(self, app_session, env):
        """List incidents filtered by severity."""

    async def test_list_incidents_filter_by_date_range(self, app_session, env):
        """List incidents filtered by date range."""

    async def test_update_incident(self, app_session, env):
        """Update incident description and action_taken."""
        # Create incident
        # Update with new description + action_taken
        # Assert: fields updated, status unchanged

    async def test_notify_parent_from_reported(self, app_session, env):
        """Transition from reported → parent_notified."""
        # Create incident (status=reported)
        # Call service.notify_parent_incident(...)
        # Assert: status='parent_notified', parent_notified_at set, parent_notified_by set

    async def test_notify_parent_from_reviewed(self, app_session, env):
        """Transition from reviewed → parent_notified."""

    async def test_resolve_from_parent_notified(self, app_session, env):
        """Transition from parent_notified → resolved."""
        # Assert: status='resolved', resolved_at set, resolved_by set, follow_up_notes saved

    async def test_resolve_from_reported_minor(self, app_session, env):
        """Minor incidents can be resolved directly without parent notification."""
        # Create minor incident → resolve directly
        # Assert: valid transition (reported → resolved)

    async def test_invalid_transition_rejected(self, app_session, env):
        """Cannot transition from resolved to any other state."""
        # Create → resolve
        # Attempt to notify parent → assert INVALID_TRANSITION error

    async def test_incident_soft_delete(self, app_session, env):
        """Deleted incidents are not returned in list queries."""
        # Create incident
        # Soft-delete (set deleted_at)
        # List → assert 0 results

    async def test_incident_attachments(self, app_session, env):
        """Incident with photo attachments."""
        # Create incident with attachments JSONB
        # Get incident → verify attachments returned correctly
```

---

## 4.2 Pickup Authorization Tests

**File:** `backend/tests/test_preschool_pickups.py`

### Test Cases

```python
class TestAuthorizedPickups:
    """Test authorized pickup person management."""

    async def test_add_authorized_pickup(self, app_session, env):
        """Add an authorized pickup person for a student."""
        # Assert: created with is_active=True, student_id correct

    async def test_add_duplicate_phone_rejected(self, app_session, env):
        """Cannot add same phone number for same student twice."""
        # Add person with phone X
        # Add another person with phone X for same student
        # Assert: unique constraint violation

    async def test_list_authorized_pickups(self, app_session, env):
        """List all authorized pickup persons for a student."""
        # Add 3 persons
        # List → assert 3 results

    async def test_update_authorized_pickup(self, app_session, env):
        """Update name and phone of authorized person."""

    async def test_deactivate_authorized_pickup(self, app_session, env):
        """Soft-delete an authorized person."""
        # Deactivate → list → assert not returned

    async def test_student_not_found(self, app_session, env):
        """Error when student doesn't belong to tenant."""


class TestPickupLogs:
    """Test pickup log recording and validation."""

    async def test_record_pickup_by_guardian_with_can_pickup(self, app_session, env):
        """Record pickup by a guardian who has can_pickup=True."""
        # Assert: log created, pickup_date set to today (server-side)

    async def test_reject_pickup_by_guardian_without_can_pickup(self, app_session, env):
        """Reject pickup by guardian with can_pickup=False."""
        # Set guardian's can_pickup to False
        # Attempt record_pickup → assert GUARDIAN_PICKUP_NOT_AUTHORIZED

    async def test_reject_pickup_by_unlinked_guardian(self, app_session, env):
        """Reject pickup by guardian not linked to student."""
        # Use guardian_2 who is linked to a different student
        # Assert: GUARDIAN_NOT_LINKED

    async def test_record_pickup_by_authorized_person(self, app_session, env):
        """Record pickup by an active authorized person."""
        # Add authorized person → record pickup
        # Assert: log created with picked_up_by_type='authorized_person'

    async def test_reject_pickup_by_inactive_authorized_person(self, app_session, env):
        """Reject pickup by deactivated authorized person."""
        # Add person → deactivate → attempt pickup
        # Assert: AUTHORIZED_PICKUP_NOT_FOUND

    async def test_list_pickup_logs_by_student(self, app_session, env):
        """List pickup logs filtered by student."""

    async def test_list_pickup_logs_by_date_range(self, app_session, env):
        """List pickup logs filtered by date range."""

    async def test_pickup_date_set_server_side(self, app_session, env):
        """Verify pickup_date is always today, not client-provided."""
        # Record pickup → assert pickup_date == date.today()
```

---

## 4.3 Allergy Alert Tests

**File:** `backend/tests/test_preschool_allergy_alerts.py`

### Test Cases

```python
class TestAllergyAlerts:
    """Test dietary requirements and allergy alert system."""

    async def test_update_dietary_requirements(self, app_session, env):
        """Set structured dietary requirements for a student."""
        # Update with allergies + dietary_restrictions + notes
        # Get → verify all fields returned correctly

    async def test_clear_dietary_requirements(self, app_session, env):
        """Clear dietary requirements by setting to None."""
        # Set data → clear to None → get → verify None

    async def test_get_class_allergy_alerts(self, app_session, env):
        """Get allergy alerts for a class."""
        # Set allergies for student_1 (peanuts, dairy)
        # Set no allergies for student_2
        # Get alerts for class → assert 1 result with correct data

    async def test_class_allergy_alerts_empty(self, app_session, env):
        """Empty list when no students have allergies."""
        # Get alerts for class → assert 0 results

    async def test_dietary_restrictions_only(self, app_session, env):
        """Student with dietary restrictions but no allergies still shows in alerts."""
        # Set dietary_restrictions=['vegetarian'] with no allergies
        # Get alerts → assert 1 result

    async def test_student_not_found(self, app_session, env):
        """Error when student doesn't belong to tenant."""
```

---

## 4.4 Session-Based Fee Tests

**File:** `backend/tests/test_preschool_session_fees.py`

### Test Cases

```python
class TestSessionFees:
    """Test session-based fee structure filtering."""

    async def test_fee_structure_with_session_type(self, admin_session, env):
        """Create fee structure with session_type='half_day_morning'."""
        # Insert fee_structure with session_type via raw SQL
        # Verify it's stored correctly

    async def test_fee_structure_null_session_applies_to_all(self, admin_session, env):
        """Fee structure with NULL session_type applies to all students."""
        # Insert fee_structure with session_type=NULL
        # Assert: matches both half-day and full-day students

    async def test_student_enrollment_session_set(self, app_session, env):
        """Set enrollment_session on a preschool student."""
        # Update student with enrollment_session='full_day'
        # Verify stored correctly

    async def test_enrollment_session_null_for_non_preschool(self, app_session, env):
        """enrollment_session remains NULL for non-preschool students."""
```

---

## 4.5 RLS Isolation Tests

**File:** `backend/tests/test_preschool_phase1_rls.py`

### Test Cases

```python
class TestPreschoolPhase1RLS:
    """Verify RLS isolation for Phase 1 preschool tables."""

    async def test_incident_tenant_isolation(self, admin_session, app_session):
        """Incidents from tenant A are invisible to tenant B."""
        # Create tenant A and tenant B with seeded data
        # Insert incident via admin_session for tenant A
        # Set app_session context to tenant B
        # Query preschool_incidents → assert 0 results

    async def test_authorized_pickup_tenant_isolation(self, admin_session, app_session):
        """Authorized pickups from tenant A are invisible to tenant B."""
        # Same pattern as above

    async def test_pickup_log_tenant_isolation(self, admin_session, app_session):
        """Pickup logs from tenant A are invisible to tenant B."""
        # Same pattern as above

    async def test_cross_tenant_incident_insert_blocked(self, admin_session, app_session):
        """Cannot insert an incident for a different tenant's student."""
        # Set app_session context to tenant A
        # Attempt to INSERT into preschool_incidents with tenant_id = tenant B
        # Assert: RLS WITH CHECK violation

    async def test_dietary_requirements_via_students_rls(self, admin_session, app_session):
        """dietary_requirements on students table inherits existing students RLS."""
        # Students table already has RLS — verify dietary data is isolated
```

**Pattern for RLS tests** (follow existing `test_admissions_rls.py`):

```python
async def test_incident_tenant_isolation(self, admin_session, app_session):
    tenant_a_id = uuid.uuid4()
    tenant_b_id = uuid.uuid4()

    # Seed both tenants via admin_session (bypasses RLS)
    # ...

    # Insert incident for tenant A
    await admin_session.execute(text("""
        INSERT INTO preschool_incidents (id, tenant_id, student_id, incident_type, severity, status, incident_date, description)
        VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), CAST(:sid AS uuid), 'accident', 'minor', 'reported', '2026-03-28', 'Test incident')
    """), {"id": str(uuid.uuid4()), "tid": str(tenant_a_id), "sid": str(student_a_id)})
    await admin_session.commit()

    # Set context to tenant B
    await app_session.execute(text(
        "SELECT set_config('app.current_tenant_id', :tid, true)"
    ), {"tid": str(tenant_b_id)})

    # Query — should return 0 rows
    result = await app_session.execute(text("SELECT COUNT(*) FROM preschool_incidents"))
    count = result.scalar()
    assert count == 0, f"Expected 0 incidents for tenant B, got {count}"
```

---

## Test Run Command

```bash
# Run all Phase 1 preschool tests
pytest backend/tests/test_preschool_incidents.py \
       backend/tests/test_preschool_pickups.py \
       backend/tests/test_preschool_allergy_alerts.py \
       backend/tests/test_preschool_session_fees.py \
       backend/tests/test_preschool_phase1_rls.py \
       -v --tb=short

# Run with coverage
pytest backend/tests/test_preschool_incidents.py \
       backend/tests/test_preschool_pickups.py \
       backend/tests/test_preschool_allergy_alerts.py \
       backend/tests/test_preschool_session_fees.py \
       backend/tests/test_preschool_phase1_rls.py \
       --cov=app.services.preschool --cov=app.api.v1.endpoints.preschool \
       --cov-report=term-missing
```

---

## Expected Test Count

| File | Tests | Focus |
|------|-------|-------|
| `test_preschool_incidents.py` | 13 | Incident CRUD + workflow transitions |
| `test_preschool_pickups.py` | 12 | Authorized pickups + pickup log validation |
| `test_preschool_allergy_alerts.py` | 6 | Dietary requirements + class alerts |
| `test_preschool_session_fees.py` | 4 | Session-based fee structures |
| `test_preschool_phase1_rls.py` | 5 | Tenant isolation verification |
| **Total** | **40** | |
