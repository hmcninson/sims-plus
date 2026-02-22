/**
 * SIMS Plus - Server-Side API Helpers
 *
 * Automatically injects subdomain and auth token from the request context.
 * Handles 401 responses by refreshing the access token and retrying once.
 *
 * Use this in Server Actions instead of importing from lib/api.ts directly.
 *
 * Usage in a server action:
 *   import { serverGet, serverPost } from "@/lib/server-api";
 *   const students = await serverGet<Student[]>("/students");
 */
import "server-only";

import { cookies, headers } from "next/headers";
import { apiFetch, ApiError } from "@/lib/api";
import { refreshAccessToken } from "@/actions/auth.action";

/**
 * Get subdomain from the current server request context.
 * Checks headers first (set by proxy.ts), then falls back to cookie.
 */
async function getSubdomain(): Promise<string | undefined> {
  const headerStore = await headers();
  const cookieStore = await cookies();

  // proxy.ts sets x-subdomain header
  const fromHeader = headerStore.get("x-subdomain");
  if (fromHeader) return fromHeader;

  // Fallback to cookie (set by proxy.ts response)
  const fromCookie = cookieStore.get("x-subdomain")?.value;
  if (fromCookie) return fromCookie;

  return undefined;
}

/**
 * Get access token from cookies.
 */
async function getToken(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("access_token")?.value;
}

// ---------------------------------------------------------------------------
// 401 Retry Logic
// ---------------------------------------------------------------------------

interface FetchArgs {
  endpoint: string;
  method: string;
  body?: string;
}

/**
 * Execute an API request, automatically retrying once on 401 after
 * refreshing the access token. This prevents users from seeing auth
 * errors when their access token expires mid-session.
 *
 * Max 1 retry to avoid infinite refresh loops (e.g., if the refresh
 * token is also expired, the error propagates to the caller).
 */
async function fetchWithRetry<T>(args: FetchArgs): Promise<T> {
  const [token, subdomain] = await Promise.all([getToken(), getSubdomain()]);

  try {
    return await apiFetch<T>(args.endpoint, {
      method: args.method,
      body: args.body,
      token,
      subdomain,
    });
  } catch (error) {
    // Only retry on 401 (expired/invalid token)
    if (!(error instanceof ApiError && error.status === 401)) {
      throw error;
    }

    // Attempt token refresh -- returns new access token or null
    const newToken = await refreshAccessToken();
    if (!newToken) {
      // Refresh failed (e.g., refresh token also expired) -- propagate original error
      throw error;
    }

    // Retry with the freshly minted token
    return await apiFetch<T>(args.endpoint, {
      method: args.method,
      body: args.body,
      token: newToken,
      subdomain,
    });
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Server-side GET request with automatic subdomain, token injection,
 * and 401 retry.
 */
export async function serverGet<T>(endpoint: string): Promise<T> {
  return fetchWithRetry<T>({ endpoint, method: "GET" });
}

/**
 * Server-side POST request with automatic subdomain, token injection,
 * and 401 retry.
 */
export async function serverPost<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  return fetchWithRetry<T>({
    endpoint,
    method: "POST",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Server-side PUT request with automatic subdomain, token injection,
 * and 401 retry.
 */
export async function serverPut<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  return fetchWithRetry<T>({
    endpoint,
    method: "PUT",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Server-side PATCH request with automatic subdomain, token injection,
 * and 401 retry.
 */
export async function serverPatch<T>(
  endpoint: string,
  data?: unknown
): Promise<T> {
  return fetchWithRetry<T>({
    endpoint,
    method: "PATCH",
    body: data ? JSON.stringify(data) : undefined,
  });
}

/**
 * Server-side DELETE request with automatic subdomain, token injection,
 * and 401 retry.
 */
export async function serverDelete<T>(endpoint: string): Promise<T> {
  return fetchWithRetry<T>({ endpoint, method: "DELETE" });
}
