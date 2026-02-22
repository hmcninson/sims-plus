/**
 * SIMS Plus - Tenant Context (Re-export)
 *
 * This file re-exports from the canonical TenantProvider for backward compatibility.
 * New code should import directly from "@/components/providers/TenantProvider".
 */

export {
  TenantProvider,
  useTenant,
  useRequiredTenant,
  type TenantInfo,
  type TenantBranding,
} from "@/components/providers/TenantProvider";

// Backward-compatible aliases for hooks that existed in the old implementation
export { useTenant as useTenantData } from "@/components/providers/TenantProvider";

/**
 * @deprecated Use `useTenant().subdomain` instead.
 */
export function useSubdomain(): string | null {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { useTenant: useTenantHook } = require("@/components/providers/TenantProvider");
  const { subdomain } = useTenantHook();
  return subdomain;
}

/**
 * @deprecated Use `useTenant().isTenantContext` instead.
 */
export function useHasTenant(): boolean {
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { useTenant: useTenantHook } = require("@/components/providers/TenantProvider");
  const { tenant } = useTenantHook();
  return tenant !== null;
}
