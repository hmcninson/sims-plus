import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getCurrentUserContext } from "@/actions/auth.action";
import { ApiError } from "@/lib/api";
import { SessionProvider } from "@/components/providers/SessionProvider";
import { ParentGuard } from "@/components/auth/ParentGuard";
import { ParentSidebar } from "@/components/parent/parent-sidebar";
import { ParentHeader } from "@/components/parent/parent-header";
import { ParentBottomNav } from "@/components/parent/parent-bottom-nav";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

/**
 * Helper to wait a fixed number of milliseconds.
 */
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Parent Portal Layout
 *
 * A separate layout from the admin dashboard, designed mobile-first
 * for parents. Includes:
 * - Server-side auth check (same pattern as admin dashboard)
 * - Role check: only "parent" role users can access
 * - Desktop sidebar + header
 * - Mobile bottom tab navigation
 * - School branding via tenant CSS variables
 */
export default async function ParentLayout({
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

  // Server-side role check: redirect non-parents to admin dashboard
  if (session.user.role !== "parent") {
    redirect("/dashboard");
  }

  // Extract tenant branding for CSS variables
  const primaryColor = session.tenant.primary_color;
  const schoolName = session.tenant.name;
  const schoolLogo = session.tenant.logo_url || null;

  return (
    <SessionProvider session={session}>
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
          <ParentSidebar
            user={session.user}
            schoolName={schoolName}
            schoolLogo={schoolLogo}
          />
          <SidebarInset className="flex flex-col min-h-svh">
            <ParentHeader
              user={session.user}
              schoolName={schoolName}
              schoolLogo={schoolLogo}
            />
            {/* ParentGuard is an additional client-side role check */}
            <ParentGuard>
              {/* Main content area. On mobile, add bottom padding for the tab bar */}
              <main className="flex-1 p-4 md:p-6 pb-20 md:pb-6">
                {children}
              </main>
            </ParentGuard>
          </SidebarInset>
        </SidebarProvider>
        {/* Mobile bottom navigation */}
        <ParentBottomNav />
      </div>
    </SessionProvider>
  );
}
