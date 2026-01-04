"use client";

/**
 * SIMS Plus - Tenant Context Provider
 *
 * Provides tenant information to client components.
 * The tenant is resolved server-side and passed down via this context.
 */

import {
  createContext,
  useContext,
  ReactNode,
} from "react";

/**
 * Tenant branding information.
 */
export interface TenantBranding {
  logo_url: string | null;
  primary_color: string | null;
}

/**
 * Public tenant information.
 */
export interface Tenant {
  id: string;
  name: string;
  subdomain: string;
  tenant_type: string;
  is_active: boolean;
  branding: TenantBranding | null;
}

/**
 * Tenant context value.
 */
interface TenantContextValue {
  tenant: Tenant | null;
  subdomain: string | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Default context value.
 */
const defaultContextValue: TenantContextValue = {
  tenant: null,
  subdomain: null,
  isLoading: false,
  error: null,
};

/**
 * Tenant context.
 */
const TenantContext = createContext<TenantContextValue>(defaultContextValue);

/**
 * Props for TenantProvider.
 */
interface TenantProviderProps {
  children: ReactNode;
  tenant: Tenant | null;
  subdomain: string | null;
  error?: string | null;
}

/**
 * Tenant context provider component.
 *
 * This should wrap the application and receive tenant data
 * that was fetched server-side.
 *
 * @example
 * ```tsx
 * // In layout.tsx (Server Component)
 * const tenant = await getCurrentTenant();
 * const subdomain = await getSubdomain();
 *
 * return (
 *   <TenantProvider tenant={tenant} subdomain={subdomain}>
 *     {children}
 *   </TenantProvider>
 * );
 * ```
 */
export function TenantProvider({
  children,
  tenant,
  subdomain,
  error = null,
}: TenantProviderProps) {
  const value: TenantContextValue = {
    tenant,
    subdomain,
    isLoading: false,
    error,
  };

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  );
}

/**
 * Hook to access tenant context.
 *
 * @returns Tenant context value
 * @throws Error if used outside of TenantProvider
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { tenant, subdomain } = useTenant();
 *
 *   if (!tenant) {
 *     return <div>No tenant context</div>;
 *   }
 *
 *   return <div>Welcome to {tenant.name}</div>;
 * }
 * ```
 */
export function useTenant(): TenantContextValue {
  const context = useContext(TenantContext);

  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider");
  }

  return context;
}

/**
 * Hook to get just the tenant object.
 *
 * @returns Tenant or null
 */
export function useTenantData(): Tenant | null {
  const { tenant } = useTenant();
  return tenant;
}

/**
 * Hook to get the current subdomain.
 *
 * @returns Subdomain or null
 */
export function useSubdomain(): string | null {
  const { subdomain } = useTenant();
  return subdomain;
}

/**
 * Hook to check if we're in a tenant context.
 *
 * @returns True if we have a valid tenant
 */
export function useHasTenant(): boolean {
  const { tenant } = useTenant();
  return tenant !== null && tenant.is_active;
}

/**
 * Hook to get tenant branding.
 *
 * @returns Branding object with defaults
 */
export function useTenantBranding(): TenantBranding {
  const { tenant } = useTenant();

  return {
    logo_url: tenant?.branding?.logo_url ?? null,
    primary_color: tenant?.branding?.primary_color ?? "#1B4F72",
  };
}
