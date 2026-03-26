/**
 * SIMS Plus - API Configuration
 *
 * Server-side API client for use with Server Actions.
 * Uses process.env.API_URL which is only available server-side.
 *
 * Chain support: automatically reads the "x-active-school" cookie and
 * includes it as the X-Active-School header on all API calls. This is
 * centralized here so individual action files do not need modification.
 */
import "server-only";

import { cookies } from "next/headers";

const API_BASE_URL = process.env.API_URL || "http://localhost:8000/api/v1";

/**
 * Read the active school ID from the x-active-school cookie.
 * Returns undefined if the cookie is not set (single-school tenant).
 * Wrapped in try/catch because cookies() is only available during
 * a Server Action or Route Handler render -- not during static build.
 */
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function getActiveSchoolFromCookie(): Promise<string | undefined> {
  try {
    const cookieStore = await cookies();
    const value = cookieStore.get("x-active-school")?.value;
    // Validate UUID format to prevent arbitrary values being forwarded as header
    if (value && UUID_RE.test(value)) return value;
    return undefined;
  } catch {
    // cookies() throws outside of request context (e.g., build time)
    return undefined;
  }
}

/**
 * Typed API error that preserves HTTP status code and request ID
 * for structured error handling in callers (e.g., distinguishing
 * 401 unauthorized from 429 rate limited).
 */
export class ApiError extends Error {
  /** True when the server explicitly flagged the 401 as an inactivity timeout */
  public readonly sessionExpired: boolean;

  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
    sessionExpired = false,
  ) {
    super(message);
    this.name = "ApiError";
    this.sessionExpired = sessionExpired;
  }
}

/**
 * Subscription/limit error thrown when the backend returns a 403
 * with a subscription-related error code (e.g., TRIAL_EXPIRED,
 * STUDENT_LIMIT_EXCEEDED). Frontend can catch this to show appropriate UI.
 */
export class SubscriptionError extends ApiError {
  public readonly code: string;
  public readonly graceDaysRemaining?: number;

  constructor(
    message: string,
    status: number,
    code: string,
    graceDaysRemaining?: number,
  ) {
    super(message, status);
    this.name = "SubscriptionError";
    this.code = code;
    this.graceDaysRemaining = graceDaysRemaining;
  }
}

/** Subscription/limit 403 error codes that trigger SubscriptionError */
const SUBSCRIPTION_ERROR_CODES = new Set([
  "TRIAL_EXPIRED",
  "SUBSCRIPTION_EXPIRED",
  "TRIAL_GRACE_PERIOD",
  "SUBSCRIPTION_GRACE_PERIOD",
  "TENANT_SUSPENDED",
  "TENANT_CANCELLED",
  "STUDENT_LIMIT_EXCEEDED",
  "USER_LIMIT_EXCEEDED",
  "SMS_LIMIT_EXCEEDED",
  "STAFF_LIMIT_EXCEEDED",
  "FEATURE_NOT_AVAILABLE",
  "ADDON_NOT_PURCHASED",
]);

/** Parse FastAPI error response body into a human-readable message. */
function parseErrorDetail(
  body: Record<string, unknown>,
  fallbackMessage: string,
): string {
  if (body.detail) {
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((e: { msg?: string; message?: string }) => e.msg || e.message || JSON.stringify(e))
        .join(", ");
    }
    if (typeof body.detail === "object") {
      const d = body.detail as Record<string, string>;
      return d.message || d.msg || JSON.stringify(body.detail);
    }
  }
  if (typeof body.message === "string") return body.message;
  return fallbackMessage;
}

interface FetchOptions extends RequestInit {
  token?: string;
  subdomain?: string;
  activeSchoolId?: string;
}

/**
 * Fetch wrapper with error handling.
 *
 * Automatically includes X-Active-School from the cookie when no explicit
 * activeSchoolId is provided. This ensures chain school context propagates
 * through all API calls without modifying individual action files.
 */
export async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, subdomain, activeSchoolId, ...fetchOptions } = options;

  // Auto-resolve active school from cookie if not explicitly provided
  const resolvedSchoolId = activeSchoolId ?? (await getActiveSchoolFromCookie());

  // Correlate client requests with backend structured logs
  const requestId = crypto.randomUUID();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    "X-Request-ID": requestId,
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
    ...(resolvedSchoolId && { "X-Active-School": resolvedSchoolId }),
    ...options.headers,
  };

  const url = `${API_BASE_URL}${endpoint}`;

  // Caching strategy:
  // - GET requests use next.revalidate=0: always revalidates with the server
  //   but still allows Next.js per-request deduplication within a single render pass.
  // - Mutation requests (POST/PUT/PATCH/DELETE) use cache:"no-store" to bypass
  //   all caching and deduplication, since mutations must always execute.
  const method = (fetchOptions.method ?? "GET").toUpperCase();
  const isMutation = method !== "GET" && method !== "HEAD";

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    ...(isMutation
      ? { cache: "no-store" as const }
      : { next: { revalidate: 0 } }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const errorMessage = parseErrorDetail(error, `API Error: ${response.status}`);

    // Detect subscription/limit-related 403 errors and throw SubscriptionError
    if (response.status === 403) {
      const code = typeof error.code === "string" ? error.code : "";
      if (SUBSCRIPTION_ERROR_CODES.has(code)) {
        throw new SubscriptionError(
          errorMessage,
          response.status,
          code,
          typeof error.grace_days_remaining === "number"
            ? error.grace_days_remaining
            : undefined,
        );
      }
    }

    // Detect inactivity-based session expiry from the X-Session-Expired header
    const isSessionExpired =
      response.status === 401 &&
      response.headers.get("X-Session-Expired") === "inactivity";

    throw new ApiError(
      errorMessage,
      response.status,
      requestId,
      isSessionExpired,
    );
  }

  // Handle 204 No Content responses
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json();
}

interface ApiOptions {
  token?: string;
  subdomain?: string;
  activeSchoolId?: string;
}

/**
 * GET request
 */
export async function apiGet<T>(endpoint: string, options?: ApiOptions | string): Promise<T> {
  // Backward compatibility: if string passed, treat as token
  const opts = typeof options === "string" ? { token: options } : options;
  return apiFetch<T>(endpoint, { method: "GET", ...opts });
}

/**
 * POST request
 */
export async function apiPost<T>(
  endpoint: string,
  data: unknown,
  options?: ApiOptions | string
): Promise<T> {
  const opts = typeof options === "string" ? { token: options } : options;
  return apiFetch<T>(endpoint, {
    method: "POST",
    body: JSON.stringify(data),
    ...opts,
  });
}

/**
 * PUT request
 */
export async function apiPut<T>(
  endpoint: string,
  data: unknown,
  options?: ApiOptions | string
): Promise<T> {
  const opts = typeof options === "string" ? { token: options } : options;
  return apiFetch<T>(endpoint, {
    method: "PUT",
    body: JSON.stringify(data),
    ...opts,
  });
}

/**
 * PATCH request
 */
export async function apiPatch<T>(
  endpoint: string,
  data: unknown,
  options?: ApiOptions | string
): Promise<T> {
  const opts = typeof options === "string" ? { token: options } : options;
  return apiFetch<T>(endpoint, {
    method: "PATCH",
    body: JSON.stringify(data),
    ...opts,
  });
}

/**
 * DELETE request
 */
export async function apiDelete<T>(endpoint: string, options?: ApiOptions | string): Promise<T> {
  const opts = typeof options === "string" ? { token: options } : options;
  return apiFetch<T>(endpoint, { method: "DELETE", ...opts });
}

/**
 * Upload file (multipart/form-data)
 * Note: Don't set Content-Type header - browser will set it with boundary
 */
export async function apiUpload<T>(
  endpoint: string,
  formData: FormData,
  options?: ApiOptions
): Promise<T> {
  const { token, subdomain, activeSchoolId } = options || {};

  // Auto-resolve active school from cookie if not explicitly provided
  const resolvedSchoolId = activeSchoolId ?? (await getActiveSchoolFromCookie());

  const requestId = crypto.randomUUID();

  const headers: HeadersInit = {
    // Don't set Content-Type - let browser set it with boundary for multipart
    "X-Request-ID": requestId,
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
    ...(resolvedSchoolId && { "X-Active-School": resolvedSchoolId }),
  };

  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
    cache: "no-store",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      parseErrorDetail(error, `Upload Error: ${response.status}`),
      response.status,
      requestId,
    );
  }

  // Handle 204 No Content responses
  if (response.status === 204 || response.headers.get("content-length") === "0") {
    return undefined as T;
  }

  return response.json();
}
