# Phase 2B: Setup Wizard Improvements

**Complexity:** Medium
**Requirements:** TS-004
**Dependencies:** Phase 2A (GES subject template endpoint)
**Estimated effort:** 2 days

---

## Summary

Enhance the existing setup wizard with two new steps (Terms, Subjects) and improve the Complete step with actionable next-steps links. Update the setup-check criteria to include terms and subjects.

---

## Current State

### Existing Steps (in `frontend/components/setup-wizard/setup-wizard.tsx`):
1. **Welcome** — Introduction
2. **School Profile** — Motto, description, phone, email, address, city
3. **Academic Year** — Name, start date, end date
4. **Classes** — Add/remove classes with sections
5. **Complete** — Success screen

### Current Setup-Check Trigger (`frontend/components/setup-wizard/setup-check.tsx`):
```typescript
const needsSetup = academicYears.length === 0 || classes.length === 0;
```

---

## Task 1: Add Terms/Semesters Step

Insert between "Academic Year" and "Classes" steps.

### File: `frontend/components/setup-wizard/setup-wizard.tsx`

**New step index: 4 (shift Classes to 5, Complete to 6)**

Updated steps array:
```typescript
const STEPS = [
  { id: "welcome", title: "Welcome" },
  { id: "school-profile", title: "School Profile" },
  { id: "academic-year", title: "Academic Year" },
  { id: "terms", title: "Terms" },          // NEW
  { id: "classes", title: "Classes" },
  { id: "subjects", title: "Subjects" },     // NEW
  { id: "complete", title: "Complete" },
];
```

### Terms Step Component (inline in setup-wizard.tsx or extracted):

```tsx
function TermsStep({
  academicYearId,
  academicYearName,
  onComplete,
}: {
  academicYearId: string;
  academicYearName: string;
  onComplete: () => void;
}) {
  // Pre-fill with 3 terms (Ghana standard)
  const [terms, setTerms] = useState([
    { name: "First Term", short_name: "T1", sequence: 1, start_date: "", end_date: "" },
    { name: "Second Term", short_name: "T2", sequence: 2, start_date: "", end_date: "" },
    { name: "Third Term", short_name: "T3", sequence: 3, start_date: "", end_date: "" },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    try {
      for (const term of terms) {
        if (!term.start_date || !term.end_date) continue; // Skip empty terms

        const result = await createTerm({
          academic_year_id: academicYearId,
          name: term.name,
          short_name: term.short_name,
          sequence: term.sequence,
          start_date: term.start_date,
          end_date: term.end_date,
        });

        if (!result.success) {
          // Skip duplicates, fail on other errors
          if (!result.error?.includes("already exists")) {
            toast.error(`Failed to create ${term.name}: ${result.error}`);
          }
        }
      }

      toast.success("Terms created successfully");
      onComplete();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-medium">Set Up Terms</h3>
        <p className="text-sm text-muted-foreground">
          Define the terms for {academicYearName}. Ghana typically uses 3 terms.
        </p>
      </div>

      {terms.map((term, index) => (
        <Card key={index}>
          <CardContent className="pt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Term Name</Label>
                <Input
                  value={term.name}
                  onChange={(e) => {
                    const updated = [...terms];
                    updated[index].name = e.target.value;
                    setTerms(updated);
                  }}
                />
              </div>
              <div>
                <Label>Short Name</Label>
                <Input
                  value={term.short_name}
                  onChange={(e) => {
                    const updated = [...terms];
                    updated[index].short_name = e.target.value;
                    setTerms(updated);
                  }}
                />
              </div>
              <div>
                <Label>Start Date</Label>
                <Input
                  type="date"
                  value={term.start_date}
                  onChange={(e) => {
                    const updated = [...terms];
                    updated[index].start_date = e.target.value;
                    setTerms(updated);
                  }}
                />
              </div>
              <div>
                <Label>End Date</Label>
                <Input
                  type="date"
                  value={term.end_date}
                  onChange={(e) => {
                    const updated = [...terms];
                    updated[index].end_date = e.target.value;
                    setTerms(updated);
                  }}
                />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={() => setTerms([...terms, {
            name: `Term ${terms.length + 1}`,
            short_name: `T${terms.length + 1}`,
            sequence: terms.length + 1,
            start_date: "",
            end_date: "",
          }])}
        >
          Add Term
        </Button>
        {terms.length > 1 && (
          <Button
            variant="outline"
            onClick={() => setTerms(terms.slice(0, -1))}
          >
            Remove Last
          </Button>
        )}
      </div>

      <div className="flex justify-between">
        <Button variant="ghost" onClick={onComplete}>
          Skip for now
        </Button>
        <Button onClick={handleSubmit} disabled={loading}>
          {loading ? "Creating terms..." : "Create Terms & Continue"}
        </Button>
      </div>
    </div>
  );
}
```

**Dependencies:** Requires `createTerm` server action in `frontend/actions/academic.action.ts`. This should already exist — verify and add if missing:

```typescript
export async function createTerm(data: {
  academic_year_id: string;
  name: string;
  short_name?: string;
  sequence: number;
  start_date: string;
  end_date: string;
}): Promise<ActionResult<Term>> {
  try {
    const response = await apiPost<Term>("/academic/terms", data);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create term",
    };
  }
}
```

---

## Task 2: Add Subjects Step

Insert after "Classes" step.

### Subjects Step Component:

```tsx
function SubjectsStep({
  schoolType,
  onComplete,
}: {
  schoolType: string;
  onComplete: () => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-medium">Set Up Subjects</h3>
        <p className="text-sm text-muted-foreground">
          Load standard GES curriculum subjects for your school, or skip to add them later.
        </p>
      </div>

      {/* Reuses the SubjectTemplateSelector from Phase 2A */}
      <SubjectTemplateSelector
        schoolType={schoolType}
        onComplete={() => onComplete()}
      />

      <Button variant="ghost" onClick={onComplete} className="w-full">
        Skip — I'll add subjects later
      </Button>
    </div>
  );
}
```

**Import required:**
```typescript
import { SubjectTemplateSelector } from "@/components/academic/SubjectTemplateSelector";
```

---

## Task 3: Enhance Complete Step

Replace the current minimal "Complete" step with actionable next-steps:

```tsx
function CompleteStep() {
  return (
    <div className="space-y-6 text-center">
      <div>
        <CheckCircle2 className="mx-auto h-12 w-12 text-green-600" />
        <h3 className="mt-4 text-xl font-medium">Setup Complete!</h3>
        <p className="mt-2 text-muted-foreground">
          Your school is ready. Here are your recommended next steps:
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-left">
        <NextStepCard
          icon={<Users className="h-5 w-5" />}
          title="Import Students"
          description="Upload student data from CSV/Excel"
          href="/students?import=true"
        />
        <NextStepCard
          icon={<UserPlus className="h-5 w-5" />}
          title="Add Staff"
          description="Create teacher and staff accounts"
          href="/staff"
        />
        <NextStepCard
          icon={<DollarSign className="h-5 w-5" />}
          title="Fee Structures"
          description="Set up tuition and fee schedules"
          href="/finance/fee-structures"
        />
        <NextStepCard
          icon={<Settings className="h-5 w-5" />}
          title="School Settings"
          description="Logo, branding, and preferences"
          href="/settings/school"
        />
      </div>

      <Button asChild className="mt-4">
        <Link href="/dashboard">Go to Dashboard</Link>
      </Button>
    </div>
  );
}

function NextStepCard({
  icon,
  title,
  description,
  href,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link href={href}>
      <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
        <CardContent className="pt-4 flex items-start gap-3">
          <div className="text-muted-foreground">{icon}</div>
          <div>
            <p className="font-medium text-sm">{title}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
```

---

## Task 4: Update Setup-Check Criteria

### File: `frontend/components/setup-wizard/setup-check.tsx`

Update the check to also verify terms and subjects exist:

```typescript
// Current:
const needsSetup = academicYears.length === 0 || classes.length === 0;

// Updated:
const needsSetup =
  academicYears.length === 0 ||
  classes.length === 0 ||
  terms.length === 0 ||
  subjects.length === 0;
```

**Add API calls to fetch terms and subjects:**

```typescript
const [terms, setTerms] = useState<Term[]>([]);
const [subjects, setSubjects] = useState<Subject[]>([]);

useEffect(() => {
  // Existing fetches for academicYears and classes...

  // Add:
  getTerms().then((result) => {
    if (result.success) setTerms(result.data);
  });

  getSubjects().then((result) => {
    if (result.success) setSubjects(result.data);
  });
}, []);
```

**Ensure server actions exist** for `getTerms()` and `getSubjects()` in `frontend/actions/academic.action.ts`. These likely already exist — verify.

---

## Task 5: Pass Context Between Steps

The wizard needs to pass data between steps:
- Academic Year step creates an academic year → pass its `id` to Terms step
- School type is needed by Subjects step

### State Management in Setup Wizard:

```typescript
const [createdAcademicYear, setCreatedAcademicYear] = useState<{
  id: string;
  name: string;
} | null>(null);

// In Academic Year step's onComplete callback:
const handleAcademicYearCreated = (year: AcademicYear) => {
  setCreatedAcademicYear({ id: year.id, name: year.name });
  nextStep();
};

// In Terms step rendering:
{step === 3 && createdAcademicYear && (
  <TermsStep
    academicYearId={createdAcademicYear.id}
    academicYearName={createdAcademicYear.name}
    onComplete={nextStep}
  />
)}

// School type for Subjects step — fetch from school profile or pass from context:
{step === 5 && (
  <SubjectsStep
    schoolType={schoolProfile?.school_type || "primary"}
    onComplete={nextStep}
  />
)}
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `frontend/components/setup-wizard/setup-wizard.tsx` | Add Terms step (index 3), Subjects step (index 5), enhanced Complete step (index 6). Update STEPS array. Add state for passing academic year ID between steps. |
| `frontend/components/setup-wizard/setup-check.tsx` | Add terms and subjects to `needsSetup` criteria. Add API calls for getTerms() and getSubjects(). |
| `frontend/actions/academic.action.ts` | Verify `createTerm()`, `getTerms()`, `getSubjects()` exist. Add if missing. |
| `frontend/components/academic/SubjectTemplateSelector.tsx` | Already created in Phase 2A — reused here. |

---

## Testing Checklist

- [ ] New school registration → wizard shows all 7 steps
- [ ] Terms step pre-fills 3 terms with Ghana naming convention
- [ ] Terms created successfully for the academic year
- [ ] Skip button works on Terms step
- [ ] Subjects step shows GES template selector
- [ ] For SHS schools: programme picker appears in Subjects step
- [ ] Skip button works on Subjects step
- [ ] Complete step shows 4 next-step cards with correct links
- [ ] Setup-check triggers wizard when terms=0 or subjects=0
- [ ] Existing schools with terms+subjects: wizard does NOT trigger
- [ ] Step navigation (back/next) works correctly with 7 steps
- [ ] Academic year ID correctly passed from Academic Year step to Terms step
