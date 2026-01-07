"use server";

/**
 * SIMS Plus - Tenant Management Server Actions
 *
 * Server actions for tenant management operations including:
 * - Subdomain availability checking
 * - Tenant validation
 * - Current tenant retrieval
 */

import { cookies, headers } from "next/headers";
import { apiGet, apiPost } from "@/lib/api";
import type {
  ActionResult,
  SubdomainCheckResponse,
  TenantValidationResponse,
  TenantPublic,
} from "@/types";

/**
 * Get subdomain from cookies or headers (set by proxy.ts)
 */
async function getSubdomainFromContext(): Promise<string | undefined> {
  // Try cookies first
  const cookieStore = await cookies();
  const cookieSubdomain = cookieStore.get("x-subdomain")?.value;
  if (cookieSubdomain) {
    return cookieSubdomain;
  }

  // Fallback to headers
  const headersList = await headers();
  return headersList.get("x-subdomain") || undefined;
}

// =========================
// Subdomain Availability
// =========================

/**
 * Check if a subdomain is available for registration (GET method)
 *
 * @param subdomain - Subdomain to check (4-63 chars, lowercase alphanumeric and hyphens)
 * @returns Availability check response
 */
export async function checkSubdomainAvailability(
  subdomain: string
): Promise<ActionResult<SubdomainCheckResponse>> {
  try {
    // Client-side validation first
    if (subdomain.length < 4) {
      return {
        success: true,
        data: {
          subdomain,
          available: false,
          reason: "Subdomain must be at least 4 characters",
        },
      };
    }

    if (subdomain.length > 63) {
      return {
        success: true,
        data: {
          subdomain,
          available: false,
          reason: "Subdomain must be at most 63 characters",
        },
      };
    }

    const pattern = /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$/;
    if (!pattern.test(subdomain.toLowerCase())) {
      return {
        success: true,
        data: {
          subdomain,
          available: false,
          reason: "Subdomain can only contain lowercase letters, numbers, and hyphens",
        },
      };
    }

    const response = await apiGet<SubdomainCheckResponse>(
      `/tenant/check-subdomain?subdomain=${encodeURIComponent(subdomain.toLowerCase())}`
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check subdomain availability",
    };
  }
}

/**
 * Check if a subdomain is available for registration (POST method)
 *
 * @param subdomain - Subdomain to check
 * @returns Availability check response
 */
export async function checkSubdomainAvailabilityPost(
  subdomain: string
): Promise<ActionResult<SubdomainCheckResponse>> {
  try {
    const response = await apiPost<SubdomainCheckResponse>(
      "/tenant/check-subdomain",
      { subdomain: subdomain.toLowerCase() }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to check subdomain availability",
    };
  }
}

// =========================
// Tenant Validation
// =========================

/**
 * Validate a tenant by subdomain
 *
 * Checks if a tenant exists, is active, and not deleted.
 *
 * @param subdomain - Subdomain to validate
 * @returns Validation response with tenant info if valid
 */
export async function validateTenant(
  subdomain: string
): Promise<ActionResult<TenantValidationResponse>> {
  try {
    const response = await apiGet<TenantValidationResponse>(
      `/tenant/validate/${encodeURIComponent(subdomain.toLowerCase())}`
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to validate tenant",
    };
  }
}

// =========================
// Current Tenant
// =========================

/**
 * Get the current tenant based on subdomain context
 *
 * Uses the subdomain from cookies/headers (set by proxy.ts) to retrieve
 * the current tenant information.
 *
 * @returns Current tenant info if in tenant context
 */
export async function getCurrentTenant(): Promise<ActionResult<TenantValidationResponse>> {
  try {
    const subdomain = await getSubdomainFromContext();

    const response = await apiGet<TenantValidationResponse>(
      "/tenant/current",
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get current tenant",
    };
  }
}

/**
 * Get the current tenant's public info
 *
 * Convenience method that returns just the tenant object or null.
 *
 * @returns Tenant public info or null if not in tenant context
 */
export async function getCurrentTenantInfo(): Promise<TenantPublic | null> {
  const result = await getCurrentTenant();

  if (!result.success || !result.data?.valid || !result.data.tenant) {
    return null;
  }

  return result.data.tenant;
}

/**
 * Check if we're currently in a valid tenant context
 *
 * @returns true if in valid tenant context, false otherwise
 */
export async function isInTenantContext(): Promise<boolean> {
  const tenant = await getCurrentTenantInfo();
  return tenant !== null && tenant.is_active;
}

/**
 * Get the current subdomain from context
 *
 * @returns Subdomain string or null if not in tenant context
 */
export async function getSubdomain(): Promise<string | null> {
  const subdomain = await getSubdomainFromContext();
  return subdomain || null;
}
