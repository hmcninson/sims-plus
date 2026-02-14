/**
 * SIMS Plus - Tenant Utilities
 *
 * Server-side utilities for tenant detection and validation.
 *
 * For server actions, use @/actions/tenant.action.ts instead.
 * This file provides utility functions for use in Server Components.
 */

import { headers } from "next/headers";
import { apiGet } from "./api";
import type {
  TenantBranding,
  TenantPublic,
  TenantValidationResponse,
  SubdomainCheckResponse,
} from "@/types";

// Re-export types for convenience
export type { TenantBranding, TenantPublic, TenantValidationResponse, SubdomainCheckResponse };

/**
 * Get the current subdomain from request headers.
 *
 * This reads the x-subdomain header set by proxy.ts.
 *
 * @returns Subdomain or null if not present
 */
export async function getSubdomain(): Promise<string | null> {
  const headersList = await headers();
  return headersList.get("x-subdomain");
}

/**
 * Get the current subdomain synchronously from headers.
 *
 * Note: This should only be used in Server Components.
 */
export function getSubdomainSync(headersList: Headers): string | null {
  return headersList.get("x-subdomain");
}

/**
 * Validate a tenant by subdomain.
 *
 * @param subdomain - Subdomain to validate
 * @returns Tenant validation response
 */
export async function validateTenant(
  subdomain: string
): Promise<TenantValidationResponse> {
  try {
    const response = await apiGet<TenantValidationResponse>(
      `/tenant/validate/${subdomain}`
    );
    return response;
  } catch (error) {
    console.error("Failed to validate tenant:", error);
    return {
      valid: false,
      tenant: null,
      error: "Failed to validate tenant",
    };
  }
}

/**
 * Get the current tenant based on subdomain header.
 *
 * This is the main function to use in Server Components
 * to get the current tenant context.
 *
 * @returns Tenant if valid, null otherwise
 */
export async function getCurrentTenant(): Promise<TenantPublic | null> {
  const subdomain = await getSubdomain();

  if (!subdomain) {
    return null;
  }

  const response = await validateTenant(subdomain);

  if (!response.valid || !response.tenant) {
    return null;
  }

  return response.tenant;
}

/**
 * Check if a subdomain is available for registration.
 *
 * @param subdomain - Subdomain to check
 * @returns Availability check response
 */
export async function checkSubdomainAvailability(
  subdomain: string
): Promise<SubdomainCheckResponse> {
  try {
    const response = await apiGet<SubdomainCheckResponse>(
      `/tenant/check-subdomain?subdomain=${encodeURIComponent(subdomain)}`
    );
    return response;
  } catch (error) {
    console.error("Failed to check subdomain:", error);
    return {
      subdomain,
      available: false,
      reason: "Failed to check availability",
    };
  }
}

/**
 * Extract subdomain from a full hostname.
 *
 * @param hostname - Full hostname (e.g., "presec.simsplus.io")
 * @returns Subdomain or null
 */
export function extractSubdomainFromHostname(hostname: string): string | null {
  // Remove port if present
  const hostWithoutPort = hostname.split(":")[0];

  // Check if it's localhost
  if (hostWithoutPort === "localhost" || hostWithoutPort === "127.0.0.1") {
    return null;
  }

  const parts = hostWithoutPort.split(".");

  // Need at least 3 parts for subdomain
  if (parts.length < 3) {
    return null;
  }

  const subdomain = parts[0].toLowerCase();

  // Reserved subdomains
  const reserved = ["www", "app", "api", "admin", "mail", "staging", "dev"];
  if (reserved.includes(subdomain)) {
    return null;
  }

  return subdomain;
}
