import { redirect } from "next/navigation";
import { getCurrentUser } from "@/actions/auth.action";
import { getSchoolProfile } from "@/actions/school.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import { AppSidebar } from "@/components/dashboard/app-sidebar";
import { DashboardHeader } from "@/components/dashboard/dashboard-header";
import { SetupCheck } from "@/components/setup-wizard";
import {
  SidebarInset,
  SidebarProvider,
} from "@/components/ui/sidebar";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  // Sidebar always defaults to expanded state on page load

  // Fetch data for setup check
  const [schoolResult, academicYearsResult, classesResult] = await Promise.all([
    getSchoolProfile(),
    getAcademicYears(),
    getClasses(),
  ]);

  const schoolProfile = schoolResult.success ? schoolResult.data : null;
  const academicYears = academicYearsResult.success ? academicYearsResult.data || [] : [];
  const classes = classesResult.success ? classesResult.data || [] : [];

  return (
    <SidebarProvider defaultOpen={true}>
      <AppSidebar user={user} />
      <SidebarInset>
        <DashboardHeader user={user} />
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
  );
}
