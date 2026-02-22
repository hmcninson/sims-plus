# Preschool Support Architecture

## Overview

This document outlines the comprehensive preschool support for SIMS Plus, using a hybrid approach that leverages existing infrastructure while adding preschool-specific models and features.

## Key Differences: Preschool vs Traditional Schools

| Aspect | Primary/JHS/SHS | Preschool |
|--------|-----------------|-----------|
| **Age Range** | 6-18 years | 2-5 years |
| **Assessment** | Scores, grades, exams | Developmental observations, milestones |
| **Grading** | A1-F9, percentages | Descriptive ratings, visual indicators |
| **Subjects** | Academic subjects | Learning/Developmental areas |
| **Reports** | Score tables, rankings | Narrative reports, skill checklists |
| **Exams** | Formal examinations | No formal exams |
| **Ranking** | Class positions | Not applicable |
| **Attendance** | Present/Absent | Present/Absent + mood, nap time, meals |

---

## Preschool Level Categories

```
Preschool Levels:
├── Creche (0-1 years)
├── Nursery 1 (2-3 years)
├── Nursery 2 (3-4 years)
├── Kindergarten 1 / KG1 (4-5 years)
└── Kindergarten 2 / KG2 (5-6 years)
```

---

## Database Models

### 1. Learning Areas (Replaces Subjects for Preschool)

```python
class LearningArea(Base):
    """
    Developmental/Learning areas for preschool assessment.
    Examples: Social-Emotional, Language & Literacy, Numeracy, etc.
    """
    __tablename__ = "learning_areas"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    name = Column(String(100))  # "Social-Emotional Development"
    code = Column(String(20))   # "SED"
    description = Column(Text)
    icon = Column(String(50))   # Icon identifier for UI
    color = Column(String(7))   # Hex color for visual representation
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Relationships
    skills = relationship("DevelopmentalSkill", back_populates="learning_area")
```

**Default Learning Areas:**
- Social-Emotional Development (SED)
- Language & Literacy (LL)
- Mathematical Thinking / Numeracy (MT)
- Scientific Exploration (SE)
- Physical Development - Gross Motor (PD-GM)
- Physical Development - Fine Motor (PD-FM)
- Creative Arts & Expression (CA)
- Personal Hygiene & Self-Care (PH)

### 2. Developmental Skills/Milestones

```python
class DevelopmentalSkill(Base):
    """
    Specific skills/milestones within a learning area.
    Example: Under "Language & Literacy" -> "Recognizes own name in print"
    """
    __tablename__ = "developmental_skills"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    learning_area_id = Column(UUID, ForeignKey("learning_areas.id"))

    name = Column(String(255))  # "Recognizes own name in print"
    description = Column(Text)
    age_range_months_min = Column(Integer)  # 36 months
    age_range_months_max = Column(Integer)  # 48 months
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # Which class levels this applies to
    applicable_levels = Column(JSONB)  # ["nursery_1", "nursery_2"]
```

### 3. Preschool Assessment Rating Scale

```python
class PreschoolRatingScale(Base):
    """
    Rating scales for preschool assessments.
    Example: 4-point scale (Emerging, Developing, Proficient, Advanced)
    """
    __tablename__ = "preschool_rating_scales"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    name = Column(String(100))  # "4-Point Developmental Scale"
    description = Column(Text)
    is_default = Column(Boolean, default=False)

class PreschoolRating(Base):
    """
    Individual ratings within a scale.
    """
    __tablename__ = "preschool_ratings"

    id = Column(UUID, primary_key=True)
    scale_id = Column(UUID, ForeignKey("preschool_rating_scales.id"))

    name = Column(String(50))       # "Proficient"
    short_code = Column(String(5))  # "P" or "3"
    description = Column(Text)      # "Child consistently demonstrates this skill"
    numeric_value = Column(Integer) # 3 (for calculations/sorting)
    color = Column(String(7))       # "#22c55e" (green)
    icon = Column(String(50))       # "star-filled" or emoji
    display_order = Column(Integer)
```

**Default Rating Scale (4-Point):**
| Rating | Code | Value | Color | Description |
|--------|------|-------|-------|-------------|
| Not Yet Observed | NYO | 0 | Gray | Skill not yet observed or too early |
| Emerging | E | 1 | Red | Beginning to show awareness |
| Developing | D | 2 | Yellow | Progressing, needs support |
| Proficient | P | 3 | Green | Consistently demonstrates |
| Advanced | A | 4 | Blue | Exceeds expectations |

### 4. Student Skill Assessment

```python
class StudentSkillAssessment(Base):
    """
    Records a student's progress on a specific skill.
    """
    __tablename__ = "student_skill_assessments"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    student_id = Column(UUID, ForeignKey("students.id"))
    skill_id = Column(UUID, ForeignKey("developmental_skills.id"))
    academic_year_id = Column(UUID, ForeignKey("academic_years.id"))
    term_id = Column(UUID, ForeignKey("terms.id"))

    rating_id = Column(UUID, ForeignKey("preschool_ratings.id"))
    observation_notes = Column(Text)  # Teacher's observation
    evidence_url = Column(String(500))  # Photo/video evidence (optional)

    assessed_by = Column(UUID, ForeignKey("users.id"))
    assessed_at = Column(DateTime)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    # Unique constraint: one assessment per student per skill per term
    __table_args__ = (
        UniqueConstraint('tenant_id', 'student_id', 'skill_id', 'term_id'),
    )
```

### 5. Progress Observations (Daily/Weekly)

```python
class ProgressObservation(Base):
    """
    General observations about a student's progress.
    Can be daily anecdotes, photos, or milestone achievements.
    """
    __tablename__ = "progress_observations"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    student_id = Column(UUID, ForeignKey("students.id"))
    learning_area_id = Column(UUID, ForeignKey("learning_areas.id"), nullable=True)

    observation_type = Column(String(20))  # "anecdote", "milestone", "photo", "incident"
    title = Column(String(255))
    description = Column(Text)
    observation_date = Column(Date)

    # Media attachments
    attachments = Column(JSONB)  # [{url, type, thumbnail}]

    # Visibility
    share_with_parents = Column(Boolean, default=True)
    is_highlight = Column(Boolean, default=False)  # Featured on student profile

    recorded_by = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime)
```

### 6. Daily Activity Log (Preschool-Specific)

```python
class DailyActivityLog(Base):
    """
    Daily log for preschool - tracks meals, naps, mood, activities.
    Parents love this feature!
    """
    __tablename__ = "daily_activity_logs"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    student_id = Column(UUID, ForeignKey("students.id"))
    log_date = Column(Date)

    # Arrival/Departure
    arrival_time = Column(Time)
    arrival_mood = Column(String(20))  # "happy", "tired", "upset", "excited"
    departure_time = Column(Time)
    departure_mood = Column(String(20))

    # Meals (JSONB for flexibility)
    meals = Column(JSONB)
    # Example: [
    #   {"type": "breakfast", "time": "08:30", "amount": "all", "notes": "Enjoyed porridge"},
    #   {"type": "snack", "time": "10:30", "amount": "some"},
    #   {"type": "lunch", "time": "12:30", "amount": "most", "notes": "Didn't eat vegetables"}
    # ]

    # Nap/Rest
    nap_start = Column(Time)
    nap_end = Column(Time)
    nap_quality = Column(String(20))  # "good", "restless", "didn't_sleep"

    # Bathroom (for younger children)
    diaper_changes = Column(Integer)
    potty_successes = Column(Integer)
    accidents = Column(Integer)

    # Activities participated in
    activities = Column(JSONB)  # ["outdoor_play", "art", "music", "story_time"]

    # General notes
    notes = Column(Text)
    highlights = Column(Text)  # Special moments to share with parents

    logged_by = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

### 7. Preschool Report Card

```python
class PreschoolReport(Base):
    """
    Term report for preschool students.
    Different structure from traditional report cards.
    """
    __tablename__ = "preschool_reports"

    id = Column(UUID, primary_key=True)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))

    student_id = Column(UUID, ForeignKey("students.id"))
    academic_year_id = Column(UUID, ForeignKey("academic_years.id"))
    term_id = Column(UUID, ForeignKey("terms.id"))
    class_id = Column(UUID, ForeignKey("classes.id"))

    # Attendance summary
    days_present = Column(Integer)
    days_absent = Column(Integer)
    total_school_days = Column(Integer)

    # Overall assessment by learning area (computed from skill assessments)
    learning_area_summaries = Column(JSONB)
    # Example: {
    #   "social_emotional": {"rating": "proficient", "summary": "..."},
    #   "language_literacy": {"rating": "developing", "summary": "..."},
    # }

    # Narrative sections
    overall_progress = Column(Text)       # General progress narrative
    strengths = Column(Text)              # What the child excels at
    areas_for_growth = Column(Text)       # Areas needing development
    teacher_recommendations = Column(Text) # Suggestions for parents

    # Special achievements/highlights
    highlights = Column(JSONB)  # ["Learned to tie shoes", "Made first friend"]

    # Goals for next term
    next_term_goals = Column(JSONB)

    # Teacher remarks
    class_teacher_remark = Column(Text)
    head_teacher_remark = Column(Text)

    # Status
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

---

## API Endpoints

### Learning Areas
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/learning-areas` | List all learning areas |
| POST | `/preschool/learning-areas` | Create learning area |
| GET | `/preschool/learning-areas/{id}` | Get learning area with skills |
| PUT | `/preschool/learning-areas/{id}` | Update learning area |
| DELETE | `/preschool/learning-areas/{id}` | Delete learning area |

### Developmental Skills
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/skills` | List skills (filter by learning area, level) |
| POST | `/preschool/skills` | Create skill |
| PUT | `/preschool/skills/{id}` | Update skill |
| DELETE | `/preschool/skills/{id}` | Delete skill |
| POST | `/preschool/skills/bulk` | Bulk create skills |

### Rating Scales
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/rating-scales` | List rating scales |
| POST | `/preschool/rating-scales` | Create rating scale with ratings |
| GET | `/preschool/rating-scales/{id}` | Get scale with all ratings |
| PUT | `/preschool/rating-scales/{id}` | Update scale |

### Student Assessments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/assessments` | List assessments (filter by student, term, area) |
| POST | `/preschool/assessments` | Create/update assessment |
| POST | `/preschool/assessments/bulk` | Bulk assess skills for a student |
| GET | `/preschool/assessments/student/{id}` | Get all assessments for a student |
| GET | `/preschool/assessments/class/{id}` | Get class assessment overview |

### Progress Observations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/observations` | List observations |
| POST | `/preschool/observations` | Create observation |
| PUT | `/preschool/observations/{id}` | Update observation |
| DELETE | `/preschool/observations/{id}` | Delete observation |
| GET | `/preschool/observations/student/{id}` | Get student's observations |

### Daily Activity Logs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/preschool/daily-logs` | List logs (filter by student, date range) |
| POST | `/preschool/daily-logs` | Create/update daily log |
| GET | `/preschool/daily-logs/student/{id}` | Get student's logs |
| GET | `/preschool/daily-logs/class/{id}/date/{date}` | Get class logs for a date |

### Preschool Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/preschool/reports/generate` | Generate reports for class/term |
| GET | `/preschool/reports` | List reports |
| GET | `/preschool/reports/{id}` | Get single report |
| PUT | `/preschool/reports/{id}` | Update report narratives |
| POST | `/preschool/reports/publish` | Publish reports |
| GET | `/preschool/reports/{id}/pdf` | Download PDF report |

---

## Frontend Pages

```
frontend/app/(dashboard)/preschool/
├── page.tsx                          # Preschool dashboard overview
├── learning-areas/
│   ├── page.tsx                      # Manage learning areas
│   └── [id]/
│       └── skills/page.tsx           # Manage skills for an area
├── assessments/
│   ├── page.tsx                      # Assessment entry (select class/term)
│   ├── class/[classId]/page.tsx      # Class assessment grid
│   └── student/[studentId]/page.tsx  # Individual student assessment
├── observations/
│   ├── page.tsx                      # All observations (feed view)
│   ├── new/page.tsx                  # Add new observation
│   └── student/[studentId]/page.tsx  # Student's observation timeline
├── daily-logs/
│   ├── page.tsx                      # Today's logs overview
│   ├── class/[classId]/page.tsx      # Class daily entry
│   └── student/[studentId]/page.tsx  # Student's log history
├── reports/
│   ├── page.tsx                      # Report management
│   ├── generate/page.tsx             # Generate reports
│   └── [id]/page.tsx                 # View/edit single report
└── settings/
    ├── rating-scales/page.tsx        # Manage rating scales
    └── default-skills/page.tsx       # Manage default skill sets
```

---

## UI Components

### 1. Skill Assessment Grid
```
┌─────────────────────────────────────────────────────────────┐
│ Social-Emotional Development                          [SED] │
├─────────────────────────────────────────────────────────────┤
│ Skill                          │ NYO │  E  │  D  │  P  │  A │
├────────────────────────────────┼─────┼─────┼─────┼─────┼────┤
│ Separates from caregiver       │     │     │     │ ●   │    │
│ Plays alongside other children │     │     │ ●   │     │    │
│ Shares toys when prompted      │     │ ●   │     │     │    │
│ Expresses emotions verbally    │     │     │     │ ●   │    │
└────────────────────────────────┴─────┴─────┴─────┴─────┴────┘
```

### 2. Daily Log Entry Form
```
┌─────────────────────────────────────────────────────────────┐
│ Daily Log: Kofi Mensah - January 9, 2026                    │
├─────────────────────────────────────────────────────────────┤
│ 😊 Arrival: 7:45 AM  Mood: [Happy ▼]                        │
│                                                             │
│ MEALS                                                       │
│ ┌──────────┬──────────┬──────────┬────────────────────────┐ │
│ │ Meal     │ Time     │ Amount   │ Notes                  │ │
│ ├──────────┼──────────┼──────────┼────────────────────────┤ │
│ │ Breakfast│ 8:30 AM  │ [All ▼]  │ Loved the pancakes    │ │
│ │ Snack    │ 10:30 AM │ [Some ▼] │                        │ │
│ │ Lunch    │ 12:30 PM │ [Most ▼] │ Didn't eat carrots    │ │
│ └──────────┴──────────┴──────────┴────────────────────────┘ │
│                                                             │
│ 😴 NAP: 1:00 PM - 2:30 PM  Quality: [Good ▼]               │
│                                                             │
│ 🚽 BATHROOM: Diaper changes: [2]  Potty: [1]  Accidents: [0]│
│                                                             │
│ 🎨 ACTIVITIES: [✓] Outdoor Play [✓] Art [ ] Music [✓] Story│
│                                                             │
│ 📝 Notes for Parents:                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Kofi made a beautiful finger painting today! He's       │ │
│ │ really enjoying the sensory activities.                 │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                             │
│                              [Cancel]  [Save & Next Student]│
└─────────────────────────────────────────────────────────────┘
```

### 3. Progress Timeline (Parent View)
```
┌─────────────────────────────────────────────────────────────┐
│ Ama's Progress Timeline                                     │
├─────────────────────────────────────────────────────────────┤
│ 📅 Jan 9, 2026                                              │
│ ├─ 📸 Photo: "Ama building with blocks"                     │
│ │   [Image thumbnail]                                       │
│ │   "Showed great problem-solving skills!"                  │
│ │                                                           │
│ ├─ 🌟 Milestone: "First time tying shoelaces!"             │
│ │   Learning Area: Fine Motor Skills                        │
│ │                                                           │
│ 📅 Jan 8, 2026                                              │
│ ├─ 📝 Daily Log                                             │
│ │   Arrival: 😊 Happy | Meals: Good | Nap: 1.5hrs          │
│ │                                                           │
│ ├─ 💬 Anecdote: "Helped a friend who was sad"              │
│ │   Learning Area: Social-Emotional                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Report Card Template (PDF)

```
╔══════════════════════════════════════════════════════════════╗
║           BRIGHT FUTURE ACADEMY                              ║
║           PRESCHOOL PROGRESS REPORT                          ║
╠══════════════════════════════════════════════════════════════╣
║ Student: Kofi Mensah          Class: KG1A                    ║
║ Term: First Term 2025-2026    Teacher: Mrs. Addo             ║
╠══════════════════════════════════════════════════════════════╣
║ ATTENDANCE                                                   ║
║ Days Present: 58/60  |  Days Absent: 2  |  Rate: 97%        ║
╠══════════════════════════════════════════════════════════════╣
║ DEVELOPMENTAL PROGRESS                                       ║
║                                                              ║
║ Social-Emotional Development                    [████████░░] ║
║ ● Separates from caregiver with ease                     P  ║
║ ● Plays cooperatively with peers                         D  ║
║ ● Manages emotions appropriately                         P  ║
║ Summary: Kofi has grown tremendously in his social skills.  ║
║ He now initiates play with classmates confidently.          ║
║                                                              ║
║ Language & Literacy                             [███████░░░] ║
║ ● Recognizes own name in print                           P  ║
║ ● Speaks in complete sentences                           P  ║
║ ● Identifies letters of the alphabet                     D  ║
║ Summary: Strong verbal communication. Working on letter     ║
║ recognition through fun activities.                         ║
║                                                              ║
║ [Additional learning areas...]                               ║
╠══════════════════════════════════════════════════════════════╣
║ HIGHLIGHTS THIS TERM                                         ║
║ ⭐ Learned to tie shoelaces independently                    ║
║ ⭐ Won the "Kindness Award" for helping classmates          ║
║ ⭐ Performed in the Christmas concert                        ║
╠══════════════════════════════════════════════════════════════╣
║ TEACHER'S NARRATIVE                                          ║
║ Kofi has had a wonderful first term! He comes to school     ║
║ with enthusiasm and a genuine curiosity about learning.      ║
║ His greatest strengths are his kind heart and creativity.   ║
║ We're working on building his confidence in group settings. ║
╠══════════════════════════════════════════════════════════════╣
║ GOALS FOR NEXT TERM                                          ║
║ • Continue developing letter recognition skills              ║
║ • Practice counting to 20                                    ║
║ • Encourage participation in group activities               ║
╠══════════════════════════════════════════════════════════════╣
║ Rating Key: NYO=Not Yet Observed, E=Emerging, D=Developing, ║
║            P=Proficient, A=Advanced                          ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Implementation Phases

### Phase 1: Foundation ✅ Completed
- [x] Add `is_preschool` flag to Class model (or use level_category)
- [x] Create LearningArea and DevelopmentalSkill models
- [x] Create PreschoolRatingScale and PreschoolRating models
- [x] Migration for new tables
- [x] Seed default learning areas and skills
- [x] Basic API endpoints

### Phase 2: Assessment Module ✅ Completed
- [x] StudentSkillAssessment model and API
- [x] Assessment entry UI (grid view)
- [x] Bulk assessment functionality
- [x] Class overview dashboard

### Phase 3: Observations & Daily Logs ✅ Completed
- [x] ProgressObservation model and API
- [x] DailyActivityLog model and API
- [x] Daily log entry UI
- [x] Observation feed UI
- [x] Photo upload integration

### Phase 4: Reports ✅ Completed
- [x] PreschoolReport model and API
- [x] Report generation logic
- [x] Report viewing UI
- [x] PDF generation with preschool template (WeasyPrint + Jinja2)
- [ ] Parent portal view

### Phase 4.5: Configuration Settings ✅ Completed
- [x] Add `preschool_settings` JSONB column to School model
- [x] Preschool configuration API endpoints (GET/PATCH `/schools/current/preschool-settings`)
- [x] Configuration UI in Settings > Preschool > Configuration tab
- [x] Toggle settings: enabled, daily_logs, meal_tracking, nap_tracking, diaper_tracking, potty_training, observation_photos, parent_daily_updates
- [x] Default rating scale selection

### Phase 5: Parent Communication
- [ ] Daily log notification to parents
- [ ] Observation sharing
- [ ] Report publishing workflow
- [ ] Mobile-friendly parent view

---

## Configuration Flags ✅ Implemented

Stored in `schools.preschool_settings` JSONB column:
```json
{
  "preschool_settings": {
    "enabled": true,
    "daily_logs_enabled": true,
    "meal_tracking": true,
    "nap_tracking": true,
    "diaper_tracking": true,
    "potty_training_tracking": true,
    "observation_photos_enabled": true,
    "parent_daily_updates": true,
    "default_rating_scale_id": "uuid"
  }
}
```

### API Endpoints
- `GET /schools/current/preschool-settings` - Get preschool configuration
- `PATCH /schools/current/preschool-settings` - Update preschool configuration

### Frontend Location
Settings > Preschool > Configuration tab

---

## Migration Strategy

For existing schools adding preschool:
1. Create preschool class levels (Nursery 1, Nursery 2, KG1, KG2)
2. Mark these classes with `level_category = "preschool"`
3. System detects preschool classes and shows appropriate UI
4. Regular classes continue to use traditional grading

---

## Notes

1. **Backward Compatibility**: Traditional schools unaffected - preschool features only show for preschool classes
2. **Data Sharing**: Some student data shared (name, DOB, guardians), assessments separate
3. **Teacher Training**: Different assessment paradigm - consider in-app guidance
4. **Parent Expectations**: Parents of preschoolers expect more frequent updates than older students
