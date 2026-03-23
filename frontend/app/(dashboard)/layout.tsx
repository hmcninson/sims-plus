import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUserContext } from "@/actions/auth.action";
import { getAccessibleSchools } from "@/actions/chain.action";
import { ApiError } from "@/lib/api";
import { getCachedSchoolProfile } from "@/actions/school.action";
import { AppSidebar } from "@/components/dashboard/app-sidebar";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { SetupCheck } from "@/components/setup-wizard";
import { SessionProvider } from "@/components/providers/SessionProvider";
import { SessionTimeoutProvider } from "@/components/providers/SessionTimeoutProvider";
import { SchoolProvider } from "@/contexts/school-context";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { InstallPrompt } from "@/components/pwa/install-prompt";
import { OfflineBanner } from "@/components/offline/offline-banner";
import { TrialBanner } from "@/components/subscription/trial-banner";
import { ExpiredGate } from "@/components/subscription/expired-gate";
import { MFAEnforcementBanner } from "@/components/mfa/mfa-enforcement-banner";
import { ImpersonationBanner } from "@/components/platform/impersonation-banner";
import { getSubscriptionStatus } from "@/actions/subscription.action";

// Accessible schools is only used in the layout, so a local cache wrapper is fine
const getCachedAccessibleSchools = cache(() => getAccessibleSchools());

/**
 * Helper to wait a fixed number of milliseconds.
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Detect whether the user had a previous session (refresh token still present).
  // This lets us show a "session expired" message instead of a bare login redirect.
  const cookieStore = await cookies();
  const hadSession = !!cookieStore.get("refresh_token")?.value;

  // Detect platform admin impersonation by decoding the JWT payload (server-side).
  // The JWT payload is the second base64url segment; we only need is_impersonation
  // and tenant_subdomain claims. This avoids installing a JWT library for a single check.
  let isImpersonation = false;
  let impersonationSubdomain = "";
  const accessToken = cookieStore.get("access_token")?.value;
  if (accessToken) {
    try {
      const parts = accessToken.split(".");
      if (parts.length === 3) {
        const payload = JSON.parse(
          Buffer.from(parts[1], "base64url").toString("utf-8"),
        );
        if (payload.is_impersonation === true) {
          isImpersonation = true;
          impersonationSubdomain = payload.tenant_subdomain || "";
        }
      }
    } catch {
      // JWT decode failed -- not impersonating
    }
  }

  let session;
  try {
    session = await getCurrentUserContext();
  } catch (error) {
    // Rate limited (429) does NOT mean the session is invalid.
    // The user's auth tokens are still valid; the backend is just throttling.
    // Wait briefly and retry once before giving up.
    if (error instanceof ApiError && error.status === 429) {
      const retryAfter = Math.min(
        parseInt(String(error.message).match(/\d+/)?.[0] ?? "2", 10),
        5,
      );
      await delay(retryAfter * 1000);
      try {
        session = await getCurrentUserContext();
      } catch {
        // Second attempt also failed -- still don't redirect to login.
        // The auth tokens are valid; we just can't verify right now.
        // Re-throw so Next.js error boundary handles it.
        throw new Error(
          "Too many requests. Please wait a moment and refresh the page."
        );
      }
    } else {
      throw error;
    }
  }

  if (!session) {
    if (hadSession) {
      // User was logged in but both tokens have expired
      redirect("/login?error=session_expired&message=Your session has expired. Please sign in again.");
    }
    redirect("/login");
  }

  // Parents should use the parent portal, not the admin dashboard
  if (session.user.role === "parent") {
    redirect("/parent/dashboard");
  }

  // Sidebar always defaults to expanded state on page load

  // Determine if this user might manage a chain.
  // Only chain_admin and platform_admin roles need the school switcher.
  // TODO: Use session.tenant.tenant_type once backend returns it in /auth/me
  const isPotentiallyChain = session.user.role === "chain_admin"
    || session.user.role === "platform_admin";

  // Fetch data for setup check and chain schools in parallel.
  // Uses React.cache()-wrapped versions so any child server component
  // calling the same action during this render reuses the result.
  const [schoolResult, schoolsResult, subscriptionResult] = await Promise.all([
    getCachedSchoolProfile(),
    // Only fetch accessible schools for chain admin roles
    isPotentiallyChain ? getCachedAccessibleSchools() : Promise.resolve({ success: true as const, data: [] }),
    // M7: Fetch subscription status server-side to pass to TrialBanner
    getSubscriptionStatus(),
  ]);

  const schoolProfile = schoolResult.success ? schoolResult.data : null;
  const accessibleSchools = schoolsResult.success ? schoolsResult.data || [] : [];
  const subscriptionStatus = subscriptionResult.success ? subscriptionResult.data : null;

  // A tenant is truly a chain only if it has multiple schools
  const isTrueChain = accessibleSchools.length > 1;

  // Determine if we need to show an expired gate overlay
  const isExpired =
    subscriptionStatus &&
    subscriptionStatus.status === "trial" &&
    subscriptionStatus.days_remaining !== null &&
    subscriptionStatus.days_remaining <= 0;

  // Detect grace period vs hard block for expired trials
  // Grace period: trial expired but within 7-day window (status still "trial", days_remaining <= 0)
  // The backend returns specific error codes on API calls;
  // here we use the subscription status to show a preemptive overlay
  const expiredCode = isExpired ? "TRIAL_EXPIRED" as const : null;

  return (
    <SessionProvider session={session}>
      <SessionTimeoutProvider>
        <SchoolProvider schools={accessibleSchools} isChain={isTrueChain}>
          {isImpersonation && (
            <ImpersonationBanner tenantSubdomain={impersonationSubdomain} />
          )}
          <SidebarProvider defaultOpen={true}>
            <AppSidebar user={session.user} isChain={isTrueChain} />
            <SidebarInset className="flex flex-col min-h-svh">
              <DashboardHeader user={session.user} />
              {subscriptionStatus && (
                <TrialBanner
                  initialStatus={{
                    plan: subscriptionStatus.plan,
                    status: subscriptionStatus.status,
                    days_remaining: subscriptionStatus.days_remaining,
                  }}
                />
              )}
              <OfflineBanner />
              <MFAEnforcementBanner
                requireMfa={
                  subscriptionStatus?.features?.require_mfa_admin_roles === true
                }
                userRole={session.user.role}
                mfaEnabled={session.user.mfa_enabled}
              />
              {expiredCode && <ExpiredGate code={expiredCode} />}
              <div className="flex-1 p-4 md:p-6">
                <SetupCheck
                  schoolProfile={schoolProfile}
                >
                  {children}
                </SetupCheck>
              </div>
            </SidebarInset>
          </SidebarProvider>
          <InstallPrompt />
        </SchoolProvider>
      </SessionTimeoutProvider>
    </SessionProvider>
  );
}
