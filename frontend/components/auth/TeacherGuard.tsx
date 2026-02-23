"use client";

/**
 * SIMS Plus - Teacher Auth Guard
 *
 * Ensures only authenticated users with the "teacher" or "academic_head"
 * role can access the teacher portal. Non-teachers are redirected to the
 * appropriate login or dashboard page.
 */

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useSession } from "@/components/providers/SessionProvider";

interface TeacherGuardProps {
  children: ReactNode;
}

/**
 * Client-side guard that checks if the current user has a teacher role.
 *
 * - If no session exists, redirect to /login
 * - If user is a parent, redirect to /parent/dashboard
 * - If user exists but is not a teacher/academic_head, redirect to /dashboard (admin side)
 * - If user is a teacher or academic_head, render children
 *
 * Note: The server-side layout already performs the initial session check
 * and redirects unauthenticated users. This guard is an additional
 * client-side safety net for role checking.
 */
export function TeacherGuard({ children }: TeacherGuardProps) {
  const router = useRouter();
  const { user } = useSession();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    if (!user) {
      router.replace("/login");
      return;
    }

    // Teachers, academic heads, and school admins can access the teacher portal
    const teacherRoles = ["teacher", "academic_head", "school_admin"];
    if (!teacherRoles.includes(user.role)) {
      if (user.role === "parent") {
        router.replace("/parent/dashboard");
      } else {
        // Admins and other roles use the admin dashboard
        router.replace("/dashboard");
      }
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
