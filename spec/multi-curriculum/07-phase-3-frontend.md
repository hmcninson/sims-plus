# Phase 3: Frontend — External Exams, Credits & Transcripts

**Phase:** MC-Sprint 3
**Depends on:** Phase 3 Backend (06)
**Parallel with:** None

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 7.1 | Add Phase 3 types | `frontend/types/curriculum.type.ts` | 0.5d |
| 7.2 | Add Phase 3 server actions | `frontend/actions/curriculum.action.ts` | 1d |
| 7.3 | Create ExternalExamRegistrationForm component | `frontend/components/curriculum/ExternalExamRegistrationForm.tsx` | 1d |
| 7.4 | Create ExternalExamRegistrationTable component | `frontend/components/curriculum/ExternalExamRegistrationTable.tsx` | 0.75d |
| 7.5 | Create ResultsImportWizard component | `frontend/components/curriculum/ResultsImportWizard.tsx` | 1.5d |
| 7.6 | Create PredictedGradeEntry component | `frontend/components/curriculum/PredictedGradeEntry.tsx` | 1d |
| 7.7 | Create CreditProgressDashboard component | `frontend/components/curriculum/CreditProgressDashboard.tsx` | 1d |
| 7.8 | Create TranscriptViewer component | `frontend/components/curriculum/TranscriptViewer.tsx` | 1d |
| 7.9 | Create external exams page | `frontend/app/(dashboard)/exams/external/page.tsx` | 0.5d |
| 7.10 | Create external exam detail page | `frontend/app/(dashboard)/exams/external/[id]/page.tsx` | 0.5d |
| 7.11 | Create results import page | `frontend/app/(dashboard)/exams/external/import/page.tsx` | 0.5d |
| 7.12 | Create predicted grades page | `frontend/app/(dashboard)/exams/predicted-grades/page.tsx` | 0.5d |
| 7.13 | Create student transcript page | `frontend/app/(dashboard)/students/[id]/transcript/page.tsx` | 0.5d |
| 7.14 | Create student credits page | `frontend/app/(dashboard)/students/[id]/credits/page.tsx` | 0.5d |
| 7.15 | Update student detail page with credits/transcript tabs | `frontend/app/(dashboard)/students/[id]/page.tsx` | 0.5d |
| 7.16 | Update sidebar navigation | `frontend/components/dashboard/app-sidebar.tsx` | 0.25d |

---

## 7.1 Additional TypeScript Types

Add to `frontend/types/curriculum.type.ts`:

```typescript
// External Exam Board
export type ExternalExamBoard =
  | "waec"
  | "cambridge_international"
  | "edexcel"
  | "college_board"
  | "ibo"
  | "none";

// External Exam Registration
export interface ExternalExamRegistration {
  id: string;
  student_id: string;
  student_name?: string;
  student_number?: string;
  exam_board: ExternalExamBoard;
  exam_session: string;
  candidate_number?: string;
  center_number?: string;
  registration_status: "pending" | "registered" | "confirmed";
  subjects: ExternalExamSubject[];
  results?: ExternalExamResult[];
  registration_date?: string;
  results_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ExternalExamSubject {
  subject_code: string;
  subject_name: string;
  level?: string;
  paper_numbers?: string[];
}

export interface ExternalExamResult {
  subject_code: string;
  grade: string;
  score?: number;
  date_received?: string;
}

export interface ExternalExamRegistrationCreate {
  student_id: string;
  exam_board: ExternalExamBoard;
  exam_session: string;
  candidate_number?: string;
  center_number?: string;
  subjects: ExternalExamSubject[];
  registration_date?: string;
  notes?: string;
}

export interface ExternalExamRegistrationUpdate {
  candidate_number?: string;
  center_number?: string;
  registration_status?: "pending" | "registered" | "confirmed";
  subjects?: ExternalExamSubject[];
  registration_date?: string;
  notes?: string;
}

// Results Import
export interface ResultsImportPreview {
  total_rows: number;
  matched: number;
  unmatched: number;
  errors: string[];
  preview_rows?: ResultsImportRow[];
}

export interface ResultsImportRow {
  candidate_number: string;
  subject_code: string;
  grade: string;
  score?: number;
  matched_student?: string;
  status: "matched" | "unmatched" | "error";
  error?: string;
}

// Predicted Grades
export interface PredictedGrade {
  id: string;
  student_id: string;
  student_name?: string;
  subject_id: string;
  subject_name?: string;
  academic_year_id: string;
  term_id?: string;
  predicted_grade?: string;
  target_grade?: string;
  predicted_score?: number;
  predicted_by?: string;
  predicted_by_name?: string;
  predicted_at?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface PredictedGradeCreate {
  student_id: string;
  subject_id: string;
  academic_year_id: string;
  term_id?: string;
  predicted_grade?: string;
  target_grade?: string;
  predicted_score?: number;
  notes?: string;
}

export interface PredictedGradeBulk {
  entries: PredictedGradeCreate[];
}

// Credits & GPA
export interface StudentCredits {
  student_id: string;
  curriculum_profile_id: string;
  records: CreditRecord[];
  total_credits_attempted: number;
  total_credits_earned: number;
}

export interface CreditRecord {
  id: string;
  subject_id: string;
  subject_name?: string;
  academic_year_id: string;
  academic_year_name?: string;
  term_id?: string;
  term_name?: string;
  credits_attempted: number;
  credits_earned: number;
  grade_points?: number;
  weighted_grade_points?: number;
  is_ap: boolean;
  is_honors: boolean;
}

export interface StudentGPA {
  student_id: string;
  term_gpa?: number;
  term_weighted_gpa?: number;
  cumulative_gpa: number;
  cumulative_weighted_gpa?: number;
  total_credits_attempted: number;
  total_credits_earned: number;
  honor_roll: boolean;
}

// Transcript
export interface TranscriptData {
  student: {
    name: string;
    id: string;
    student_number?: string;
    enrollment_date?: string;
    expected_graduation?: string;
  };
  school: {
    name: string;
    address?: string;
    logo_url?: string;
  };
  curriculum: {
    name: string;
    type: string;
  };
  terms: TranscriptTerm[];
  cumulative_gpa: number;
  cumulative_weighted_gpa?: number;
  total_credits_earned: number;
  graduation_credits_required?: number;
  credits_remaining?: number;
}

export interface TranscriptTerm {
  academic_year: string;
  term: string;
  subjects: TranscriptSubject[];
  term_gpa: number;
  term_credits_earned: number;
}

export interface TranscriptSubject {
  name: string;
  code?: string;
  credits_attempted: number;
  credits_earned: number;
  grade: string;
  grade_points: number;
  is_ap: boolean;
  is_honors: boolean;
}
```

---

## 7.2 Server Actions

Add to `frontend/actions/curriculum.action.ts`:

```typescript
// External Exam Registrations
export async function getExternalExamRegistrations(
  filters?: { student_id?: string; exam_board?: string; exam_session?: string; status?: string }
): Promise<ActionResult<ExternalExamRegistration[]>>

export async function getExternalExamRegistration(
  id: string
): Promise<ActionResult<ExternalExamRegistration>>

export async function createExternalExamRegistration(
  data: ExternalExamRegistrationCreate
): Promise<ActionResult<ExternalExamRegistration>>

export async function updateExternalExamRegistration(
  id: string, data: ExternalExamRegistrationUpdate
): Promise<ActionResult<ExternalExamRegistration>>

export async function bulkRegisterExternalExam(
  data: ExternalExamRegistrationCreate[]
): Promise<ActionResult<{ created: number; errors: string[] }>>

export async function importExternalExamResults(
  examBoard: ExternalExamBoard,
  examSession: string,
  csvData: string,
  dryRun: boolean
): Promise<ActionResult<ResultsImportPreview>>

export async function exportWaecRegistrations(
  examSession: string
): Promise<ActionResult<Blob>>

export async function exportCambridgeRegistrations(
  examSession: string
): Promise<ActionResult<Blob>>

// Predicted Grades
export async function getPredictedGrades(
  filters?: { student_id?: string; subject_id?: string; academic_year_id?: string }
): Promise<ActionResult<PredictedGrade[]>>

export async function createPredictedGrade(
  data: PredictedGradeCreate
): Promise<ActionResult<PredictedGrade>>

export async function updatePredictedGrade(
  id: string, data: Partial<PredictedGradeCreate>
): Promise<ActionResult<PredictedGrade>>

export async function bulkSetPredictedGrades(
  data: PredictedGradeBulk
): Promise<ActionResult<{ created: number; updated: number }>>

// Credits & GPA
export async function getStudentCredits(
  studentId: string, profileId: string
): Promise<ActionResult<StudentCredits>>

export async function getStudentGPA(
  studentId: string, profileId: string,
  academicYearId?: string, termId?: string
): Promise<ActionResult<StudentGPA>>

export async function getStudentTranscript(
  studentId: string, profileId: string
): Promise<ActionResult<TranscriptData>>

export async function recalculateStudentCredits(
  studentId: string
): Promise<ActionResult<void>>

export async function downloadTranscriptPDF(
  studentId: string, profileId: string
): Promise<ActionResult<Blob>>
```

---

## 7.3 ExternalExamRegistrationForm

**File:** `frontend/components/curriculum/ExternalExamRegistrationForm.tsx`

A form for registering a student for an external exam:

- **Exam Board** select: WAEC, Cambridge International, Edexcel, College Board, IBO
- **Exam Session** input: e.g., "May 2026", "Nov 2026" (text input with suggestions)
- **Student** select: searchable student picker (existing `StudentSelector` component)
- **Candidate Number** input (optional, assigned by exam board)
- **Center Number** input (optional, school's exam center number)
- **Registration Date** date picker
- **Subjects** dynamic array:
  - Each row: Subject Code input, Subject Name input, Level select (Core/Extended for Cambridge, SL/HL for IB), Paper Numbers multi-select
  - Add Subject button at bottom
  - Remove button on each row
- **Notes** textarea

Uses React Hook Form + Zod validation:
- `exam_board` required
- `exam_session` required, max 20 chars
- `subjects` must have at least 1 entry
- Each subject: `subject_code` and `subject_name` required

---

## 7.4 ExternalExamRegistrationTable

**File:** `frontend/components/curriculum/ExternalExamRegistrationTable.tsx`

A TanStack Table data table listing external exam registrations:

**Columns:**
- Student Name (with link to student profile)
- Exam Board (badge: WAEC=green, Cambridge=blue, Edexcel=purple, IB=amber)
- Session (e.g., "May 2026")
- Candidate # (displayed if set, else "—")
- Status (badge: pending=gray, registered=blue, confirmed=green)
- Subjects Count
- Results (icon: checkmark if results imported, dash if not)
- Actions (View, Edit, Delete)

**Filters:**
- Exam Board multi-select
- Exam Session text filter
- Status select
- Student search

**Bulk Actions:**
- Export selected as CSV
- Bulk update status

---

## 7.5 ResultsImportWizard

**File:** `frontend/components/curriculum/ResultsImportWizard.tsx`

A multi-step wizard for importing external exam results from CSV:

**Step 1: Configuration**
- Select Exam Board (determines CSV format)
- Enter Exam Session (e.g., "Nov 2026")
- Upload CSV file (drag-and-drop zone + file input)
- Show format hint based on selected board:
  - WAEC: "Expected columns: CandidateNumber, SubjectCode, SubjectName, Grade, Score"
  - Cambridge: "Expected columns: CandidateNumber, CenterNumber, ComponentCode, ComponentName, Grade, Mark, MaxMark"

**Step 2: Preview (Dry Run)**
- Calls `importExternalExamResults()` with `dryRun: true`
- Shows summary: total rows, matched, unmatched, errors
- Table of preview rows with status indicators:
  - Green row: matched to existing registration
  - Yellow row: candidate found but no registration for this session
  - Red row: error (invalid data, candidate not found)
- Error details expandable per row

**Step 3: Confirm & Import**
- Summary of what will be imported
- "Import Results" button → calls with `dryRun: false`
- Progress indicator during import
- Success/failure summary on completion

---

## 7.6 PredictedGradeEntry

**File:** `frontend/components/curriculum/PredictedGradeEntry.tsx`

A spreadsheet-style grid for entering predicted and target grades:

- **Context selectors** at top: Academic Year, Term (optional), Class/Section, Subject
- **Grid layout:**
  - Rows: students in the selected class
  - Columns: Student Name | Current Average | Predicted Grade (editable) | Target Grade (editable) | Notes (editable)
- Predicted Grade and Target Grade columns use inline selects with grade options from the curriculum's grading scale
- Current Average is read-only, fetched from existing exam scores
- Notes is an inline text input
- **Save All** button at bottom — calls `bulkSetPredictedGrades()`
- Shows unsaved changes indicator
- Auto-saves on blur (optional, configurable)

Detection logic — only show for Cambridge/IB profiles:
```typescript
const classProfile = await getCurriculumProfileForClass(classId);
const showPredicted = classProfile?.curriculum_type === "cambridge"
  || classProfile?.curriculum_type === "edexcel"
  || classProfile?.curriculum_type === "ib";
```

---

## 7.7 CreditProgressDashboard

**File:** `frontend/components/curriculum/CreditProgressDashboard.tsx`

A dashboard showing a student's credit accumulation and GPA progress:

**Props:** `studentId: string`, `profileId: string`

**Layout:**

**Top Row — Summary Cards:**
- Cumulative GPA (large number, color-coded: >= 3.5 green, >= 2.5 amber, < 2.5 red)
- Weighted GPA (if AP/Honors courses exist)
- Credits Earned / Required (with progress bar)
- Honor Roll badge (if applicable)

**Middle Row — GPA Trend Chart:**
- Line chart (Recharts) showing GPA by term
- X-axis: Term labels ("2025/26 S1", "2025/26 S2", etc.)
- Y-axis: GPA scale (0.0 - 4.0)
- Two lines: unweighted GPA + weighted GPA

**Bottom Row — Credit Breakdown Table:**
- Table: Academic Year | Term | Subject | Credits Attempted | Credits Earned | Grade | Points | AP/Honors
- Group by academic year with subtotal rows
- AP courses highlighted with badge
- Honors courses highlighted with badge

**Actions:**
- "View Transcript" button → navigates to transcript page
- "Download Transcript PDF" button → triggers PDF download
- "Recalculate" button (admin only) → calls `recalculateStudentCredits()`

---

## 7.8 TranscriptViewer

**File:** `frontend/components/curriculum/TranscriptViewer.tsx`

A formatted, print-ready transcript view:

**Props:** `data: TranscriptData`

**Layout (designed for A4 printing):**

**Header:**
- School logo (left), School name + address (center), "Official Transcript" (right)
- Student info block: Name, Student ID, Enrollment Date, Expected Graduation
- Curriculum: Profile name, type

**Body — Term Sections:**
- For each term, a bordered section:
  - Header: "Academic Year 2025/2026 — Semester 1"
  - Table: Subject | Code | Credits | Grade | Points | AP/Honors flag
  - Footer: Term GPA: X.XX | Credits Earned: X.X

**Footer:**
- Cumulative Summary box:
  - Cumulative GPA (Unweighted): X.XX
  - Cumulative GPA (Weighted): X.XX
  - Total Credits Earned: XX.X / XX.X required
  - Credits Remaining: X.X
- Signature line: "Registrar" with date
- "This is an official transcript of [School Name]" notice

**Print styles:**
- `@media print` CSS for clean A4 output
- Page break between terms if content overflows
- No sidebar/header/footer from dashboard layout

---

## 7.9 External Exams Page

**File:** `frontend/app/(dashboard)/exams/external/page.tsx`

Main listing page for external exam registrations:

- Header: "External Exams" with description
- Action buttons:
  - "Register Student" → opens registration form (modal or page)
  - "Bulk Register" → opens bulk registration dialog (CSV upload or class selection)
  - "Import Results" → navigates to `/exams/external/import`
  - "Export" dropdown → "WAEC Registration Export", "Cambridge Registration Export"
- Renders `ExternalExamRegistrationTable` component
- Filters bar above table

---

## 7.10 External Exam Detail Page

**File:** `frontend/app/(dashboard)/exams/external/[id]/page.tsx`

Detail page for a single registration:

- **Registration Info Card:**
  - Student name + link to profile
  - Exam board, session, status
  - Candidate number, center number
  - Registration date
  - Notes
- **Registered Subjects Table:**
  - Subject Code | Subject Name | Level | Papers
- **Results Section** (if results exist):
  - Subject Code | Subject Name | Grade | Score | Date Received
  - Overall summary (total subjects passed, highest grade, etc.)
- **Actions:**
  - Edit registration (opens form in edit mode)
  - Update status dropdown
  - Manually add/edit results (inline editing)
  - Delete registration (with confirmation)

---

## 7.11 Results Import Page

**File:** `frontend/app/(dashboard)/exams/external/import/page.tsx`

Standalone page rendering the `ResultsImportWizard` component:

- Breadcrumb: Exams > External Exams > Import Results
- Full-width wizard layout
- On success, redirects back to `/exams/external` with success toast

---

## 7.12 Predicted Grades Page

**File:** `frontend/app/(dashboard)/exams/predicted-grades/page.tsx`

Page for managing predicted grades:

- Header: "Predicted Grades" with description
- Context selectors: Academic Year, Term, Class/Section, Subject
- Renders `PredictedGradeEntry` component with selected context
- Only visible for schools with Cambridge, Edexcel, or IB profiles
- If no applicable profile: show info card explaining that predicted grades are for Cambridge/IB curricula

---

## 7.13 Student Transcript Page

**File:** `frontend/app/(dashboard)/students/[id]/transcript/page.tsx`

Individual student transcript page:

- Breadcrumb: Students > [Student Name] > Transcript
- Curriculum profile selector (if student has multiple profiles or school has multiple)
- Renders `TranscriptViewer` component with fetched `TranscriptData`
- Action buttons:
  - "Download PDF" → calls `downloadTranscriptPDF()`
  - "Print" → triggers `window.print()`
- Only visible for American and IB curriculum profiles (where credits/GPA apply)
- If no applicable profile: show info card explaining that transcripts are for credit-based curricula

---

## 7.14 Student Credits Page

**File:** `frontend/app/(dashboard)/students/[id]/credits/page.tsx`

Individual student credits dashboard:

- Breadcrumb: Students > [Student Name] > Credits & GPA
- Curriculum profile selector
- Renders `CreditProgressDashboard` component
- Only visible for American and IB curriculum profiles
- If no applicable profile: redirect to student detail page

---

## 7.15 Update Student Detail Page

**File:** `frontend/app/(dashboard)/students/[id]/page.tsx`

Add new tabs/sections to the existing student detail page:

- **Credits & GPA tab** (conditional): Shown only when student's class has an American or IB curriculum profile. Links to `/students/[id]/credits`.
- **Transcript tab** (conditional): Shown only when student's class has a credit-based curriculum profile. Links to `/students/[id]/transcript`.
- **External Exams tab** (conditional): Shows external exam registrations for this student. Shown when any registrations exist for this student. Displays a compact version of `ExternalExamRegistrationTable` filtered to `student_id`.
- **Predicted Grades tab** (conditional): Shows predicted/target grades for this student. Shown for Cambridge/Edexcel/IB profiles. Read-only view (editing done from the predicted grades page).

Tab visibility detection:
```typescript
const classProfile = await getCurriculumProfileForClass(student.current_class_id);
const showCredits = classProfile?.use_credits || classProfile?.use_gpa;
const showTranscript = classProfile?.use_credits;
const showPredicted = ["cambridge", "edexcel", "ib"].includes(classProfile?.curriculum_type ?? "");

// External exams: always check if registrations exist
const externalExams = await getExternalExamRegistrations({ student_id: student.id });
const showExternalExams = externalExams.success && externalExams.data.length > 0;
```

---

## 7.16 Update Sidebar Navigation

Add external exams sub-items under the existing "Exams" section:

```typescript
{
  title: "Exams",
  icon: ClipboardCheckIcon,
  items: [
    // ... existing exam items ...
    {
      title: "External Exams",
      url: "/exams/external",
    },
    {
      title: "Predicted Grades",
      url: "/exams/predicted-grades",
    },
  ],
}
```

These items should be visible to `school_admin` and `academic_head` roles. The "Predicted Grades" item should only appear when the school has at least one Cambridge, Edexcel, or IB curriculum profile (check via `getCurriculumProfiles()` in the sidebar data loader).
