/**
 * SIMS Plus - Public Application Form Layout
 *
 * Branded layout for the admissions portal.
 * Uses TenantProvider from parent (auth) layout for tenant context.
 * Provides minimal chrome: centered content with school branding header.
 *
 * Auth gating: /apply/dashboard/* routes require an authenticated applicant.
 * Unauthenticated users are redirected to /apply/login.
 */

import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

import { Skeleton } from "@/components/ui/skeleton";
import { getApplicantUser } from "@/actions/applicant.action";

export default async function ApplyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Check if current path requires auth (dashboard routes)
  const headersList = await headers();
  const pathname = headersList.get("x-pathname") || "";

  const isDashboardRoute = pathname.startsWith("/apply/dashboard");

  if (isDashboardRoute) {
    const user = await getApplicantUser();
    if (!user) {
      redirect("/apply/login?error=session_expired");
    }
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="w-full max-w-3xl space-y-4">
              <Skeleton className="mx-auto h-20 w-20 rounded-full" />
              <Skeleton className="mx-auto h-8 w-64" />
              <Skeleton className="mx-auto h-4 w-48" />
              <Skeleton className="h-64 w-full rounded-lg" />
            </div>
          </div>
        }
      >
        {children}
      </Suspense>
    </div>
  );
}
