"use server";

import type { SchoolSearchResult, SchoolSearchResponse } from "@/types/tenant.type";

// Re-export the type so existing imports from this module continue to work
export type { SchoolSearchResult } from "@/types/tenant.type";

/**
 * Search for registered schools by name or subdomain.
 *
 * This calls the public (unauthenticated) search endpoint.
 * Minimum query length of 2 characters is enforced by the backend.
 */
/**
 * Validate a tenant by subdomain code.
 *
 * Calls the public (unauthenticated) tenant validation endpoint.
 */
export async function validateTenant(subdomain: string): Promise<{
  success: boolean;
  data: { valid: boolean; tenant: SchoolSearchResult | null; error?: string };
}> {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  try {
    const response = await fetch(
      `${apiUrl}/tenant/validate/${encodeURIComponent(subdomain)}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      return {
        success: false,
        data: { valid: false, tenant: null, error: "Validation failed" },
      };
    }

    const data = await response.json();
    return { success: true, data };
  } catch {
    return {
      success: false,
      data: { valid: false, tenant: null, error: "Network error" },
    };
  }
}

export async function searchSchools(
  query: string
): Promise<{ success: true; data: SchoolSearchResponse } | { success: false; error: string }> {
  if (!query || query.trim().length < 2) {
    return { success: true, data: { results: [], count: 0 } };
  }

  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  try {
    const response = await fetch(
      `${apiUrl}/tenant/search?q=${encodeURIComponent(query.trim())}`,
      {
        method: "GET",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      const message =
        errorData?.detail || `Search failed (${response.status})`;
      return { success: false, error: message };
    }

    const data: SchoolSearchResponse = await response.json();
    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to search schools",
    };
  }
}
