"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import type { PlatformAnalytics, TenantSummary } from "@/types/platform.type";
import { Building2, Users, UserCog, School, TrendingUp } from "lucide-react";

interface AnalyticsPageProps {
  analytics: PlatformAnalytics;
}

const PLAN_COLORS: Record<string, string> = {
  starter: "#6366f1",
  professional: "#8b5cf6",
  enterprise: "#a855f7",
  trial: "#3b82f6",
};

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case "active":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
          Active
        </Badge>
      );
    case "trial":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
          Trial
        </Badge>
      );
    case "suspended":
      return <Badge variant="destructive">Suspended</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export function AnalyticsPage({ analytics }: AnalyticsPageProps) {
  const router = useRouter();

  const kpiCards = [
    {
      label: "Total Tenants",
      value: analytics.total_tenants,
      icon: Building2,
      color: "text-indigo-400",
      bg: "bg-indigo-600/10",
    },
    {
      label: "Active",
      value: analytics.active_tenants,
      icon: TrendingUp,
      color: "text-green-400",
      bg: "bg-green-600/10",
    },
    {
      label: "Trial",
      value: analytics.trial_tenants,
      icon: Building2,
      color: "text-blue-400",
      bg: "bg-blue-600/10",
    },
    {
      label: "Suspended",
      value: analytics.suspended_tenants,
      icon: Building2,
      color: "text-red-400",
      bg: "bg-red-600/10",
    },
  ];

  const secondaryCards = [
    {
      label: "Total Students",
      value: analytics.total_students,
      icon: Users,
      color: "text-blue-400",
      bg: "bg-blue-600/10",
    },
    {
      label: "Total Staff",
      value: analytics.total_staff,
      icon: UserCog,
      color: "text-amber-400",
      bg: "bg-amber-600/10",
    },
    {
      label: "Total Schools",
      value: analytics.total_schools,
      icon: School,
      color: "text-green-400",
      bg: "bg-green-600/10",
    },
  ];

  // Build chart data from tenants_by_plan
  const planChartData = Object.entries(analytics.tenants_by_plan).map(
    ([plan, count]) => ({
      name: plan.charAt(0).toUpperCase() + plan.slice(1),
      value: count,
      fill: PLAN_COLORS[plan] || "#6366f1",
    }),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Analytics</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Platform-wide statistics and trends
        </p>
      </div>

      {/* Tenant KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpiCards.map((card) => (
          <Card key={card.label} className="border-zinc-800 bg-zinc-900">
            <CardContent className="flex items-center gap-4 p-6">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${card.bg}`}
              >
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <div>
                <p className="text-sm text-zinc-400">{card.label}</p>
                <p className="text-2xl font-bold text-white">
                  {card.value.toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Secondary KPI cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        {secondaryCards.map((card) => (
          <Card key={card.label} className="border-zinc-800 bg-zinc-900">
            <CardContent className="flex items-center gap-4 p-6">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${card.bg}`}
              >
                <card.icon className={`h-5 w-5 ${card.color}`} />
              </div>
              <div>
                <p className="text-sm text-zinc-400">{card.label}</p>
                <p className="text-2xl font-bold text-white">
                  {card.value.toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Bar chart */}
        <Card className="border-zinc-800 bg-zinc-900">
          <CardHeader>
            <CardTitle className="text-white">Tenants by Plan</CardTitle>
          </CardHeader>
          <CardContent>
            {planChartData.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center text-zinc-500">
                No data available
              </div>
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={planChartData}>
                    <XAxis
                      dataKey="name"
                      tick={{ fill: "#a1a1aa", fontSize: 12 }}
                      axisLine={{ stroke: "#3f3f46" }}
                    />
                    <YAxis
                      tick={{ fill: "#a1a1aa", fontSize: 12 }}
                      axisLine={{ stroke: "#3f3f46" }}
                      allowDecimals={false}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: 8,
                        color: "#fff",
                      }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {planChartData.map((entry, index) => (
                        <Cell key={index} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pie chart */}
        <Card className="border-zinc-800 bg-zinc-900">
          <CardHeader>
            <CardTitle className="text-white">Plan Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            {planChartData.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center text-zinc-500">
                No data available
              </div>
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPieChart>
                    <Pie
                      data={planChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {planChartData.map((entry, index) => (
                        <Cell key={index} fill={entry.fill} />
                      ))}
                    </Pie>
                    <Legend
                      wrapperStyle={{ color: "#a1a1aa", fontSize: 12 }}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#18181b",
                        border: "1px solid #3f3f46",
                        borderRadius: 8,
                        color: "#fff",
                      }}
                    />
                  </RechartsPieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Registrations */}
      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <CardTitle className="text-white">Recent Registrations</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {analytics.recent_registrations.length === 0 ? (
            <div className="py-12 text-center text-zinc-500">
              No recent registrations
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableHead className="text-zinc-400">Name</TableHead>
                    <TableHead className="hidden text-zinc-400 sm:table-cell">
                      Subdomain
                    </TableHead>
                    <TableHead className="text-zinc-400">Status</TableHead>
                    <TableHead className="hidden text-zinc-400 md:table-cell">
                      Students
                    </TableHead>
                    <TableHead className="hidden text-zinc-400 lg:table-cell">
                      Created
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {analytics.recent_registrations.map(
                    (tenant: TenantSummary) => (
                      <TableRow
                        key={tenant.id}
                        className="cursor-pointer border-zinc-800 text-zinc-300 hover:bg-zinc-800/50"
                        onClick={() =>
                          router.push(`/platform/tenants/${tenant.id}`)
                        }
                      >
                        <TableCell className="font-medium text-white">
                          {tenant.name}
                        </TableCell>
                        <TableCell className="hidden text-zinc-400 sm:table-cell">
                          {tenant.subdomain}
                        </TableCell>
                        <TableCell>{statusBadge(tenant.status)}</TableCell>
                        <TableCell className="hidden md:table-cell">
                          {tenant.student_count}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {formatDate(tenant.created_at)}
                        </TableCell>
                      </TableRow>
                    ),
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
