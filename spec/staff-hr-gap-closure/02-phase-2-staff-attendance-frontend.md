# Phase 2: Staff Attendance Frontend

**Duration:** 2-3 days
**Prerequisites:** None (backend already exists, can run in parallel with Phase 1)
**Migrations:** None
**New Tables:** 0
**New Endpoints:** 0
**Tests:** ~8

---

## 1. Overview

The staff attendance backend is fully implemented — endpoints exist for marking, bulk marking, summaries, listing, and deletion. However, there is **no frontend UI** for staff attendance. The existing attendance pages only handle student attendance. This phase builds the frontend.

---

## 2. Existing Backend Endpoints (Already Working)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/attendance/staff` | Mark single staff attendance |
| `POST` | `/attendance/staff/bulk` | Bulk mark staff attendance |
| `GET` | `/attendance/staff/{staff_id}/summary` | Get staff attendance summary |
| `GET` | `/attendance/staff` | List staff attendance records (paginated, filterable) |
| `DELETE` | `/attendance/staff/{attendance_id}` | Delete staff attendance record |

### Existing Server Actions (Already Working)

Verify these exist in `frontend/actions/attendance.action.ts`:

```typescript
// These should already exist — verify and add if missing:
export async function markStaffAttendance(data: MarkStaffAttendance): Promise<ActionResult<StaffAttendance>>
export async function bulkMarkStaffAttendance(data: BulkMarkStaffAttendance): Promise<ActionResult<BulkResult>>
export async function getStaffAttendanceSummary(staffId: string, params?: AttendanceParams): Promise<ActionResult<AttendanceSummary>>
export async function listStaffAttendance(params?: StaffAttendanceListParams): Promise<ActionResult<PaginatedResult<StaffAttendance>>>
export async function deleteStaffAttendance(id: string): Promise<ActionResult<void>>
```

If any are missing, add them following the existing student attendance action patterns.

---

## 3. Task Breakdown

### Task 2.1: Staff Attendance Overview Page

**File:** `frontend/app/(dashboard)/attendance/staff/page.tsx` (NEW)

Server Component that:
1. Fetches today's staff attendance summary
2. Displays 4 stats cards: Total Staff, Present Today, Absent Today, Late Today
3. Links to "Mark Attendance" and "Reports" sub-pages
4. Shows a quick table of today's absent/late staff (if any)

```tsx
// Layout:
// ┌─────────────────────────────────────────────────────┐
// │ Staff Attendance                [Mark] [Reports]     │
// ├──────────┬──────────┬──────────┬──────────┐         │
// │ Total    │ Present  │ Absent   │ Late     │         │
// │ 45       │ 40       │ 3        │ 2        │         │
// └──────────┴──────────┴──────────┴──────────┘         │
// │                                                      │
// │ Today's Absent/Late Staff                            │
// │ ┌────────────────────────────────────────────┐      │
// │ │ Name         │ Status  │ Remarks           │      │
// │ │ John Doe     │ Absent  │ Called in sick     │      │
// │ │ Jane Smith   │ Late    │ Traffic delay      │      │
// │ └────────────────────────────────────────────┘      │
// └─────────────────────────────────────────────────────┘
```

### Task 2.2: Staff Attendance Marking Page

**File:** `frontend/app/(dashboard)/attendance/staff/mark/page.tsx` (NEW)

Server Component wrapper that renders the client component.

### Task 2.3: Staff Attendance Marking Component

**File:** `frontend/components/attendance/staff-attendance-marking.tsx` (NEW)

Client Component — the main marking interface:

**UI Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Mark Staff Attendance                                    │
│                                                          │
│ Date: [Date Picker - defaults to today]                  │
│                                                          │
│ Filter: [Department ▼]  [Staff Type ▼]  [Search...]     │
│                                                          │
│ Quick Actions: [Mark All Present] [Mark All Absent]      │
│                                                          │
│ ┌────────────────────────────────────────────────────┐  │
│ │ □ │ Photo │ Name           │ Status  ▼ │ Remarks  │  │
│ │ ☑ │ 👤    │ John Doe       │ Present   │          │  │
│ │ ☑ │ 👤    │ Jane Smith     │ Late      │ Traffic  │  │
│ │ ☑ │ 👤    │ Bob Johnson    │ Absent    │ Sick     │  │
│ │ ☑ │ 👤    │ Alice Brown    │ Excused   │ Leave    │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ Selected: 42 staff    [Save Attendance]                  │
└─────────────────────────────────────────────────────────┘
```

**Implementation details:**

1. **Date picker** — defaults to today, allows selecting past dates for correction
2. **Staff list** — fetch all active staff via `getStaff({status: 'active'})` or a dedicated bulk attendance endpoint
3. **Pre-populate** — if attendance already marked for selected date, pre-fill statuses
4. **Status selector per staff** — dropdown with: Present, Absent, Late, Excused, Sick
5. **Remarks field** — optional text input per staff member
6. **Quick actions** — "Mark All Present" sets all to present; "Mark All Absent" sets all
7. **Department filter** — filter staff list by department
8. **Staff type filter** — teaching, non_teaching, administrative
9. **Search** — filter by name
10. **Submit** — calls `bulkMarkStaffAttendance()` with all entries
11. **Success feedback** — toast notification with count marked
12. **Mobile responsive** — on mobile, each staff member renders as a card instead of a table row

**State management:**
```typescript
interface StaffAttendanceEntry {
  staff_id: string
  staff_name: string
  department?: string
  staff_type: string
  photo_url?: string
  status: "present" | "absent" | "late" | "excused" | "sick"
  remarks: string
  check_in_time?: string
  check_out_time?: string
}

const [entries, setEntries] = useState<StaffAttendanceEntry[]>([])
const [date, setDate] = useState<Date>(new Date())
const [isSubmitting, setIsSubmitting] = useState(false)
```

### Task 2.4: Staff Attendance Reports Page

**File:** `frontend/app/(dashboard)/attendance/staff/reports/page.tsx` (NEW)

Server Component wrapper.

### Task 2.5: Staff Attendance Reports Component

**File:** `frontend/components/attendance/staff-attendance-reports.tsx` (NEW)

Client Component with multiple report views:

**UI Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Staff Attendance Reports                                 │
│                                                          │
│ Date Range: [From] - [To]  Department: [All ▼]          │
│                                                          │
│ ┌──── Overview ──────────────────────────────────────┐  │
│ │ Attendance Rate: 94.2%                              │  │
│ │ ┌──────────────────────────────────────────────┐   │  │
│ │ │ [Bar Chart: Daily attendance rate over range] │   │  │
│ │ └──────────────────────────────────────────────┘   │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌──── By Department ─────────────────────────────────┐  │
│ │ Department    │ Present % │ Absent % │ Late %       │  │
│ │ Mathematics   │ 96%       │ 2%       │ 2%           │  │
│ │ English       │ 92%       │ 5%       │ 3%           │  │
│ │ Admin         │ 98%       │ 1%       │ 1%           │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ ┌──── Individual Staff ──────────────────────────────┐  │
│ │ Staff Name     │ Days │ Present │ Absent │ Rate     │  │
│ │ John Doe       │ 22   │ 21      │ 1      │ 95.5%   │  │
│ │ Jane Smith     │ 22   │ 20      │ 2      │ 90.9%   │  │
│ └────────────────────────────────────────────────────┘  │
│                                                          │
│ [Export CSV]                                             │
└─────────────────────────────────────────────────────────┘
```

**Components used:**
- **Recharts** — `BarChart` for daily attendance rate, `PieChart` for status breakdown
- **TanStack Table** — for individual staff attendance data table (sortable, paginated)
- **Date range picker** — using existing date picker component
- **Department filter** — dropdown from `getDepartments()` action

**Data fetching:**
- Use `listStaffAttendance()` with date range and department filters
- Calculate aggregations client-side for small datasets, or add a backend summary endpoint if needed

### Task 2.6: Update Sidebar Navigation

**File:** `frontend/components/dashboard/app-sidebar.tsx`

Add "Staff Attendance" sub-item under the existing Attendance section:

```tsx
// Under the Attendance menu items, add:
{
  title: "Staff Attendance",
  url: "/attendance/staff",
  icon: Users,  // or UserCheck
  permission: "attendance.read",  // or "attendance.mark"
}
```

Ensure the sub-navigation includes:
- Mark Attendance → `/attendance/staff/mark`
- Reports → `/attendance/staff/reports`

### Task 2.7: Server Actions Verification

**File:** `frontend/actions/attendance.action.ts`

Verify and add if missing:

```typescript
export async function getStaffForAttendance(
  date: string,
  department_id?: string,
  staff_type?: string,
): Promise<ActionResult<StaffAttendanceEntry[]>> {
  // GET /attendance/staff?date={date}&department_id={department_id}
  // Returns staff list with their attendance status for the given date
  // If no attendance marked yet, returns staff with no status
}

export async function getStaffAttendanceReport(params: {
  start_date: string
  end_date: string
  department_id?: string
  staff_type?: string
}): Promise<ActionResult<StaffAttendanceReportData>> {
  // GET /attendance/reports/daily?type=staff&start_date=...&end_date=...
  // Returns aggregated report data
}
```

### Task 2.8: TypeScript Types

**File:** `frontend/types/index.ts` (verify existing types, add if missing)

```typescript
export interface StaffAttendanceEntry {
  id?: string
  staff_id: string
  staff_name: string
  staff_code: string
  department?: string
  staff_type: string
  photo_url?: string
  status: "present" | "absent" | "late" | "excused" | "sick"
  remarks?: string
  check_in_time?: string
  check_out_time?: string
  date: string
}

export interface StaffAttendanceReportData {
  total_staff: number
  date_range: { start: string; end: string }
  overall_rate: number
  daily_breakdown: Array<{
    date: string
    present: number
    absent: number
    late: number
    excused: number
    sick: number
    rate: number
  }>
  by_department: Array<{
    department: string
    total: number
    present_rate: number
    absent_rate: number
    late_rate: number
  }>
  by_staff: Array<{
    staff_id: string
    staff_name: string
    department?: string
    total_days: number
    present: number
    absent: number
    late: number
    rate: number
  }>
}
```

### Task 2.9: Mobile Responsiveness

Apply existing responsive patterns:
- Table columns: `hidden sm:table-cell` for department, remarks
- Mobile card view for the marking interface (stack name + status vertically)
- Collapsible filters on mobile
- Full-screen dialogs on mobile via `max-sm:` prefix

### Task 2.10: Tests

**File:** `backend/tests/test_staff_attendance_frontend.py` (~8 tests)

These are integration tests that verify the frontend <-> backend contract:

```python
# test_mark_single_staff_attendance_returns_correct_response
# test_bulk_mark_staff_attendance_all_present
# test_bulk_mark_staff_attendance_mixed_statuses
# test_list_staff_attendance_with_date_filter
# test_list_staff_attendance_with_department_filter
# test_get_staff_attendance_summary_returns_correct_counts
# test_staff_attendance_report_daily_breakdown
# test_delete_staff_attendance_record
```

---

## 4. Acceptance Criteria

- [ ] Staff attendance marking page loads all active staff with department grouping
- [ ] Date picker defaults to today and allows past date selection
- [ ] "Mark All Present" quick action works correctly
- [ ] Individual status selection works for all 5 statuses (present, absent, late, excused, sick)
- [ ] Remarks can be entered per staff member
- [ ] Bulk save submits all entries and shows success toast
- [ ] If attendance already marked for a date, pre-populates the form
- [ ] Department and staff type filters work correctly
- [ ] Reports page shows daily attendance chart (Recharts BarChart)
- [ ] Reports page shows department breakdown table
- [ ] Reports page shows individual staff attendance table (sortable, paginated)
- [ ] Date range filter works on reports
- [ ] "Staff Attendance" appears in sidebar under Attendance section
- [ ] Mobile responsive: cards on marking page, collapsible filters on reports
- [ ] All 8 tests pass
