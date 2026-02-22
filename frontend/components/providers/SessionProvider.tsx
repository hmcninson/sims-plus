"use client";

/**
 * SIMS Plus - Session Context Provider
 *
 * Provides the authenticated user, tenant metadata, and permission strings
 * to all dashboard client components. Populated server-side by the dashboard
 * layout.tsx, so no client-side fetching is needed.
 *
 * @example
 * ```tsx
 * // In a client component:
 * import { useSession, usePermissions } from "@/components/providers/SessionProvider";
 *
 * function MyComponent() {
 *   const { user, tenant, permissions } = useSession();
 *   const can = usePermissions();
 *
 *   if (!can("students.read")) return <NoAccess />;
 *   return <div>Welcome {user.first_name}</div>;
 * }
 * ```
 */

import {
  createContext,
  useContext,
  useCallback,
  type ReactNode,
} from "react";
import type { User, SessionContext } from "@/types";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface SessionContextState {
  /** Current authenticated user */
  user: User;
  /** Tenant metadata for the current session */
  tenant: SessionContext["tenant"];
  /** Flat list of permission strings (e.g., "students.read", "finance.*") */
  permissions: string[];
}

const SessionCtx = createContext<SessionContextState | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface SessionProviderProps {
  children: ReactNode;
  session: SessionContext;
}

/**
 * Session context provider.
 *
 * Wraps dashboard children with user/tenant/permissions context.
 * Must be rendered inside the dashboard layout (Server Component)
 * which fetches the session via getCurrentUserContext().
 */
export function SessionProvider({ children, session }: SessionProviderProps) {
  const value: SessionContextState = {
    user: session.user,
    tenant: session.tenant,
    permissions: session.permissions,
  };

  return (
    <SessionCtx.Provider value={value}>
      {children}
    </SessionCtx.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Access the current session (user, tenant, permissions).
 *
 * Throws if called outside a SessionProvider (i.e., outside the dashboard).
 */
export function useSession(): SessionContextState {
  const context = useContext(SessionCtx);
  if (!context) {
    throw new Error(
      "useSession must be used within a SessionProvider. " +
      "Ensure this component is rendered inside the dashboard layout."
    );
  }
  return context;
}

/**
 * Returns a permission checker function.
 *
 * Supports exact matches ("students.read") and wildcard permissions
 * ("students.*" matches "students.read", "students.write", etc.).
 * The "*" (all) permission grants access to everything.
 *
 * @example
 * ```tsx
 * const can = usePermissions();
 * if (can("finance.invoices.read")) { ... }
 * ```
 */
export function usePermissions(): (permission: string) => boolean {
  const { permissions } = useSession();

  return useCallback(
    (permission: string): boolean => {
      // Superadmin wildcard
      if (permissions.includes("*")) return true;

      // Exact match
      if (permissions.includes(permission)) return true;

      // Wildcard match: "students.*" should match "students.read"
      const segments = permission.split(".");
      for (let i = segments.length - 1; i > 0; i--) {
        const wildcardPerm = segments.slice(0, i).join(".") + ".*";
        if (permissions.includes(wildcardPerm)) return true;
      }

      return false;
    },
    [permissions]
  );
}

export default SessionProvider;
