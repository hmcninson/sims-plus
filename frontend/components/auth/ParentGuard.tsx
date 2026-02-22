"use client";

/**
 * SIMS Plus - Parent Auth Guard
 *
 * Ensures only authenticated users with the "parent" role can access
 * the parent portal. Non-parents are redirected to the appropriate
 * login or dashboard page.
 */

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useSession } from "@/components/providers/SessionProvider";

interface ParentGuardProps {
  children: ReactNode;
  /** Whether to check onboarding completion. Defaults to true. */
  requireOnboarding?: boolean;
}

/**
 * Client-side guard that checks if the current user has the "parent" role.
 *
 * - If no session exists, redirect to /login
 * - If user exists but is not a parent, redirect to /dashboard (admin side)
 * - If user is a parent, render children
 *
 * Note: The server-side layout already performs the initial session check
 * and redirects unauthenticated users. This guard is an additional
 * client-side safety net for role checking.
 */
export function ParentGuard({ children }: ParentGuardProps) {
  const router = useRouter();
  const { user } = useSession();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    if (!user) {
      router.replace("/login");
      return;
    }

    if (user.role !== "parent") {
      // Non-parent users should use the admin dashboard
      router.replace("/dashboard");
      return;
    }

    setAuthorized(true);
  }, [user, router]);

  if (!authorized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Verifying access...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
