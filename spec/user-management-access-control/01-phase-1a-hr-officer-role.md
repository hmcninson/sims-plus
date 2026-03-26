# Phase 1A: HR Officer Role

**Complexity:** Small
**Requirements:** Section 4.1 (Role definitions)
**Dependencies:** None
**Estimated effort:** 0.5 days

---

## Summary

Add the missing HR Officer role to the `UserRole` enum, define its permissions, and update the frontend role configuration. This is a low-risk, additive change.

---

## Task 1: Add HR_OFFICER Enum Value

### File: `backend/app/models/user.py`

**Current enum (around line 25-37):**
```python
class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
    APPLICANT = "applicant"
```

**Add after FINANCE_OFFICER:**
```python
    HR_OFFICER = "hr_officer"
```

**Result:**
```python
class UserRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    CHAIN_ADMIN = "chain_admin"
    SCHOOL_ADMIN = "school_admin"
    ACADEMIC_HEAD = "academic_head"
    FINANCE_OFFICER = "finance_officer"
    HR_OFFICER = "hr_officer"          # NEW
    TEACHER = "teacher"
    HOUSE_PARENT = "house_parent"
    PARENT = "parent"
    STUDENT = "student"
    APPLICANT = "applicant"
```

---

## Task 2: Add HR Officer Permissions

### File: `backend/app/services/auth.py`

**Add to ROLE_PERMISSIONS dict (after the finance_officer entry):**

```python
"hr_officer": [
    "staff.*",
    "students.read",
    "attendance.read",
    "reports.hr",
    "users.read",
    "boarding.read",
],
```

**Permission rationale:**

| Permission | Why |
|------------|-----|
| `staff.*` | Full staff management (CRUD, departments, employment details) |
| `students.read` | Cross-reference student-staff relationships (e.g., class assignments) |
| `attendance.read` | View staff attendance data for HR reporting |
| `reports.hr` | Generate HR-specific reports |
| `users.read` | View user accounts (needed for staff onboarding context) |
| `boarding.read` | View boarding staff assignments (residential schools) |

---

## Task 3: Add HR Officer to Frontend Role Config

### File: `frontend/app/(dashboard)/settings/users/users-management.tsx`

**Find the ROLE_CONFIG object and add:**

```typescript
hr_officer: {
    label: "HR Officer",
    color: "bg-teal-500",
    description: "Staff management, attendance, HR reports",
},
```

Place it after the `finance_officer` entry to maintain alphabetical/hierarchy ordering.

---

## Task 4: Update TypeScript UserRole Type

### File: Search for where `UserRole` type/union is defined

Likely in `frontend/types/index.ts` or a similar types file.

**Add `"hr_officer"` to the UserRole union type.**

If the type is:
```typescript
type UserRole = "platform_admin" | "chain_admin" | "school_admin" | ...
```

Add `| "hr_officer"` in the appropriate position.

---

## Task 5: Update Sidebar Navigation (if role-specific)

### File: `frontend/components/dashboard/app-sidebar.tsx`

Check if the sidebar has role-specific navigation items. If so, ensure `hr_officer` has access to:
- Staff section
- Attendance (read-only view)
- Reports (HR reports)

Follow the existing pattern for how other roles like `finance_officer` are handled in the sidebar visibility logic.

---

## Task 6: Update Exhaustive Role Lists

Search the codebase for any arrays or lists that enumerate all roles and need updating:

```bash
# Search patterns:
grep -rn "platform_admin.*chain_admin.*school_admin" frontend/
grep -rn "STAFF_ROLES\|staffRoles\|ROLE_OPTIONS" frontend/
grep -rn "finance_officer.*teacher" backend/
```

Common locations to check:
- User creation form role dropdowns (ensure hr_officer appears as an option)
- Role filter dropdowns on user list page
- Any role-to-label mapping objects
- Test files that enumerate roles

---

## Task 7: Database Migration (Part of Combined Migration)

The enum addition will be in the combined migration file (see `07-migration-plan.md`):

```sql
ALTER TYPE userrole ADD VALUE 'hr_officer';
```

**Note:** PostgreSQL enum value additions are irreversible but backward-compatible. This is the same pattern used when `applicant` was added.

---

## Verification Checklist

- [ ] `UserRole.HR_OFFICER` is accessible in Python code
- [ ] `ROLE_PERMISSIONS["hr_officer"]` returns the correct permission list
- [ ] HR Officer appears in the user creation role dropdown (frontend)
- [ ] HR Officer appears with correct color badge in user list (frontend)
- [ ] HR Officer can access staff endpoints but NOT finance/exam endpoints
- [ ] JWT token for HR Officer contains correct permissions
- [ ] HR Officer role appears in role statistics on user management page
