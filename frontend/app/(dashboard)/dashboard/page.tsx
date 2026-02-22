import { KpiCard } from "@/components/dashboard/kpi-card";
import { WelcomeBanner } from "@/components/dashboard/welcome-banner";
import { AttendanceChart } from "@/components/dashboard/attendance-chart";
import { FeeCollectionChart } from "@/components/dashboard/fee-collection-chart";
import { GenderDonut } from "@/components/dashboard/gender-donut";
import { QuickActions } from "@/components/dashboard/quick-actions";
import { MobileQuickActions } from "@/components/dashboard/mobile-quick-actions";
import { PushPermissionPrompt } from "@/components/pwa/push-permission";

import { getCurrentUser } from "@/actions/auth.action";
import {
  getDashboardStats,
  getAttendanceTrend,
  getFeeCollectionTrend,
  getGenderDistribution,
} from "@/actions/dashboard.action";

export const metadata = {
  title: "Dashboard",
};

export default async function DashboardPage() {
  const [user, statsResult, attendanceResult, feeResult, genderResult] =
    await Promise.all([
      getCurrentUser(),
      getDashboardStats(),
      getAttendanceTrend(),
      getFeeCollectionTrend(),
      getGenderDistribution(),
    ]);

  const firstName = user?.first_name || "there";
  const stats = statsResult.success ? statsResult.data : null;
  const attendanceTrend = attendanceResult.success ? attendanceResult.data : [];
  const feeTrend = feeResult.success ? feeResult.data : [];
  const gender = genderResult.success ? genderResult.data : null;

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <WelcomeBanner
        firstName={firstName}
        totalStudents={stats ? stats.total_students.toLocaleString() : "--"}
        attendanceRate={stats ? `${stats.attendance_today.rate}%` : "--"}
        collectionRate={stats ? `${stats.finance.collection_rate}%` : "--"}
      />

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Total Students"
          value={stats ? stats.total_students.toLocaleString() : "--"}
          iconName="Users"
          href="/students"
        />
        <KpiCard
          title="Total Staff"
          value={stats ? stats.total_staff.toLocaleString() : "--"}
          iconName="UserCog"
          href="/staff"
        />
        <KpiCard
          title="Attendance Today"
          value={stats ? `${stats.attendance_today.rate}%` : "--"}
          iconName="ClipboardCheck"
          href="/attendance"
        />
        <KpiCard
          title="Fees Collected"
          value={
            stats
              ? `GHS ${stats.finance.total_collected.toLocaleString()}`
              : "--"
          }
          iconName="Wallet"
          href="/finance"
        />
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <AttendanceChart data={attendanceTrend} />
        <FeeCollectionChart data={feeTrend} />
      </div>

      {/* Bottom Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        <GenderDonut data={gender} />
        <div className="lg:col-span-2">
          <QuickActions />
        </div>
      </div>

      {/* Mobile FAB for quick actions (visible on small screens only) */}
      <MobileQuickActions />

      {/* Push notification opt-in prompt (shows once after delay) */}
      <PushPermissionPrompt />
    </div>
  );
}
