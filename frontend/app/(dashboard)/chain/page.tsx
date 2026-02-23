import { getChainDashboard } from "@/actions/chain.action";
import { ChainDashboardView } from "./chain-dashboard-view";

export const metadata = {
  title: "Chain Dashboard",
};

export default async function ChainDashboardPage() {
  const result = await getChainDashboard();

  const defaultDashboard = {
    total_schools: 0,
    total_students: 0,
    total_staff: 0,
    overall_attendance_rate: 0,
    total_revenue: 0,
    total_outstanding: 0,
    schools: [],
  };

  return (
    <ChainDashboardView
      dashboard={result.success ? result.data : defaultDashboard}
      error={result.success ? undefined : result.error}
    />
  );
}
