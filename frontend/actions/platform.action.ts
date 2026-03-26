"use server";

import { cookies } from "next/headers";
import type { ActionResult } from "@/types";
import type {
  PlatformLoginResult,
  PlatformLoginResponse,
  PlatformMFARequiredResponse,
  PlatformMFASetupRequiredResponse,
  PlatformUser,
  TenantListResponse,
  TenantDetail,
  ImpersonationResponse,
  PlatformAnalytics,
  PlatformAuditLogResponse,
  MFAGenerateResponse,
} from "@/types/platform.type";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ============================================================
// Helpers
// ============================================================

/**
 * Get platform access token from cookies.
 * Platform admin uses SEPARATE cookies from school auth.
 */
async function getPlatformToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("platform_access_token")?.value || null;
}

/**
 * Make authenticated platform API call.
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
      ...(options.headers as Record<string, string> | undefined),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail =
      typeof error.detail === "string"
        ? error.detail
        : error.message || `Request failed: ${response.status}`;
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * Set platform auth cookies (separate namespace from school cookies).
 */
async function setPlatformAuthCookies(
  accessToken: string,
  refreshToken: string,
) {
  const cookieStore = await cookies();
  cookieStore.set("platform_access_token", accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60, // 1 hour
  });
  cookieStore.set("platform_refresh_token", refreshToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 60 * 60, // 7 days
  });
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
      const detail =
        typeof error.detail === "string"
          ? error.detail
          : "Login failed";
      return {
        success: false,
        error: detail,
        code: response.status,
      };
    }

    const data = await response.json();

    // MFA required -- return token for TOTP verification step
    if (data.mfa_required) {
      return {
        success: true,
        data: data as PlatformMFARequiredResponse,
      };
    }

    // MFA setup required -- store setup_token temporarily
    if (data.mfa_setup_required) {
      return {
        success: true,
        data: data as PlatformMFASetupRequiredResponse,
      };
    }

    // Full login success -- set cookies
    const loginData = data as PlatformLoginResponse;
    await setPlatformAuthCookies(loginData.access_token, loginData.refresh_token);

    return { success: true, data: loginData };
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
// MFA
// ============================================================

export async function platformMfaVerify(
  mfaPendingToken: string,
  totpCode: string,
): Promise<ActionResult<PlatformLoginResult>> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/platform/mfa/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        mfa_pending_token: mfaPendingToken,
        totp_code: totpCode,
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error:
          typeof error.detail === "string"
            ? error.detail
            : "MFA verification failed",
        code: response.status,
      };
    }

    const data = await response.json() as PlatformLoginResponse;
    await setPlatformAuthCookies(data.access_token, data.refresh_token);
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA verification failed",
    };
  }
}

export async function platformMfaGenerate(
  setupToken: string,
): Promise<ActionResult<MFAGenerateResponse>> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/platform/mfa/generate`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${setupToken}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error:
          typeof error.detail === "string"
            ? error.detail
            : "Failed to generate MFA",
      };
    }

    const data = await response.json() as MFAGenerateResponse;
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate MFA",
    };
  }
}

export async function platformMfaSetup(
  setupToken: string,
  totpCode: string,
  mfaSecret: string,
): Promise<ActionResult<PlatformLoginResult>> {
  try {
    const response = await fetch(`${API_BASE}/api/v1/platform/mfa/setup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        setup_token: setupToken,
        totp_code: totpCode,
        mfa_secret: mfaSecret,
      }),
      cache: "no-store",
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return {
        success: false,
        error:
          typeof error.detail === "string"
            ? error.detail
            : "MFA setup failed",
        code: response.status,
      };
    }

    const data = await response.json() as PlatformLoginResponse;
    await setPlatformAuthCookies(data.access_token, data.refresh_token);
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA setup failed",
    };
  }
}

export async function refreshPlatformToken(): Promise<ActionResult<{ access_token: string }>> {
  try {
    const cookieStore = await cookies();
    const refreshToken = cookieStore.get("platform_refresh_token")?.value;

    if (!refreshToken) {
      return { success: false, error: "No refresh token" };
    }

    const response = await fetch(`${API_BASE}/api/v1/platform/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${refreshToken}`,
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return { success: false, error: "Token refresh failed" };
    }

    const data = await response.json() as PlatformLoginResponse;
    await setPlatformAuthCookies(data.access_token, data.refresh_token);
    return { success: true, data: { access_token: data.access_token } };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Token refresh failed",
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
      `/platform/tenants?${query.toString()}`,
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
      `/platform/tenants/${tenantId}`,
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
): Promise<ActionResult<TenantDetail>> {
  try {
    const result = await platformFetch<TenantDetail>(
      `/platform/tenants/${tenantId}`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
    );
    return { success: true, data: result };
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
): Promise<ActionResult<void>> {
  try {
    await platformFetch(`/platform/tenants/${tenantId}/suspend`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to suspend tenant",
    };
  }
}

export async function activateTenant(
  tenantId: string,
): Promise<ActionResult<void>> {
  try {
    await platformFetch(`/platform/tenants/${tenantId}/activate`, {
      method: "POST",
    });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to activate tenant",
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

    // Set the impersonation token as the school's access_token cookie
    const cookieStore = await cookies();
    cookieStore.set("access_token", data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 60, // 30 minutes
    });
    // Set a non-httpOnly cookie for client-side impersonation detection
    cookieStore.set("is_impersonation", "true", {
      httpOnly: false,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 30 * 60,
    });

    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to impersonate",
    };
  }
}

export async function exitImpersonation(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");
  cookieStore.delete("is_impersonation");
}

// ============================================================
// Analytics
// ============================================================

export async function getPlatformAnalytics(): Promise<
  ActionResult<PlatformAnalytics>
> {
  try {
    const data = await platformFetch<PlatformAnalytics>(
      "/platform/analytics",
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to get analytics",
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
      `/platform/audit-log?${query.toString()}`,
    );
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to get audit log",
    };
  }
}
