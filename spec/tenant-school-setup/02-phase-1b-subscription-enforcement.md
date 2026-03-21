# Phase 1B: Subscription Plan Limit Enforcement

**Complexity:** Medium
**Requirements:** TS-003
**Dependencies:** Phase 1A (shared migration, subscription status endpoint)
**Estimated effort:** 3-4 days
**Reference:** `docs/SIMS_Plus_Subscription_Tiers.md`

---

## Summary

Enforce subscription plan limits and feature gating based on the official SIMS Plus Subscription Tiers document. This includes:
- **Per-student pricing model** (not flat rate)
- **Student limits**: Trial 100, Starter 300 (soft, billed per-student), Professional/Enterprise unlimited
- **User account limits**: Starter 10, Professional 50, Enterprise unlimited
- **Storage limits**: Starter 5GB, Professional 20GB, Enterprise 100GB
- **SMS limits**: Starter 50/mo, Professional 200/mo, Enterprise unlimited
- **Feature gating** by tier (parent portal, admissions, boarding, transport, API, multi-school, etc.)
- **Add-on system** for Professional tier (Boarding, Transport, Preschool)
- **Paystack checkout** for upgrades (reusing parent portal integration)

---

## Pricing Model — Per-Student, Per-Term

This is **NOT** a flat monthly fee. Pricing is based on enrolled student count:

| Tier | Per Term | Per Academic Year (3 terms, 10% off) | Max Students |
|------|----------|--------------------------------------|--------------|
| **Trial** | Free | Free (90 days) | 100 |
| **Starter** | GHS 5 / student / term | GHS 13.50 / student / year | 300 |
| **Professional** | GHS 10 / student / term | GHS 27 / student / year | Unlimited |
| **Enterprise** | GHS 15 / student / term | GHS 40.50 / student / year | Unlimited |

### Add-Ons (Professional Tier Only)

| Add-On | Price | Included in Enterprise |
|--------|-------|----------------------|
| Boarding / Hostel Management | GHS 300 / term | Yes (included) |
| Transport Management | GHS 200 / term | Yes (included) |
| Preschool Module | GHS 200 / term | Yes (included) |
| HR & Payroll (Enterprise only) | GHS 500 / term | Add-on |

### Discounts

- **Annual upfront payment**: 10% off
- **School chain discount (2+ schools)**: 10%-25%
- **2-year contract**: 15% off

---

## Official Feature Matrix

Source: `docs/SIMS_Plus_Subscription_Tiers.md`

| Feature | Trial | Starter | Professional | Enterprise |
|---------|-------|---------|--------------|------------|
| **Student Management** | ✓ | ✓ | ✓ | ✓ |
| **Attendance (Offline PWA)** | ✓ | ✓ | ✓ | ✓ |
| **Basic Report Cards** | ✓ | ✓ | ✓ | ✓ |
| **Basic Finance (tuition, PTA, MTN MoMo)** | ✓ | ✓ | ✓ | ✓ |
| **Staff Records & Attendance** | ✓ | ✓ | ✓ | ✓ |
| **Teachers Portal** | — | ✓ | ✓ | ✓ |
| **Enrollment & Admissions** | — | Basic | Advanced | Full |
| **Customizable Report Cards** | — | — | ✓ | ✓ |
| **Timetable & PDF Export** | — | — | ✓ | ✓ |
| **Grade Moderation Workflow** | — | — | ✓ | ✓ |
| **Scholarships & Discounts** | — | — | ✓ | ✓ |
| **Vodafone Cash & AirtelTigo** | — | — | ✓ | ✓ |
| **Parent Portal** | — | — | ✓ | ✓ |
| **Teachers App (iOS/Android)** | — | — | ✓ | ✓ |
| **Mobile Apps** | — | — | ✓ | ✓ |
| **Push Notifications** | — | — | ✓ | ✓ |
| **HR Leave Management** | — | — | ✓ | ✓ |
| **Boarding Management** | — | — | **Add-on** | ✓ (included) |
| **Transport Management** | — | — | **Add-on** | ✓ (included) |
| **Preschool Module** | — | — | **Add-on** | ✓ (included) |
| **Multi-Curriculum Support** | — | — | — | ✓ |
| **Asset & Inventory** | — | — | — | ✓ |
| **Chain / Multi-School** | — | — | — | ✓ |
| **API Access** | — | — | — | ✓ |
| **Custom Domain** | — | — | — | ✓ |
| **SSO Integration** | — | — | — | ✓ |
| **SMS / month** | Limited | 50 | 200 | Unlimited |
| **Storage** | — | 5 GB | 20 GB | 100 GB |
| **User Accounts** | — | 10 | 50 | Unlimited |
| **Support** | Email | Email | Email + Chat | Priority + Phone |
| **Uptime SLA** | — | 99% | 99.5% | 99.9% |

---

## Task 1: Create Subscription Service

### New File: `backend/app/services/subscription.py`

```python
"""
Subscription enforcement service.

Checks plan limits (student count, user accounts, storage, SMS) and
feature access before allowing creation of new resources.

Pricing model: per-student, per-term (not flat rate).
See docs/SIMS_Plus_Subscription_Tiers.md for full details.
"""

import structlog
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant, SubscriptionTier
from app.models.student import Student
from app.models.staff import Staff
from app.models.user import User

logger = structlog.get_logger()


class SubscriptionError(Exception):
    """Base class for subscription-related errors."""
    def __init__(self, message: str, code: str):
        self.message = message
        self.code = code
        super().__init__(message)


class LimitExceededError(SubscriptionError):
    """Raised when a plan limit is reached."""
    pass


class FeatureNotAvailableError(SubscriptionError):
    """Raised when accessing a feature not in the current plan."""
    pass


# ============================================================================
# PLAN LIMITS
# ============================================================================

# Student limits — Professional and Enterprise are unlimited (None = no limit)
MAX_STUDENTS_BY_TIER = {
    SubscriptionTier.TRIAL: 100,
    SubscriptionTier.STARTER: 300,
    SubscriptionTier.PROFESSIONAL: None,  # Unlimited (billed per-student)
    SubscriptionTier.ENTERPRISE: None,    # Unlimited (billed per-student)
}

# User account limits
MAX_USERS_BY_TIER = {
    SubscriptionTier.TRIAL: 10,       # Same as Starter during trial
    SubscriptionTier.STARTER: 10,
    SubscriptionTier.PROFESSIONAL: 50,
    SubscriptionTier.ENTERPRISE: None,  # Unlimited
}

# Storage limits in bytes
STORAGE_LIMIT_BY_TIER = {
    SubscriptionTier.TRIAL: 5 * 1024 * 1024 * 1024,       # 5 GB (same as Starter)
    SubscriptionTier.STARTER: 5 * 1024 * 1024 * 1024,      # 5 GB
    SubscriptionTier.PROFESSIONAL: 20 * 1024 * 1024 * 1024, # 20 GB
    SubscriptionTier.ENTERPRISE: 100 * 1024 * 1024 * 1024,  # 100 GB
}

# Monthly SMS limits
SMS_LIMIT_BY_TIER = {
    SubscriptionTier.TRIAL: 50,       # Same as Starter during trial
    SubscriptionTier.STARTER: 50,
    SubscriptionTier.PROFESSIONAL: 200,
    SubscriptionTier.ENTERPRISE: None,  # Unlimited
}

# ============================================================================
# FEATURE AVAILABILITY BY PLAN
# ============================================================================
# True = included, False = not available, "addon" = available as paid add-on
#
# The "addon" state means the feature is gated but can be unlocked via
# tenant.features JSONB (set when add-on is purchased).

PLAN_FEATURES = {
    SubscriptionTier.TRIAL: {
        # Trial gets all Starter features for 90 days
        "teachers_portal": False,
        "admissions_basic": False,
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
        "boarding": False,
        "transport": False,
        "preschool": False,
        "multi_curriculum": False,
        "asset_inventory": False,
        "multi_school": False,
        "api_access": False,
        "custom_domain": False,
        "sso": False,
    },
    SubscriptionTier.STARTER: {
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
        "boarding": False,
        "transport": False,
        "preschool": False,
        "multi_curriculum": False,
        "asset_inventory": False,
        "multi_school": False,
        "api_access": False,
        "custom_domain": False,
        "sso": False,
    },
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
        "boarding": "addon",      # GHS 300/term add-on
        "transport": "addon",     # GHS 200/term add-on
        "preschool": "addon",     # GHS 200/term add-on
        "multi_curriculum": False,
        "asset_inventory": False,
        "multi_school": False,
        "api_access": False,
        "custom_domain": False,
        "sso": False,
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
        "boarding": True,         # Included
        "transport": True,        # Included
        "preschool": True,        # Included
        "multi_curriculum": True,
        "asset_inventory": True,
        "multi_school": True,
        "api_access": True,
        "custom_domain": True,
        "sso": True,
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
    "boarding": "Professional (add-on) or Enterprise",
    "transport": "Professional (add-on) or Enterprise",
    "preschool": "Professional (add-on) or Enterprise",
    "multi_curriculum": "Enterprise",
    "asset_inventory": "Enterprise",
    "multi_school": "Enterprise",
    "api_access": "Enterprise",
    "custom_domain": "Enterprise",
    "sso": "Enterprise",
}


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_tenant(self, tenant_id: UUID) -> Tenant:
        tenant = await self.db.get(Tenant, tenant_id)
        if not tenant:
            raise SubscriptionError("Tenant not found", "TENANT_NOT_FOUND")
        return tenant

    # ========================================================================
    # STUDENT LIMIT
    # ========================================================================

    async def check_student_limit(self, tenant_id: UUID, additional: int = 1) -> None:
        """
        Check if adding `additional` students would exceed the plan limit.

        Trial: max 100 students
        Starter: max 300 students
        Professional & Enterprise: unlimited (None)

        Args:
            tenant_id: The tenant UUID
            additional: Number of students being added (default 1, higher for bulk import)

        Raises:
            LimitExceededError: If limit would be exceeded
        """
        tenant = await self._get_tenant(tenant_id)
        max_students = MAX_STUDENTS_BY_TIER.get(tenant.subscription_tier)

        if max_students is None:
            return  # Unlimited (Professional/Enterprise)

        count = await self.db.scalar(
            select(func.count(Student.id)).where(
                Student.tenant_id == tenant_id,
                Student.status.in_(["active", "inactive"]),  # Don't count graduated/withdrawn
                Student.deleted_at.is_(None),
            )
        ) or 0

        if count + additional > max_students:
            raise LimitExceededError(
                message=(
                    f"Student limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {max_students} students (current: {count}). "
                    f"Upgrade your plan to add more students."
                ),
                code="STUDENT_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # USER ACCOUNT LIMIT
    # ========================================================================

    async def check_user_limit(self, tenant_id: UUID, additional: int = 1) -> None:
        """
        Check if adding `additional` user accounts would exceed the plan limit.

        Starter: 10 accounts
        Professional: 50 accounts
        Enterprise: unlimited

        Raises:
            LimitExceededError: If limit would be exceeded
        """
        tenant = await self._get_tenant(tenant_id)
        max_users = MAX_USERS_BY_TIER.get(tenant.subscription_tier)

        if max_users is None:
            return  # Unlimited (Enterprise)

        count = await self.db.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.status.in_(["active", "pending"]),
                User.deleted_at.is_(None),
            )
        ) or 0

        if count + additional > max_users:
            raise LimitExceededError(
                message=(
                    f"User account limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {max_users} user accounts (current: {count}). "
                    f"Upgrade your plan to add more."
                ),
                code="USER_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # SMS LIMIT (Monthly)
    # ========================================================================

    async def check_sms_limit(self, tenant_id: UUID, count: int = 1) -> None:
        """
        Check if sending `count` SMS messages would exceed the monthly limit.

        Starter: 50/month
        Professional: 200/month
        Enterprise: unlimited

        Raises:
            LimitExceededError: If monthly limit would be exceeded
        """
        tenant = await self._get_tenant(tenant_id)
        monthly_limit = SMS_LIMIT_BY_TIER.get(tenant.subscription_tier)

        if monthly_limit is None:
            return  # Unlimited (Enterprise)

        # Count SMS sent this month
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        from app.models.sms_log import SmsLog  # Assumes SmsLog model exists
        sent_this_month = await self.db.scalar(
            select(func.count(SmsLog.id)).where(
                SmsLog.tenant_id == tenant_id,
                SmsLog.created_at >= month_start,
                SmsLog.status.in_(["sent", "pending"]),
            )
        ) or 0

        if sent_this_month + count > monthly_limit:
            remaining = max(0, monthly_limit - sent_this_month)
            raise LimitExceededError(
                message=(
                    f"SMS limit reached. Your {tenant.subscription_tier.value} plan "
                    f"allows {monthly_limit} SMS/month ({remaining} remaining). "
                    f"Upgrade for more SMS capacity."
                ),
                code="SMS_LIMIT_EXCEEDED",
            )

    # ========================================================================
    # FEATURE ACCESS
    # ========================================================================

    async def check_feature_access(self, tenant_id: UUID, feature: str) -> None:
        """
        Check if a feature is available on the tenant's current plan.

        Resolution order:
        1. tenant.features JSONB (admin overrides & purchased add-ons)
        2. PLAN_FEATURES defaults for the subscription tier

        For "addon" features (Professional tier):
        - The feature is gated by default
        - When the school purchases the add-on, set tenant.features[feature] = True
        - This allows unlocking without changing the subscription tier

        Args:
            tenant_id: The tenant UUID
            feature: Feature key (e.g., "boarding", "parent_portal", "api_access")

        Raises:
            FeatureNotAvailableError: If feature not available
        """
        tenant = await self._get_tenant(tenant_id)

        # 1. Check tenant-level override first (admin grants & purchased add-ons)
        tenant_features = tenant.features or {}
        if feature in tenant_features:
            if tenant_features[feature]:
                return  # Explicitly enabled (add-on purchased or admin override)
            # Explicitly disabled — fall through to plan check
            # (allows admin to disable a feature even if plan includes it)

        # 2. Fall back to plan defaults
        plan_defaults = PLAN_FEATURES.get(tenant.subscription_tier, {})
        feature_status = plan_defaults.get(feature, False)

        if feature_status is True:
            return  # Included in plan

        if feature_status == "addon":
            # Available as add-on but not purchased
            required_tier = FEATURE_TIER_REQUIREMENTS.get(feature, "a higher")
            raise FeatureNotAvailableError(
                message=(
                    f"The {feature.replace('_', ' ')} feature is available as an add-on "
                    f"on the Professional plan. Contact support to enable it, "
                    f"or upgrade to Enterprise where it's included."
                ),
                code="ADDON_NOT_PURCHASED",
            )

        # Not available on this tier
        required_tier = FEATURE_TIER_REQUIREMENTS.get(feature, "a higher")
        raise FeatureNotAvailableError(
            message=(
                f"The {feature.replace('_', ' ')} feature requires "
                f"the {required_tier} plan or higher."
            ),
            code="FEATURE_NOT_AVAILABLE",
        )
```

---

## Task 2: Register Exception Handlers

### File: `backend/app/main.py`

Add exception handlers for subscription errors:

```python
from app.services.subscription import LimitExceededError, FeatureNotAvailableError

@app.exception_handler(LimitExceededError)
async def limit_exceeded_handler(request, exc: LimitExceededError):
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message, "code": exc.code},
    )

@app.exception_handler(FeatureNotAvailableError)
async def feature_not_available_handler(request, exc: FeatureNotAvailableError):
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message, "code": exc.code},
    )
```

---

## Task 3: Integrate Limit Checks into Services

### Student Creation

**File:** `backend/app/services/student/student_service.py`

In the `create_student()` method, add at the top (before any DB operations):

```python
from app.services.subscription import SubscriptionService

async def create_student(self, tenant_id: UUID, ...) -> Student:
    # Check plan limit BEFORE creating
    sub_service = SubscriptionService(self.db)
    await sub_service.check_student_limit(tenant_id)

    # ... existing creation logic ...
```

### Student Bulk Import

In the `import_students_from_file()` method, add a pre-check with the count of students being imported:

```python
async def import_students_from_file(self, tenant_id: UUID, file, ...) -> dict:
    # Parse file to get count first
    records = self._parse_import_file(file)

    # Check if we have capacity for ALL records
    sub_service = SubscriptionService(self.db)
    await sub_service.check_student_limit(tenant_id, additional=len(records))

    # ... existing import logic ...
```

### User Account Creation

**File:** `backend/app/services/auth.py` (or wherever users are created)

```python
async def create_user(self, tenant_id: UUID, ...) -> User:
    sub_service = SubscriptionService(self.db)
    await sub_service.check_user_limit(tenant_id)
    # ... existing creation logic ...
```

Also in user invite endpoint:
```python
async def invite_user(self, tenant_id: UUID, ...) -> User:
    sub_service = SubscriptionService(self.db)
    await sub_service.check_user_limit(tenant_id)
    # ... existing invite logic ...
```

### SMS Sending

**File:** `backend/app/services/messaging/sms_service.py`

```python
async def send_sms(self, tenant_id: UUID, ...) -> SmsLog:
    sub_service = SubscriptionService(self.db)
    await sub_service.check_sms_limit(tenant_id)
    # ... existing send logic ...

async def send_bulk_sms(self, tenant_id: UUID, recipients: list, ...) -> dict:
    sub_service = SubscriptionService(self.db)
    await sub_service.check_sms_limit(tenant_id, count=len(recipients))
    # ... existing bulk send logic ...
```

### Staff Creation (no change from original plan)

**File:** `backend/app/services/staff/staff_service.py`

Note: The tiers document doesn't define explicit staff limits separate from user accounts. Staff records are distinct from user accounts. However, the `max_staff` field on tenants can still be used for soft limits. Keep the existing staff limit check but update the defaults:

```python
# Staff creation doesn't have an explicit cap in the tiers doc,
# but we can use max_staff from tenant for safety.
# Consider: staff records != user accounts.
# A school can have 200 staff records but only 50 user accounts.
```

---

## Task 4: Feature Gating on Endpoints

### File: `backend/app/api/deps.py`

Add a reusable dependency factory:

```python
from app.services.subscription import SubscriptionService

def require_feature(feature: str):
    """
    Dependency factory that checks if a feature is available on the tenant's plan.

    Handles three states:
    - True: feature included in plan → access granted
    - "addon": feature available as add-on → check tenant.features JSONB
    - False: feature not available on this plan → 403

    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_feature("boarding"))])

    Or at router level:
        router = APIRouter(dependencies=[Depends(require_feature("boarding"))])
    """
    async def _check_feature(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(get_validated_current_user),
    ):
        tenant_id = UUID(current_user["tenant_id"])
        sub_service = SubscriptionService(db)
        await sub_service.check_feature_access(tenant_id, feature)

    return _check_feature
```

### Apply to Routers:

| Router File | Feature Gate | Min Tier |
|-------------|-------------|----------|
| `boarding.py` | `require_feature("boarding")` | Professional (add-on) / Enterprise |
| `transport.py` | `require_feature("transport")` | Professional (add-on) / Enterprise |
| `preschool.py` | `require_feature("preschool")` | Professional (add-on) / Enterprise |
| `chain.py` | `require_feature("multi_school")` | Enterprise |
| `parent/` (all) | `require_feature("parent_portal")` | Professional |
| `timetable.py` | `require_feature("timetable")` | Professional |
| `curriculum/` (all) | `require_feature("multi_curriculum")` | Enterprise |
| `admissions/` (advanced) | `require_feature("admissions_advanced")` | Professional |
| `admissions/` (full) | `require_feature("admissions_full")` | Enterprise |

**Example — Boarding router:**
```python
router = APIRouter(
    prefix="/boarding",
    tags=["boarding"],
    dependencies=[Depends(require_feature("boarding"))],
)
```

**Example — Parent portal router:**
```python
router = APIRouter(
    prefix="/parent",
    tags=["parent"],
    dependencies=[Depends(require_feature("parent_portal"))],
)
```

**Note on granularity for admissions:**
The tiers doc says Starter gets "Basic" enrollment, Professional gets "Advanced", Enterprise gets "Full". Implement this with three separate feature keys:
- `admissions_basic`: Application tracking, status updates (Starter+)
- `admissions_advanced`: Online forms, waitlist, re-enrollment (Professional+)
- `admissions_full`: Inquiry management, tours, entrance exams, analytics (Enterprise)

Gate individual endpoints within the admissions router based on which level they belong to.

---

## Task 5: Paystack Subscription Checkout

### Pricing Calculation

Since pricing is per-student, the checkout amount must be calculated dynamically:

```python
# Pricing in pesewas per student per term
PRICE_PER_STUDENT_PER_TERM = {
    SubscriptionTier.STARTER: 500,        # GHS 5 = 500 pesewas
    SubscriptionTier.PROFESSIONAL: 1000,   # GHS 10
    SubscriptionTier.ENTERPRISE: 1500,     # GHS 15
}

# Annual discount: 10% off (3 terms paid upfront)
ANNUAL_DISCOUNT = 0.10

# Per-student per year (with discount)
PRICE_PER_STUDENT_PER_YEAR = {
    SubscriptionTier.STARTER: 1350,       # GHS 13.50 = 1350 pesewas
    SubscriptionTier.PROFESSIONAL: 2700,   # GHS 27
    SubscriptionTier.ENTERPRISE: 4050,     # GHS 40.50
}

# Add-on pricing in pesewas per term
ADDON_PRICING = {
    "boarding": 30000,   # GHS 300
    "transport": 20000,  # GHS 200
    "preschool": 20000,  # GHS 200
    "hr_payroll": 50000, # GHS 500 (Enterprise only)
}
```

### New File: `backend/app/services/subscription_payment.py`

```python
"""
Subscription payment service using Paystack.

Handles per-student pricing model:
- Calculates total based on active student count * price per student
- Supports term-based and annual billing
- Handles add-on purchases separately
"""

import hashlib
import hmac
import httpx
import structlog
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.tenant import Tenant, TenantStatus, SubscriptionTier
from app.models.student import Student

logger = structlog.get_logger()

# Pricing constants (pesewas)
PRICE_PER_STUDENT_PER_TERM = {
    SubscriptionTier.STARTER: 500,
    SubscriptionTier.PROFESSIONAL: 1000,
    SubscriptionTier.ENTERPRISE: 1500,
}

PRICE_PER_STUDENT_PER_YEAR = {
    SubscriptionTier.STARTER: 1350,
    SubscriptionTier.PROFESSIONAL: 2700,
    SubscriptionTier.ENTERPRISE: 4050,
}

ADDON_PRICING_PER_TERM = {
    "boarding": 30000,
    "transport": 20000,
    "preschool": 20000,
    "hr_payroll": 50000,
}

# Student limits by tier (for display/enforcement)
MAX_STUDENTS_BY_TIER = {
    SubscriptionTier.TRIAL: 100,
    SubscriptionTier.STARTER: 300,
    SubscriptionTier.PROFESSIONAL: None,
    SubscriptionTier.ENTERPRISE: None,
}

# User account limits by tier
MAX_USERS_BY_TIER = {
    SubscriptionTier.TRIAL: 10,
    SubscriptionTier.STARTER: 10,
    SubscriptionTier.PROFESSIONAL: 50,
    SubscriptionTier.ENTERPRISE: None,
}


class SubscriptionPaymentService:
    PAYSTACK_BASE_URL = "https://api.paystack.co"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _count_active_students(self, tenant_id: UUID) -> int:
        return await self.db.scalar(
            select(func.count(Student.id)).where(
                Student.tenant_id == tenant_id,
                Student.status.in_(["active", "inactive"]),
                Student.deleted_at.is_(None),
            )
        ) or 0

    async def calculate_upgrade_cost(
        self,
        tenant_id: UUID,
        target_tier: SubscriptionTier,
        billing_period: str,  # "term" or "year"
        addons: list[str] | None = None,
    ) -> dict:
        """
        Calculate the total cost for upgrading to a target tier.

        Returns:
            {
                "student_count": int,
                "price_per_student": int (pesewas),
                "subtotal": int (pesewas),
                "addon_total": int (pesewas),
                "total": int (pesewas),
                "total_ghs": float,
                "billing_period": "term" | "year",
                "breakdown": [...]
            }
        """
        student_count = await self._count_active_students(tenant_id)

        # Use at least 1 student for pricing (minimum charge)
        billable_students = max(student_count, 1)

        if billing_period == "year":
            price_map = PRICE_PER_STUDENT_PER_YEAR
        else:
            price_map = PRICE_PER_STUDENT_PER_TERM

        price_per_student = price_map.get(target_tier, 0)
        subtotal = billable_students * price_per_student

        # Add-on costs
        addon_total = 0
        addon_breakdown = []
        if addons:
            for addon in addons:
                addon_price = ADDON_PRICING_PER_TERM.get(addon, 0)
                if billing_period == "year":
                    # 3 terms with 10% annual discount
                    addon_price = int(addon_price * 3 * 0.9)
                addon_total += addon_price
                addon_breakdown.append({
                    "name": addon,
                    "amount": addon_price,
                })

        total = subtotal + addon_total

        return {
            "student_count": student_count,
            "billable_students": billable_students,
            "price_per_student": price_per_student,
            "subtotal": subtotal,
            "addon_total": addon_total,
            "total": total,
            "total_ghs": total / 100,
            "billing_period": billing_period,
            "tier": target_tier.value,
            "breakdown": [
                {
                    "description": f"{billable_students} students x GHS {price_per_student / 100:.2f}/{billing_period}",
                    "amount": subtotal,
                },
                *addon_breakdown,
            ],
        }

    async def initiate_upgrade(
        self,
        tenant_id: UUID,
        target_tier: SubscriptionTier,
        billing_period: str,
        payer_email: str,
        callback_url: str,
        addons: list[str] | None = None,
    ) -> dict:
        """
        Initiate a Paystack payment for a subscription upgrade.

        Calculates total based on active student count, then creates
        a Paystack transaction.

        Returns:
            {authorization_url, reference, access_code, cost_breakdown}
        """
        cost = await self.calculate_upgrade_cost(
            tenant_id, target_tier, billing_period, addons
        )

        if cost["total"] <= 0:
            raise ValueError("Cannot process zero-amount payment")

        reference = f"sub_{tenant_id}_{target_tier.value}_{billing_period}_{int(datetime.now(timezone.utc).timestamp())}"

        duration_days = 365 if billing_period == "year" else 120  # ~4 months per term

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.PAYSTACK_BASE_URL}/transaction/initialize",
                headers={
                    "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": payer_email,
                    "amount": cost["total"],
                    "currency": "GHS",
                    "reference": reference,
                    "callback_url": callback_url,
                    "metadata": {
                        "tenant_id": str(tenant_id),
                        "target_tier": target_tier.value,
                        "billing_period": billing_period,
                        "duration_days": duration_days,
                        "student_count": cost["student_count"],
                        "addons": addons or [],
                        "type": "subscription_upgrade",
                    },
                },
            )

            data = response.json()
            if not data.get("status"):
                raise Exception(f"Paystack error: {data.get('message', 'Unknown error')}")

            return {
                "authorization_url": data["data"]["authorization_url"],
                "reference": data["data"]["reference"],
                "access_code": data["data"]["access_code"],
                "cost": cost,
            }

    async def handle_webhook(self, payload_body: bytes, signature: str) -> None:
        """
        Handle Paystack webhook for subscription payments.

        Verifies signature, extracts metadata, upgrades tenant tier,
        and enables any purchased add-ons.
        """
        # Verify HMAC-SHA512 signature
        expected = hmac.new(
            settings.PAYSTACK_WEBHOOK_SECRET.encode(),
            payload_body,
            hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("subscription_webhook_invalid_signature")
            raise ValueError("Invalid webhook signature")

        import json
        payload = json.loads(payload_body)
        event = payload.get("event")

        if event != "charge.success":
            return

        data = payload.get("data", {})
        metadata = data.get("metadata", {})

        if metadata.get("type") != "subscription_upgrade":
            return

        tenant_id = UUID(metadata["tenant_id"])
        target_tier = SubscriptionTier(metadata["target_tier"])
        billing_period = metadata["billing_period"]
        duration_days = int(metadata["duration_days"])
        addons = metadata.get("addons", [])

        tenant = await self.db.get(Tenant, tenant_id)
        if not tenant:
            logger.error("subscription_webhook_tenant_not_found", tenant_id=str(tenant_id))
            return

        now = datetime.now(timezone.utc)

        # Upgrade tenant
        tenant.subscription_tier = target_tier
        tenant.status = TenantStatus.ACTIVE
        tenant.subscription_start = now.date()
        tenant.subscription_end = (now + timedelta(days=duration_days)).date()

        # Update limits based on tier
        tenant.max_students = MAX_STUDENTS_BY_TIER.get(target_tier)  # None = unlimited
        # max_staff is not explicitly in tiers doc — keep existing or derive from tier

        # Enable purchased add-ons in features JSONB
        if addons:
            features = tenant.features or {}
            for addon in addons:
                features[addon] = True
            tenant.features = features

        await self.db.flush()

        logger.info(
            "subscription_upgraded",
            tenant_id=str(tenant_id),
            tier=target_tier.value,
            billing_period=billing_period,
            subscription_end=str(tenant.subscription_end),
            addons=addons,
        )
```

---

## Task 6: Subscription Endpoints

### File: `backend/app/api/v1/endpoints/subscription.py`

Add upgrade and cost-calculation endpoints to the subscription router (created in Phase 1A):

```python
@router.post("/calculate-cost", response_model=CostBreakdownResponse)
async def calculate_upgrade_cost(
    request: CalculateCostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Calculate the cost of upgrading to a target tier.

    Returns a detailed breakdown including per-student pricing,
    add-on costs, and totals in both pesewas and GHS.
    """
    tenant_id = UUID(current_user["tenant_id"])
    service = SubscriptionPaymentService(db)

    return await service.calculate_upgrade_cost(
        tenant_id=tenant_id,
        target_tier=SubscriptionTier(request.target_tier),
        billing_period=request.billing_period,
        addons=request.addons,
    )


@router.post("/upgrade", response_model=UpgradeResponse)
async def initiate_upgrade(
    request: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Initiate a subscription upgrade via Paystack.

    Calculates total based on active student count, creates a Paystack
    transaction, and returns the authorization URL to redirect the user.
    """
    role = current_user.get("role")
    if role not in ("school_admin", "chain_admin", "platform_admin"):
        raise HTTPException(403, "Only administrators can upgrade subscriptions")

    tenant_id = UUID(current_user["tenant_id"])
    service = SubscriptionPaymentService(db)

    return await service.initiate_upgrade(
        tenant_id=tenant_id,
        target_tier=SubscriptionTier(request.target_tier),
        billing_period=request.billing_period,
        payer_email=current_user["email"],
        callback_url=request.callback_url,
        addons=request.addons,
    )


@router.post("/purchase-addon", response_model=UpgradeResponse)
async def purchase_addon(
    request: PurchaseAddonRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Purchase an add-on for the current plan (Professional tier only).

    Available add-ons: boarding (GHS 300/term), transport (GHS 200/term),
    preschool (GHS 200/term).
    """
    role = current_user.get("role")
    if role not in ("school_admin", "chain_admin", "platform_admin"):
        raise HTTPException(403, "Only administrators can purchase add-ons")

    tenant_id = UUID(current_user["tenant_id"])
    tenant = await db.get(Tenant, tenant_id)

    if tenant.subscription_tier != SubscriptionTier.PROFESSIONAL:
        raise HTTPException(400, "Add-ons are only available on the Professional plan")

    service = SubscriptionPaymentService(db)

    # For add-on purchase, keep the same tier
    return await service.initiate_upgrade(
        tenant_id=tenant_id,
        target_tier=tenant.subscription_tier,
        billing_period=request.billing_period,
        payer_email=current_user["email"],
        callback_url=request.callback_url,
        addons=request.addons,
    )


@router.post("/webhook", include_in_schema=False)
async def subscription_webhook(
    request: Request,
    db: AsyncSession = Depends(get_unscoped_db),
):
    """Paystack webhook handler for subscription payments."""
    payload = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    service = SubscriptionPaymentService(db)
    await service.handle_webhook(payload, signature)

    # Invalidate tenant cache
    import json
    data = json.loads(payload)
    metadata = data.get("data", {}).get("metadata", {})
    if metadata.get("type") == "subscription_upgrade":
        tenant_id = UUID(metadata["tenant_id"])
        tenant = await db.get(Tenant, tenant_id)
        if tenant and hasattr(request.app.state, "redis"):
            from app.middleware.tenant import invalidate_tenant_cache
            await invalidate_tenant_cache(request.app.state.redis, tenant.subdomain)

    await db.commit()
    return {"status": "ok"}
```

### Schemas

### File: `backend/app/schemas/subscription.py`

Add:

```python
class CalculateCostRequest(BaseModel):
    target_tier: str  # "starter", "professional", "enterprise"
    billing_period: str  # "term" or "year"
    addons: list[str] | None = None  # ["boarding", "transport", "preschool"]

    @field_validator("target_tier")
    @classmethod
    def validate_tier(cls, v):
        if v not in ("starter", "professional", "enterprise"):
            raise ValueError("Target tier must be: starter, professional, or enterprise")
        return v

    @field_validator("billing_period")
    @classmethod
    def validate_period(cls, v):
        if v not in ("term", "year"):
            raise ValueError("Billing period must be: term or year")
        return v

    @field_validator("addons")
    @classmethod
    def validate_addons(cls, v):
        valid = ["boarding", "transport", "preschool", "hr_payroll"]
        if v:
            for a in v:
                if a not in valid:
                    raise ValueError(f"Invalid add-on '{a}'. Valid: {valid}")
        return v


class CostBreakdownResponse(BaseModel):
    student_count: int
    billable_students: int
    price_per_student: int       # pesewas
    subtotal: int                # pesewas
    addon_total: int             # pesewas
    total: int                   # pesewas
    total_ghs: float             # GHS
    billing_period: str
    tier: str
    breakdown: list[dict]


class UpgradeRequest(BaseModel):
    target_tier: str
    billing_period: str
    callback_url: str
    addons: list[str] | None = None

    @field_validator("target_tier")
    @classmethod
    def validate_tier(cls, v):
        if v not in ("starter", "professional", "enterprise"):
            raise ValueError("Target tier must be: starter, professional, or enterprise")
        return v

    @field_validator("billing_period")
    @classmethod
    def validate_period(cls, v):
        if v not in ("term", "year"):
            raise ValueError("Billing period must be: term or year")
        return v

    @field_validator("callback_url")
    @classmethod
    def validate_callback_url(cls, v):
        if not v.startswith("https://"):
            raise ValueError("Callback URL must use HTTPS")
        return v


class UpgradeResponse(BaseModel):
    authorization_url: str
    reference: str
    access_code: str
    cost: CostBreakdownResponse


class PurchaseAddonRequest(BaseModel):
    addons: list[str]
    billing_period: str  # "term" or "year"
    callback_url: str

    @field_validator("addons")
    @classmethod
    def validate_addons(cls, v):
        valid = ["boarding", "transport", "preschool", "hr_payroll"]
        if not v:
            raise ValueError("At least one add-on is required")
        for a in v:
            if a not in valid:
                raise ValueError(f"Invalid add-on '{a}'. Valid: {valid}")
        return v
```

### Add webhook path to public prefixes:

**File:** `backend/app/middleware/tenant.py` and `backend/app/api/deps.py`
```python
PUBLIC_PATH_PREFIXES = (
    # ... existing ...
    "/api/v1/subscription/webhook/",
)
```

---

## Task 7: Frontend Subscription Settings Page

### New File: `frontend/app/(dashboard)/settings/subscription/page.tsx`

Key sections of the page:

```
+---------------------------------------------------------------+
| CURRENT PLAN                                                   |
|                                                                |
| [Trial] Your 90-day trial ends in 67 days                     |
|                                                                |
| Usage:                                                         |
| Students: ████████░░ 45/100                                    |
| Users:    ██░░░░░░░░ 3/10                                      |
| SMS:      ░░░░░░░░░░ 0/50 this month                          |
| Storage:  ░░░░░░░░░░ 0.2/5.0 GB                               |
+---------------------------------------------------------------+

+---------------------------------------------------------------+
| CHOOSE A PLAN                                                  |
|                                                                |
| [Starter]           [Professional]         [Enterprise]        |
| GHS 5/student/term  GHS 10/student/term   GHS 15/student/term |
| GHS 13.50/yr (10%)  GHS 27/yr (10%)       GHS 40.50/yr (10%) |
|                                                                |
| 300 students        Unlimited              Unlimited           |
| 10 users            50 users               Unlimited users     |
| Basic reports       Custom reports         Full custom         |
| MTN MoMo            + Voda, AirtelTigo     All payment methods |
| 50 SMS/mo           200 SMS/mo             Unlimited SMS       |
| 5 GB                20 GB                  100 GB              |
| -                   Parent Portal          Parent Portal       |
| -                   Mobile Apps            Mobile Apps         |
| -                   Boarding (add-on)      Boarding (included) |
| -                   Transport (add-on)     Transport (included)|
| -                   -                      Multi-curriculum    |
| -                   -                      Chain/Multi-school  |
| -                   -                      API Access          |
|                                                                |
| [Current Plan]      [Upgrade]              [Contact Sales]     |
+---------------------------------------------------------------+

| When user clicks "Upgrade":                                    |
| 1. Select billing period: [Per Term] [Per Year (Save 10%)]    |
| 2. Shows cost calculation:                                     |
|    "45 students x GHS 10/term = GHS 450"                      |
| 3. Add-ons (Professional only):                                |
|    [ ] Boarding (GHS 300/term)                                 |
|    [ ] Transport (GHS 200/term)                                |
|    [ ] Preschool (GHS 200/term)                                |
| 4. Total: GHS 450 + GHS 300 = GHS 750                         |
| 5. [Pay with Paystack] → redirects to Paystack                |
+---------------------------------------------------------------+
```

### Server Actions

### File: `frontend/actions/subscription.action.ts`

Add (supplement what was created in Phase 1A):

```typescript
export interface CostBreakdown {
  student_count: number;
  billable_students: number;
  price_per_student: number;
  subtotal: number;
  addon_total: number;
  total: number;
  total_ghs: number;
  billing_period: string;
  tier: string;
  breakdown: Array<{ description: string; amount: number; name?: string }>;
}

export interface UpgradeResponse {
  authorization_url: string;
  reference: string;
  access_code: string;
  cost: CostBreakdown;
}

export async function calculateUpgradeCost(
  targetTier: string,
  billingPeriod: string,
  addons?: string[],
): Promise<ActionResult<CostBreakdown>> {
  try {
    const response = await apiPost<CostBreakdown>("/subscription/calculate-cost", {
      target_tier: targetTier,
      billing_period: billingPeriod,
      addons,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to calculate cost",
    };
  }
}

export async function initiateUpgrade(
  targetTier: string,
  billingPeriod: string,
  callbackUrl: string,
  addons?: string[],
): Promise<ActionResult<UpgradeResponse>> {
  try {
    const response = await apiPost<UpgradeResponse>("/subscription/upgrade", {
      target_tier: targetTier,
      billing_period: billingPeriod,
      callback_url: callbackUrl,
      addons,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate upgrade",
    };
  }
}

export async function purchaseAddon(
  addons: string[],
  billingPeriod: string,
  callbackUrl: string,
): Promise<ActionResult<UpgradeResponse>> {
  try {
    const response = await apiPost<UpgradeResponse>("/subscription/purchase-addon", {
      addons,
      billing_period: billingPeriod,
      callback_url: callbackUrl,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to purchase add-on",
    };
  }
}
```

### Add Navigation Link

**File:** `frontend/app/(dashboard)/settings/layout.tsx`

```tsx
{ title: "Subscription", href: "/settings/subscription", icon: CreditCard }
```

---

## Task 8: Frontend Upgrade Prompt Component

### New File: `frontend/components/subscription/upgrade-prompt.tsx`

```tsx
"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface UpgradePromptProps {
  open: boolean;
  onClose: () => void;
  code: string;
  message: string;
}

export function UpgradePrompt({ open, onClose, code, message }: UpgradePromptProps) {
  const titles: Record<string, string> = {
    STUDENT_LIMIT_EXCEEDED: "Student Limit Reached",
    USER_LIMIT_EXCEEDED: "User Account Limit Reached",
    STAFF_LIMIT_EXCEEDED: "Staff Limit Reached",
    SMS_LIMIT_EXCEEDED: "SMS Limit Reached",
    FEATURE_NOT_AVAILABLE: "Feature Not Available",
    ADDON_NOT_PURCHASED: "Add-On Required",
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titles[code] || "Plan Limit Reached"}</DialogTitle>
          <DialogDescription>{message}</DialogDescription>
        </DialogHeader>
        <div className="flex gap-2 justify-end mt-4">
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Link href="/settings/subscription">
            <Button>
              {code === "ADDON_NOT_PURCHASED" ? "View Add-Ons" : "View Plans"}
            </Button>
          </Link>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Task 9: Update Phase 1A Subscription Status Response

The `GET /subscription/status` endpoint (from Phase 1A) should include the additional limits:

### File: `backend/app/schemas/subscription.py`

Update `SubscriptionStatusResponse`:

```python
class SubscriptionStatusResponse(BaseModel):
    plan: str
    status: str
    trial_ends_at: datetime | None
    subscription_start: date | None
    subscription_end: date | None
    days_remaining: int | None
    # Student limits
    max_students: int | None          # None = unlimited
    current_student_count: int
    # User account limits
    max_users: int | None             # None = unlimited
    current_user_count: int
    # SMS limits
    sms_monthly_limit: int | None     # None = unlimited
    sms_sent_this_month: int
    # Storage limits
    storage_limit_bytes: int | None   # None = unlimited
    storage_used_bytes: int
    # Features
    features: dict[str, Any]          # Tenant features JSONB (add-ons + overrides)
    available_addons: list[str]       # Add-ons available for purchase on current plan
```

---

## Testing Checklist

- [ ] **Student limit:** Trial tenant with 100 students → create 101st → 403 STUDENT_LIMIT_EXCEEDED
- [ ] **Student limit:** Starter with 300 students → 403; Professional → no limit
- [ ] **User limit:** Starter with 10 users → create 11th → 403 USER_LIMIT_EXCEEDED
- [ ] **User limit:** Professional with 50 users → 403; Enterprise → no limit
- [ ] **SMS limit:** Starter sends 50 SMS → 51st → 403 SMS_LIMIT_EXCEEDED
- [ ] **SMS limit:** Professional 200/mo; Enterprise → no limit
- [ ] **Feature gate — Starter:** Parent portal → 403 FEATURE_NOT_AVAILABLE
- [ ] **Feature gate — Starter:** Boarding → 403 FEATURE_NOT_AVAILABLE
- [ ] **Feature gate — Professional:** Parent portal → allowed
- [ ] **Feature gate — Professional:** Boarding without add-on → 403 ADDON_NOT_PURCHASED
- [ ] **Feature gate — Professional:** Boarding with add-on purchased → allowed
- [ ] **Feature gate — Enterprise:** All features → allowed
- [ ] **Add-on purchase:** Professional buys boarding add-on → tenant.features.boarding = true
- [ ] **Cost calculation:** 50 students x GHS 10/term = GHS 500 (Professional)
- [ ] **Cost calculation:** 50 students x GHS 27/year = GHS 1,350 (Professional annual)
- [ ] **Cost with add-on:** GHS 500 + GHS 300 boarding = GHS 800 (Professional term)
- [ ] **Paystack checkout:** Initiates correctly with calculated amount
- [ ] **Paystack webhook:** Upgrades tenant tier and enables add-ons
- [ ] **Cache invalidation:** After webhook, middleware picks up new tier
- [ ] **Frontend:** Subscription page shows correct tier comparison
- [ ] **Frontend:** Cost calculator shows live breakdown
- [ ] **Frontend:** Upgrade prompt appears on all limit/feature 403s
- [ ] **Frontend:** Add-on purchase flow works for Professional tier
