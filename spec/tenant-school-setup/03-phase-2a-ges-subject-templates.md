# Phase 2A: GES Curriculum Subject Templates

**Complexity:** Medium
**Requirements:** TS-015
**Dependencies:** None
**Estimated effort:** 2 days

---

## Summary

Create seed data for standard Ghana Education Service (GES) subjects across all school levels (preschool, primary, JHS, SHS). Provide an endpoint to auto-populate subjects from these templates during onboarding or later in academic settings.

---

## Task 1: GES Subject Seed Data

### New File: `backend/app/data/ges_subjects.py`

```python
"""
Standard Ghana Education Service (GES) curriculum subjects.

Based on the 2019 revised GES curriculum standards.
Organized by school level with subject code, name, and category.

Usage:
    from app.data.ges_subjects import GES_SUBJECTS
    subjects = GES_SUBJECTS["primary"]  # All primary school subjects
"""

GES_SUBJECTS: dict[str, list[dict]] = {
    # =========================================================================
    # PRESCHOOL (Creche, Nursery, KG)
    # =========================================================================
    "preschool": [
        {"name": "Language and Literacy", "code": "LL", "category": "core"},
        {"name": "Mathematics", "code": "MATH", "category": "core"},
        {"name": "Creative Arts", "code": "CA", "category": "core"},
        {"name": "Physical Development", "code": "PD", "category": "core"},
        {"name": "Our World Our People", "code": "OWOP", "category": "core"},
    ],

    # =========================================================================
    # PRIMARY (Class 1-6)
    # =========================================================================
    "primary": [
        {"name": "English Language", "code": "ENG", "category": "core"},
        {"name": "Mathematics", "code": "MATH", "category": "core"},
        {"name": "Science", "code": "SCI", "category": "core"},
        {"name": "Social Studies", "code": "SS", "category": "core"},
        {"name": "Computing", "code": "COMP", "category": "core"},
        {"name": "French", "code": "FRE", "category": "core"},
        {"name": "Ghanaian Language", "code": "GHL", "category": "core"},
        {"name": "Religious and Moral Education", "code": "RME", "category": "core"},
        {"name": "Creative Arts and Design", "code": "CAD", "category": "core"},
        {"name": "Physical Education", "code": "PE", "category": "core"},
        {"name": "Career Technology", "code": "CT", "category": "core"},
    ],

    # =========================================================================
    # JHS (JHS 1-3)
    # =========================================================================
    "jhs": [
        {"name": "English Language", "code": "ENG", "category": "core"},
        {"name": "Mathematics", "code": "MATH", "category": "core"},
        {"name": "Integrated Science", "code": "ISCI", "category": "core"},
        {"name": "Social Studies", "code": "SS", "category": "core"},
        {"name": "Computing", "code": "COMP", "category": "core"},
        {"name": "French", "code": "FRE", "category": "core"},
        {"name": "Ghanaian Language", "code": "GHL", "category": "core"},
        {"name": "Religious and Moral Education", "code": "RME", "category": "core"},
        {"name": "Creative Arts and Design", "code": "CAD", "category": "core"},
        {"name": "Career Technology", "code": "CT", "category": "core"},
        {"name": "Physical Education", "code": "PE", "category": "core"},
    ],

    # =========================================================================
    # SHS CORE (Required for all SHS students)
    # =========================================================================
    "shs_core": [
        {"name": "English Language", "code": "ENG", "category": "core"},
        {"name": "Core Mathematics", "code": "CMATH", "category": "core"},
        {"name": "Integrated Science", "code": "ISCI", "category": "core"},
        {"name": "Social Studies", "code": "SS", "category": "core"},
    ],
}

# SHS Elective Programmes — each programme has 4 elective subjects
SHS_ELECTIVE_PROGRAMMES: dict[str, list[dict]] = {
    "General Science": [
        {"name": "Elective Mathematics", "code": "EMATH", "category": "elective"},
        {"name": "Physics", "code": "PHY", "category": "elective"},
        {"name": "Chemistry", "code": "CHEM", "category": "elective"},
        {"name": "Biology", "code": "BIO", "category": "elective"},
    ],
    "General Arts": [
        {"name": "Literature in English", "code": "LIT", "category": "elective"},
        {"name": "Government", "code": "GOV", "category": "elective"},
        {"name": "Economics", "code": "ECON", "category": "elective"},
        {"name": "History", "code": "HIST", "category": "elective"},
    ],
    "Business": [
        {"name": "Business Management", "code": "BM", "category": "elective"},
        {"name": "Accounting", "code": "ACC", "category": "elective"},
        {"name": "Economics", "code": "ECON", "category": "elective"},
        {"name": "Elective Mathematics", "code": "EMATH", "category": "elective"},
    ],
    "Visual Arts": [
        {"name": "Graphic Design", "code": "GD", "category": "elective"},
        {"name": "Basketry", "code": "BKT", "category": "elective"},
        {"name": "Ceramics", "code": "CER", "category": "elective"},
        {"name": "Sculpture", "code": "SCL", "category": "elective"},
    ],
    "Home Economics": [
        {"name": "Food and Nutrition", "code": "FN", "category": "elective"},
        {"name": "Clothing and Textiles", "code": "CLT", "category": "elective"},
        {"name": "Management in Living", "code": "MIL", "category": "elective"},
        {"name": "General Knowledge in Art", "code": "GKA", "category": "elective"},
    ],
    "Agriculture": [
        {"name": "General Agriculture", "code": "AGRI", "category": "elective"},
        {"name": "Animal Husbandry", "code": "AH", "category": "elective"},
        {"name": "Crop Husbandry", "code": "CH", "category": "elective"},
        {"name": "Elective Mathematics", "code": "EMATH", "category": "elective"},
    ],
    "Technical": [
        {"name": "Technical Drawing", "code": "TD", "category": "vocational"},
        {"name": "Building Construction", "code": "BC", "category": "vocational"},
        {"name": "Woodwork", "code": "WW", "category": "vocational"},
        {"name": "Metalwork", "code": "MW", "category": "vocational"},
    ],
}

# Maps school_type → which subject lists to use
SCHOOL_TYPE_SUBJECT_MAP: dict[str, list[str]] = {
    "preschool": ["preschool"],
    "primary": ["primary"],
    "jhs": ["jhs"],
    "shs": ["shs_core"],  # SHS electives selected separately via programmes
    "basic": ["primary", "jhs"],                      # Primary + JHS combined
    "preschool_primary": ["preschool", "primary"],
    "basic_preschool": ["preschool", "primary", "jhs"],
    "basic_shs": ["preschool", "primary", "jhs", "shs_core"],
    "international": ["primary", "jhs", "shs_core"],  # Baseline — school customizes
    "technical": ["jhs", "shs_core"],                  # Plus Technical electives
}

# Applicable class levels per subject list (for the applicable_levels JSONB field)
LEVEL_MAPPING: dict[str, list[str]] = {
    "preschool": ["preschool", "creche", "nursery_1", "nursery_2", "kg_1", "kg_2"],
    "primary": ["primary", "primary_1", "primary_2", "primary_3", "primary_4", "primary_5", "primary_6"],
    "jhs": ["jhs", "jhs_1", "jhs_2", "jhs_3"],
    "shs_core": ["shs", "shs_1", "shs_2", "shs_3"],
}
```

---

## Task 2: Subject Template Service

### New File: `backend/app/services/academic/subject_template_service.py`

```python
"""
Service to initialize subjects from GES curriculum templates.

Idempotent: skips subjects that already exist (by code) for the tenant/school.
"""

import structlog
from uuid import UUID
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.ges_subjects import (
    GES_SUBJECTS,
    SHS_ELECTIVE_PROGRAMMES,
    SCHOOL_TYPE_SUBJECT_MAP,
    LEVEL_MAPPING,
)
from app.models.academic.subject_models import Subject, SubjectCategory

logger = structlog.get_logger()


class SubjectTemplateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def initialize_from_template(
        self,
        tenant_id: UUID,
        school_type: str,
        school_id: UUID | None = None,
        programmes: list[str] | None = None,
    ) -> dict:
        """
        Create standard GES subjects for a given school type.

        Args:
            tenant_id: Tenant UUID
            school_type: SchoolType value (e.g., "primary", "jhs", "shs", "basic")
            school_id: Optional school UUID (for chain tenants)
            programmes: SHS elective programme names (required for SHS schools)
                       e.g., ["General Science", "Business"]

        Returns:
            {"created": int, "skipped": int, "subjects": list[dict]}
        """
        # Determine which subject lists to use
        subject_keys = SCHOOL_TYPE_SUBJECT_MAP.get(school_type, [])
        if not subject_keys:
            raise ValueError(f"Unknown school type: {school_type}")

        # Collect all subjects to create
        subjects_to_create: list[dict] = []
        seen_codes: set[str] = set()

        for key in subject_keys:
            template_subjects = GES_SUBJECTS.get(key, [])
            applicable_levels = LEVEL_MAPPING.get(key, [])

            for subj in template_subjects:
                if subj["code"] not in seen_codes:
                    subjects_to_create.append({
                        **subj,
                        "applicable_levels": applicable_levels,
                    })
                    seen_codes.add(subj["code"])

        # Add SHS elective programmes if applicable
        if school_type in ("shs", "basic_shs", "international") and programmes:
            shs_levels = LEVEL_MAPPING["shs_core"]
            for programme_name in programmes:
                programme_subjects = SHS_ELECTIVE_PROGRAMMES.get(programme_name, [])
                for subj in programme_subjects:
                    if subj["code"] not in seen_codes:
                        subjects_to_create.append({
                            **subj,
                            "applicable_levels": shs_levels,
                        })
                        seen_codes.add(subj["code"])

        # Check existing subjects (by code) to avoid duplicates
        existing_codes_query = select(Subject.code).where(
            and_(
                Subject.tenant_id == tenant_id,
                Subject.deleted_at.is_(None),
            )
        )
        if school_id:
            existing_codes_query = existing_codes_query.where(Subject.school_id == school_id)

        result = await self.db.execute(existing_codes_query)
        existing_codes = {row[0] for row in result.all()}

        # Create subjects
        created = 0
        skipped = 0
        created_subjects = []

        for subj_data in subjects_to_create:
            if subj_data["code"] in existing_codes:
                skipped += 1
                continue

            subject = Subject(
                tenant_id=tenant_id,
                school_id=school_id,
                name=subj_data["name"],
                code=subj_data["code"],
                category=SubjectCategory(subj_data["category"]),
                applicable_levels=subj_data["applicable_levels"],
                is_active=True,
            )
            self.db.add(subject)
            created += 1
            created_subjects.append({
                "name": subj_data["name"],
                "code": subj_data["code"],
                "category": subj_data["category"],
            })

        await self.db.flush()

        logger.info(
            "subjects_initialized_from_template",
            tenant_id=str(tenant_id),
            school_type=school_type,
            created=created,
            skipped=skipped,
            programmes=programmes,
        )

        return {
            "created": created,
            "skipped": skipped,
            "subjects": created_subjects,
        }

    def get_available_programmes(self) -> list[str]:
        """Return list of available SHS elective programme names."""
        return list(SHS_ELECTIVE_PROGRAMMES.keys())
```

---

## Task 3: API Endpoint

### File: `backend/app/api/v1/endpoints/academic/` (add to subjects endpoint file)

If subjects have their own file, add there. Otherwise add to the academic router.

```python
from app.services.academic.subject_template_service import SubjectTemplateService

@router.post(
    "/subjects/initialize-from-template",
    response_model=SubjectTemplateInitResponse,
    dependencies=[Depends(require_permissions("academic.*"))],
)
async def initialize_subjects_from_template(
    request: SubjectTemplateInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
    school_context: SchoolContext = Depends(get_school_context),
):
    """
    Initialize subjects from GES curriculum templates.

    Creates standard subjects for the school type. Idempotent:
    skips subjects that already exist (by code).

    For SHS schools, optionally specify elective programmes
    to include their subjects.
    """
    tenant_id = UUID(current_user["tenant_id"])
    service = SubjectTemplateService(db)

    result = await service.initialize_from_template(
        tenant_id=tenant_id,
        school_type=request.school_type,
        school_id=school_context.school_id,
        programmes=request.programmes,
    )

    return result


@router.get("/subjects/available-programmes")
async def get_available_programmes(
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Get list of available SHS elective programmes.

    Used by frontend to show programme selection when school_type is SHS.
    """
    service = SubjectTemplateService(None)  # No DB needed for this
    return {"programmes": service.get_available_programmes()}
```

### Schema

### File: `backend/app/schemas/academic.py`

Add:

```python
class SubjectTemplateInitRequest(BaseModel):
    school_type: str  # SchoolType value: "primary", "jhs", "shs", "basic", etc.
    programmes: list[str] | None = None  # SHS elective programme names

    @field_validator("school_type")
    @classmethod
    def validate_school_type(cls, v):
        from app.data.ges_subjects import SCHOOL_TYPE_SUBJECT_MAP
        if v not in SCHOOL_TYPE_SUBJECT_MAP:
            raise ValueError(
                f"Invalid school type '{v}'. "
                f"Valid options: {list(SCHOOL_TYPE_SUBJECT_MAP.keys())}"
            )
        return v

    @field_validator("programmes")
    @classmethod
    def validate_programmes(cls, v):
        if v:
            from app.data.ges_subjects import SHS_ELECTIVE_PROGRAMMES
            for p in v:
                if p not in SHS_ELECTIVE_PROGRAMMES:
                    raise ValueError(
                        f"Unknown programme '{p}'. "
                        f"Valid options: {list(SHS_ELECTIVE_PROGRAMMES.keys())}"
                    )
        return v


class SubjectTemplateInitResponse(BaseModel):
    created: int
    skipped: int
    subjects: list[dict]
```

---

## Task 4: Frontend Subject Template Selector

### New File: `frontend/components/academic/SubjectTemplateSelector.tsx`

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Loader2, CheckCircle2 } from "lucide-react";
import { initializeSubjectsFromTemplate } from "@/actions/academic.action";
import { toast } from "sonner";

interface SubjectTemplateSelectorProps {
  schoolType: string;
  onComplete?: (result: { created: number; skipped: number }) => void;
}

const SHS_PROGRAMMES = [
  "General Science",
  "General Arts",
  "Business",
  "Visual Arts",
  "Home Economics",
  "Agriculture",
  "Technical",
];

const isSHSType = (type: string) =>
  ["shs", "basic_shs", "international"].includes(type);

export function SubjectTemplateSelector({
  schoolType,
  onComplete,
}: SubjectTemplateSelectorProps) {
  const [selectedProgrammes, setSelectedProgrammes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ created: number; skipped: number } | null>(null);

  const handleToggleProgramme = (programme: string) => {
    setSelectedProgrammes((prev) =>
      prev.includes(programme)
        ? prev.filter((p) => p !== programme)
        : [...prev, programme]
    );
  };

  const handleInitialize = async () => {
    setLoading(true);
    try {
      const res = await initializeSubjectsFromTemplate(
        schoolType,
        isSHSType(schoolType) ? selectedProgrammes : undefined,
      );
      if (res.success) {
        setResult(res.data);
        toast.success(`Created ${res.data.created} subjects (${res.data.skipped} already existed)`);
        onComplete?.(res.data);
      } else {
        toast.error(res.error || "Failed to initialize subjects");
      }
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <Card>
        <CardContent className="pt-6 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-green-600" />
          <p className="mt-2 font-medium">
            {result.created} subjects created
            {result.skipped > 0 && ` (${result.skipped} already existed)`}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BookOpen className="h-5 w-5" />
          Load GES Standard Subjects
        </CardTitle>
        <CardDescription>
          Automatically create standard subjects based on the GES curriculum for your school type.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* SHS Programme Selection */}
        {isSHSType(schoolType) && (
          <div className="mb-4">
            <p className="text-sm font-medium mb-2">
              Select SHS elective programmes:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SHS_PROGRAMMES.map((programme) => (
                <label
                  key={programme}
                  className="flex items-center gap-2 rounded-md border p-3 cursor-pointer hover:bg-muted/50"
                >
                  <Checkbox
                    checked={selectedProgrammes.includes(programme)}
                    onCheckedChange={() => handleToggleProgramme(programme)}
                  />
                  <span className="text-sm">{programme}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <Button onClick={handleInitialize} disabled={loading} className="w-full">
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating subjects...
            </>
          ) : (
            "Initialize Subjects"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
```

### Server Action

### File: `frontend/actions/academic.action.ts`

Add:

```typescript
export async function initializeSubjectsFromTemplate(
  schoolType: string,
  programmes?: string[],
): Promise<ActionResult<{ created: number; skipped: number; subjects: any[] }>> {
  try {
    const response = await apiPost<{ created: number; skipped: number; subjects: any[] }>(
      "/academic/subjects/initialize-from-template",
      { school_type: schoolType, programmes },
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initialize subjects",
    };
  }
}
```

---

## Task 5: Integration with Academic Settings Page

### File: `frontend/app/(dashboard)/settings/academic/page.tsx`

Add the SubjectTemplateSelector above the existing subjects list, conditionally shown:

```tsx
import { SubjectTemplateSelector } from "@/components/academic/SubjectTemplateSelector";

// In the Subjects section, add before the subject list:
{subjects.length < 5 && (
  <SubjectTemplateSelector
    schoolType={school.school_type}
    onComplete={() => {
      // Refresh subjects list
      router.refresh();
    }}
  />
)}
```

This shows the template selector when there are fewer than 5 subjects, suggesting the school hasn't configured subjects yet.

---

## Testing Checklist

- [ ] Template data: verify all school types have correct subject lists
- [ ] `POST /academic/subjects/initialize-from-template` with school_type="primary" creates 11 subjects
- [ ] Same call again creates 0 (idempotent — all skipped)
- [ ] SHS with programmes=["General Science"] creates 4 core + 4 elective = 8 subjects
- [ ] Invalid school_type returns 422
- [ ] Invalid programme name returns 422
- [ ] Subjects created with correct `applicable_levels` JSONB
- [ ] Subjects scoped to correct tenant_id and school_id
- [ ] Frontend selector shows programme picker for SHS types only
- [ ] Frontend shows success state after initialization
- [ ] Academic settings page shows template button when <5 subjects
