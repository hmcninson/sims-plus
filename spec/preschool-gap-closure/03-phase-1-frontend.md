# Phase 1: Frontend — Safety & Enrollment

**Sprint:** 20.5
**Depends on:** Phase 1 Schemas & Endpoints (doc 02)
**Parallel with:** Phase 1 Testing (doc 04)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | Add TypeScript types | `frontend/types/index.ts` | 0.25d |
| 3.2 | Add server actions | `frontend/actions/preschool.action.ts` | 0.5d |
| 3.3 | Create AllergyAlert component | `frontend/components/preschool/AllergyAlert.tsx` | 0.25d |
| 3.4 | Create DietaryRequirementsForm component | `frontend/components/preschool/DietaryRequirementsForm.tsx` | 0.25d |
| 3.5 | Create IncidentForm component | `frontend/components/preschool/IncidentForm.tsx` | 0.5d |
| 3.6 | Create IncidentTimeline component | `frontend/components/preschool/IncidentTimeline.tsx` | 0.25d |
| 3.7 | Create Incidents page | `frontend/app/(dashboard)/preschool/incidents/page.tsx` | 0.75d |
| 3.8 | Create AuthorizedPickupList component | `frontend/components/preschool/AuthorizedPickupList.tsx` | 0.5d |
| 3.9 | Create PickupLogForm component | `frontend/components/preschool/PickupLogForm.tsx` | 0.25d |
| 3.10 | Create Pickups page | `frontend/app/(dashboard)/preschool/pickups/page.tsx` | 0.5d |
| 3.11 | Update sidebar navigation | `frontend/components/dashboard/app-sidebar.tsx` | 0.15d |
| 3.12 | Update daily log form with allergy alerts | `frontend/app/(dashboard)/preschool/daily-logs/page.tsx` | 0.25d |
| 3.13 | Update ConfigurationSettings with new toggles | `frontend/components/preschool/ConfigurationSettings.tsx` | 0.15d |
| 3.14 | Update component index | `frontend/components/preschool/index.ts` | 0.05d |

---

## 3.1 TypeScript Types

**File:** `frontend/types/index.ts` (append after existing preschool types)

```typescript
// =========================
// Preschool Phase 1 Types
// =========================

// Enums
type PreschoolSessionType = "half_day_morning" | "half_day_afternoon" | "full_day" | "extended";
type PreschoolIncidentType = "accident" | "illness" | "behavioral" | "allergic_reaction" | "other";
type PreschoolIncidentSeverity = "minor" | "moderate" | "serious";
type PreschoolIncidentStatus = "reported" | "reviewed" | "parent_notified" | "resolved";

// Allergy / Dietary
interface AllergyEntry {
  allergen: string;
  severity: "mild" | "moderate" | "severe";
  reaction?: string;
  medication?: string;
}

interface DietaryRequirements {
  allergies: AllergyEntry[];
  dietary_restrictions: string[];
  notes?: string;
}

interface AllergyAlertResponse {
  student_id: string;
  student_name: string;
  allergies: AllergyEntry[];
  dietary_restrictions: string[];
  notes?: string;
}

// Incidents
interface PreschoolIncident {
  id: string;
  tenant_id: string;
  student_id: string;
  incident_type: PreschoolIncidentType;
  severity: PreschoolIncidentSeverity;
  status: PreschoolIncidentStatus;
  incident_date: string;
  incident_time?: string;
  location?: string;
  description: string;
  action_taken?: string;
  first_aid_given: boolean;
  medical_attention_required: boolean;
  parent_notified_at?: string;
  parent_notified_by?: string;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
  follow_up_notes?: string;
  resolved_at?: string;
  resolved_by?: string;
  reported_by?: string;
  created_at: string;
  updated_at: string;
}

interface PreschoolIncidentCreate {
  student_id: string;
  incident_type: PreschoolIncidentType;
  severity: PreschoolIncidentSeverity;
  incident_date: string;
  incident_time?: string;
  location?: string;
  description: string;
  action_taken?: string;
  first_aid_given?: boolean;
  medical_attention_required?: boolean;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
}

interface PreschoolIncidentUpdate {
  incident_type?: PreschoolIncidentType;
  severity?: PreschoolIncidentSeverity;
  location?: string;
  description?: string;
  action_taken?: string;
  first_aid_given?: boolean;
  medical_attention_required?: boolean;
  witnesses?: string[];
  attachments?: ProgressObservationAttachment[];
  follow_up_notes?: string;
}

// Authorized Pickups
interface AuthorizedPickup {
  id: string;
  tenant_id: string;
  student_id: string;
  full_name: string;
  phone: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

interface AuthorizedPickupCreate {
  full_name: string;
  phone: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  notes?: string;
}

interface AuthorizedPickupUpdate {
  full_name?: string;
  phone?: string;
  relationship_to_student?: string;
  photo_url?: string;
  id_document_url?: string;
  is_active?: boolean;
  notes?: string;
}

// Pickup Logs
interface PickupLog {
  id: string;
  tenant_id: string;
  student_id: string;
  pickup_date: string;
  pickup_time: string;
  picked_up_by_type: "guardian" | "authorized_person";
  picked_up_by_guardian_id?: string;
  picked_up_by_authorized_id?: string;
  verified_by?: string;
  notes?: string;
  created_at: string;
}

interface PickupLogCreate {
  student_id: string;
  pickup_time: string;
  picked_up_by_type: "guardian" | "authorized_person";
  picked_up_by_guardian_id?: string;
  picked_up_by_authorized_id?: string;
  notes?: string;
}
```

Also add to existing `Student` type:

```typescript
interface Student {
  // ... existing fields ...
  enrollment_session?: PreschoolSessionType;
  dietary_requirements?: DietaryRequirements;
}
```

---

## 3.2 Server Actions

**File:** `frontend/actions/preschool.action.ts` (append to existing file)

```typescript
// =========================
// Incident Actions
// =========================

export async function listIncidents(
  params?: {
    student_id?: string;
    class_id?: string;
    status?: string;
    severity?: string;
    date_from?: string;
    date_to?: string;
  }
): Promise<ActionResult<PreschoolIncident[]>> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.student_id) searchParams.set("student_id", params.student_id);
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.status) searchParams.set("status", params.status);
    if (params?.severity) searchParams.set("severity", params.severity);
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<PreschoolIncident[]>(
      `/preschool/incidents${query ? `?${query}` : ""}`
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch incidents" };
  }
}

export async function createIncident(
  data: PreschoolIncidentCreate
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const response = await apiPost<PreschoolIncident>("/preschool/incidents", data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to create incident" };
  }
}

export async function getIncident(id: string): Promise<ActionResult<PreschoolIncident>> {
  try {
    const response = await apiGet<PreschoolIncident>(`/preschool/incidents/${id}`);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch incident" };
  }
}

export async function updateIncident(
  id: string, data: PreschoolIncidentUpdate
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const response = await apiPut<PreschoolIncident>(`/preschool/incidents/${id}`, data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update incident" };
  }
}

export async function notifyParentIncident(
  id: string
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const response = await apiPost<PreschoolIncident>(`/preschool/incidents/${id}/notify-parent`, {});
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to notify parent" };
  }
}

export async function resolveIncident(
  id: string, follow_up_notes?: string
): Promise<ActionResult<PreschoolIncident>> {
  try {
    const response = await apiPost<PreschoolIncident>(
      `/preschool/incidents/${id}/resolve`,
      { follow_up_notes }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to resolve incident" };
  }
}

// =========================
// Authorized Pickup Actions
// =========================

export async function listAuthorizedPickups(
  studentId: string
): Promise<ActionResult<AuthorizedPickup[]>> {
  try {
    const response = await apiGet<AuthorizedPickup[]>(
      `/preschool/students/${studentId}/authorized-pickups`
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch authorized pickups" };
  }
}

export async function addAuthorizedPickup(
  studentId: string, data: AuthorizedPickupCreate
): Promise<ActionResult<AuthorizedPickup>> {
  try {
    const response = await apiPost<AuthorizedPickup>(
      `/preschool/students/${studentId}/authorized-pickups`, data
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to add authorized pickup" };
  }
}

export async function updateAuthorizedPickup(
  id: string, data: AuthorizedPickupUpdate
): Promise<ActionResult<AuthorizedPickup>> {
  try {
    const response = await apiPut<AuthorizedPickup>(`/preschool/authorized-pickups/${id}`, data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update authorized pickup" };
  }
}

export async function deleteAuthorizedPickup(id: string): Promise<ActionResult<void>> {
  try {
    await apiDelete(`/preschool/authorized-pickups/${id}`);
    return { success: true, data: undefined };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to delete authorized pickup" };
  }
}

// =========================
// Pickup Log Actions
// =========================

export async function recordPickup(
  data: PickupLogCreate
): Promise<ActionResult<PickupLog>> {
  try {
    const response = await apiPost<PickupLog>("/preschool/pickup-logs", data);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to record pickup" };
  }
}

export async function listPickupLogs(
  params?: { student_id?: string; class_id?: string; date_from?: string; date_to?: string }
): Promise<ActionResult<PickupLog[]>> {
  try {
    const searchParams = new URLSearchParams();
    if (params?.student_id) searchParams.set("student_id", params.student_id);
    if (params?.class_id) searchParams.set("class_id", params.class_id);
    if (params?.date_from) searchParams.set("date_from", params.date_from);
    if (params?.date_to) searchParams.set("date_to", params.date_to);
    const query = searchParams.toString();
    const response = await apiGet<PickupLog[]>(`/preschool/pickup-logs${query ? `?${query}` : ""}`);
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch pickup logs" };
  }
}

// =========================
// Allergy / Dietary Actions
// =========================

export async function getStudentDietaryRequirements(
  studentId: string
): Promise<ActionResult<DietaryRequirements | null>> {
  try {
    const response = await apiGet<DietaryRequirements | null>(
      `/preschool/students/${studentId}/dietary-requirements`
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch dietary requirements" };
  }
}

export async function updateDietaryRequirements(
  studentId: string, data: DietaryRequirements | null
): Promise<ActionResult<void>> {
  try {
    await apiPut(`/preschool/students/${studentId}/dietary-requirements`, {
      dietary_requirements: data,
    });
    return { success: true, data: undefined };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to update dietary requirements" };
  }
}

export async function getClassAllergyAlerts(
  classId: string
): Promise<ActionResult<AllergyAlertResponse[]>> {
  try {
    const response = await apiGet<AllergyAlertResponse[]>(
      `/preschool/allergy-alerts?class_id=${classId}`
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch allergy alerts" };
  }
}
```

---

## 3.3 AllergyAlert Component

**File:** `frontend/components/preschool/AllergyAlert.tsx`

**Purpose:** Banner component shown at the top of the daily log form when a student has allergies or dietary restrictions.

**Props:**
```typescript
interface AllergyAlertProps {
  alerts: AllergyAlertResponse[];
  selectedStudentId?: string;
}
```

**Behavior:**
- If `selectedStudentId` is set, show only that student's alert
- If not set, show all alerts (class-wide view)
- Uses `Alert` component from shadcn/ui with `variant="destructive"` for severe allergies, `variant="warning"` for moderate
- Displays allergen name, severity badge, reaction, and medication
- Collapsible for class-wide view (shows count, expandable)

**UI elements:**
- `AlertTriangle` icon from lucide-react
- Severity badges: `Badge variant="destructive"` for severe, `Badge variant="secondary"` for moderate/mild
- Medication info highlighted with pill icon

---

## 3.4 DietaryRequirementsForm Component

**File:** `frontend/components/preschool/DietaryRequirementsForm.tsx`

**Purpose:** Form for adding/editing structured dietary requirements for a student. Used in student detail page's preschool section.

**Props:**
```typescript
interface DietaryRequirementsFormProps {
  studentId: string;
  initialData?: DietaryRequirements;
  onSave: (data: DietaryRequirements) => void;
  isSaving?: boolean;
}
```

**UI structure:**
- **Allergies section:** Dynamic list of allergy entries
  - Each entry: allergen (Input), severity (Select: mild/moderate/severe), reaction (Input), medication (Input)
  - "Add Allergy" button to add new entry
  - Remove button (X) on each entry
- **Dietary Restrictions section:** Multi-select or checkbox group
  - Common options: vegetarian, vegan, halal, kosher, gluten-free, lactose-free, nut-free
  - "Other" option with custom text input
- **Notes section:** Textarea for additional dietary notes
- **Save button** with loading state

---

## 3.5 IncidentForm Component

**File:** `frontend/components/preschool/IncidentForm.tsx`

**Purpose:** Dialog/sheet for creating and editing preschool incidents.

**Props:**
```typescript
interface IncidentFormProps {
  incident?: PreschoolIncident;  // If provided, edit mode
  students: Student[];           // Filtered to preschool levels
  onSubmit: (data: PreschoolIncidentCreate | PreschoolIncidentUpdate) => Promise<void>;
  onCancel: () => void;
  isSaving?: boolean;
}
```

**Form fields:**
- Student select (ComboBox, disabled in edit mode)
- Incident type select: Accident, Illness, Behavioral, Allergic Reaction, Other
- Severity select: Minor (green), Moderate (amber), Serious (red)
- Date picker (defaults to today)
- Time input (optional)
- Location input (optional, e.g., "Playground", "Classroom 2")
- Description textarea (required, min 10 chars)
- Action taken textarea (optional)
- First aid given checkbox
- Medical attention required checkbox
- Witnesses: dynamic list of text inputs
- Follow-up notes textarea (edit mode only)

**Validation:** React Hook Form + Zod schema matching the backend validation.

---

## 3.6 IncidentTimeline Component

**File:** `frontend/components/preschool/IncidentTimeline.tsx`

**Purpose:** Visual status workflow display for a single incident.

**Props:**
```typescript
interface IncidentTimelineProps {
  incident: PreschoolIncident;
}
```

**UI:** Horizontal or vertical stepper showing the 4 status states:
- **Reported** → **Reviewed** → **Parent Notified** → **Resolved**
- Current status highlighted, past statuses marked with checkmark
- Timestamps shown below each completed step
- User names (if available) below timestamps

Uses shadcn/ui stepper pattern or custom timeline with circles and connecting lines.

---

## 3.7 Incidents Page

**File:** `frontend/app/(dashboard)/preschool/incidents/page.tsx`

**Component:** `IncidentsManager` (client component with `"use client"`)

**UI structure:**
1. **Header:** "Incident Reports" title + "Report Incident" button
2. **Filters row:**
   - Class select (filtered to preschool levels)
   - Status filter: All, Reported, Reviewed, Parent Notified, Resolved
   - Severity filter: All, Minor, Moderate, Serious
   - Date range picker
3. **Stats cards** (4 cards, md:grid-cols-4):
   - Total incidents (this term)
   - Open incidents (not resolved)
   - Serious incidents
   - Avg. resolution time
4. **Incidents table** (DataTable pattern):
   - Columns: Date, Student, Type (with icon), Severity (with colored badge), Status (with badge), Actions
   - Row click → expand to show IncidentTimeline + detail fields
   - Action buttons: View/Edit, Notify Parent, Resolve
5. **Create/Edit dialog:** Uses IncidentForm component

**Data flow:**
- On mount: fetch classes (preschool only), then fetch incidents
- Class change → refetch incidents with class_id filter
- After create/edit → refetch incident list

---

## 3.8 AuthorizedPickupList Component

**File:** `frontend/components/preschool/AuthorizedPickupList.tsx`

**Purpose:** Manage authorized pickup persons for a specific student.

**Props:**
```typescript
interface AuthorizedPickupListProps {
  studentId: string;
}
```

**UI structure:**
- Card list of authorized persons showing:
  - Photo (or avatar placeholder)
  - Full name
  - Phone number
  - Relationship
  - Active/Inactive badge
  - Edit and Delete buttons
- "Add Person" button → opens dialog with form fields:
  - Full name (required)
  - Phone (required)
  - Relationship (optional)
  - Notes (optional)
  - Photo upload (optional, uses existing media upload)
  - ID document upload (optional)
- Edit dialog: same form, pre-populated
- Delete: confirmation dialog, soft-deletes

---

## 3.9 PickupLogForm Component

**File:** `frontend/components/preschool/PickupLogForm.tsx`

**Purpose:** Record a student pickup event.

**Props:**
```typescript
interface PickupLogFormProps {
  students: Student[];
  guardians: Map<string, Guardian[]>;        // studentId → guardians (with can_pickup)
  authorizedPickups: Map<string, AuthorizedPickup[]>;  // studentId → authorized
  onSubmit: (data: PickupLogCreate) => Promise<void>;
  isSaving?: boolean;
}
```

**Form flow:**
1. Select student (ComboBox)
2. Select pickup person type: "Guardian" or "Authorized Person"
3. If Guardian: show dropdown of guardians with `can_pickup=true` for selected student
4. If Authorized Person: show dropdown of active authorized pickups for selected student
5. Pickup time (defaults to current time)
6. Notes (optional)
7. Submit button

---

## 3.10 Pickups Page

**File:** `frontend/app/(dashboard)/preschool/pickups/page.tsx`

**Component:** `PickupsManager` (client component)

**UI structure:** Tabs component with 2 tabs:

**Tab 1: "Record Pickup"**
- Class select (preschool levels)
- PickupLogForm component
- Recent pickups table (today's pickups for selected class):
  - Columns: Time, Student, Picked Up By, Type, Verified By

**Tab 2: "Authorized Persons"**
- Class select → Student select (ComboBox)
- AuthorizedPickupList for selected student
- Also show guardians with `can_pickup` status (read-only display)

---

## 3.11 Sidebar Navigation Update

**File:** `frontend/components/dashboard/app-sidebar.tsx`

Add under the existing "Preschool" menu group, after "Daily Logs":

```typescript
{
  title: "Incidents",
  url: "/preschool/incidents",
  icon: AlertTriangle,  // from lucide-react
},
{
  title: "Pickups",
  url: "/preschool/pickups",
  icon: UserCheck,  // from lucide-react
},
```

**Note:** Only show these items when the user has `preschool.read` permission. Follow the existing sidebar permission filtering pattern.

---

## 3.12 Daily Log Form Update

**File:** `frontend/app/(dashboard)/preschool/daily-logs/page.tsx`

Modify the existing `DailyLogsManager` component:

1. When a class is selected, call `getClassAllergyAlerts(classId)` to fetch allergy data
2. When a student is selected, check if they have allergies in the alerts list
3. If yes, render `<AllergyAlert alerts={alerts} selectedStudentId={selectedStudentId} />` at the top of the form, above the arrival/departure section
4. The alert should be dismissible (collapsed state) but visible by default

---

## 3.13 Configuration Settings Update

**File:** `frontend/components/preschool/ConfigurationSettings.tsx`

Add new toggle cards in the settings section:

```typescript
// New settings to add alongside existing ones:
{
  key: "incident_tracking_enabled",
  label: "Incident Tracking",
  description: "Enable incident/accident reporting and tracking",
  icon: AlertTriangle,
},
{
  key: "pickup_verification_enabled",
  label: "Pickup Verification",
  description: "Enable authorized pickup person management and logging",
  icon: UserCheck,
},
{
  key: "allergy_alerts_enabled",
  label: "Allergy Alerts",
  description: "Show allergy alerts when recording daily activities",
  icon: Heart,
},
```

These keys are stored in the `schools.preschool_settings` JSONB column via the existing settings save mechanism.

---

## 3.14 Component Index Update

**File:** `frontend/components/preschool/index.ts`

Add exports for all new components:

```typescript
export { AllergyAlert } from "./AllergyAlert";
export { DietaryRequirementsForm } from "./DietaryRequirementsForm";
export { IncidentForm } from "./IncidentForm";
export { IncidentTimeline } from "./IncidentTimeline";
export { AuthorizedPickupList } from "./AuthorizedPickupList";
export { PickupLogForm } from "./PickupLogForm";
```

---

## UI/UX Conventions to Follow

1. **Responsive design:** All new pages use `grid-cols-1 md:grid-cols-2` for form layouts, `hidden sm:table-cell` for non-essential table columns on mobile
2. **Dialogs:** Use `max-sm:` prefix for full-screen on mobile (existing pattern from `dialog.tsx`)
3. **Loading states:** Skeleton placeholders while data loads
4. **Toast notifications:** Success/error toasts using existing toast infrastructure
5. **Color scheme:** Follow GitHub Primer theme colors; severity badges use semantic colors (green=minor, amber=moderate, red=serious)
6. **Icons:** Use lucide-react icons consistently
7. **Date format:** DD/MM/YYYY per CLAUDE.md conventions
8. **Phone format:** +233 XX XXX XXXX for Ghana numbers
