import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUserContext } from "@/actions/auth.action";
import { ApiError } from "@/lib/api";
import { getSchoolProfile } from "@/actions/school.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import { AppSidebar } from "@/components/dashboard/app-sidebar";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { SetupCheck } from "@/components/setup-wizard";
import { SessionProvider } from "@/components/providers/SessionProvider";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";
import { InstallPrompt } from "@/components/pwa/install-prompt";
import { OfflineBanner } from "@/components/offline/offline-banner";

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

  // Fetch data for setup check in parallel
  const [schoolResult, academicYearsResult, classesResult] = await Promise.all([
    getSchoolProfile(),
    getAcademicYears(),
    getClasses(),
  ]);

  const schoolProfile = schoolResult.success ? schoolResult.data : null;
  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const classes = classesResult.success ? classesResult.data || [] : [];

  return (
    <SessionProvider session={session}>
      <SidebarProvider defaultOpen={true}>
        <AppSidebar user={session.user} />
        <SidebarInset className="flex flex-col min-h-svh">
          <DashboardHeader user={session.user} />
          <OfflineBanner />
          <div className="flex-1 p-4 md:p-6">
            {schoolProfile ? (
              <SetupCheck
                schoolProfile={schoolProfile}
                academicYears={academicYears}
                classes={classes}
              >
                {children}
              </SetupCheck>
            ) : (
              children
            )}
          </div>
        </SidebarInset>
      </SidebarProvider>
      <InstallPrompt />
    </SessionProvider>
  );
}
