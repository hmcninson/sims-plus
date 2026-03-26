# Phase 3: Frontend — Platform Portal

**Complexity:** Medium-Large
**Dependencies:** Phase 2 (backend endpoints must be working)
**Estimated effort:** 3-4 days

---

## Summary

Build the platform admin portal accessible at `admin.simsplus.io`. This includes modifying proxy.ts to handle the admin subdomain, creating the platform login page, tenant management dashboard, impersonation flow, and the impersonation banner shown in school dashboards.

---

## Task 1: Update proxy.ts for Admin Subdomain

### File: `frontend/proxy.ts`

Read this file first. Currently, "admin" is in `RESERVED_SUBDOMAINS` (line 17-24) and is rejected by `extractSubdomain()`. We need to:

1. **Keep "admin" in `RESERVED_SUBDOMAINS`** (RISK FIX R-BC3: prevents `?subdomain=admin` from persisting as a cookie and causing routing confusion in dev mode)
2. Add special-case handling BEFORE subdomain extraction in the proxy function

**RISK NOTE (R-BC3):** The original plan removed "admin" from the frontend RESERVED_SUBDOMAINS set. This is dangerous because in development mode, visiting `?subdomain=admin` would set an `x-subdomain` cookie to "admin", and all subsequent requests would try to route to a nonexistent "admin" tenant. By keeping "admin" in the reserved set, `extractSubdomain()` continues to return null for it. The admin domain detection happens BEFORE `extractSubdomain()` is called, so it is handled correctly regardless.

**RISK NOTE (R14):** The actual proxy.ts file exports `export default function proxy()`, NOT `export async function middleware()`. The code below uses the correct function signature.

**Changes:**

```typescript
// In the proxy function, add admin detection BEFORE subdomain extraction.
// Do NOT remove "admin" from RESERVED_SUBDOMAINS.

export default function proxy(request: NextRequest): NextResponse {
  // In production behind Nginx, the original host may be in x-forwarded-host
  const hostname = request.headers.get("x-forwarded-host")
    || request.headers.get("host")
    || "";
  const pathname = request.nextUrl.pathname;
  const searchParams = request.nextUrl.searchParams;
  const hostWithoutPort = hostname.split(":")[0];

  // ============================================================
  // Platform Admin Portal (admin.simsplus.io or admin.localhost)
  // Must be checked BEFORE extractSubdomain() to intercept the
  // "admin" subdomain before it hits the RESERVED_SUBDOMAINS check.
  // ============================================================
  const isAdminDomain =
    hostWithoutPort === "admin.simsplus.io" ||
    hostWithoutPort === "admin.staging.simsplus.io" ||
    hostWithoutPort.startsWith("admin.localhost") ||
    (hostWithoutPort === "localhost" &&
      searchParams.get("subdomain") === "admin");

  if (isAdminDomain) {
    const requestHeaders = new Headers(request.headers);
    // Platform admin portal -- do NOT set x-subdomain
    requestHeaders.set("x-platform-admin", "true");
    requestHeaders.set("x-pathname", pathname);

    // Redirect non-login platform paths without auth cookie to login
    const platformToken = request.cookies.get("platform_access_token")?.value;
    const isPublicPath =
      pathname.startsWith("/platform-login") ||
      pathname.startsWith("/platform/mfa") ||
      pathname.startsWith("/_next") ||
      pathname.startsWith("/api") ||
      pathname === "/favicon.ico";

    if (!platformToken && !isPublicPath) {
      return NextResponse.redirect(
        new URL("/platform-login", request.url)
      );
    }

    return NextResponse.next({
      request: { headers: requestHeaders },
    });
  }

  // ... rest of existing proxy function unchanged ...
  // (extractSubdomain, subdomain handling, etc.)
}
```

**Key points:**
- No `x-subdomain` header/cookie set for admin domain — prevents `TenantMiddleware` from resolving a tenant.
- Separate cookie name `platform_access_token` — doesn't conflict with school auth cookies.
- Development mode: `?subdomain=admin` on localhost works for testing.
- Redirect unauthenticated requests to `/platform-login`.

---

## Task 2: Create Platform Types

### New File: `frontend/types/platform.type.ts`

```typescript
/**
 * Types for the platform admin portal.
 */

export interface PlatformUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "platform_admin";
  mfa_enabled: boolean;
}

export interface PlatformLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: PlatformUser;
}

export interface PlatformMFARequiredResponse {
  mfa_required: true;
  mfa_pending_token: string;
}

export interface PlatformMFASetupRequiredResponse {
  mfa_setup_required: true;
  access_token: string;
  message: string;
}

export type PlatformLoginResult =
  | PlatformLoginResponse
  | PlatformMFARequiredResponse
  | PlatformMFASetupRequiredResponse;

export interface TenantSummary {
  id: string;
  name: string;
  subdomain: string;
  tenant_type: string;
  status: string;
  subscription_tier: string;
  is_active: boolean;
  max_students: number;
  max_staff: number;
  created_at: string;
  student_count: number;
  staff_count: number;
  school_count: number;
}

export interface TenantDetail extends TenantSummary {
  email: string | null;
  phone: string | null;
  logo_url: string | null;
  primary_color: string | null;
  features: Record<string, unknown> | null;
  subscription_start: string | null;
  subscription_end: string | null;
  trial_ends_at: string | null;
  updated_at: string;
}

export interface TenantListResponse {
  items: TenantSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface ImpersonationResponse {
  access_token: string;
  tenant_id: string;
  tenant_name: string;
  tenant_subdomain: string;
  expires_in: number;
}

export interface PlatformAnalytics {
  total_tenants: number;
  active_tenants: number;
  trial_tenants: number;
  suspended_tenants: number;
  total_students: number;
  total_staff: number;
  total_schools: number;
  tenants_by_plan: Record<string, number>;
  recent_registrations: TenantSummary[];
}

export interface PlatformAuditEntry {
  id: string;
  actor_user_id: string;
  actor_email: string | null;
  action: string;
  target_tenant_id: string | null;
  target_tenant_name: string | null;
  target_entity_type: string | null;
  target_entity_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface PlatformAuditLogResponse {
  items: PlatformAuditEntry[];
  total: number;
  page: number;
  page_size: number;
}
```

---

## Task 3: Create Platform Server Actions

### New File: `frontend/actions/platform.action.ts`

```typescript
"use server";

import { cookies } from "next/headers";
import type { ActionResult } from "@/types";
import type {
  PlatformLoginResult,
  PlatformUser,
  TenantListResponse,
  TenantDetail,
  ImpersonationResponse,
  PlatformAnalytics,
  PlatformAuditLogResponse,
} from "@/types/platform.type";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Helper: get platform access token from cookies.
 * Platform admin uses SEPARATE cookies from school auth.
 */
async function getPlatformToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("platform_access_token")?.value || null;
}

/**
 * Helper: make authenticated platform API call.
 * Does NOT send x-subdomain header (platform endpoints are tenant-agnostic).
 */
async function platformFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getPlatformToken();
  if (!token) {
    throw new Error("Not authenticated");
  }

  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

// ============================================================
// Auth
// ============================================================

export async function platformLogin(
  email: string,
  password: string,
): Promise<ActionResult<PlatformLoginResult>> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/platform/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return { success: false, error: error.detail || "Login failed" };
    }

    const data = await response.json();

    // MFA required
    if (data.mfa_required) {
      return { success: true, data: data as PlatformLoginResult };
    }

    // MFA setup required
    if (data.mfa_setup_required) {
      // Store temp token for MFA setup
      const cookieStore = await cookies();
      cookieStore.set("platform_access_token", data.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        maxAge: 30 * 60, // 30 minutes for setup
      });
      return { success: true, data: data as PlatformLoginResult };
    }

    // Full login — set cookies
    const cookieStore = await cookies();
    cookieStore.set("platform_access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60, // 1 hour
    });
    cookieStore.set("platform_refresh_token", data.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 7 * 24 * 60 * 60, // 7 days
    });

    return { success: true, data: data as PlatformLoginResult };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Login failed",
    };
  }
}

export async function platformLogout(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete("platform_access_token");
  cookieStore.delete("platform_refresh_token");
}

export async function getPlatformUser(): Promise<ActionResult<PlatformUser>> {
  try {
    const data = await platformFetch<PlatformUser>("/platform/me");
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get user",
    };
  }
}

// ============================================================
// Tenants
// ============================================================

export async function listTenants(params: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  tier?: string;
}): Promise<ActionResult<TenantListResponse>> {
  try {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.search) query.set("search", params.search);
    if (params.status) query.set("status", params.status);
    if (params.tier) query.set("tier", params.tier);

    const data = await platformFetch<TenantListResponse>(
      `/platform/tenants?${query.toString()}`
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to list tenants",
    };
  }
}

export async function getTenantDetail(
  tenantId: string,
): Promise<ActionResult<TenantDetail>> {
  try {
    const data = await platformFetch<TenantDetail>(
      `/platform/tenants/${tenantId}`
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get tenant",
    };
  }
}

export async function updateTenant(
  tenantId: string,
  data: Record<string, unknown>,
): Promise<ActionResult> {
  try {
    await platformFetch(`/platform/tenants/${tenantId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update tenant",
    };
  }
}

export async function suspendTenant(
  tenantId: string,
  reason: string,
): Promise<ActionResult> {
  try {
    await platformFetch(`/platform/tenants/${tenantId}/suspend`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to suspend tenant",
    };
  }
}

export async function activateTenant(
  tenantId: string,
): Promise<ActionResult> {
  try {
    await platformFetch(`/platform/tenants/${tenantId}/activate`, {
      method: "POST",
    });
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to activate tenant",
    };
  }
}

// ============================================================
// Impersonation
// ============================================================

export async function impersonateTenant(
  tenantId: string,
): Promise<ActionResult<ImpersonationResponse>> {
  try {
    const data = await platformFetch<ImpersonationResponse>(
      `/platform/impersonate/${tenantId}`,
      { method: "POST" },
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to impersonate",
    };
  }
}

// ============================================================
// Analytics
// ============================================================

export async function getPlatformAnalytics(): Promise<
  ActionResult<PlatformAnalytics>
> {
  try {
    const data = await platformFetch<PlatformAnalytics>(
      "/platform/analytics"
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get analytics",
    };
  }
}

// ============================================================
// Audit Log
// ============================================================

export async function getPlatformAuditLog(params: {
  page?: number;
  page_size?: number;
  action?: string;
}): Promise<ActionResult<PlatformAuditLogResponse>> {
  try {
    const query = new URLSearchParams();
    if (params.page) query.set("page", String(params.page));
    if (params.page_size) query.set("page_size", String(params.page_size));
    if (params.action) query.set("action", params.action);

    const data = await platformFetch<PlatformAuditLogResponse>(
      `/platform/audit-log?${query.toString()}`
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get audit log",
    };
  }
}
```

---

## Task 4: Create Platform Login Page

### New File: `frontend/app/(platform)/platform-login/page.tsx`

A standalone login page for admin.simsplus.io. Follows the pattern of the existing school login page but simpler (no tenant branding, no registration link).

**Key elements:**
- SIMS Plus logo + "Platform Administration" title
- Email + password form
- MFA verification step (if MFA enabled)
- MFA setup redirect (if first login)
- Error handling for invalid credentials, lockout
- Redirect to `/platform/tenants` on success

---

## Task 5: Create Platform Layout

### New File: `frontend/app/(platform)/layout.tsx`

Server component layout for all platform admin pages. Includes:
- Platform sidebar with navigation (Tenants, Analytics, Audit Log)
- User menu (profile, logout)
- No school branding (platform-neutral design)

### New File: `frontend/app/(platform)/platform/layout.tsx`

Inner layout that wraps authenticated platform pages. Checks for `platform_access_token` cookie — redirects to login if missing.

---

## Task 6: Create Platform Dashboard Pages

### Tenant List Page

**File:** `frontend/app/(platform)/platform/tenants/page.tsx`

- Server component that fetches initial tenant list
- Search bar with debounced search
- Filter dropdowns: status (active, trial, suspended), subscription tier
- Table with columns: Name, Subdomain, Type, Plan, Status, Students, Staff, Created
- Row actions: View Details, Impersonate, Suspend/Activate
- Pagination

### Tenant Detail Page

**File:** `frontend/app/(platform)/platform/tenants/[id]/page.tsx`

- Tenant header with name, status badge, actions
- Overview cards: student count, staff count, school count
- Subscription details (tier, limits, dates)
- Schools list (for chain tenants)
- Settings section (update subscription, limits)
- Impersonate button
- Suspend/Activate toggle

### Analytics Page

**File:** `frontend/app/(platform)/platform/analytics/page.tsx`

- Overview cards: total tenants, active, trial, suspended
- Total students, staff, schools across platform
- Tenants by plan (pie/bar chart using Recharts)
- Recent registrations table

### Audit Log Page

**File:** `frontend/app/(platform)/platform/audit-log/page.tsx`

- Paginated table of audit entries
- Filter by action type
- Columns: Timestamp, Actor, Action, Target Tenant, Details
- Expandable rows to show full details JSON

---

## Task 7: Create Impersonation Banner

### New File: `frontend/components/platform/impersonation-banner.tsx`

```typescript
"use client";

/**
 * Banner shown at the top of the school dashboard when a platform admin
 * is impersonating a tenant. Non-dismissible.
 *
 * Reads is_impersonation from the JWT claims (decoded client-side from
 * the access token payload, NOT from httpOnly cookie).
 *
 * Shows: "You are viewing [School Name] as Platform Admin"
 * Button: "Exit Impersonation" → clears school cookies, redirects to
 *         admin.simsplus.io/platform/tenants
 */
```

**Key behaviors:**
- Sticky banner at the very top of the page (above even the header)
- Amber/yellow background for visibility
- Shows target school name
- "Exit Impersonation" button clears the impersonation token cookies and redirects to the platform admin portal
- Non-dismissible (cannot be closed)

### Integration Point

**File:** `frontend/app/(dashboard)/layout.tsx`

Add the impersonation banner at the top of the dashboard layout. It should only render when the JWT contains `is_impersonation: true`.

To detect impersonation without decoding the JWT on the client:
- Option A: Pass `is_impersonation` as a server-side prop from the layout's server component (decode JWT server-side)
- Option B: Store a separate `is_impersonation` non-httpOnly cookie when setting the impersonation token

**Recommended: Option A** — decode the JWT's payload on the server side in the layout component and pass `isImpersonation` as a prop to a client component wrapper.

---

## Task 8: Impersonation Flow (Frontend)

When a platform admin clicks "Impersonate" on a tenant:

1. Call `impersonateTenant(tenantId)` server action
2. Receive `ImpersonationResponse` with `access_token` and `tenant_subdomain`
3. Set the impersonation token as the school's `access_token` cookie:
   ```typescript
   // Set as school auth cookie (NOT platform cookie)
   cookies().set("access_token", data.access_token, {
     httpOnly: true,
     secure: process.env.NODE_ENV === "production",
     sameSite: "lax",
     path: "/",
     maxAge: 30 * 60, // 30 minutes (matches token expiry)
   });
   ```
4. Redirect to `https://${data.tenant_subdomain}.simsplus.io/dashboard`
5. The impersonation token passes `ValidatedTokenTenant` because its `tenant_id` matches the target subdomain
6. The impersonation banner appears because the JWT has `is_impersonation: true`
7. "Exit Impersonation" clears the school cookie and redirects back to `admin.simsplus.io`

**Development mode:** Redirect to `localhost:3000?subdomain=${data.tenant_subdomain}` instead.

---

## Verification Checklist

- [ ] admin.simsplus.io (or admin.localhost:3000) shows platform login page
- [ ] Unauthenticated users redirected to /platform-login
- [ ] Platform login works with valid credentials
- [ ] MFA flow works for platform admins
- [ ] MFA setup required on first login
- [ ] Platform sidebar shows Tenants, Analytics, Audit Log
- [ ] Tenant list loads with search, filters, pagination
- [ ] Tenant detail page shows correct data
- [ ] Impersonate button creates impersonation token
- [ ] Impersonation redirects to target school's dashboard
- [ ] Impersonation banner shown during impersonation
- [ ] "Exit Impersonation" returns to platform portal
- [ ] Analytics page shows platform-wide counts
- [ ] Audit log page shows platform admin actions
- [ ] Platform cookies (platform_access_token) separate from school cookies (access_token)
- [ ] No x-subdomain header set for admin domain requests
- [ ] School login flows unaffected by proxy.ts changes
