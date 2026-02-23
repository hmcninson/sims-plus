import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUserContext } from "@/actions/auth.action";
import { getAccessibleSchools } from "@/actions/chain.action";
import { ApiError } from "@/lib/api";
import { SessionProvider } from "@/components/providers/SessionProvider";
import { SchoolProvider } from "@/contexts/school-context";
import { TeacherGuard } from "@/components/auth/TeacherGuard";
import { TeacherSidebar } from "@/components/teacher/teacher-sidebar";
import { TeacherHeader } from "@/components/teacher/teacher-header";
import { TeacherBottomNav } from "@/components/teacher/teacher-bottom-nav";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

/**
 * Helper to wait a fixed number of milliseconds.
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Teacher Portal Layout
 *
 * A separate layout from the admin dashboard, designed for teachers.
 * Includes:
 * - Server-side auth check (same pattern as parent portal)
 * - Role check: only "teacher" and "academic_head" roles can access
 * - Desktop sidebar + header
 * - Mobile bottom tab navigation
 * - School branding via tenant CSS variables
 */
export default async function TeacherLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Detect whether the user had a previous session
  const cookieStore = await cookies();
  const hadSession = !!cookieStore.get("refresh_token")?.value;

  let session;
  try {
    session = await getCurrentUserContext();
  } catch (error) {
    // Rate limited -- wait briefly and retry once
    if (error instanceof ApiError && error.status === 429) {
      const retryAfter = Math.min(
        parseInt(String(error.message).match(/\d+/)?.[0] ?? "2", 10),
        5
      );
      await delay(retryAfter * 1000);
      try {
        session = await getCurrentUserContext();
      } catch {
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
      redirect(
        "/login?error=session_expired&message=Your session has expired. Please sign in again."
      );
    }
    redirect("/login");
  }

  // Server-side role check: redirect non-teachers
  // school_admin is included because the backend grants teacher.* permissions to school_admin
  const teacherRoles = ["teacher", "academic_head", "school_admin"];
  if (!teacherRoles.includes(session.user.role)) {
    if (session.user.role === "parent") {
      redirect("/parent/dashboard");
    }
    redirect("/dashboard");
  }

  // Fetch accessible schools for chain tenant support.
  // Any teacher can be at a chain tenant, so always fetch and check count.
  const schoolsResult = await getAccessibleSchools();
  const accessibleSchools = schoolsResult.success ? schoolsResult.data || [] : [];

  // A tenant is truly a chain only if it has multiple schools
  const isTrueChain = accessibleSchools.length > 1;

  // Extract tenant branding for CSS variables
  const primaryColor = session.tenant.primary_color;
  const schoolName = session.tenant.name;
  const schoolLogo = session.tenant.logo_url || null;

  return (
    <SessionProvider session={session}>
      <SchoolProvider
        schools={accessibleSchools}
        isChain={isTrueChain}
        redirectPath="/teacher/dashboard"
      >
        <div
          style={
            primaryColor
              ? ({
                  "--primary": primaryColor,
                  "--tenant-primary-color": primaryColor,
                } as React.CSSProperties)
              : undefined
          }
        >
          <SidebarProvider defaultOpen={true}>
            <TeacherSidebar
              user={session.user}
              schoolName={schoolName}
              schoolLogo={schoolLogo}
              isChain={isTrueChain}
            />
            <SidebarInset className="flex flex-col min-h-svh">
              <TeacherHeader
                user={session.user}
                schoolName={schoolName}
                schoolLogo={schoolLogo}
              />
              {/* TeacherGuard is an additional client-side role check */}
              <TeacherGuard>
                {/* Main content area. On mobile, add bottom padding for the tab bar */}
                <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
                  {children}
                </main>
              </TeacherGuard>
            </SidebarInset>
          </SidebarProvider>
          {/* Mobile bottom navigation */}
          <TeacherBottomNav />
        </div>
      </SchoolProvider>
    </SessionProvider>
  );
}
