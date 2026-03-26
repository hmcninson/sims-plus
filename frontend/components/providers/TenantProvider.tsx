"use client";

/**
 * SIMS Plus - Tenant Context Provider
 *
 * Provides tenant context to client components.
 * Reads subdomain from cookie (set by proxy.ts) and fetches tenant data.
 */

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { TenantPublic, TenantBranding, TenantValidationResponse } from "@/types";

// Re-export types for backward compatibility
export type { TenantBranding };

/**
 * Public tenant information (alias for TenantPublic).
 */
export type TenantInfo = TenantPublic;

/**
 * Tenant context state.
 */
interface TenantContextState {
  /** Current tenant info (null if not loaded or not on tenant subdomain) */
  tenant: TenantInfo | null;
  /** Current subdomain (null if not on tenant subdomain) */
  subdomain: string | null;
  /** Whether tenant data is loading */
  isLoading: boolean;
  /** Error message if tenant validation failed */
  error: string | null;
  /** Whether the tenant is suspended (middleware returned 403 TENANT_SUSPENDED) */
  isSuspended: boolean;
  /** Suspension notice message from the backend */
  suspensionMessage: string | null;
  /** Whether we're on a valid tenant subdomain */
  isTenantContext: boolean;
  /** Refresh tenant data */
  refreshTenant: () => Promise<void>;
}

/**
 * Default context state.
 */
const defaultContext: TenantContextState = {
  tenant: null,
  subdomain: null,
  isLoading: true,
  error: null,
  isSuspended: false,
  suspensionMessage: null,
  isTenantContext: false,
  refreshTenant: async () => {},
};

/**
 * Tenant context.
 */
const TenantContext = createContext<TenantContextState>(defaultContext);

/**
 * Get subdomain from cookie.
 */
function getSubdomainFromCookie(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "x-subdomain") {
      return decodeURIComponent(value);
    }
  }
  return null;
}

/**
 * Result of tenant validation, extended with suspension info.
 */
interface FetchTenantResult extends TenantValidationResponse {
  /** Set when the validate response includes code TENANT_SUSPENDED */
  isSuspended?: boolean;
  /** Suspension message from the backend */
  suspensionMessage?: string;
}

async function fetchTenant(subdomain: string): Promise<FetchTenantResult> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  try {
    const response = await fetch(`${apiUrl}/tenant/validate/${subdomain}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!response.ok) {
      return {
        valid: false,
        tenant: null,
        error: `Failed to validate tenant: ${response.status}`,
      };
    }

    const data: TenantValidationResponse = await response.json();

    // Detect suspended tenant from the response body code field.
    // The validate endpoint is a public path so the TenantMiddleware's
    // status-aware routing never fires for it — suspension must be
    // detected from the response payload instead.
    if (data.code === "TENANT_SUSPENDED") {
      return {
        ...data,
        isSuspended: true,
        suspensionMessage:
          data.error ||
          "This school account has been suspended. Contact your administrator.",
      };
    }

    return data;
  } catch (error) {
    console.error("Failed to fetch tenant:", error);
    return {
      valid: false,
      tenant: null,
      error: "Failed to connect to server",
    };
  }
}

/**
 * Props for TenantProvider.
 */
interface TenantProviderProps {
  children: ReactNode;
  /** Optional server-side tenant data for hydration */
  initialTenant?: TenantInfo | null;
  /** Optional server-side subdomain */
  initialSubdomain?: string | null;
}

/**
 * Tenant context provider component.
 *
 * Provides tenant information to all child components.
 * Automatically fetches tenant data based on subdomain cookie.
 *
 * @example
 * ```tsx
 * // In layout.tsx
 * import { TenantProvider } from "@/components/providers/TenantProvider";
 *
 * export default function Layout({ children }) {
 *   return (
 *     <TenantProvider>
 *       {children}
 *     </TenantProvider>
 *   );
 * }
 *
 * // In a component
 * import { useTenant } from "@/components/providers/TenantProvider";
 *
 * function MyComponent() {
 *   const { tenant, isLoading } = useTenant();
 *
 *   if (isLoading) return <div>Loading...</div>;
 *   if (!tenant) return <div>No tenant</div>;
 *
 *   return <div>Welcome to {tenant.name}</div>;
 * }
 * ```
 */
export function TenantProvider({
  children,
  initialTenant = null,
  initialSubdomain = null,
}: TenantProviderProps) {
  const [tenant, setTenant] = useState<TenantInfo | null>(initialTenant);
  const [subdomain, setSubdomain] = useState<string | null>(initialSubdomain);
  const [isLoading, setIsLoading] = useState(!initialTenant);
  const [error, setError] = useState<string | null>(null);
  const [isSuspended, setIsSuspended] = useState(false);
  const [suspensionMessage, setSuspensionMessage] = useState<string | null>(null);

  /**
   * Load tenant data from API.
   */
  const loadTenant = useCallback(async (subdomainToLoad: string) => {
    setIsLoading(true);
    setError(null);
    setIsSuspended(false);
    setSuspensionMessage(null);

    const result = await fetchTenant(subdomainToLoad);

    if (result.isSuspended) {
      // Tenant exists but is suspended — show suspension notice instead of login
      setTenant(null);
      setIsSuspended(true);
      setSuspensionMessage(result.suspensionMessage || null);
      setError(null);
    } else if (result.valid && result.tenant) {
      setTenant(result.tenant);
      setError(null);
    } else {
      setTenant(null);
      setError(result.error || "Invalid tenant");
    }

    setIsLoading(false);
  }, []);

  /**
   * Refresh tenant data.
   */
  const refreshTenant = useCallback(async () => {
    if (subdomain) {
      await loadTenant(subdomain);
    }
  }, [subdomain, loadTenant]);

  /**
   * Initialize tenant context on mount.
   */
  useEffect(() => {
    // If we have initial data, don't fetch again
    if (initialTenant && initialSubdomain) {
      setSubdomain(initialSubdomain);
      return;
    }

    // Get subdomain from cookie
    const cookieSubdomain = getSubdomainFromCookie();

    if (cookieSubdomain) {
      setSubdomain(cookieSubdomain);
      loadTenant(cookieSubdomain);
    } else {
      setIsLoading(false);
    }
  }, [initialTenant, initialSubdomain, loadTenant]);

  /**
   * Apply tenant branding to document.
   */
  useEffect(() => {
    if (tenant?.branding?.primary_color) {
      document.documentElement.style.setProperty(
        "--tenant-primary-color",
        tenant.branding.primary_color
      );
    }
  }, [tenant]);

  const value: TenantContextState = {
    tenant,
    subdomain,
    isLoading,
    error,
    isSuspended,
    suspensionMessage,
    isTenantContext: !!tenant,
    refreshTenant,
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
 * @returns Tenant context state
 * @throws Error if used outside TenantProvider
 *
 * @example
 * ```tsx
 * const { tenant, subdomain, isLoading } = useTenant();
 * ```
 */
export function useTenant(): TenantContextState {
  const context = useContext(TenantContext);

  if (context === undefined) {
    throw new Error("useTenant must be used within a TenantProvider");
  }

  return context;
}

/**
 * Hook to require tenant context.
 * Throws error if not in a tenant context.
 *
 * @returns Tenant info (guaranteed non-null)
 * @throws Error if tenant is not loaded
 *
 * @example
 * ```tsx
 * const tenant = useRequiredTenant();
 * // tenant is guaranteed to be non-null here
 * ```
 */
export function useRequiredTenant(): TenantInfo {
  const { tenant, isLoading, error } = useTenant();

  if (isLoading) {
    throw new Error("Tenant is still loading");
  }

  if (!tenant) {
    throw new Error(error || "No tenant context available");
  }

  return tenant;
}

export default TenantProvider;
