# Phase 2: Frontend — Enhancement & Integration

**Sprint:** 21
**Depends on:** Phase 2 Services & Endpoints (doc 06)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 7.1 | Add Phase 2 TypeScript types | `frontend/types/index.ts` | 0.25d |
| 7.2 | Add Phase 2 server actions | `frontend/actions/preschool.action.ts` | 0.5d |
| 7.3 | Create Portfolio page | `frontend/app/(dashboard)/preschool/portfolio/page.tsx` | 0.75d |
| 7.4 | Create LearningStoryCard component | `frontend/components/preschool/LearningStoryCard.tsx` | 0.25d |
| 7.5 | Create LearningStoryForm component | `frontend/components/preschool/LearningStoryForm.tsx` | 0.5d |
| 7.6 | Create Extended Care page | `frontend/app/(dashboard)/preschool/extended-care/page.tsx` | 0.75d |
| 7.7 | Create ExtendedCareCheckIn component | `frontend/components/preschool/ExtendedCareCheckIn.tsx` | 0.25d |
| 7.8 | Create Timeline page | `frontend/app/(dashboard)/preschool/timeline/page.tsx` | 0.5d |
| 7.9 | Create ProgressTimeline component | `frontend/components/preschool/ProgressTimeline.tsx` | 0.5d |
| 7.10 | Create CaregiverRatioConfig component | `frontend/components/preschool/CaregiverRatioConfig.tsx` | 0.25d |
| 7.11 | Create DailyReportSendButton component | `frontend/components/preschool/DailyReportSendButton.tsx` | 0.15d |
| 7.12 | Update sidebar navigation | `frontend/components/dashboard/app-sidebar.tsx` | 0.1d |
| 7.13 | Update ConfigurationSettings | `frontend/components/preschool/ConfigurationSettings.tsx` | 0.15d |

---

## 7.1 TypeScript Types

**File:** `frontend/types/index.ts` (append after Phase 1 types)

```typescript
// =========================
// Preschool Phase 2 Types
// =========================

// Learning Stories
interface LearningStory {
  id: string;
  tenant_id: string;
  student_id: string;
  term_id?: string;
  title: string;
  narrative: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents: boolean;
  created_by?: string;
  created_at: string;
  updated_at: string;
}

interface LearningStoryCreate {
  student_id: string;
  term_id?: string;
  title: string;
  narrative: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents?: boolean;
}

interface LearningStoryUpdate {
  title?: string;
  narrative?: string;
  learning_area_ids?: string[];
  skill_ids?: string[];
  observation_ids?: string[];
  attachments?: ProgressObservationAttachment[];
  is_shared_with_parents?: boolean;
}

// Extended Care
type ExtendedCareSessionType = "before_care" | "after_care";

interface ExtendedCareSession {
  id: string;
  tenant_id: string;
  student_id: string;
  session_date: string;
  session_type: ExtendedCareSessionType;
  check_in_time: string;
  check_out_time?: string;
  duration_minutes?: number;
  checked_in_by?: string;
  checked_out_by?: string;
  notes?: string;
  created_at: string;
}

interface ExtendedCareBillingSummary {
  student_id: string;
  student_name: string;
  total_sessions: number;
  total_minutes: number;
  total_hours: number;
  rate_per_hour?: number;
  flat_rate?: number;
  estimated_charge: number;
}

// Caregiver Ratios
interface CaregiverRatio {
  id: string;
  tenant_id: string;
  class_id: string;
  academic_year_id: string;
  max_children_per_caregiver: number;
  current_caregiver_count: number;
  max_capacity: number;
  current_enrollment: number;
  is_compliant: boolean;
}

// Timeline
interface TimelineEntry {
  date: string;
  type: "assessment" | "observation" | "incident" | "learning_story";
  title: string;
  summary?: string;
  details: Record<string, unknown>;
  id: string;
}

// Updated PreschoolReport (add new fields to existing type)
// Add to existing PreschoolReport interface:
//   report_type: "term" | "interim" | "progress_update";
//   photo_urls?: { url: string; caption?: string }[];
//   chart_data?: { labels: string[]; values: number[]; max_value: number };
```

---

## 7.3 Portfolio Page

**File:** `frontend/app/(dashboard)/preschool/portfolio/page.tsx`

**Component:** `PortfolioManager` (client component)

**UI structure:**
1. **Header:** "Learning Portfolio" title + "New Story" button
2. **Filters:**
   - Class select (preschool levels)
   - Student select (ComboBox)
   - Term select (optional filter)
   - Share filter: All / Shared with Parents / Not Shared
3. **Stats cards** (3 cards):
   - Total stories
   - Stories this term
   - Shared with parents
4. **Story grid** (responsive: 1 col mobile, 2 cols md, 3 cols lg):
   - Uses `LearningStoryCard` component for each story
   - Masonry-like layout for varying content heights
5. **Create/Edit sheet** (side panel, not dialog — more room for narrative):
   - Uses `LearningStoryForm` component

---

## 7.4 LearningStoryCard Component

**Props:**
```typescript
interface LearningStoryCardProps {
  story: LearningStory;
  onEdit: (story: LearningStory) => void;
  onDelete: (id: string) => void;
}
```

**UI:**
- Card with optional hero image (first attachment thumbnail)
- Title (bold, truncated to 2 lines)
- Narrative preview (truncated to 3 lines)
- Learning area badges (colored chips matching area colors)
- Date + "Shared with parents" badge
- Footer: Edit button, Delete button, Observation count badge

---

## 7.5 LearningStoryForm Component

**Props:**
```typescript
interface LearningStoryFormProps {
  story?: LearningStory;  // Edit mode if provided
  students: Student[];
  learningAreas: LearningArea[];
  skills: DevelopmentalSkill[];
  observations: ProgressObservation[];  // For linking
  onSubmit: (data: LearningStoryCreate | LearningStoryUpdate) => Promise<void>;
  onCancel: () => void;
  isSaving?: boolean;
}
```

**Form fields:**
- Student (select, disabled in edit mode)
- Title (text input)
- Narrative (rich textarea — no WYSIWYG, but larger textarea with line count)
- Learning areas (multi-select checkboxes from existing areas)
- Skills demonstrated (multi-select, filtered by selected learning areas)
- Linked observations (multi-select from student's observations)
- Photo uploads (drag-and-drop zone, reuse existing media upload pattern)
- Caption for each photo
- Share with parents toggle

---

## 7.6 Extended Care Page

**File:** `frontend/app/(dashboard)/preschool/extended-care/page.tsx`

**Component:** `ExtendedCareManager` (client component)

**UI structure:** Tabs with 3 tabs:

**Tab 1: "Check In / Out"**
- Class select → loads students in class
- Two columns: "Before Care" and "After Care"
- Each column shows students currently checked in (with check-in time)
- "Check In" button per student (opens time picker if not auto)
- "Check Out" button for checked-in students
- Status indicators: green dot = checked in, no dot = not checked in

**Tab 2: "Session History"**
- Date range picker
- Class filter
- DataTable: Date, Student, Type, Check In, Check Out, Duration
- Exportable to CSV

**Tab 3: "Billing Summary"**
- Date range picker (required)
- Class filter
- Summary table: Student, Sessions, Total Hours, Rate, Estimated Charge
- Total row at bottom
- "Generate for selected period" action (data only, not invoice creation)

---

## 7.8 Timeline Page

**File:** `frontend/app/(dashboard)/preschool/timeline/page.tsx`

**Component:** `StudentTimelinePage` (client component)

**UI structure:**
1. **Student selection:**
   - Class select (preschool levels)
   - Student ComboBox
2. **Date range filter** (optional)
3. **ProgressTimeline component** (main content)

---

## 7.9 ProgressTimeline Component

**Props:**
```typescript
interface ProgressTimelineProps {
  entries: TimelineEntry[];
  isLoading?: boolean;
}
```

**UI:** Vertical timeline with left-aligned date labels and right-aligned content cards.

**Visual design:**
- Vertical line (2px, gray) running down the left side
- Each entry is a card connected to the timeline via a colored dot
- Dot colors by type:
  - Assessment: blue
  - Observation: green
  - Incident: red/amber (based on severity)
  - Learning Story: purple
- Card shows:
  - Type badge (colored)
  - Title
  - Date
  - Summary (truncated, expandable)
  - "View details" link (opens detail dialog or navigates to source page)
- Entries grouped by month with month headers
- Infinite scroll or "Load more" button at bottom

---

## 7.10 CaregiverRatioConfig Component

**File:** `frontend/components/preschool/CaregiverRatioConfig.tsx`

**Purpose:** Added as a new tab "Ratios" in the Preschool Settings page.

**UI:**
- Table of preschool classes with columns:
  - Class Name
  - Level
  - Max Children per Caregiver (editable number input)
  - Current Caregivers (editable number input)
  - Max Capacity (computed, read-only)
  - Current Enrollment (read-only, from student count)
  - Status (green "Compliant" badge or red "Over Capacity" badge)
- Save button (saves all rows)
- Info text: "Ghana ECCD recommended ratios: Creche 1:5, Nursery 1:10, KG 1:15"

---

## 7.11 DailyReportSendButton Component

**File:** `frontend/components/preschool/DailyReportSendButton.tsx`

**Purpose:** Added to the Daily Logs page — allows sending a log to parents.

**Props:**
```typescript
interface DailyReportSendButtonProps {
  logId: string;
  studentName: string;
  onSent?: () => void;
}
```

**UI:**
- Button: "Send to Parents" with Send icon
- Confirmation dialog: "Send daily report for {studentName} to their guardians?"
- Loading state while sending
- Success toast: "Report sent to X guardians"
- Error toast on failure

Also add a "Send All" button at the class level:
```typescript
interface BulkSendButtonProps {
  classId: string;
  logDate: string;
  onSent?: () => void;
}
```

---

## 7.12 Sidebar Update

Add under "Preschool" menu, after Phase 1 items:

```typescript
{
  title: "Portfolio",
  url: "/preschool/portfolio",
  icon: BookOpen,
},
{
  title: "Extended Care",
  url: "/preschool/extended-care",
  icon: Clock,
},
{
  title: "Timeline",
  url: "/preschool/timeline",
  icon: GitBranch,
},
```

**Full sidebar order:**
```
Preschool
  ├── Overview
  ├── Assessment
  ├── Observations
  ├── Daily Logs
  ├── Incidents        (Phase 1)
  ├── Pickups          (Phase 1)
  ├── Portfolio         (Phase 2)
  ├── Extended Care     (Phase 2)
  ├── Timeline          (Phase 2)
  ├── Reports
  └── Settings
```

---

## 7.13 Configuration Settings Update

Add new toggle cards and settings:

```typescript
// Extended care settings
{
  key: "extended_care_enabled",
  label: "Extended Care",
  description: "Enable before/after school care tracking",
  icon: Clock,
},

// Extended care rates (shown when extended_care_enabled is true)
// Input fields:
// - extended_care_rate_per_hour (number input, with currency label)
// - extended_care_flat_rate (number input, with "per session" label)
// Radio: "Charge by hour" vs "Flat rate per session"

// Daily report auto-send
{
  key: "daily_report_auto_send",
  label: "Auto-Send Daily Reports",
  description: "Automatically send daily activity reports to parents",
  icon: Send,
},
// When enabled, show time picker for daily_report_send_time
```

Add "Ratios" as a 4th tab in the Settings page:
```
Settings Tabs: Configuration | Learning Areas | Rating Scales | Ratios
```

---

## Server Action Additions

**File:** `frontend/actions/preschool.action.ts`

```typescript
// Learning Stories
export async function listLearningStories(params?) → ActionResult<LearningStory[]>
export async function createLearningStory(data) → ActionResult<LearningStory>
export async function getLearningStory(id) → ActionResult<LearningStory>
export async function updateLearningStory(id, data) → ActionResult<LearningStory>
export async function deleteLearningStory(id) → ActionResult<void>

// Extended Care
export async function checkInExtendedCare(data) → ActionResult<ExtendedCareSession>
export async function checkOutExtendedCare(sessionId, notes?) → ActionResult<ExtendedCareSession>
export async function listExtendedCareSessions(params?) → ActionResult<ExtendedCareSession[]>
export async function getExtendedCareBillingSummary(params) → ActionResult<ExtendedCareBillingSummary[]>

// Caregiver Ratios
export async function listCaregiverRatios(academicYearId?) → ActionResult<CaregiverRatio[]>
export async function setCaregiverRatio(classId, data) → ActionResult<CaregiverRatio>

// Timeline
export async function getStudentTimeline(studentId, params?) → ActionResult<TimelineEntry[]>

// Daily Report Sending
export async function sendDailyLogToParents(logId) → ActionResult<{sent_count: number}>
export async function bulkSendDailyLogs(classId, logDate) → ActionResult<{total: number, sent: number}>
```
