import { Suspense } from "react";
import { getCurrentUser } from "@/actions/auth.action";
import { getParentDashboard } from "@/actions/parent.action";
import { ParentDashboardView } from "./parent-dashboard";
import ParentDashboardLoading from "./loading";

export const metadata = {
  title: "Parent Dashboard",
};

export default async function ParentDashboardPage() {
  const [user, dashboardResult] = await Promise.all([
    getCurrentUser(),
    getParentDashboard(),
  ]);

  const dashboard = dashboardResult.success ? dashboardResult.data : null;

  return (
    <Suspense fallback={<ParentDashboardLoading />}>
      <ParentDashboardView
        userName={user?.first_name || "Parent"}
        dashboard={dashboard}
      />
    </Suspense>
  );
}
