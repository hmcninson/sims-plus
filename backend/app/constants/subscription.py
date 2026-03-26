"""
SIMS Plus - Subscription Plan Constants

Single source of truth for all plan limits, features, and pricing.
Referenced by SubscriptionService, endpoints, and frontend-facing APIs.

BILLING SCOPE: Subscription is at the TENANT level, not per-school.
For chain tenants (multi-school), the subscription covers ALL schools
under the tenant. Student/staff counts are aggregated across all schools.
Individual schools within a chain do not have separate subscriptions.

Pricing model: per-student, per-term (not flat rate).
See docs/SIMS_Plus_Subscription_Tiers.md for full details.
"""

from app.models.tenant import SubscriptionTier


# ============================================================================
# PLAN LIMITS
# ============================================================================

# 999999 sentinel for "unlimited" (C4 — avoids NULL on NOT NULL column)
UNLIMITED = 999999

# Student limits by tier
MAX_STUDENTS_BY_TIER = {
    SubscriptionTier.TRIAL: 100,
    SubscriptionTier.STARTER: 300,
    SubscriptionTier.PROFESSIONAL: UNLIMITED,
    SubscriptionTier.ENTERPRISE: UNLIMITED,
}

# User account limits by tier
MAX_USERS_BY_TIER = {
    SubscriptionTier.TRIAL: 10,
    SubscriptionTier.STARTER: 10,
    SubscriptionTier.PROFESSIONAL: 50,
    SubscriptionTier.ENTERPRISE: UNLIMITED,
}

# Staff limits by tier (separate from user accounts — a school can have
# many staff records but fewer user login accounts)
MAX_STAFF_BY_TIER = {
    SubscriptionTier.TRIAL: 20,
    SubscriptionTier.STARTER: 50,
    SubscriptionTier.PROFESSIONAL: UNLIMITED,
    SubscriptionTier.ENTERPRISE: UNLIMITED,
}

# Monthly SMS limits
SMS_LIMIT_BY_TIER = {
    SubscriptionTier.TRIAL: 50,
    SubscriptionTier.STARTER: 50,
    SubscriptionTier.PROFESSIONAL: 200,
    SubscriptionTier.ENTERPRISE: UNLIMITED,
}

# Storage limits in bytes
STORAGE_LIMIT_BY_TIER = {
    SubscriptionTier.TRIAL: 5 * 1024 * 1024 * 1024,        # 5 GB
    SubscriptionTier.STARTER: 5 * 1024 * 1024 * 1024,       # 5 GB
    SubscriptionTier.PROFESSIONAL: 20 * 1024 * 1024 * 1024,  # 20 GB
    SubscriptionTier.ENTERPRISE: 100 * 1024 * 1024 * 1024,   # 100 GB
}


# ============================================================================
# FEATURE AVAILABILITY BY PLAN
# ============================================================================
# True = included, False = not available, "addon" = purchasable add-on
#
# C2: Trial mirrors Starter features exactly for 90 days.
_STARTER_FEATURES = {
    "teachers_portal": True,
    "admissions_basic": True,
    "admissions_advanced": False,
    "admissions_full": False,
    "customizable_reports": False,
    "timetable": False,
    "grade_moderation": False,
    "scholarships": False,
    "vodafone_cash": False,
    "airteltigo_money": False,
    "parent_portal": False,
    "teachers_app": False,
    "mobile_apps": False,
    "push_notifications": False,
    "hr_leave": False,
    "hr_payroll": False,
    "boarding": False,
    "transport": False,
    "preschool": False,
    "multi_curriculum": False,
    "asset_inventory": False,
    "multi_school": False,
    "api_access": False,
    "custom_domain": False,
    "sso": False,
    "custom_roles": False,
}

PLAN_FEATURES = {
    # Trial mirrors Starter features for 90 days (C2)
    SubscriptionTier.TRIAL: {**_STARTER_FEATURES},
    SubscriptionTier.STARTER: {**_STARTER_FEATURES},
    SubscriptionTier.PROFESSIONAL: {
        "teachers_portal": True,
        "admissions_basic": True,
        "admissions_advanced": True,
        "admissions_full": False,
        "customizable_reports": True,
        "timetable": True,
        "grade_moderation": True,
        "scholarships": True,
        "vodafone_cash": True,
        "airteltigo_money": True,
        "parent_portal": True,
        "teachers_app": True,
        "mobile_apps": True,
        "push_notifications": True,
        "hr_leave": True,
        "hr_payroll": False,
        "boarding": "addon",      # GHS 300/term add-on
        "transport": "addon",     # GHS 200/term add-on
        "preschool": "addon",     # GHS 200/term add-on
        "multi_curriculum": False,
        "asset_inventory": False,
        "multi_school": False,
        "api_access": False,
        "custom_domain": False,
        "sso": False,
        "custom_roles": True,
    },
    SubscriptionTier.ENTERPRISE: {
        "teachers_portal": True,
        "admissions_basic": True,
        "admissions_advanced": True,
        "admissions_full": True,
        "customizable_reports": True,
        "timetable": True,
        "grade_moderation": True,
        "scholarships": True,
        "vodafone_cash": True,
        "airteltigo_money": True,
        "parent_portal": True,
        "teachers_app": True,
        "mobile_apps": True,
        "push_notifications": True,
        "hr_leave": True,
        "hr_payroll": "addon",    # GHS 500/term add-on (Enterprise only)
        "boarding": True,
        "transport": True,
        "preschool": True,
        "multi_curriculum": True,
        "asset_inventory": True,
        "multi_school": True,
        "api_access": True,
        "custom_domain": True,
        "sso": True,
        "custom_roles": True,
    },
}

# Human-readable tier names for error messages
FEATURE_TIER_REQUIREMENTS = {
    "teachers_portal": "Starter",
    "admissions_basic": "Starter",
    "admissions_advanced": "Professional",
    "admissions_full": "Enterprise",
    "customizable_reports": "Professional",
    "timetable": "Professional",
    "grade_moderation": "Professional",
    "scholarships": "Professional",
    "vodafone_cash": "Professional",
    "airteltigo_money": "Professional",
    "parent_portal": "Professional",
    "teachers_app": "Professional",
    "mobile_apps": "Professional",
    "push_notifications": "Professional",
    "hr_leave": "Professional",
    "hr_payroll": "Enterprise (add-on)",
    "boarding": "Professional (add-on) or Enterprise",
    "transport": "Professional (add-on) or Enterprise",
    "preschool": "Professional (add-on) or Enterprise",
    "multi_curriculum": "Enterprise",
    "asset_inventory": "Enterprise",
    "multi_school": "Enterprise",
    "api_access": "Enterprise",
    "custom_domain": "Enterprise",
    "sso": "Enterprise",
    "custom_roles": "Professional",
}


# ============================================================================
# PRICING — Per-Student (in pesewas, GHS x 100)
# ============================================================================

# Per-student per term
PRICE_PER_STUDENT_PER_TERM = {
    SubscriptionTier.STARTER: 500,        # GHS 5
    SubscriptionTier.PROFESSIONAL: 1000,   # GHS 10
    SubscriptionTier.ENTERPRISE: 1500,     # GHS 15
}

# Per-student per year (3 terms, 10% annual discount already applied)
PRICE_PER_STUDENT_PER_YEAR = {
    SubscriptionTier.STARTER: 1350,       # GHS 13.50
    SubscriptionTier.PROFESSIONAL: 2700,   # GHS 27
    SubscriptionTier.ENTERPRISE: 4050,     # GHS 40.50
}

# Annual discount rate
ANNUAL_DISCOUNT = 0.10

# Add-on pricing per term (pesewas)
ADDON_PRICING_PER_TERM = {
    "boarding": 30000,    # GHS 300
    "transport": 20000,   # GHS 200
    "preschool": 20000,   # GHS 200
    "hr_payroll": 50000,  # GHS 500 (Enterprise only)
}

# Valid add-on names
VALID_ADDONS = list(ADDON_PRICING_PER_TERM.keys())

# Term duration in days (used for subscription end date calculation)
TERM_DURATION_DAYS = 120
YEAR_DURATION_DAYS = 365

# Available add-ons by tier
AVAILABLE_ADDONS_BY_TIER = {
    SubscriptionTier.TRIAL: [],
    SubscriptionTier.STARTER: [],
    SubscriptionTier.PROFESSIONAL: ["boarding", "transport", "preschool"],
    SubscriptionTier.ENTERPRISE: ["hr_payroll"],  # Others are included
}
