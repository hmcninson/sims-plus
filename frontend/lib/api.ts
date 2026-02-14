/**
 * SIMS Plus - API Configuration
 *
 * Server-side API client for use with Server Actions
 */

const API_BASE_URL = process.env.API_URL || "http://localhost:8000/api/v1";

interface FetchOptions extends RequestInit {
  token?: string;
  subdomain?: string;
}

/**
 * Fetch wrapper with error handling
 */
export async function apiFetch<T>(
  endpoint: string,
  options: FetchOptions = {}
): Promise<T> {
  const { token, subdomain, ...fetchOptions } = options;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
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
    let errorMessage = `API Error: ${response.status}`;
    if (error.detail) {
      if (typeof error.detail === 'string') {
        errorMessage = error.detail;
      } else if (Array.isArray(error.detail)) {
        // FastAPI validation errors come as array
        errorMessage = error.detail.map((e: { msg?: string; message?: string }) => e.msg || e.message || JSON.stringify(e)).join(', ');
      } else if (typeof error.detail === 'object') {
        errorMessage = error.detail.message || error.detail.msg || JSON.stringify(error.detail);
      }
    } else if (error.message) {
      errorMessage = error.message;
    }
    throw new Error(errorMessage);
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
  const { token, subdomain } = options || {};

  const headers: HeadersInit = {
    // Don't set Content-Type - let browser set it with boundary for multipart
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(subdomain && { "X-Subdomain": subdomain }),
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
    throw new Error(error.detail || `Upload Error: ${response.status}`);
  }

  return response.json();
}
