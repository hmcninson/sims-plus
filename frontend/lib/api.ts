/**
 * SIMS Plus - API Configuration
 *
 * Server-side API client for use with Server Actions.
 * Uses process.env.API_URL which is only available server-side.
 */
import "server-only";

const API_BASE_URL = process.env.API_URL || "http://localhost:8000/api/v1";

/**
 * Typed API error that preserves HTTP status code and request ID
 * for structured error handling in callers (e.g., distinguishing
 * 401 unauthorized from 429 rate limited).
 */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

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
 * Fetch wrapper with error handling
 */
export async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, subdomain, activeSchoolId, ...fetchOptions } = options;

  // Correlate client requests with backend structured logs
  const requestId = crypto.randomUUID();

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    "X-Request-ID": requestId,
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
    ...(activeSchoolId && { "X-Active-School": activeSchoolId }),
    ...options.headers,
  };

  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...fetchOptions,
    headers,
    cache: "no-store", // Disable Next.js fetch caching
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new ApiError(
      parseErrorDetail(error, `API Error: ${response.status}`),
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

  const requestId = crypto.randomUUID();

  const headers: HeadersInit = {
    // Don't set Content-Type - let browser set it with boundary for multipart
    "X-Request-ID": requestId,
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
    ...(activeSchoolId && { "X-Active-School": activeSchoolId }),
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
