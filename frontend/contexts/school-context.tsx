"use client";

/**
 * SIMS Plus - School Context Provider
 *
 * Manages the active school for chain tenants. For single-school tenants,
 * this provider is inert: no UI is rendered, no cookie is set, and the
 * backend auto-resolves the single school.
 *
 * The active school ID is persisted in a cookie ("x-active-school") so
 * Server Actions can read it and forward it as the X-Active-School header.
 *
 * Depends on SessionProvider for tenant_type and accessible_school_ids.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useTransition,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import type { SwitcherSchool } from "@/types/chain.type";

// ---------------------------------------------------------------------------
// Cookie helpers
// ---------------------------------------------------------------------------

const COOKIE_NAME = "x-active-school";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function getActiveSchoolFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${COOKIE_NAME}=`));
  const value = match ? decodeURIComponent(match.split("=")[1]) : null;
  // Validate UUID format to prevent arbitrary values being forwarded as header
  return value && UUID_RE.test(value) ? value : null;
}

function setActiveSchoolCookie(schoolId: string) {
  const secure = typeof window !== "undefined" && window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(schoolId)}; path=/${secure}; SameSite=Lax`;
}

function clearActiveSchoolCookie() {
  document.cookie = `${COOKIE_NAME}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT`;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface SchoolContextState {
  /** UUID of the currently active school (null for single-school tenants). */
  activeSchoolId: string | null;
  /** List of schools this user can access. Empty for single-school tenants. */
  accessibleSchools: SwitcherSchool[];
  /** Whether this tenant is a chain (has multiple schools). */
  isChain: boolean;
  /** Whether a school switch is in progress. */
  isSwitching: boolean;
  /** Switch to a different school. Clears caches and redirects to dashboard. */
  switchSchool: (schoolId: string) => void;
}

const SchoolCtx = createContext<SchoolContextState | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface SchoolProviderProps {
  children: ReactNode;
  /** Schools the current user can access (from server-side fetch). */
  schools: SwitcherSchool[];
  /** Whether the tenant is a chain. */
  isChain: boolean;
  /** Path to navigate to after switching schools. Defaults to "/dashboard". */
  redirectPath?: string;
}

/**
 * School context provider.
 *
 * For single-school tenants, `schools` is empty and `isChain` is false.
 * The provider renders children directly with no overhead.
 *
 * For chain tenants, initializes the active school from the cookie,
 * falling back to the first school in the list.
 */
export function SchoolProvider({
  children,
  schools,
  isChain,
  redirectPath = "/dashboard",
}: SchoolProviderProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Resolve the initial active school
  const [activeSchoolId, setActiveSchoolId] = useState<string | null>(() => {
    if (!isChain || schools.length === 0) return null;

    // For single-school chains (edge case: chain with only 1 school), auto-select
    if (schools.length === 1) return schools[0].id;

    // Try reading from cookie
    const cookieId = getActiveSchoolFromCookie();
    if (cookieId && schools.some((s) => s.id === cookieId)) {
      return cookieId;
    }

    // Default to first school
    return schools[0].id;
  });

  // Persist to cookie on change
  useEffect(() => {
    if (!isChain) {
      clearActiveSchoolCookie();
      return;
    }
    if (activeSchoolId) {
      setActiveSchoolCookie(activeSchoolId);
    }
  }, [activeSchoolId, isChain]);

  const switchSchool = useCallback(
    (schoolId: string) => {
      if (schoolId === activeSchoolId) return;
      if (!schools.some((s) => s.id === schoolId)) return;

      // Set cookie before any navigation so Server Actions pick it up
      setActiveSchoolCookie(schoolId);
      setActiveSchoolId(schoolId);

      // Navigate to the redirect path to clear any stale data
      startTransition(() => {
        router.push(redirectPath);
        router.refresh();
      });
    },
    [activeSchoolId, schools, router, redirectPath]
  );

  const value = useMemo<SchoolContextState>(
    () => ({
      activeSchoolId,
      accessibleSchools: schools,
      isChain,
      isSwitching: isPending,
      switchSchool,
    }),
    [activeSchoolId, schools, isChain, isPending, switchSchool]
  );

  return (
    <SchoolCtx.Provider value={value}>
      {children}
    </SchoolCtx.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Access the school context.
 *
 * @throws Error if called outside SchoolProvider
 *
 * @example
 * ```tsx
 * const { activeSchoolId, isChain, switchSchool } = useSchool();
 * ```
 */
export function useSchool(): SchoolContextState {
  const context = useContext(SchoolCtx);
  if (!context) {
    throw new Error(
      "useSchool must be used within a SchoolProvider. " +
        "Ensure this component is rendered inside the dashboard layout."
    );
  }
  return context;
}

export default SchoolProvider;
