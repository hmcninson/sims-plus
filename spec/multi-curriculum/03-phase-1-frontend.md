# Phase 1: Frontend — Curriculum Settings UI

**Phase:** MC-Sprint 1 (Foundation)
**Depends on:** Phase 1 Services & Endpoints (02)
**Parallel with:** None (must wait for API)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | Create TypeScript types | `frontend/types/curriculum.type.ts` | 0.5d |
| 3.2 | Create server actions | `frontend/actions/curriculum.action.ts` | 1d |
| 3.3 | Create CurriculumSelector component | `frontend/components/curriculum/CurriculumSelector.tsx` | 0.5d |
| 3.4 | Create TemplateSelector component | `frontend/components/curriculum/TemplateSelector.tsx` | 0.5d |
| 3.5 | Create CurriculumProfileWizard component | `frontend/components/curriculum/CurriculumProfileWizard.tsx` | 1.5d |
| 3.6 | Create AssessmentStructureEditor component | `frontend/components/curriculum/AssessmentStructureEditor.tsx` | 1d |
| 3.7 | Create curriculum settings pages | `frontend/app/(dashboard)/settings/curriculum/` | 1.5d |
| 3.8 | Update class forms with curriculum selector | `frontend/app/(dashboard)/classes/` | 0.5d |
| 3.9 | Update sidebar navigation | `frontend/components/dashboard/app-sidebar.tsx` | 0.25d |

---

## 3.1 TypeScript Types

**File:** `frontend/types/curriculum.type.ts`

```typescript
// Curriculum types
export type CurriculumType =
  | "ges"
  | "cambridge"
  | "edexcel"
  | "american"
  | "ib"
  | "french"
  | "montessori"
  | "custom";

export type ScoreDisplayMode =
  | "percentage"
  | "grade_only"
  | "grade_and_score"
  | "level"
  | "gpa"
  | "narrative"
  | "mention";

export type AssessmentComponentType =
  | "continuous_assessment"
  | "exam"
  | "class_work"
  | "homework"
  | "midterm"
  | "end_term"
  | "coursework"
  | "controlled_assessment"
  | "external_exam"
  | "practical"
  | "oral"
  | "internal_assessment"
  | "external_assessment"
  | "extended_essay"
  | "tok"
  | "cas"
  | "quiz"
  | "test"
  | "project"
  | "participation"
  | "final"
  | "controle_continu"
  | "epreuve"
  | "observation"
  | "narrative"
  | "portfolio";

// Profile
export interface CurriculumProfile {
  id: string;
  name: string;
  curriculum_type: CurriculumType;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type: "terms" | "semesters" | "quarters";
  periods_per_year: number;
  score_display_mode: ScoreDisplayMode;
  show_position: boolean;
  show_class_average: boolean;
  use_gpa: boolean;
  use_credits: boolean;
  use_criterion_grading: boolean;
  config?: Record<string, unknown>;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CurriculumProfileDetail extends CurriculumProfile {
  assessment_structure?: AssessmentStructure;
  report_config?: ReportCardConfig;
}

export interface CurriculumProfileCreate {
  name: string;
  curriculum_type: CurriculumType;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type?: "terms" | "semesters" | "quarters";
  periods_per_year?: number;
  score_display_mode?: ScoreDisplayMode;
  show_position?: boolean;
  show_class_average?: boolean;
  use_gpa?: boolean;
  use_credits?: boolean;
  use_criterion_grading?: boolean;
  config?: Record<string, unknown>;
  is_default?: boolean;
}

export interface CurriculumProfileUpdate {
  name?: string;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type?: "terms" | "semesters" | "quarters";
  periods_per_year?: number;
  score_display_mode?: ScoreDisplayMode;
  show_position?: boolean;
  show_class_average?: boolean;
  use_gpa?: boolean;
  use_credits?: boolean;
  use_criterion_grading?: boolean;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

// Assessment Structure
export interface AssessmentComponent {
  id: string;
  component_type: AssessmentComponentType;
  name: string;
  weight: number;
  max_score?: number;
  is_external: boolean;
  sequence: number;
  maps_to_ca: boolean;
  maps_to_exam: boolean;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AssessmentStructure {
  id: string;
  curriculum_profile_id: string;
  academic_year_id?: string;
  name: string;
  description?: string;
  is_active: boolean;
  components: AssessmentComponent[];
  created_at: string;
  updated_at: string;
}

export interface AssessmentComponentCreate {
  component_type: AssessmentComponentType;
  name: string;
  weight: number;
  max_score?: number;
  is_external?: boolean;
  sequence?: number;
  maps_to_ca?: boolean;
  maps_to_exam?: boolean;
  config?: Record<string, unknown>;
}

export interface AssessmentStructureCreate {
  name: string;
  description?: string;
  academic_year_id?: string;
  components: AssessmentComponentCreate[];
}

// Report Card Config
export interface ReportCardConfig {
  id: string;
  curriculum_profile_id: string;
  template_key: string;
  show_position: boolean;
  show_class_average: boolean;
  show_subject_position: boolean;
  show_effort_grade: boolean;
  show_predicted_grades: boolean;
  show_gpa: boolean;
  show_credits: boolean;
  show_honor_roll: boolean;
  show_learner_profile: boolean;
  show_atl_skills: boolean;
  custom_columns?: Record<string, unknown>;
  header_text?: string;
  footer_text?: string;
  created_at: string;
  updated_at: string;
}

export interface ReportCardConfigUpdate {
  template_key?: string;
  show_position?: boolean;
  show_class_average?: boolean;
  show_subject_position?: boolean;
  show_effort_grade?: boolean;
  show_predicted_grades?: boolean;
  show_gpa?: boolean;
  show_credits?: boolean;
  show_honor_roll?: boolean;
  show_learner_profile?: boolean;
  show_atl_skills?: boolean;
  custom_columns?: Record<string, unknown>;
  header_text?: string;
  footer_text?: string;
}

// Template
export interface CurriculumTemplateInfo {
  key: string;
  name: string;
  curriculum_type: CurriculumType;
  description: string;
}

// Validation
export interface ValidateStructureResponse {
  is_valid: boolean;
  total_weight: number;
  message: string;
}
```

---

## 3.2 Server Actions

**File:** `frontend/actions/curriculum.action.ts`

Follow the project convention: `"use server"` directive, `apiGet`/`apiPost`/`apiPut`/`apiDelete` helpers, return `ActionResult<T>`.

### Actions

```typescript
"use server";

import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import type { ActionResult } from "@/types";
import type {
  CurriculumProfile,
  CurriculumProfileDetail,
  CurriculumProfileCreate,
  CurriculumProfileUpdate,
  CurriculumTemplateInfo,
  AssessmentStructure,
  AssessmentStructureCreate,
  AssessmentComponentCreate,
  AssessmentComponentUpdate,
  ReportCardConfig,
  ReportCardConfigUpdate,
  ValidateStructureResponse,
} from "@/types/curriculum.type";

// Profile CRUD
export async function getCurriculumProfiles(): Promise<ActionResult<CurriculumProfile[]>>
export async function getCurriculumProfile(id: string): Promise<ActionResult<CurriculumProfileDetail>>
export async function createCurriculumProfile(data: CurriculumProfileCreate): Promise<ActionResult<CurriculumProfile>>
export async function updateCurriculumProfile(id: string, data: CurriculumProfileUpdate): Promise<ActionResult<CurriculumProfile>>
export async function deleteCurriculumProfile(id: string): Promise<ActionResult<void>>
export async function setDefaultProfile(id: string): Promise<ActionResult<CurriculumProfile>>

// Templates
export async function getCurriculumTemplates(): Promise<ActionResult<CurriculumTemplateInfo[]>>
export async function createFromTemplate(templateKey: string, nameOverride?: string): Promise<ActionResult<CurriculumProfileDetail>>

// Assessment Structure
export async function getAssessmentStructure(profileId: string): Promise<ActionResult<AssessmentStructure>>
export async function createAssessmentStructure(profileId: string, data: AssessmentStructureCreate): Promise<ActionResult<AssessmentStructure>>
export async function addAssessmentComponent(structureId: string, data: AssessmentComponentCreate): Promise<ActionResult<AssessmentComponent>>
export async function updateAssessmentComponent(componentId: string, data: AssessmentComponentUpdate): Promise<ActionResult<AssessmentComponent>>
export async function deleteAssessmentComponent(componentId: string): Promise<ActionResult<void>>
export async function validateAssessmentStructure(structureId: string): Promise<ActionResult<ValidateStructureResponse>>

// Report Config
export async function getReportConfig(profileId: string): Promise<ActionResult<ReportCardConfig>>
export async function updateReportConfig(profileId: string, data: ReportCardConfigUpdate): Promise<ActionResult<ReportCardConfig>>
```

---

## 3.3 - 3.6 Component Descriptions

### CurriculumSelector (`CurriculumSelector.tsx`)
- Dropdown component for selecting a curriculum profile
- Used in class edit/create forms
- Fetches profiles via `getCurriculumProfiles()` action
- Shows profile name + curriculum type badge
- Props: `value`, `onChange`, `placeholder`, `disabled`

### TemplateSelector (`TemplateSelector.tsx`)
- Grid of template cards for the wizard's first step
- Each card shows: template name, curriculum type, description, number of components
- Clicking a card selects it for instantiation
- Props: `templates`, `selectedKey`, `onSelect`

### CurriculumProfileWizard (`CurriculumProfileWizard.tsx`)
- Multi-step form wizard (responsive stepper pattern from existing `responsive-stepper.tsx`)
- **Step 1:** Choose method — "Start from template" or "Create custom"
  - If template: show TemplateSelector, then customize name
  - If custom: show curriculum type selector
- **Step 2:** Configure profile settings (calendar type, display mode, flags)
- **Step 3:** Define assessment structure (uses AssessmentStructureEditor)
- **Step 4:** Review & create
- Uses React Hook Form + Zod for validation

### AssessmentStructureEditor (`AssessmentStructureEditor.tsx`)
- Table of components with inline editing
- Each row: component type select, name input, weight input (%), external checkbox, CA/Exam mapping toggles
- Add Component button at bottom
- Delete button on each row (with confirmation)
- Shows running total of weights with green/red indicator (must = 100%)
- Reorder via sequence number
- Validates that total weight = 100 before allowing form submission

---

## 3.7 Curriculum Settings Pages

### Overview Page (`settings/curriculum/page.tsx`)
- Shows current school curriculum status
- Cards: "Curriculum Profiles" (count), "Active Profile", "Assessment Components" (count)
- Quick links to profile list, create wizard
- If no profiles exist, show a call-to-action to create from template

### Profile List Page (`settings/curriculum/profiles/page.tsx`)
- Data table with columns: Name, Type (badge), Calendar, Default (star icon), Status, Actions
- Actions: Edit, Set Default, Delete
- "Create Profile" button -> links to wizard
- Filter by curriculum type

### New Profile Page (`settings/curriculum/profiles/new/page.tsx`)
- Renders `CurriculumProfileWizard` component
- On success, redirects to profile detail page

### Profile Detail Page (`settings/curriculum/profiles/[id]/page.tsx`)
- Profile info card (name, type, settings)
- Edit form (inline or modal)
- Assessment structure section (shows AssessmentStructureEditor)
- Report card config section (toggle switches)
- "Classes using this profile" list

### Assessment Editor Page (`settings/curriculum/profiles/[id]/assessment/page.tsx`)
- Full-page AssessmentStructureEditor
- Validate button
- Save changes

---

## 3.8 Update Class Forms

Add `CurriculumSelector` to class create and edit forms:

- In class create dialog/form: add optional "Curriculum Profile" dropdown
- In class edit page: add "Curriculum Profile" field
- When a profile is selected, show a brief description of what it means (e.g., "Cambridge IGCSE - 3 terms, A*-G grading")

---

## 3.9 Update Sidebar

Add a "Curriculum" menu item under the Settings section of the sidebar:

```typescript
{
  title: "Curriculum",
  url: "/settings/curriculum",
  icon: BookOpenIcon,
}
```

This should appear after "Academic Settings" in the sidebar navigation, only visible to school_admin+ roles.
