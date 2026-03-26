# Phase 2: Frontend — Admin Dashboard

**Sprint:** 21-22 (parallel with backend exams/decisions/promotion services)
**Agent:** 6 (UI Agent)
**Depends on:** Backend admin endpoints (Agent 3), public frontend (Agent 4)
**Produces:** Admin dashboard pages, application management UI, sidebar navigation update

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 6.1 | Update sidebar navigation | `frontend/components/dashboard/app-sidebar.tsx` | 0.25d |
| 6.2 | Create admissions dashboard page | `frontend/app/(dashboard)/admissions/page.tsx` | 1.5d |
| 6.3 | Create admission periods page | `frontend/app/(dashboard)/admissions/periods/page.tsx` | 1d |
| 6.4 | Create period detail page | `frontend/app/(dashboard)/admissions/periods/[id]/page.tsx` | 1d |
| 6.5 | Create application list page | `frontend/app/(dashboard)/admissions/applications/page.tsx` | 1.5d |
| 6.6 | Create application detail page | `frontend/app/(dashboard)/admissions/applications/[id]/page.tsx` | 2d |
| 6.7 | Create entrance exam pages | `frontend/app/(dashboard)/admissions/exams/` | 1d |
| 6.8 | Create decisions page | `frontend/app/(dashboard)/admissions/decisions/page.tsx` | 1d |
| 6.9 | Create enrollment page | `frontend/app/(dashboard)/admissions/enrollment/page.tsx` | 1d |
| 6.10 | Create class promotion page | `frontend/app/(dashboard)/admissions/promotions/page.tsx` | 1.5d |
| 6.10b | Create return intent page | `frontend/app/(dashboard)/admissions/return-intents/page.tsx` | 0.75d |
| 6.11 | Create shared components | `frontend/components/admissions/` | 1.5d |
| 6.12 | Replace students/enrollments placeholder | `frontend/app/(dashboard)/students/enrollments/page.tsx` | 0.1d |

---

## 6.1 Sidebar Navigation Update

**File to modify:** `frontend/components/dashboard/app-sidebar.tsx`

Add an "Enrollment" group to `navigationGroups` array. Insert it between "People" and "Academics" groups (after line ~140 in the current file).

### Import Addition

Add `UserPlus` icon to the lucide-react import:

```typescript
import {
  // ... existing imports ...
  UserPlus,       // ADD THIS
} from "lucide-react";
```

### New Navigation Group

Insert after the "People" group (after `{ label: "People", items: [...] }`):

```typescript
{
  label: "Enrollment",
  items: [
    {
      title: "Admissions",
      url: "/admissions",
      icon: UserPlus,
      subItems: [
        { title: "Dashboard", url: "/admissions" },
        { title: "Applications", url: "/admissions/applications" },
        { title: "Entrance Exams", url: "/admissions/exams" },
        { title: "Decisions", url: "/admissions/decisions" },
        { title: "Enrollment", url: "/admissions/enrollment" },
        { title: "Promotions", url: "/admissions/promotions" },
        { title: "Return Intents", url: "/admissions/return-intents" },
        { title: "Periods", url: "/admissions/periods" },
      ],
    },
  ],
},
```

---

## 6.2 Admissions Dashboard Page

**File:** `frontend/app/(dashboard)/admissions/page.tsx`

Server Component that renders pipeline stats, conversion funnel, and recent applications.

```tsx
/**
 * SIMS Plus - Admissions Dashboard
 *
 * Overview page with pipeline stats, funnel chart, and recent applications.
 */

import { getAdmissionsDashboard, getAdmissionsDemographics } from "@/actions/admissions.action";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PipelineChart } from "@/components/admissions/pipeline-chart";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { Users, CheckCircle, Clock, TrendingUp } from "lucide-react";
import Link from "next/link";

export default async function AdmissionsDashboardPage() {
  const [dashResult, demoResult] = await Promise.all([
    getAdmissionsDashboard(),
    getAdmissionsDemographics(),
  ]);

  if (!dashResult.success) {
    return <div className="p-6"><p className="text-muted-foreground">Failed to load dashboard.</p></div>;
  }

  const stats = dashResult.data;
  const demographics = demoResult.success ? demoResult.data : null;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Admissions Dashboard</h1>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Applications</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total_applications}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending Decisions</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending_decisions}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Awaiting Enrollment</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending_enrollment}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Conversion Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.conversion_rate ? `${(stats.conversion_rate * 100).toFixed(1)}%` : "—"}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pipeline Chart + Demographics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Application Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <PipelineChart data={stats.by_status} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>By Target Class</CardTitle>
          </CardHeader>
          <CardContent>
            {/* Bar chart or table showing applications by class */}
            <div className="space-y-2">
              {stats.by_class.map((item) => (
                <div key={item.class_name} className="flex justify-between items-center">
                  <span className="text-sm">{item.class_name}</span>
                  <span className="font-medium">{item.count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent Applications */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Applications</CardTitle>
          <Link href="/admissions/applications" className="text-sm text-primary underline">
            View All
          </Link>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {stats.recent_applications.map((app) => (
              <Link
                key={app.id}
                href={`/admissions/applications/${app.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-muted/50"
              >
                <div>
                  <span className="font-medium">
                    {app.applicant_first_name} {app.applicant_last_name}
                  </span>
                  <span className="text-sm text-muted-foreground ml-2">
                    {app.target_class_name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <ApplicationStatusBadge status={app.status} />
                  <span className="text-xs text-muted-foreground">
                    {new Date(app.created_at).toLocaleDateString("en-GB")}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 6.3 Admission Periods Page

**File:** `frontend/app/(dashboard)/admissions/periods/page.tsx`

Data table listing all admission periods with status, date range, and application count.

```tsx
/**
 * SIMS Plus - Admission Periods Management
 *
 * List, create, and manage admission periods.
 * Uses TanStack Table with status filter.
 */

// Server Component that fetches periods and renders DataTable
// Create/edit dialog using React Hook Form + Zod
// Status change dropdown (draft→open→closed→archived)
// Link to period detail page for form config editing

// IMPLEMENTATION NOTES:
// 1. Fetch periods via getAdmissionPeriods() Server Action
// 2. Render DataTable with columns: name, academic year, dates, status, app count, actions
// 3. "Create Period" button opens dialog with AdmissionPeriodCreate form
// 4. Status dropdown allows valid transitions (draft→open→closed→archived)
// 5. Row click navigates to /admissions/periods/[id] for detail + form config
```

---

## 6.4 Period Detail Page

**File:** `frontend/app/(dashboard)/admissions/periods/[id]/page.tsx`

Shows period details and includes the form configuration editor (JSON Schema builder).

```tsx
/**
 * SIMS Plus - Admission Period Detail
 *
 * Period info, statistics, and form configuration editor.
 *
 * IMPLEMENTATION NOTES:
 * 1. Top section: period info (name, dates, status, fee, exam required)
 * 2. Stats cards: total applications, by status breakdown
 * 3. Form Config section:
 *    - JSON Schema editor for custom fields
 *    - Required documents checklist
 *    - Save via updateFormConfig() action
 * 4. For MVP: form_schema is a JSON editor (textarea)
 *    For full: visual form builder with drag-and-drop fields
 * 5. Required documents: checkboxes for common types
 *    (birth_certificate, passport_photo, transcript, medical_report, etc.)
 */
```

---

## 6.5 Application List Page

**File:** `frontend/app/(dashboard)/admissions/applications/page.tsx`

The primary work surface for admissions staff. Full-featured data table with filters.

```tsx
/**
 * SIMS Plus - Application List
 *
 * Main admissions work surface. TanStack Table with:
 * - Status filter dropdown (14 statuses)
 * - Admission period filter
 * - Target class filter
 * - Search (name, tracking code)
 * - Sort by date, name, status
 * - Bulk selection for bulk actions
 *
 * IMPLEMENTATION NOTES:
 * 1. Fetch via getApplications() with query params
 * 2. Columns: tracking_code, name, class, status, submitted_at, actions
 * 3. CollapsibleFilters component (mobile-friendly)
 * 4. BulkDecisionToolbar appears when rows selected
 * 5. Row click → /admissions/applications/[id]
 * 6. Export to CSV button (client-side from current page data)
 *
 * Components used:
 * - ApplicationStatusBadge
 * - BulkDecisionToolbar (for selected rows)
 * - CollapsibleFilters
 */
```

---

## 6.6 Application Detail Page

**File:** `frontend/app/(dashboard)/admissions/applications/[id]/page.tsx`

Full application view with all related data and admin actions.

```tsx
/**
 * SIMS Plus - Application Detail
 *
 * Comprehensive view of a single application with all admin actions.
 *
 * Layout:
 * ┌──────────────────────────────────────────┐
 * │ Header: Name, Status Badge, Actions Menu │
 * ├────────────────────┬─────────────────────┤
 * │ Personal Info      │ Status Timeline     │
 * │ Guardian Info      │ Notes Section       │
 * │ Documents          │ Decision Info       │
 * │ Exam Results       │ Payment Info        │
 * │ Custom Fields      │                     │
 * └────────────────────┴─────────────────────┘
 *
 * Admin Actions (in dropdown or buttons):
 * - Change Status (dropdown with valid transitions)
 * - Waive Fee (dialog with reason)
 * - Waive Exam (dialog with reason)
 * - Add Note (inline form)
 * - Make Decision (dialog: accept/reject/waitlist/defer)
 * - Enroll (dialog with confirmation + section selection)
 *
 * IMPLEMENTATION NOTES:
 * 1. Fetch via getApplicationDetail(id)
 * 2. Left column: ApplicationDetailCard component
 * 3. Right column: status timeline, notes, decision
 * 4. DecisionDialog: select decision_type, offered_class, conditions, deadline
 * 5. EnrollDialog: confirm enrollment, optional section, generate invoice toggle
 * 6. Status change: dropdown filtered by VALID_TRANSITIONS from current status
 * 7. Document download: generate presigned URL on click
 *
 * Components used:
 * - ApplicationDetailCard
 * - ApplicationStatusBadge
 * - DecisionDialog
 * - Status timeline (vertical)
 */
```

---

## 6.7 Entrance Exam Pages

**Files:**
- `frontend/app/(dashboard)/admissions/exams/page.tsx` — List exam sessions
- `frontend/app/(dashboard)/admissions/exams/[id]/page.tsx` — Exam detail with registrations and results

```tsx
/**
 * EXAMS LIST PAGE
 *
 * Table of entrance exam sessions with:
 * - Period filter, status filter
 * - Columns: name, date, venue, capacity, registered/attended, status
 * - "Create Exam" button → dialog
 * - Row click → detail page
 */

/**
 * EXAM DETAIL PAGE
 *
 * Tab layout:
 * 1. Info tab: exam details (date, venue, capacity, instructions)
 * 2. Registrations tab: list of registered applicants with seat numbers
 *    - "Register Applicants" button: multi-select from shortlisted applicants
 *    - Mark attendance checkboxes
 * 3. Results tab: score entry table (ExamResultsTable component)
 *    - Columns: applicant name, score, max_score, grade, passed, remarks
 *    - Editable cells for score entry
 *    - "Save Results" button submits all at once
 *
 * Components used:
 * - ExamResultsTable (editable data table for score entry)
 */
```

---

## 6.8 Decisions Page

**File:** `frontend/app/(dashboard)/admissions/decisions/page.tsx`

```tsx
/**
 * SIMS Plus - Admission Decisions
 *
 * Bulk decision management page. Shows applications ready for decision.
 *
 * Layout:
 * 1. Filter: period, class, current status (shortlisted, exam_completed, waitlisted)
 * 2. Data table with checkboxes for bulk selection
 * 3. BulkDecisionToolbar at top when rows selected:
 *    - "Accept Selected" → dialog with offered_class, conditions, deadline
 *    - "Reject Selected" → confirmation dialog
 *    - "Waitlist Selected" → confirmation dialog
 * 4. Individual decision button per row
 * 5. Results: shows BulkDecisionResponse (succeeded/failed counts)
 *
 * Components used:
 * - BulkDecisionToolbar
 * - DecisionDialog
 * - ApplicationStatusBadge
 */
```

---

## 6.9 Enrollment Page

**File:** `frontend/app/(dashboard)/admissions/enrollment/page.tsx`

```tsx
/**
 * SIMS Plus - Enrollment Queue
 *
 * Shows accepted applicants ready for enrollment (conversion to students).
 *
 * Layout:
 * 1. Filter: period, class
 * 2. Table of accepted applicants (status = "accepted")
 *    Columns: name, class, guardian, decision date, actions
 * 3. "Enroll" button per row → confirmation dialog
 *    - Generate invoice toggle (default: true)
 *    - Optional section assignment dropdown
 * 4. Bulk enroll: checkbox selection + "Enroll Selected" toolbar
 * 5. Results display: shows EnrollResponse with student_id, invoice info
 * 6. BulkEnrollResponse handling: toast for succeeded, error list for failed
 *
 * After enrollment:
 * - Row moves to "enrolled" status
 * - Link to newly created student record
 */
```

---

## 6.10 Class Promotion Page

**File:** `frontend/app/(dashboard)/admissions/promotions/page.tsx`

```tsx
/**
 * SIMS Plus - Class Promotion Management
 *
 * End-of-year class promotion workflow. This is the primary tool
 * for Ghanaian academic year transitions.
 *
 * Layout:
 * 1. Promotion batches list (DataTable): name, source/target year, status, counts
 * 2. "Create Promotion Batch" button → dialog:
 *    - Name, source academic year, target academic year
 * 3. Batch detail view (separate page or expandable):
 *    - Summary cards: total, promoted, repeated, graduated, withdrawn
 *    - "Generate Preview" button (populates entries with defaults)
 *    - Student entries table (TanStack Table):
 *      - Columns: Student Name, Student #, Current Class, Action (dropdown), Target Class, Reason
 *      - Filter by: source class, action type
 *      - Inline editing: action dropdown (promote/repeat/graduate/withdraw), target class, reason
 *    - Bulk action toolbar: "Set Selected to Repeat", "Set Selected to Withdraw"
 *    - "Execute Promotion" button (confirmation dialog with summary)
 *    - Status badges: draft (gray), preview (blue), in_progress (yellow), completed (green), failed (red)
 *
 * Components used:
 * - PromotionBatchForm (dialog)
 * - PromotionEntryTable (TanStack Table with inline editing)
 * - PromotionSummaryCards
 */
```

---

## 6.10b Return Intent Page

**File:** `frontend/app/(dashboard)/admissions/return-intents/page.tsx`

```tsx
/**
 * SIMS Plus - Return Intent Surveys (Optional)
 *
 * Optional intent-to-return survey for boarding/private schools.
 * Results are advisory only — does NOT block promotion or enrollment.
 *
 * Layout:
 * 1. Campaign list (DataTable): name, academic year, classes, status, stats
 * 2. "Create Survey" button → dialog:
 *    - Name, academic year, target classes (multi-select), message template, deadline
 * 3. Campaign detail (expandable or separate page):
 *    - Student list with intent status (pending/returning/not_returning/undecided)
 *    - "Send Survey" button (changes status to 'sent')
 *    - Stats: total/returning/not_returning/undecided/pending counts
 *    - Progress bar/pie chart visualization
 *    - Advisory note: "These results are informational only"
 *
 * Components used:
 * - ReturnIntentCampaignForm
 * - Progress indicators
 */
```

---

## 6.11 Shared Components

### `frontend/components/admissions/pipeline-chart.tsx`

```tsx
/**
 * Admissions Pipeline Chart
 *
 * Horizontal bar chart (Recharts) showing application count by status.
 * Rendered as a funnel: submitted → under_review → shortlisted → offered → enrolled
 *
 * Props:
 * - data: Record<string, number> (status → count)
 *
 * Uses Recharts BarChart with horizontal layout.
 * Color coding matches ApplicationStatusBadge colors.
 */

"use client";

import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

interface PipelineChartProps {
  data: Record<string, number>;
}

const PIPELINE_ORDER = [
  "submitted", "under_review", "shortlisted",
  "exam_scheduled", "exam_completed",
  "offered", "accepted", "enrolled",
  "waitlisted", "rejected", "withdrawn",
];

const STATUS_COLORS: Record<string, string> = {
  submitted: "#3b82f6",
  under_review: "#8b5cf6",
  shortlisted: "#06b6d4",
  exam_scheduled: "#f59e0b",
  exam_completed: "#eab308",
  offered: "#10b981",
  accepted: "#22c55e",
  enrolled: "#059669",
  waitlisted: "#6b7280",
  rejected: "#ef4444",
  withdrawn: "#9ca3af",
};

export function PipelineChart({ data }: PipelineChartProps) {
  const chartData = PIPELINE_ORDER
    .filter((s) => (data[s] ?? 0) > 0)
    .map((status) => ({
      status: status.replace(/_/g, " "),
      count: data[status] ?? 0,
      fill: STATUS_COLORS[status] ?? "#6b7280",
    }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} layout="vertical">
        <XAxis type="number" />
        <YAxis type="category" dataKey="status" width={120} className="text-xs capitalize" />
        <Tooltip />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### `frontend/components/admissions/decision-dialog.tsx`

```tsx
/**
 * Admission Decision Dialog
 *
 * Modal dialog for making admission decisions (single or contextual).
 *
 * Props:
 * - applicationId: string
 * - currentStatus: ApplicationStatus
 * - onSuccess: () => void
 * - trigger: ReactNode (button that opens the dialog)
 *
 * Fields:
 * - decision_type: select (accepted/rejected/waitlisted/deferred)
 * - offered_class_id: select (shown only for 'accepted', populated from classes)
 * - conditions: textarea (optional)
 * - response_deadline: date picker (shown only for 'accepted')
 *
 * On submit: calls makeDecision() action, shows toast, calls onSuccess
 */
```

### `frontend/components/admissions/bulk-decision-toolbar.tsx`

```tsx
/**
 * Bulk Decision Toolbar
 *
 * Sticky toolbar that appears when applications are selected in the table.
 *
 * Props:
 * - selectedIds: string[]
 * - onComplete: () => void (refresh table)
 *
 * Actions:
 * - "Accept Selected" → opens dialog (offered_class required)
 * - "Reject Selected" → confirmation dialog
 * - "Waitlist Selected" → confirmation dialog
 *
 * Shows result: "15 accepted, 2 failed" with details expandable
 */
```

### `frontend/components/admissions/application-detail-card.tsx`

```tsx
/**
 * Application Detail Card
 *
 * Displays full application info in a structured layout.
 * Used in the application detail page.
 *
 * Sections:
 * 1. Personal Info: name, DOB, gender, nationality, class, photo
 * 2. Previous School & Medical Info
 * 3. Custom Fields (rendered dynamically from JSONB)
 * 4. Guardians (table/list with contact info)
 * 5. Documents (list with download links)
 * 6. Payment Info (status, amount, date)
 *
 * Props:
 * - application: ApplicationDetail
 */
```

### `frontend/components/admissions/exam-results-table.tsx`

```tsx
/**
 * Exam Results Table
 *
 * Editable data table for entering/viewing entrance exam results.
 *
 * Props:
 * - examId: string
 * - results: ExamResult[]
 * - editable: boolean (true for score entry mode)
 * - onSave: (results: ExamResultEntry[]) => void
 *
 * Columns (editable mode):
 * - Applicant Name (read-only)
 * - Score (number input)
 * - Max Score (number input, pre-filled)
 * - Grade (text input)
 * - Passed (checkbox)
 * - Remarks (text input)
 *
 * "Save All" button at bottom calls onSave with all rows.
 */
```

### `frontend/components/admissions/promotion-entry-table.tsx`

```tsx
/**
 * Class Promotion Entry Table
 *
 * TanStack Table for per-student promotion decisions.
 * Supports inline editing of action, target class, and reason.
 *
 * Columns:
 * - Student Name (read-only)
 * - Student # (read-only)
 * - Current Class (read-only)
 * - Action (dropdown: promote/repeat/graduate/withdraw)
 * - Target Class (dropdown, disabled for graduate/withdraw)
 * - Target Section (dropdown, optional)
 * - Reason (text input, shown for repeat/withdraw)
 *
 * Features:
 * - Row selection for bulk actions
 * - Filter by source class, action type
 * - Pagination (50 per page)
 * - On change: calls updatePromotionEntry() action
 */
```

### `frontend/components/admissions/return-intent-campaign-form.tsx`

```tsx
/**
 * Return Intent Campaign Form
 *
 * Form for creating intent-to-return survey campaigns.
 * Used in a dialog or inline.
 *
 * Fields:
 * - Name (text)
 * - Academic Year (select from available years)
 * - Target Classes (multi-select checkboxes)
 * - Message Template (textarea with placeholder tokens: {student_name}, {class_name})
 * - Deadline (date picker)
 *
 * Advisory note at top: "This survey is informational only and does not affect promotions."
 *
 * On submit: calls createReturnIntentCampaign() action
 */
```

---

## 6.12 Replace Students/Enrollments Placeholder

**File to modify:** `frontend/app/(dashboard)/students/enrollments/page.tsx`

Replace the current placeholder content with a redirect to the admissions enrollment page:

```tsx
import { redirect } from "next/navigation";

export default function EnrollmentsPage() {
  redirect("/admissions/enrollment");
}
```

---

## File Summary

| File | Type | Purpose |
|------|------|---------|
| `components/dashboard/app-sidebar.tsx` | Modified | Add Enrollment nav group |
| `app/(dashboard)/admissions/page.tsx` | Page (RSC) | Dashboard with pipeline stats |
| `app/(dashboard)/admissions/periods/page.tsx` | Page | Period list + create |
| `app/(dashboard)/admissions/periods/[id]/page.tsx` | Page | Period detail + form config |
| `app/(dashboard)/admissions/applications/page.tsx` | Page | Application list with filters |
| `app/(dashboard)/admissions/applications/[id]/page.tsx` | Page | Application detail + all actions |
| `app/(dashboard)/admissions/exams/page.tsx` | Page | Exam sessions list |
| `app/(dashboard)/admissions/exams/[id]/page.tsx` | Page | Exam detail + results entry |
| `app/(dashboard)/admissions/decisions/page.tsx` | Page | Bulk decision management |
| `app/(dashboard)/admissions/enrollment/page.tsx` | Page | Enrollment queue |
| `app/(dashboard)/admissions/promotions/page.tsx` | Page | Class promotion management |
| `app/(dashboard)/admissions/return-intents/page.tsx` | Page | Return intent surveys (optional) |
| `components/admissions/pipeline-chart.tsx` | Component | Pipeline bar chart (Recharts) |
| `components/admissions/decision-dialog.tsx` | Component | Decision making dialog |
| `components/admissions/bulk-decision-toolbar.tsx` | Component | Bulk action toolbar |
| `components/admissions/application-detail-card.tsx` | Component | Full application info display |
| `components/admissions/exam-results-table.tsx` | Component | Editable score entry table |
| `components/admissions/promotion-entry-table.tsx` | Component | Promotion entries with inline editing |
| `components/admissions/return-intent-campaign-form.tsx` | Component | Return intent campaign form |
| `app/(dashboard)/students/enrollments/page.tsx` | Modified | Redirect to admissions |

### Design Patterns

- **Server Components** for data fetching (dashboard, lists)
- **Client Components** for interactive features (forms, dialogs, bulk actions)
- **TanStack Table** for data tables (applications, exams, promotions, return intents)
- **React Hook Form + Zod** for all forms
- **Recharts** for pipeline visualization
- **Shadcn/ui** components: Card, Badge, Dialog, Select, Table, Button, DropdownMenu
- **CollapsibleFilters** for mobile-friendly filter UI
- **Toast** notifications (sonner) for action feedback
