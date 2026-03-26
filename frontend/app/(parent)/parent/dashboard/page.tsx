import { Suspense } from "react";
import { getCurrentUser } from "@/actions/auth.action";
import { getParentDashboard } from "@/actions/parent.action";
import { PhoneVerificationBanner } from "@/components/banners/phone-verification-banner";
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

  // Show phone verification prompt for parents with unverified phone
  const showPhoneBanner = user?.phone && !user?.phone_verified;

  return (
    <>
      {showPhoneBanner && (
        <PhoneVerificationBanner settingsPath="/parent/settings" />
      )}
      <Suspense fallback={<ParentDashboardLoading />}>
        <ParentDashboardView
          userName={user?.first_name || "Parent"}
          dashboard={dashboard}
        />
      </Suspense>
    </>
  );
}
