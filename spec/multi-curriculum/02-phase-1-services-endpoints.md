# Phase 1: Services & Endpoints

**Phase:** MC-Sprint 1 (Foundation)
**Depends on:** Phase 1 Models & Migration (01)
**Parallel with:** Phase 1 Frontend (after endpoints are ready)

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 2.1 | Create CurriculumServiceError | `backend/app/services/curriculum/_shared.py` | 0.25d |
| 2.2 | Create built-in templates constants | `backend/app/services/curriculum/profile_service.py` | 1d |
| 2.3 | Create CurriculumProfileService | `backend/app/services/curriculum/profile_service.py` | 1.5d |
| 2.4 | Create AssessmentStructureService | `backend/app/services/curriculum/assessment_service.py` | 1d |
| 2.5 | Create curriculum Pydantic schemas | `backend/app/schemas/curriculum.py` | 1d |
| 2.6 | Create profile endpoints | `backend/app/api/v1/endpoints/curriculum/profiles.py` | 1d |
| 2.7 | Create assessment endpoints | `backend/app/api/v1/endpoints/curriculum/assessment.py` | 0.75d |
| 2.8 | Create report config endpoints | `backend/app/api/v1/endpoints/curriculum/profiles.py` | 0.5d |
| 2.9 | Create curriculum router + register | `backend/app/api/v1/endpoints/curriculum/__init__.py`, `router.py` | 0.25d |
| 2.10 | Modify ClassService for curriculum assignment | `backend/app/services/academic/class_service.py` | 0.5d |
| 2.11 | Add _resolve_curriculum_profile helper | `backend/app/services/exam/report_service.py` | 0.5d |
| 2.12 | Update academic schemas for curriculum_profile_id | `backend/app/schemas/academic.py` | 0.25d |

---

## 2.1 CurriculumServiceError

**File:** `backend/app/services/curriculum/_shared.py`

```python
"""Shared utilities for curriculum services."""


class CurriculumServiceError(Exception):
    """Base exception for curriculum service errors."""

    def __init__(self, message: str, code: str = "curriculum_error"):
        self.message = message
        self.code = code
        super().__init__(self.message)
```

**File:** `backend/app/services/curriculum/__init__.py`

```python
"""Curriculum services package."""

from app.services.curriculum.profile_service import CurriculumProfileService
from app.services.curriculum.assessment_service import AssessmentStructureService

__all__ = [
    "CurriculumProfileService",
    "AssessmentStructureService",
]
```

---

## 2.2 Built-in Curriculum Templates

**File:** `backend/app/services/curriculum/profile_service.py` (top section)

Templates are Python dictionaries, NOT database rows. Each template defines a complete `curriculum_profile` + `assessment_structure` + `assessment_components` + `report_card_config`.

```python
CURRICULUM_TEMPLATES = {
    "ges_standard": {
        "profile": {
            "name": "GES Standard",
            "curriculum_type": "ges",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": True,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": None,
        },
        "assessment": {
            "name": "GES Assessment Structure",
            "components": [
                {"type": "class_work", "name": "Class Work", "weight": 20, "seq": 1, "ca": True, "exam": False},
                {"type": "homework", "name": "Homework", "weight": 10, "seq": 2, "ca": True, "exam": False},
                {"type": "midterm", "name": "Midterm", "weight": 20, "seq": 3, "ca": True, "exam": False},
                {"type": "end_term", "name": "End of Term", "weight": 50, "seq": 4, "ca": False, "exam": True},
            ],
        },
        "report_config": {
            "template_key": "ges",
            "show_position": True,
            "show_class_average": True,
            "show_subject_position": True,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "cambridge_igcse": {
        "profile": {
            "name": "Cambridge IGCSE",
            "curriculum_type": "cambridge",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "igcse"},
        },
        "assessment": {
            "name": "IGCSE Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "controlled_assessment", "name": "Controlled Assessment", "weight": 25, "seq": 2, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 50, "seq": 3, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "cambridge_a_level": {
        "profile": {
            "name": "Cambridge A-Level",
            "curriculum_type": "cambridge",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_only",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "a_level"},
        },
        "assessment": {
            "name": "A-Level Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 20, "seq": 1, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 80, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "edexcel_igcse": {
        "profile": {
            "name": "Edexcel IGCSE",
            "curriculum_type": "edexcel",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "grade_and_score",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {"programme": "igcse"},
        },
        "assessment": {
            "name": "Edexcel Assessment Structure",
            "components": [
                {"type": "coursework", "name": "Coursework", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "external_exam", "name": "External Exam", "weight": 75, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "cambridge",  # Shares template with Cambridge
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": True,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "american_standard": {
        "profile": {
            "name": "American Standard",
            "curriculum_type": "american",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "gpa",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": True,
            "use_credits": True,
            "use_criterion_grading": False,
            "config": {
                "gpa_scale": 4.0,
                "weighted_gpa": True,
                "honor_roll_threshold": 3.5,
                "ap_weight_bonus": 1.0,
                "honors_weight_bonus": 0.5,
                "graduation_credits_required": 24,
            },
        },
        "assessment": {
            "name": "American Assessment Structure",
            "components": [
                {"type": "homework", "name": "Homework", "weight": 15, "seq": 1, "ca": False, "exam": False},
                {"type": "quiz", "name": "Quizzes", "weight": 15, "seq": 2, "ca": False, "exam": False},
                {"type": "test", "name": "Tests", "weight": 25, "seq": 3, "ca": False, "exam": False},
                {"type": "project", "name": "Projects", "weight": 15, "seq": 4, "ca": False, "exam": False},
                {"type": "final", "name": "Final Exam", "weight": 30, "seq": 5, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "american",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": True,
            "show_credits": True,
            "show_honor_roll": True,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "american_ap": {
        "profile": {
            "name": "American AP",
            "curriculum_type": "american",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "gpa",
            "show_position": False,
            "show_class_average": True,
            "use_gpa": True,
            "use_credits": True,
            "use_criterion_grading": False,
            "config": {
                "gpa_scale": 4.0,
                "weighted_gpa": True,
                "honor_roll_threshold": 3.5,
                "ap_weight_bonus": 1.0,
                "honors_weight_bonus": 0.5,
                "graduation_credits_required": 24,
            },
        },
        "assessment": {
            "name": "AP Assessment Structure",
            "components": [
                {"type": "participation", "name": "Participation", "weight": 10, "seq": 1, "ca": False, "exam": False},
                {"type": "homework", "name": "Homework", "weight": 15, "seq": 2, "ca": False, "exam": False},
                {"type": "test", "name": "Tests", "weight": 25, "seq": 3, "ca": False, "exam": False},
                {"type": "project", "name": "Projects", "weight": 20, "seq": 4, "ca": False, "exam": False},
                {"type": "final", "name": "Final Exam", "weight": 30, "seq": 5, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "american",
            "show_position": False,
            "show_class_average": True,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": True,
            "show_credits": True,
            "show_honor_roll": True,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "ib_myp": {
        "profile": {
            "name": "IB MYP",
            "curriculum_type": "ib",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "level",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": True,
            "config": {
                "ib_programme": "myp",
                "learner_profile_traits": [
                    "inquirers", "knowledgeable", "thinkers", "communicators",
                    "principled", "open-minded", "caring", "risk-takers",
                    "balanced", "reflective",
                ],
                "atl_skills": ["thinking", "communication", "social", "self-management", "research"],
            },
        },
        "assessment": {
            "name": "IB MYP Assessment Structure",
            "components": [
                {"type": "internal_assessment", "name": "Internal Assessment", "weight": 100, "seq": 1, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "ib",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": True,
            "show_atl_skills": True,
        },
    },

    "ib_dp": {
        "profile": {
            "name": "IB DP",
            "curriculum_type": "ib",
            "academic_calendar_type": "semesters",
            "periods_per_year": 2,
            "score_display_mode": "level",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": True,
            "config": {
                "ib_programme": "dp",
                "learner_profile_traits": [
                    "inquirers", "knowledgeable", "thinkers", "communicators",
                    "principled", "open-minded", "caring", "risk-takers",
                    "balanced", "reflective",
                ],
                "atl_skills": ["thinking", "communication", "social", "self-management", "research"],
                "max_total_points": 45,
                "bonus_points_max": 3,
                "passing_total": 24,
            },
        },
        "assessment": {
            "name": "IB DP Assessment Structure",
            "components": [
                {"type": "internal_assessment", "name": "Internal Assessment", "weight": 25, "seq": 1, "ca": False, "exam": False},
                {"type": "external_assessment", "name": "External Assessment", "weight": 75, "seq": 2, "ca": False, "exam": False, "external": True},
            ],
        },
        "report_config": {
            "template_key": "ib",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": True,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": True,
            "show_atl_skills": True,
        },
    },

    "french_bac": {
        "profile": {
            "name": "French Baccalaureate",
            "curriculum_type": "french",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "mention",
            "show_position": True,
            "show_class_average": True,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {
                "mention_thresholds": {
                    "tres_bien": 16,
                    "bien": 14,
                    "assez_bien": 12,
                    "passable": 10,
                },
                "max_score": 20,
                "coefficient_system": True,
            },
        },
        "assessment": {
            "name": "French Assessment Structure",
            "components": [
                {"type": "controle_continu", "name": "Controle Continu", "weight": 40, "seq": 1, "ca": False, "exam": False},
                {"type": "epreuve", "name": "Epreuve", "weight": 60, "seq": 2, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "french",
            "show_position": True,
            "show_class_average": True,
            "show_subject_position": True,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },

    "montessori": {
        "profile": {
            "name": "Montessori",
            "curriculum_type": "montessori",
            "academic_calendar_type": "terms",
            "periods_per_year": 3,
            "score_display_mode": "narrative",
            "show_position": False,
            "show_class_average": False,
            "use_gpa": False,
            "use_credits": False,
            "use_criterion_grading": False,
            "config": {
                "developmental_areas": ["practical_life", "sensorial", "language", "mathematics", "cultural"],
                "progress_levels": ["emerging", "developing", "proficient", "mastery"],
                "narrative_required": True,
            },
        },
        "assessment": {
            "name": "Montessori Assessment Structure",
            "components": [
                {"type": "observation", "name": "Observation", "weight": 40, "seq": 1, "ca": False, "exam": False},
                {"type": "portfolio", "name": "Portfolio", "weight": 30, "seq": 2, "ca": False, "exam": False},
                {"type": "narrative", "name": "Narrative Assessment", "weight": 30, "seq": 3, "ca": False, "exam": False},
            ],
        },
        "report_config": {
            "template_key": "montessori",
            "show_position": False,
            "show_class_average": False,
            "show_subject_position": False,
            "show_effort_grade": False,
            "show_predicted_grades": False,
            "show_gpa": False,
            "show_credits": False,
            "show_honor_roll": False,
            "show_learner_profile": False,
            "show_atl_skills": False,
        },
    },
}
```

---

## 2.3 CurriculumProfileService

**File:** `backend/app/services/curriculum/profile_service.py`

Follow the project pattern: class-based service with `__init__(self, db: AsyncSession)`, use `flush()/refresh()` not `commit()`.

### Methods

| Method | Purpose |
|--------|---------|
| `create_profile(tenant_id, school_id, data)` | Create curriculum profile |
| `get_profile(tenant_id, profile_id)` | Get single profile with structures + config |
| `list_profiles(tenant_id, school_id, curriculum_type, is_active)` | List profiles with filters |
| `update_profile(tenant_id, profile_id, data)` | Update profile |
| `delete_profile(tenant_id, profile_id)` | Soft delete (block if classes reference it) |
| `set_default_profile(tenant_id, profile_id)` | Unset existing default, set new one |
| `get_available_templates()` | Return list of built-in template keys/names |
| `create_from_template(tenant_id, school_id, template_key, name_override)` | Instantiate template into DB |

### Key Implementation Details

**`create_profile`:**
- **Feature flag check (REQUIRED):** Before creating, validate subscription tier allows the requested `curriculum_type`. Query the tenant's `subscription_plan` and `features` JSONB:
  - Starter: only `curriculum_type="ges"` allowed. Raise `CurriculumServiceError("Multi-curriculum not available on Starter plan", "plan_limit")` otherwise.
  - Professional: allow 1 non-GES profile. Count existing non-GES profiles; if >= 1, raise error.
  - Enterprise: unlimited.
  - Check `tenant.features.get("multi_curriculum", False)` for Professional, `tenant.features.get("multi_curriculum_dual", False)` for Enterprise.
- Validate `curriculum_type` is a valid enum value
- If `config` is provided, validate it against the curriculum type schema (use a simple dict-key check, not full JSON Schema — keep it lightweight)
- If `is_default = True`, unset any existing default for this school (`_unset_default_profile()`)
- Defense-in-depth: filter by `tenant_id` on all queries

**`update_profile`:**
- **Feature flag check (REQUIRED):** If `curriculum_type` is being changed from `ges` to a non-GES type, apply the same subscription tier validation as `create_profile()`. Changing from one non-GES type to another non-GES type does not count as a new profile for quota purposes.

**`set_default_profile`:**
- **Feature flag check (REQUIRED):** If the target profile has a non-GES `curriculum_type`, validate that the tenant's subscription allows non-GES profiles before setting it as default. This prevents a Starter-plan tenant from adopting a non-GES default via this endpoint.

> **NOTE:** `ClassService.update_class()` and `SchoolService.update_school()` MUST also enforce feature flag validation when setting `curriculum_profile_id` to a profile with a non-GES `curriculum_type`. These are separate mutation paths that bypass `CurriculumProfileService` but still gate access to multi-curriculum features.

**`delete_profile`:**
- Check for referencing classes: `SELECT COUNT(*) FROM classes WHERE curriculum_profile_id = :id AND deleted_at IS NULL`
- If any classes reference it, raise `CurriculumServiceError("Cannot delete profile referenced by active classes", "profile_in_use")`
- Soft delete only

**`create_from_template`:**
- **Feature flag check (REQUIRED):** Same subscription tier validation as `create_profile()` — check the template's `curriculum_type` against the tenant's plan before instantiating.
- Look up `template_key` in `CURRICULUM_TEMPLATES` dict
- If not found, raise `CurriculumServiceError("Unknown template", "invalid_template")`
- Create `CurriculumProfile` from template's `profile` dict
- Create `AssessmentStructure` from template's `assessment` dict
- Create N `AssessmentComponent` rows from template's `components` list
- Create `ReportCardConfig` from template's `report_config` dict
- Allow `name_override` to customize the profile name
- Return the created profile with all relationships loaded

---

## 2.4 AssessmentStructureService

**File:** `backend/app/services/curriculum/assessment_service.py`

### Methods

| Method | Purpose |
|--------|---------|
| `create_structure(tenant_id, profile_id, data)` | Create structure with components |
| `get_structure(tenant_id, structure_id)` | Get structure with components loaded |
| `get_structure_for_profile(tenant_id, profile_id, academic_year_id)` | Resolve active structure (year-specific or default) |
| `update_structure(tenant_id, structure_id, data)` | Update structure metadata |
| `add_component(tenant_id, structure_id, data)` | Add a component |
| `update_component(tenant_id, component_id, data)` | Update a component |
| `delete_component(tenant_id, component_id)` | Remove a component |
| `validate_structure(tenant_id, structure_id)` | Validate weights sum to 100 |

### Key Implementation Details

**Weight Validation:**
- Components within a structure MUST sum to exactly 100.00
- Validate on `create_structure` (if components provided) and `validate_structure`
- Also validate on `add_component`, `update_component`, `delete_component` — but only warn, don't block (school may be mid-edit)

**`get_structure_for_profile`:**
```python
async def get_structure_for_profile(
    self, tenant_id: uuid.UUID, profile_id: uuid.UUID,
    academic_year_id: uuid.UUID | None = None,
) -> AssessmentStructure | None:
    """
    Resolve the active assessment structure for a profile.
    Priority: year-specific > default (academic_year_id IS NULL).
    """
    # Try year-specific first
    if academic_year_id:
        stmt = (
            select(AssessmentStructure)
            .filter(
                AssessmentStructure.tenant_id == tenant_id,
                AssessmentStructure.curriculum_profile_id == profile_id,
                AssessmentStructure.academic_year_id == academic_year_id,
                AssessmentStructure.is_active == True,
            )
            .options(selectinload(AssessmentStructure.components))
        )
        result = await self.db.execute(stmt)
        structure = result.scalar_one_or_none()
        if structure:
            return structure

    # Fall back to default (NULL academic_year_id)
    stmt = (
        select(AssessmentStructure)
        .filter(
            AssessmentStructure.tenant_id == tenant_id,
            AssessmentStructure.curriculum_profile_id == profile_id,
            AssessmentStructure.academic_year_id.is_(None),
            AssessmentStructure.is_active == True,
        )
        .options(selectinload(AssessmentStructure.components))
    )
    result = await self.db.execute(stmt)
    return result.scalar_one_or_none()
```

---

## 2.5 Pydantic Schemas

**File:** `backend/app/schemas/curriculum.py`

### Profile Schemas

```python
class CurriculumProfileCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    curriculum_type: str = Field(
        ..., pattern="^(ges|cambridge|edexcel|american|ib|french|montessori|custom)$"
    )
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str = Field(
        default="terms", pattern="^(terms|semesters|quarters)$"
    )
    periods_per_year: int = Field(default=3, ge=1, le=6)
    score_display_mode: str = Field(default="grade_and_score")
    show_position: bool = True
    show_class_average: bool = True
    use_gpa: bool = False
    use_credits: bool = False
    use_criterion_grading: bool = False
    config: dict | None = None
    is_default: bool = False

    @field_validator("config")
    @classmethod
    def validate_config_size(cls, v):
        """Prevent oversized or deeply nested JSONB payloads."""
        if v is not None:
            import json
            serialized = json.dumps(v)
            if len(serialized) > 10240:
                raise ValueError("Config must be under 10KB")
            # Max nesting depth of 5
            def _check_depth(obj, depth=0):
                if depth > 5:
                    raise ValueError("Config nesting depth must not exceed 5")
                if isinstance(obj, dict):
                    for val in obj.values():
                        _check_depth(val, depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        _check_depth(item, depth + 1)
            _check_depth(v)
        return v


class CurriculumProfileUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str | None = Field(
        default=None, pattern="^(terms|semesters|quarters)$"
    )
    periods_per_year: int | None = Field(default=None, ge=1, le=6)
    score_display_mode: str | None = None
    show_position: bool | None = None
    show_class_average: bool | None = None
    use_gpa: bool | None = None
    use_credits: bool | None = None
    use_criterion_grading: bool | None = None
    config: dict | None = None
    is_active: bool | None = None


class CurriculumProfileResponse(BaseSchema):
    id: UUID
    name: str
    curriculum_type: str
    description: str | None = None
    grading_scale_id: UUID | None = None
    academic_calendar_type: str
    periods_per_year: int
    score_display_mode: str
    show_position: bool
    show_class_average: bool
    use_gpa: bool
    use_credits: bool
    use_criterion_grading: bool
    config: dict | None = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurriculumProfileDetailResponse(CurriculumProfileResponse):
    assessment_structure: "AssessmentStructureResponse | None" = None
    report_config: "ReportCardConfigResponse | None" = None


class CurriculumTemplateInfo(BaseSchema):
    key: str
    name: str
    curriculum_type: str
    description: str


class CreateFromTemplateRequest(BaseSchema):
    template_key: str = Field(..., min_length=1)
    name_override: str | None = Field(default=None, max_length=100)


class CurriculumProfileListResponse(BaseSchema):
    items: list[CurriculumProfileResponse]
    total: int
    page: int
    page_size: int
    pages: int
```

### Assessment Structure Schemas

```python
class AssessmentComponentCreate(BaseSchema):
    component_type: str
    name: str = Field(..., min_length=1, max_length=100)
    weight: Decimal = Field(..., ge=0, le=100)
    max_score: Decimal | None = None
    is_external: bool = False
    sequence: int = Field(default=1, ge=1)
    maps_to_ca: bool = False
    maps_to_exam: bool = False
    config: dict | None = None


class AssessmentComponentUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    weight: Decimal | None = Field(default=None, ge=0, le=100)
    max_score: Decimal | None = None
    is_external: bool | None = None
    sequence: int | None = Field(default=None, ge=1)
    maps_to_ca: bool | None = None
    maps_to_exam: bool | None = None
    config: dict | None = None


class AssessmentComponentResponse(BaseSchema):
    id: UUID
    component_type: str
    name: str
    weight: Decimal
    max_score: Decimal | None = None
    is_external: bool
    sequence: int
    maps_to_ca: bool
    maps_to_exam: bool
    config: dict | None = None
    created_at: datetime
    updated_at: datetime


class AssessmentStructureCreate(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    academic_year_id: UUID | None = None
    components: list[AssessmentComponentCreate] = []

    @field_validator("components")
    @classmethod
    def validate_weights_sum(cls, v):
        if v:
            total = sum(c.weight for c in v)
            if total != Decimal("100"):
                raise ValueError(
                    f"Component weights must sum to 100, got {total}"
                )
        return v


class AssessmentStructureResponse(BaseSchema):
    id: UUID
    curriculum_profile_id: UUID
    academic_year_id: UUID | None = None
    name: str
    description: str | None = None
    is_active: bool
    components: list[AssessmentComponentResponse] = []
    created_at: datetime
    updated_at: datetime


class ValidateStructureResponse(BaseSchema):
    is_valid: bool
    total_weight: Decimal
    message: str
```

### Report Card Config Schemas

```python
class ReportCardConfigUpdate(BaseSchema):
    template_key: str | None = None
    show_position: bool | None = None
    show_class_average: bool | None = None
    show_subject_position: bool | None = None
    show_effort_grade: bool | None = None
    show_predicted_grades: bool | None = None
    show_gpa: bool | None = None
    show_credits: bool | None = None
    show_honor_roll: bool | None = None
    show_learner_profile: bool | None = None
    show_atl_skills: bool | None = None
    custom_columns: dict | None = None
    header_text: str | None = None
    footer_text: str | None = None

    @field_validator("header_text", "footer_text")
    @classmethod
    def strip_html_tags(cls, v):
        """Prevent stored XSS — strip HTML tags from free-text fields.
        These fields are rendered in Jinja2 report templates. Even with
        autoescape=True, stripping at the schema level provides defense-in-depth."""
        if v is not None:
            import re
            v = re.sub(r"<[^>]+>", "", v)
        return v

    @field_validator("custom_columns")
    @classmethod
    def validate_custom_columns_size(cls, v):
        """Prevent oversized JSONB payloads."""
        if v is not None:
            import json
            if len(json.dumps(v)) > 10240:
                raise ValueError("Custom columns config must be under 10KB")
        return v


class ReportCardConfigResponse(BaseSchema):
    id: UUID
    curriculum_profile_id: UUID
    template_key: str
    show_position: bool
    show_class_average: bool
    show_subject_position: bool
    show_effort_grade: bool
    show_predicted_grades: bool
    show_gpa: bool
    show_credits: bool
    show_honor_roll: bool
    show_learner_profile: bool
    show_atl_skills: bool
    custom_columns: dict | None = None
    header_text: str | None = None
    footer_text: str | None = None
    created_at: datetime
    updated_at: datetime
```

---

## 2.6 Profile Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/profiles.py`

All endpoints require `require_permissions()` and `ValidatedUser`. Profile mutations require `curriculum.*` permissions (school_admin, chain_admin, platform_admin).

| Method | Path | Handler | Permissions | Rate Limit |
|--------|------|---------|-------------|------------|
| POST | `/curriculum/profiles` | `create_profile()` | `curriculum.create` | General (100/min) |
| GET | `/curriculum/profiles` | `list_profiles()` | `curriculum.read` | General (100/min) |
| GET | `/curriculum/profiles/templates` | `get_templates()` | `curriculum.read` | General (100/min) |
| POST | `/curriculum/profiles/from-template` | `create_from_template()` | `curriculum.create` | Bulk (10/min) |
| GET | `/curriculum/profiles/{profile_id}` | `get_profile()` | `curriculum.read` | General (100/min) |
| PUT | `/curriculum/profiles/{profile_id}` | `update_profile()` | `curriculum.update` | General (100/min) |
| DELETE | `/curriculum/profiles/{profile_id}` | `delete_profile()` | `curriculum.delete` | General (100/min) |
| POST | `/curriculum/profiles/{profile_id}/set-default` | `set_default()` | `curriculum.update` | General (100/min) |

### Endpoint Implementation Pattern

**IMPORTANT:** Use the project's dependency injection type aliases from `app/api/deps.py`, NOT raw `Depends()` calls:
- `DatabaseSession` (not `db: AsyncSession = Depends(get_db)`)
- `SchoolCtx` for school_id AND tenant_id — `SchoolCtx` already depends on `ValidatedUser` internally, so do NOT add a separate `user: ValidatedUser` parameter (that causes double-resolution of the same dependency)
- Permissions go in the decorator's `dependencies=`, NOT as endpoint params

```python
from app.api.deps import DatabaseSession, SchoolCtx

@router.post(
    "/profiles",
    response_model=CurriculumProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("curriculum.create"))],
)
async def create_profile(
    data: CurriculumProfileCreate,
    db: DatabaseSession,
    school: SchoolCtx,
):
    service = CurriculumProfileService(db)
    try:
        profile = await service.create_profile(
            data,
            tenant_id=school.tenant_id,
            school_id=school.school_id,
        )
        return profile
    except CurriculumServiceError as e:
        _handle_error(e)
```

### Error Handling — `_handle_error()` Helper

All curriculum endpoints MUST use a shared `_handle_error()` function (same pattern as the admissions module) instead of inline status-code logic:

```python
_STATUS_MAP = {
    "not_found": 404,
    "plan_limit": 403,
    "duplicate": 409,
    "weight_mismatch": 422,
    "profile_in_use": 409,
    "invalid_template": 422,
}

def _handle_error(e: CurriculumServiceError) -> None:
    raise HTTPException(
        status_code=_STATUS_MAP.get(e.code, 400),
        detail=e.message,
    )
```

### Search Safety — escape_ilike()

**All text-based ILIKE searches MUST use `escape_ilike()` from `app.utils.sanitize`.** This applies to profile name search in `list_profiles()`, and any future text filter on curriculum endpoints. Example:

```python
from app.utils.sanitize import escape_ilike

if search:
    safe = escape_ilike(search)
    query = query.where(CurriculumProfile.name.ilike(f"%{safe}%"))
```

### List Endpoint — Pagination Pattern

All list endpoints MUST return a `CurriculumProfileListResponse` (defined in Section 2.5 schemas) and accept `page: int = Query(1, ge=1)` and `page_size: int = Query(20, ge=1, le=100)` params.

---

## 2.7 Assessment Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/assessment.py`

| Method | Path | Handler | Permissions | Rate Limit |
|--------|------|---------|-------------|------------|
| POST | `/curriculum/profiles/{profile_id}/assessment-structures` | `create_structure()` | `curriculum.create` | General (100/min) |
| GET | `/curriculum/profiles/{profile_id}/assessment-structures` | `get_structure()` | `curriculum.read` | General (100/min) |
| PUT | `/curriculum/assessment-structures/{structure_id}` | `update_structure()` | `curriculum.update` | General (100/min) |
| DELETE | `/curriculum/assessment-structures/{structure_id}` | `delete_assessment_structure()` | `curriculum.delete` | General (100/min) |
| POST | `/curriculum/assessment-structures/{structure_id}/components` | `add_component()` | `curriculum.create` | General (100/min) |
| PUT | `/curriculum/assessment-components/{component_id}` | `update_component()` | `curriculum.update` | General (100/min) |
| DELETE | `/curriculum/assessment-components/{component_id}` | `delete_component()` | `curriculum.delete` | General (100/min) |
| POST | `/curriculum/assessment-structures/{structure_id}/validate` | `validate_structure()` | `curriculum.read` | General (100/min) |

**`DELETE /curriculum/assessment-structures/{structure_id}`:** Soft-deletes the assessment structure by setting `deleted_at`. Returns 204 No Content. Does NOT hard delete. If the structure is the only active structure for its profile, raise `CurriculumServiceError("Cannot delete the only assessment structure for this profile", "profile_in_use")` with HTTP 409.

---

## 2.8 Report Config Endpoints

**File:** `backend/app/api/v1/endpoints/curriculum/profiles.py` (same file as profile endpoints)

| Method | Path | Handler | Permissions | Rate Limit |
|--------|------|---------|-------------|------------|
| GET | `/curriculum/profiles/{profile_id}/report-config` | `get_report_config()` | `curriculum.read` | General (100/min) |
| PUT | `/curriculum/profiles/{profile_id}/report-config` | `update_report_config()` | `curriculum.update` | General (100/min) |

**Permissions:** GET requires `curriculum.read` (school_admin, chain_admin, platform_admin, academic_head, teacher). PUT requires `curriculum.update` (school_admin, chain_admin, platform_admin only). Both endpoints use `dependencies=[Depends(require_permissions(...))]`.

---

## 2.9 Curriculum Router

**File:** `backend/app/api/v1/endpoints/curriculum/__init__.py`

```python
"""Curriculum endpoints package."""

from fastapi import APIRouter

from .profiles import router as profiles_router
from .assessment import router as assessment_router

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])
router.include_router(profiles_router)
router.include_router(assessment_router)
```

**File:** `backend/app/api/v1/router.py` — Add:

```python
from app.api.v1.endpoints.curriculum import router as curriculum_router

api_router.include_router(curriculum_router)
```

---

## 2.10 Modify ClassService + Cross-Tenant FK Validation

**File:** `backend/app/services/academic/class_service.py`

Update `create_class()` and `update_class()` to accept and persist `curriculum_profile_id`.

- On `create_class()`: If `curriculum_profile_id` is provided, validate that it exists and belongs to the same tenant
- On `update_class()`: Same validation; additionally, if a class is switching from one profile to another mid-term, log a warning via `AuditService` (scores may need recalculation)

### CRITICAL: Cross-Tenant FK Validation for ALL Services

**PostgreSQL FK constraints bypass RLS.** This means a service that accepts a `curriculum_profile_id` from user input could reference a profile owned by a different tenant — the FK check succeeds because it runs as the table owner (bypassing RLS policies).

**Every service method that accepts a UUID referencing a tenant-scoped table MUST validate tenant ownership before using it.** This applies to:

#### Phase 1 Services

| Service | Method | FK Parameter | Validate Against |
|---------|--------|-------------|-----------------|
| `CurriculumProfileService` | `create_profile()` | `grading_scale_id` | `grading_scales.tenant_id` |
| `CurriculumProfileService` | `create_profile()` | `school_id` | `schools.tenant_id` |
| `CurriculumProfileService` | `update_profile()` | `grading_scale_id` | `grading_scales.tenant_id` |
| `AssessmentStructureService` | `create_structure()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `AssessmentStructureService` | `create_structure()` | `academic_year_id` | `academic_years.tenant_id` |
| `AssessmentStructureService` | `get_structure_for_profile()` | `academic_year_id` | `academic_years.tenant_id` |
| `ReportCardConfigService` | `update_report_config()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `ClassService` | `create_class()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `ClassService` | `update_class()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `SchoolService` | `update_school()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `StudentService` | `update_student()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |

#### Phase 2 Services

| Service | Method | FK Parameter | Validate Against |
|---------|--------|-------------|-----------------|
| `GradeEquivalencyService` | `create_mapping()` | `source_grading_scale_id` | `grading_scales.tenant_id` |
| `GradeEquivalencyService` | `create_mapping()` | `target_grading_scale_id` | `grading_scales.tenant_id` |
| `GradeEquivalencyService` | `create_mapping()` | `source_grade_id` | `grades.tenant_id` |
| `GradeEquivalencyService` | `create_mapping()` | `target_grade_id` | `grades.tenant_id` |
| `SubjectMappingService` | `create_mapping()` | `subject_id` | `subjects.tenant_id` |
| `SubjectMappingService` | `create_mapping()` | `curriculum_profile_id` | `curriculum_profiles.tenant_id` |
| `SubjectMappingService` | `create_mapping()` | `grading_scale_id` | `grading_scales.tenant_id` |

#### Phase 3 Services

| Service | Method | FK Parameter | Validate Against |
|---------|--------|-------------|-----------------|
| `ExternalExamRegistrationService` | `register_student()` | `student_id` | `students.tenant_id` |
| `ExternalExamRegistrationService` | `register_student()` | `class_section_id` | `class_sections.tenant_id` |
| `PredictedGradeService` | `create_prediction()` | `student_id` | `students.tenant_id` |
| `PredictedGradeService` | `create_prediction()` | `subject_id` | `subjects.tenant_id` |
| `PredictedGradeService` | `create_prediction()` | `predicted_by` | `users.tenant_id` |
| `CreditService` | `award_credit()` | `student_id` | `students.tenant_id` |
| `CreditService` | `award_credit()` | `subject_id` | `subjects.tenant_id` |
| `CreditService` | `award_credit()` | `term_id` | `terms.tenant_id` |
| `CreditService` | `award_credit()` | `academic_year_id` | `academic_years.tenant_id` |

#### Mandatory Helper Pattern

**Every service in the curriculum package MUST use this helper for FK validation.** Call it for EVERY externally-supplied UUID that references a tenant-scoped table:

```python
async def _validate_tenant_fk(self, model_class, id: UUID, tenant_id: UUID) -> None:
    """Validate FK target belongs to same tenant. Call for EVERY externally-supplied UUID."""
    result = await self.db.execute(
        select(model_class.id).where(model_class.id == id, model_class.tenant_id == tenant_id)
    )
    if not result.scalar_one_or_none():
        raise CurriculumServiceError(f"{model_class.__name__} not found", "not_found")
```

Usage example in `create_profile()`:
```python
if data.grading_scale_id:
    await self._validate_tenant_fk(GradingScale, data.grading_scale_id, tenant_id)
await self._validate_tenant_fk(School, school_id, tenant_id)
```

**Legacy validation pattern** (for services outside the curriculum package that cannot use the helper):
```python
# Before using the FK
profile = await self.db.execute(
    select(CurriculumProfile.id).filter(
        CurriculumProfile.id == data.curriculum_profile_id,
        CurriculumProfile.tenant_id == tenant_id,  # CRITICAL
    )
)
if not profile.scalar_one_or_none():
    raise CurriculumServiceError("Profile not found", "not_found")
```

---

## 2.11 Add _resolve_curriculum_profile Helper

**File:** `backend/app/services/exam/report_service.py`

Add this helper method to `TermReportService`:

```python
async def _resolve_curriculum_profile(
    self,
    tenant_id: uuid.UUID,
    class_id: uuid.UUID,
    student_id: uuid.UUID | None = None,
) -> CurriculumProfile | None:
    """
    Resolve the curriculum profile for a class/student.

    Resolution chain:
    1. student.curriculum_profile_id (if student_id provided)
    2. class.curriculum_profile_id
    3. school.curriculum_profile_id (via class.school_id)
    4. None (fall back to GES default logic)
    """
    # 1. Check student override
    if student_id:
        stmt = select(Student.curriculum_profile_id).filter(
            Student.tenant_id == tenant_id,
            Student.id == student_id,
        )
        result = await self.db.execute(stmt)
        student_profile_id = result.scalar_one_or_none()
        if student_profile_id:
            return await self._load_profile(tenant_id, student_profile_id)

    # 2. Check class
    stmt = select(Class.curriculum_profile_id, Class.school_id).filter(
        Class.tenant_id == tenant_id,
        Class.id == class_id,
    )
    result = await self.db.execute(stmt)
    row = result.one_or_none()
    if row and row.curriculum_profile_id:
        return await self._load_profile(tenant_id, row.curriculum_profile_id)

    # 3. Check school
    if row and row.school_id:
        stmt = select(School.curriculum_profile_id).filter(
            School.tenant_id == tenant_id,
            School.id == row.school_id,
        )
        result = await self.db.execute(stmt)
        school_profile_id = result.scalar_one_or_none()
        if school_profile_id:
            return await self._load_profile(tenant_id, school_profile_id)

    # 4. No profile found
    return None


async def _load_profile(
    self, tenant_id: uuid.UUID, profile_id: uuid.UUID
) -> CurriculumProfile | None:
    """Load a curriculum profile with its grading scale."""
    stmt = (
        select(CurriculumProfile)
        .filter(
            CurriculumProfile.tenant_id == tenant_id,
            CurriculumProfile.id == profile_id,
            CurriculumProfile.is_active == True,
            CurriculumProfile.deleted_at.is_(None),
        )
        .options(selectinload(CurriculumProfile.grading_scale))
    )
    result = await self.db.execute(stmt)
    return result.scalar_one_or_none()
```

This helper is added in Phase 1 but only used by the score engine refactor in Phase 2. Adding it now avoids merge conflicts later.

---

## 2.12 Update Academic Schemas

**File:** `backend/app/schemas/academic.py`

Add `curriculum_profile_id` to class create/update/response schemas:

```python
# In ClassCreate:
curriculum_profile_id: UUID | None = None

# In ClassUpdate:
curriculum_profile_id: UUID | None = None

# In ClassResponse and ClassWithSectionsResponse:
curriculum_profile_id: UUID | None = None
```

Add permissions for curriculum operations. In `backend/app/api/deps.py` or the permissions mapping, add:

```python
"curriculum.create": ["school_admin", "chain_admin", "platform_admin"],
"curriculum.read": ["school_admin", "chain_admin", "platform_admin", "academic_head", "teacher"],
"curriculum.update": ["school_admin", "chain_admin", "platform_admin"],
"curriculum.delete": ["school_admin", "chain_admin", "platform_admin"],
```
