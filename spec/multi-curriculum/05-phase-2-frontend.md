# Phase 2: Frontend — Grading, Equivalencies & Report Preview

**Phase:** MC-Sprint 2
**Depends on:** Phase 2 Backend (04)
**Parallel with:** None

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 5.1 | Add Phase 2 types | `frontend/types/curriculum.type.ts` | 0.25d |
| 5.2 | Add equivalency + subject mapping actions | `frontend/actions/curriculum.action.ts` | 0.5d |
| 5.3 | Create GradeEquivalencyMatrix component | `frontend/components/curriculum/GradeEquivalencyMatrix.tsx` | 1d |
| 5.4 | Create SubjectMappingTable component | `frontend/components/curriculum/SubjectMappingTable.tsx` | 1d |
| 5.5 | Create ReportCardPreview component | `frontend/components/curriculum/ReportCardPreview.tsx` | 1d |
| 5.6 | Create grade equivalencies page | `frontend/app/(dashboard)/settings/curriculum/grade-equivalencies/page.tsx` | 0.5d |
| 5.7 | Create subject mappings page | `frontend/app/(dashboard)/settings/curriculum/subject-mappings/page.tsx` | 0.5d |
| 5.8 | Create report config page | `frontend/app/(dashboard)/settings/curriculum/profiles/[id]/report-config/page.tsx` | 0.5d |
| 5.9 | Add effort grade to score entry form | `frontend/app/(dashboard)/exams/[id]/scores/[subjectId]/score-entry-form.tsx` | 0.5d |
| 5.10 | Update report card viewer for multi-curriculum | `frontend/app/(dashboard)/exams/report-cards/[id]/page.tsx` | 1d |

---

## 5.1 Additional TypeScript Types

Add to `frontend/types/curriculum.type.ts`:

```typescript
// Grade Equivalency
export interface GradeEquivalency {
  id: string;
  source_grading_scale_id: string;
  target_grading_scale_id: string;
  source_grade_id: string;
  target_grade_id: string;
  source_grade_name?: string;
  target_grade_name?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface GradeEquivalencyCreate {
  source_grading_scale_id: string;
  target_grading_scale_id: string;
  source_grade_id: string;
  target_grade_id: string;
  notes?: string;
}

// Subject Curriculum Mapping
export interface SubjectCurriculumMapping {
  id: string;
  subject_id: string;
  subject_name?: string;
  subject_code?: string;
  curriculum_profile_id: string;
  external_code?: string;
  external_name?: string;
  level?: string;
  credits?: number;
  coefficient?: number;
  is_hl: boolean;
  grading_scale_id?: string;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SubjectCurriculumMappingCreate {
  subject_id: string;
  curriculum_profile_id: string;
  external_code?: string;
  external_name?: string;
  level?: string;
  credits?: number;
  coefficient?: number;
  is_hl?: boolean;
  grading_scale_id?: string;
  config?: Record<string, unknown>;
}

// Extended report types
export interface CurriculumReportData {
  curriculum_type?: string;
  gpa?: number;
  weighted_gpa?: number;
  cumulative_gpa?: number;
  total_credits_earned?: number;
  cumulative_credits?: number;
  honor_roll?: boolean;
  ib_total_points?: number;
  french_mention?: string;
  extra_data?: Record<string, unknown>;
}
```

---

## 5.3 GradeEquivalencyMatrix Component

**Component:** `frontend/components/curriculum/GradeEquivalencyMatrix.tsx`

A visual grid that maps grades between two grading scales:

```
                Target Scale: Cambridge IGCSE
Source:         A*    A     B     C     D     E     F     G
WAEC    A1     [x]   [ ]   [ ]   [ ]   [ ]   [ ]   [ ]   [ ]
        B2     [ ]   [x]   [ ]   [ ]   [ ]   [ ]   [ ]   [ ]
        B3     [ ]   [ ]   [x]   [ ]   [ ]   [ ]   [ ]   [ ]
        C4     [ ]   [ ]   [ ]   [x]   [ ]   [ ]   [ ]   [ ]
        ...
```

Features:
- Select source and target grading scales from dropdowns
- Grid renders all source grades as rows, target grades as columns
- Click a cell to create/toggle an equivalency mapping
- Existing mappings shown as filled cells
- Notes field appears on hover/click of a mapping
- Bulk save — collects all changes and sends in one request

---

## 5.9 Effort Grade in Score Entry

**File:** `frontend/app/(dashboard)/exams/[id]/scores/[subjectId]/score-entry-form.tsx`

When the exam's class has a Cambridge or Edexcel curriculum profile:
- Show an additional "Effort" column in the score entry table
- Effort grade is a select with options: "1" (Outstanding), "2" (Very Good), "3" (Good), "4" (Satisfactory), "5" (Needs Improvement)
- Effort grade is sent with the score in `bulkEnterScores()` action
- If the class has no curriculum profile or is GES, the effort column is hidden

Detection logic:
```typescript
// Fetch class's curriculum profile
const classProfile = await getCurriculumProfileForClass(classId);
const showEffort = classProfile?.curriculum_type === "cambridge" || classProfile?.curriculum_type === "edexcel";
```

---

## 5.10 Multi-Curriculum Report Card Viewer

**File:** `frontend/app/(dashboard)/exams/report-cards/[id]/page.tsx`

Update the report card detail page to handle different curriculum formats:

- Check `termReport.curriculum_profile_id` — if present, fetch the profile
- Based on `curriculum_type`, render the appropriate layout:
  - **GES:** Existing layout (Class Score, Exams Score, Total, Position)
  - **Cambridge:** Component columns, effort grade, predicted grade, no position
  - **American:** Letter grade, GPA, credits, honor roll badge
  - **IB:** Achievement level, IB total points, learner profile grid
  - **French:** Score/20, coefficient, weighted score, mention banner
  - **Montessori:** Narrative sections, progress level indicators

Use a component switch pattern:
```typescript
function ReportCardContent({ report, profile }: Props) {
  switch (profile?.curriculum_type) {
    case "cambridge":
    case "edexcel":
      return <CambridgeReport report={report} />;
    case "american":
      return <AmericanReport report={report} />;
    case "ib":
      return <IBReport report={report} />;
    case "french":
      return <FrenchReport report={report} />;
    case "montessori":
      return <MontessoriReport report={report} />;
    default:
      return <GESReport report={report} />;  // existing component
  }
}
```

Each sub-component renders the curriculum-specific layout. The existing GES layout is extracted into `<GESReport>` but the code is unchanged.
