# Phase 1A: Trial Period (90 Days) + Expiration Enforcement

**Complexity:** Medium
**Requirements:** TS-003 (partial), TS-006
**Dependencies:** None
**Estimated effort:** 2-3 days

---

## Summary

Change the trial period from 30 to 90 days, fix inconsistent messaging across frontend, and implement trial expiration enforcement with a 7-day read-only grace period followed by a hard block.

---

## Task 1: Change Trial Duration Constant

### File: `backend/app/services/onboarding.py`

**Current (line ~43):**
```python
TRIAL_DAYS = 30
```

**Change to:**
```python
TRIAL_DAYS = 90
```

Also make this configurable via settings:

### File: `backend/app/config.py`

Add to the `Settings` class:
```python
TRIAL_DAYS: int = 90
TRIAL_GRACE_PERIOD_DAYS: int = 7  # Read-only grace period after trial expires
```

### File: `backend/app/services/onboarding.py`

Update the `register_school()` method to read from settings:
```python
from app.config import settings

# Replace hardcoded TRIAL_DAYS with:
trial_end = datetime.now(UTC) + timedelta(days=settings.TRIAL_DAYS)
```

---

## Task 2: Add Columns to Tenant Model

### File: `backend/app/models/tenant.py`

The tenant model already has `trial_ends_at` (datetime) and `subscription_end` (date). Verify these exist and add `subscription_expires_at` if needed for clarity.

**Check existing fields:**
- `trial_ends_at: Mapped[datetime | None]` — already exists, used for trial expiry
- `subscription_start: Mapped[date | None]` — already exists
- `subscription_end: Mapped[date | None]` — already exists

**No new columns needed** — the existing `trial_ends_at` and `subscription_end` fields are sufficient. The onboarding service already populates `trial_ends_at`.

---

## Task 3: Create Subscription Middleware

### New File: `backend/app/middleware/subscription.py`

This middleware runs AFTER TenantMiddleware (tenant context already set) and BEFORE RateLimitMiddleware.

```python
"""
Subscription enforcement middleware.

Checks tenant subscription/trial status and enforces access control:
- Active subscriptions: full access
- Trial (not expired): full access
- Trial expired (within grace period): read-only (GET/HEAD/OPTIONS only)
- Trial expired (past grace period): hard block
- Suspended/cancelled: hard block
"""

import structlog
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import settings

logger = structlog.get_logger()

# Paths exempt from subscription checks
SUBSCRIPTION_EXEMPT_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/api/v1/auth/",           # Login, refresh, logout, password reset
    "/api/v1/tenant/",         # Tenant validation
    "/api/v1/onboarding/",     # Registration
    "/api/v1/subscription/",   # Subscription management (upgrade flow)
    "/api/v1/parent/webhook/", # Paystack webhook
    "/api/v1/admissions/public/webhook/",  # Paystack webhook
)

# HTTP methods allowed during grace period (read-only)
GRACE_PERIOD_METHODS = {"GET", "HEAD", "OPTIONS"}


class SubscriptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip exempt paths
        if any(path.startswith(prefix) for prefix in SUBSCRIPTION_EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip if no tenant context (public paths handled by TenantMiddleware)
        tenant_id = getattr(request.state, "tenant_id", None)
        if not tenant_id:
            return await call_next(request)

        # Read tenant data from request.state (set by TenantMiddleware)
        tenant_status = getattr(request.state, "tenant_status", None)
        trial_ends_at = getattr(request.state, "tenant_trial_ends_at", None)
        subscription_end = getattr(request.state, "tenant_subscription_end", None)

        now = datetime.now(timezone.utc)

        # 1. Suspended or cancelled — hard block
        if tenant_status in ("suspended", "cancelled"):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Your account has been suspended. Contact support.",
                    "code": "TENANT_SUSPENDED",
                },
            )

        # 2. Trial tenant — check expiration
        if tenant_status == "trial" and trial_ends_at:
            if now > trial_ends_at:
                # Trial expired — check grace period
                grace_end = trial_ends_at + timedelta(
                    days=settings.TRIAL_GRACE_PERIOD_DAYS
                )

                if now > grace_end:
                    # Past grace period — hard block
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Your trial has expired. Upgrade to continue.",
                            "code": "TRIAL_EXPIRED",
                        },
                    )
                else:
                    # Within grace period — read-only
                    if request.method not in GRACE_PERIOD_METHODS:
                        days_left = (grace_end - now).days
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": f"Your trial has expired. You have {days_left} days of read-only access remaining. Upgrade to continue.",
                                "code": "TRIAL_GRACE_PERIOD",
                                "grace_days_remaining": days_left,
                            },
                        )

        # 3. Active subscription — check expiration
        if tenant_status == "active" and subscription_end:
            # subscription_end is a date, convert to datetime for comparison
            from datetime import time
            sub_expires = datetime.combine(subscription_end, time.max, tzinfo=timezone.utc)

            if now > sub_expires:
                grace_end = sub_expires + timedelta(
                    days=settings.TRIAL_GRACE_PERIOD_DAYS
                )
                if now > grace_end:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Your subscription has expired. Renew to continue.",
                            "code": "SUBSCRIPTION_EXPIRED",
                        },
                    )
                else:
                    if request.method not in GRACE_PERIOD_METHODS:
                        days_left = (grace_end - now).days
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": f"Your subscription has expired. You have {days_left} days of read-only access. Renew to continue.",
                                "code": "SUBSCRIPTION_GRACE_PERIOD",
                                "grace_days_remaining": days_left,
                            },
                        )

        return await call_next(request)
```

### Required: Expose tenant subscription data in TenantMiddleware

The TenantMiddleware currently only stores `tenant_id`, `tenant_subdomain`, `tenant_name` on `request.state`. We need to also store subscription fields.

### File: `backend/app/middleware/tenant.py`

**Modify the tenant lookup to also store:**
```python
request.state.tenant_status = tenant_data.get("status")
request.state.tenant_trial_ends_at = tenant_data.get("trial_ends_at")  # datetime or None
request.state.tenant_subscription_end = tenant_data.get("subscription_end")  # date or None
```

**Modify the tenant cache/lookup query to include these fields.** Currently the lookup returns `{id, subdomain, name, is_active}`. Extend it to also return `status`, `trial_ends_at`, `subscription_end`.

**In the DB query path** (when cache miss), add these columns to the SELECT.

**In the Redis cache path**, include these fields in the cached dict. When reading from cache, parse `trial_ends_at` back to datetime (stored as ISO string in Redis).

### Register Middleware in `backend/app/main.py`

```python
from app.middleware.subscription import SubscriptionMiddleware

# Middleware order (last added = first executed):
# SecurityHeaders → CORS → RateLimit → Subscription → Tenant → RequestLogging
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SubscriptionMiddleware)  # NEW — after Tenant, before RateLimit
app.add_middleware(TenantMiddleware)
app.add_middleware(RequestLoggingMiddleware)
```

**Important:** SubscriptionMiddleware must be added AFTER TenantMiddleware in the code (which means it executes AFTER TenantMiddleware in request flow, since Starlette reverses order). TenantMiddleware sets `request.state.tenant_*`, then SubscriptionMiddleware reads it.

Wait — Starlette middleware order: **last added = outermost = executed first**. So:
- TenantMiddleware (added earlier) is INNER
- SubscriptionMiddleware (added later) is OUTER

This means SubscriptionMiddleware runs BEFORE TenantMiddleware. That's wrong — we need tenant data first.

**Correct registration order:**
```python
# Added first → innermost → executes last
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SubscriptionMiddleware)  # Needs tenant data, runs after Tenant
app.add_middleware(TenantMiddleware)        # Sets tenant data, runs before Subscription
app.add_middleware(RateLimitMiddleware)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(SecurityHeadersMiddleware)
```

Execution order (request): SecurityHeaders → CORS → RateLimit → Tenant → Subscription → Logging

---

## Task 4: Create Subscription Status Endpoint

### New File: `backend/app/api/v1/endpoints/subscription.py`

```python
"""Subscription status and management endpoints."""

from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_validated_current_user
from app.models.student import Student
from app.models.staff import Staff
from app.models.tenant import Tenant
from app.schemas.subscription import SubscriptionStatusResponse

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_validated_current_user),
):
    """
    Get current tenant's subscription status including:
    - Plan details and limits
    - Current usage (student/staff counts)
    - Trial/subscription expiry dates
    - Days remaining
    - Available features
    """
    tenant_id = current_user["tenant_id"]

    # Fetch tenant
    tenant = await db.get(Tenant, UUID(tenant_id))

    # Count active students
    student_count = await db.scalar(
        select(func.count(Student.id)).where(
            Student.tenant_id == UUID(tenant_id),
            Student.status == "active",
            Student.deleted_at.is_(None),
        )
    )

    # Count active staff
    staff_count = await db.scalar(
        select(func.count(Staff.id)).where(
            Staff.tenant_id == UUID(tenant_id),
            Staff.status == "active",
            Staff.deleted_at.is_(None),
        )
    )

    # Calculate days remaining
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    days_remaining = None

    if tenant.status.value == "trial" and tenant.trial_ends_at:
        delta = tenant.trial_ends_at - now
        days_remaining = max(0, delta.days)
    elif tenant.subscription_end:
        from datetime import datetime as dt_module
        sub_dt = datetime.combine(tenant.subscription_end, datetime.min.time(), tzinfo=timezone.utc)
        delta = sub_dt - now
        days_remaining = max(0, delta.days)

    return SubscriptionStatusResponse(
        plan=tenant.subscription_tier.value,
        status=tenant.status.value,
        trial_ends_at=tenant.trial_ends_at,
        subscription_start=tenant.subscription_start,
        subscription_end=tenant.subscription_end,
        days_remaining=days_remaining,
        max_students=tenant.max_students,
        current_student_count=student_count or 0,
        max_staff=tenant.max_staff,
        current_staff_count=staff_count or 0,
        features=tenant.features or {},
    )
```

### New File: `backend/app/schemas/subscription.py`

```python
"""Pydantic schemas for subscription endpoints."""

from datetime import date, datetime
from typing import Any
from pydantic import BaseModel


class SubscriptionStatusResponse(BaseModel):
    plan: str                           # "trial", "starter", "professional", "enterprise"
    status: str                         # "trial", "active", "suspended", "cancelled"
    trial_ends_at: datetime | None      # Only for trial tenants
    subscription_start: date | None     # When paid subscription started
    subscription_end: date | None       # When paid subscription expires
    days_remaining: int | None          # Days until expiry (trial or subscription)
    max_students: int                   # Plan limit
    current_student_count: int          # Current active students
    max_staff: int                      # Plan limit
    current_staff_count: int            # Current active staff
    features: dict[str, Any]            # Feature flags from tenant.features JSONB
```

### Register Router in `backend/app/api/v1/router.py`

```python
from app.api.v1.endpoints.subscription import router as subscription_router

api_router.include_router(subscription_router)
```

Also add `/api/v1/subscription/` to the `SUBSCRIPTION_EXEMPT_PREFIXES` in the subscription middleware (already done above).

---

## Task 5: Celery Task for Trial Expiration Warnings

### New File: `backend/app/tasks/subscription.py`

```python
"""
Celery tasks for subscription management.

Scheduled via Celery Beat to run daily.
Sends warning notifications at 7 days and 1 day before trial expiration.
"""

import structlog
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy import select, and_

from app.db.session import async_session_factory
from app.models.tenant import Tenant, TenantStatus

logger = structlog.get_logger()

WARNING_THRESHOLDS = [
    (7, "trial_warning_7d"),   # 7 days before expiry
    (1, "trial_warning_1d"),   # 1 day before expiry
]


@shared_task(name="check_trial_expirations")
def check_trial_expirations():
    """
    Daily task: find trial tenants approaching expiration
    and send warning notifications.

    Uses tenant.features JSONB to track which warnings have been sent
    (key: "last_trial_warning") to avoid duplicate sends.

    Schedule: Run daily at 08:00 UTC via Celery Beat.
    """
    import asyncio
    asyncio.run(_check_trial_expirations_async())


async def _check_trial_expirations_async():
    now = datetime.now(timezone.utc)

    async with async_session_factory() as db:
        # Find all trial tenants with expiration dates
        result = await db.execute(
            select(Tenant).where(
                and_(
                    Tenant.status == TenantStatus.TRIAL,
                    Tenant.trial_ends_at.is_not(None),
                    Tenant.is_active.is_(True),
                )
            )
        )
        tenants = result.scalars().all()

        for tenant in tenants:
            days_until_expiry = (tenant.trial_ends_at - now).days

            for threshold_days, warning_key in WARNING_THRESHOLDS:
                if days_until_expiry <= threshold_days:
                    # Check if this warning was already sent
                    features = tenant.features or {}
                    last_warning = features.get("last_trial_warning")

                    if last_warning == warning_key:
                        continue  # Already sent this warning

                    # Send notification
                    await _send_trial_warning(tenant, days_until_expiry)

                    # Mark warning as sent
                    if not tenant.features:
                        tenant.features = {}
                    tenant.features["last_trial_warning"] = warning_key
                    await db.flush()

                    logger.info(
                        "trial_warning_sent",
                        tenant_id=str(tenant.id),
                        subdomain=tenant.subdomain,
                        days_remaining=days_until_expiry,
                        warning_type=warning_key,
                    )
                    break  # Only send the most urgent warning

        await db.commit()


async def _send_trial_warning(tenant, days_remaining: int):
    """
    Send trial expiration warning via email to the tenant's admin user.

    Uses the existing email service. Find the admin user by querying
    users with role school_admin or chain_admin for this tenant.
    """
    # Implementation: query admin user email, send via EmailService
    # Use existing email templates pattern from onboarding service
    pass  # TODO: implement with existing email infrastructure
```

### Celery Beat Schedule

Add to Celery Beat configuration (wherever it's defined, likely `backend/app/celery_app.py` or `backend/celery_config.py`):

```python
beat_schedule = {
    "check-trial-expirations": {
        "task": "check_trial_expirations",
        "schedule": crontab(hour=8, minute=0),  # Daily at 08:00 UTC
    },
}
```

---

## Task 6: Fix Inconsistent Frontend Messaging

### File: `frontend/app/page.tsx` (Landing Page)

Find the pricing/hero section that mentions trial duration. Change any occurrence of "14 days" or "14-day" to "90 days" / "90-day".

**Search for:** `14 day`, `14-day`, `30 day`, `30-day`
**Replace with:** `90 days` / `90-day`

### File: `frontend/app/(auth)/register/success/page.tsx`

**Current (~line 279):**
```
Your 30-day free trial has started
```

**Change to:**
```
Your 90-day free trial has started
```

### File: `frontend/components/landing/pricing.tsx`

**Current (~line 11):**
```
14 days
```

**Change to:**
```
90 days
```

Ensure ALL references to trial duration across the frontend say "90 days". Run a project-wide search:
```bash
grep -rn "14.day\|30.day\|14 day\|30 day" frontend/
```

---

## Task 7: Frontend Trial Banner Component

### New File: `frontend/components/subscription/trial-banner.tsx`

```tsx
"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, X, ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getSubscriptionStatus } from "@/actions/subscription.action";

interface TrialBannerProps {
  // Subscription status can be passed from layout to avoid refetching
  initialStatus?: {
    plan: string;
    status: string;
    days_remaining: number | null;
  };
}

export function TrialBanner({ initialStatus }: TrialBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const [status, setStatus] = useState(initialStatus);

  useEffect(() => {
    // Check if dismissed this session
    if (sessionStorage.getItem("trial-banner-dismissed") === "true") {
      setDismissed(true);
    }

    // Fetch status if not provided
    if (!initialStatus) {
      getSubscriptionStatus().then((result) => {
        if (result.success) setStatus(result.data);
      });
    }
  }, [initialStatus]);

  if (dismissed || !status) return null;
  if (status.plan !== "trial") return null;
  if (status.days_remaining === null) return null;

  const days = status.days_remaining;

  // Color coding: green (>7 days), yellow (3-7 days), red (<=3 days)
  let bgColor = "bg-blue-50 border-blue-200 text-blue-800";
  let iconColor = "text-blue-600";
  if (days <= 3) {
    bgColor = "bg-red-50 border-red-200 text-red-800";
    iconColor = "text-red-600";
  } else if (days <= 7) {
    bgColor = "bg-amber-50 border-amber-200 text-amber-800";
    iconColor = "text-amber-600";
  }

  const handleDismiss = () => {
    sessionStorage.setItem("trial-banner-dismissed", "true");
    setDismissed(true);
  };

  return (
    <div className={`${bgColor} border-b px-4 py-2 flex items-center justify-between text-sm`}>
      <div className="flex items-center gap-2">
        <AlertTriangle className={`h-4 w-4 ${iconColor}`} />
        <span>
          {days > 0
            ? `Your trial expires in ${days} day${days !== 1 ? "s" : ""}. Upgrade to continue using SIMS Plus.`
            : "Your trial has expired. Upgrade to continue."}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Link href="/settings/subscription">
          <Button size="sm" variant="outline" className="h-7 text-xs">
            Upgrade Now <ArrowRight className="ml-1 h-3 w-3" />
          </Button>
        </Link>
        {days > 3 && (
          <button onClick={handleDismiss} className="p-1 hover:opacity-70">
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  );
}
```

### New File: `frontend/components/subscription/expired-gate.tsx`

```tsx
"use client";

import { ShieldAlert } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface ExpiredGateProps {
  code: "TRIAL_EXPIRED" | "SUBSCRIPTION_EXPIRED" | "TRIAL_GRACE_PERIOD" | "SUBSCRIPTION_GRACE_PERIOD";
  graceDaysRemaining?: number;
}

export function ExpiredGate({ code, graceDaysRemaining }: ExpiredGateProps) {
  const isGracePeriod = code.includes("GRACE_PERIOD");
  const isTrial = code.includes("TRIAL");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="mx-4 max-w-md rounded-lg border bg-card p-8 text-center shadow-lg">
        <ShieldAlert className="mx-auto h-12 w-12 text-destructive" />
        <h2 className="mt-4 text-xl font-semibold">
          {isTrial ? "Trial Expired" : "Subscription Expired"}
        </h2>
        <p className="mt-2 text-muted-foreground">
          {isGracePeriod
            ? `You have ${graceDaysRemaining} day${graceDaysRemaining !== 1 ? "s" : ""} of read-only access remaining. Upgrade to regain full access.`
            : `Your ${isTrial ? "trial" : "subscription"} has expired. Upgrade to continue using SIMS Plus.`}
        </p>
        <div className="mt-6 flex flex-col gap-2">
          <Link href="/settings/subscription">
            <Button className="w-full">Choose a Plan</Button>
          </Link>
          <Link href="mailto:support@simsplus.io">
            <Button variant="ghost" className="w-full">
              Contact Support
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
```

---

## Task 8: Frontend Subscription Action

### New File: `frontend/actions/subscription.action.ts`

```typescript
"use server";

import { apiGet } from "@/lib/api";
import type { ActionResult } from "@/types";

export interface SubscriptionStatus {
  plan: string;
  status: string;
  trial_ends_at: string | null;
  subscription_start: string | null;
  subscription_end: string | null;
  days_remaining: number | null;
  max_students: number;
  current_student_count: number;
  max_staff: number;
  current_staff_count: number;
  features: Record<string, any>;
}

export async function getSubscriptionStatus(): Promise<ActionResult<SubscriptionStatus>> {
  try {
    const response = await apiGet<SubscriptionStatus>("/subscription/status");
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subscription status",
    };
  }
}
```

---

## Task 9: Integrate Trial Banner into Dashboard Layout

### File: `frontend/app/(dashboard)/layout.tsx`

Add the trial banner at the top of the dashboard layout, before the sidebar/content area:

```tsx
import { TrialBanner } from "@/components/subscription/trial-banner";

// In the layout's return JSX, add before the main content:
<TrialBanner />
```

### Global 403 Handling

Modify `frontend/lib/api.ts` to detect subscription-related 403 errors and expose the error code:

```typescript
// In the error handling section of the fetch wrapper:
if (response.status === 403) {
  const body = await response.json().catch(() => null);
  const code = body?.code;

  if (["TRIAL_EXPIRED", "SUBSCRIPTION_EXPIRED", "TRIAL_GRACE_PERIOD", "SUBSCRIPTION_GRACE_PERIOD", "TENANT_SUSPENDED"].includes(code)) {
    // Throw a specific error that the layout can catch
    throw new SubscriptionError(body.detail, response.status, code, body.grace_days_remaining);
  }
}
```

Add new error class:
```typescript
export class SubscriptionError extends ApiError {
  constructor(
    message: string,
    status: number,
    public code: string,
    public graceDaysRemaining?: number,
  ) {
    super(message, status);
  }
}
```

---

## Task 10: Cache Invalidation on Subscription Changes

When a tenant upgrades their plan or their trial/subscription status changes, the Redis-cached tenant data must be invalidated so the SubscriptionMiddleware picks up the new status.

### Where to invalidate:
- After Paystack webhook confirms payment → call `invalidate_tenant_cache()`
- After admin manually changes subscription → call `invalidate_tenant_cache()`
- The existing `invalidate_tenant_cache(redis_client, subdomain)` function handles this

This is already supported by the existing infrastructure. Just ensure any new subscription mutation endpoint calls it.

---

## Testing Checklist

- [ ] Register new school — verify `trial_ends_at` is set to 90 days from now
- [ ] Landing page shows "90-day" trial messaging
- [ ] Registration success page shows "90-day" trial messaging
- [ ] `GET /subscription/status` returns correct plan, counts, days_remaining
- [ ] Trial banner appears in dashboard with correct day count
- [ ] Trial banner color changes: blue (>7d), amber (3-7d), red (<=3d)
- [ ] Trial banner dismissible per session (reappears on next login)
- [ ] After trial expires: GET requests succeed (grace period)
- [ ] After trial expires: POST/PUT/DELETE return 403 TRIAL_GRACE_PERIOD
- [ ] After grace period expires: ALL requests return 403 TRIAL_EXPIRED
- [ ] Expired gate overlay renders correctly
- [ ] Suspended tenant gets 403 TENANT_SUSPENDED on all requests
- [ ] Cache invalidation works when subscription changes
