import { Suspense } from "react";

import { getEnrollmentAnalytics } from "@/actions/students.action";
import { EnrollmentAnalyticsDashboard } from "./enrollment-analytics";
import { AnalyticsLoading } from "./loading";

export const metadata = {
  title: "Enrollment Analytics",
};

export default async function EnrollmentAnalyticsPage() {
  const result = await getEnrollmentAnalytics();

  return (
    <Suspense fallback={<AnalyticsLoading />}>
      <EnrollmentAnalyticsDashboard
        data={result.success ? result.data : null}
        error={result.success ? undefined : result.error}
      />
    </Suspense>
  );
}
