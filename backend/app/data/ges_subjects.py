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
