"use client";

import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  GraduationCap,
  TrendingDown,
  TrendingUp,
  UserCheck,
  UserMinus,
  UserX,
  Users,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { EnrollmentAnalyticsResponse } from "@/types";

interface EnrollmentAnalyticsDashboardProps {
  data: EnrollmentAnalyticsResponse | null;
  error?: string;
}

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  className,
}: {
  title: string;
  value: number | string;
  icon: typeof Users;
  description?: string;
  className?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className={`rounded-full p-2 ${className || "bg-primary/10"}`}>
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-background p-3 shadow-md">
      <p className="mb-2 text-sm font-medium">{label}</p>
      {payload.map((entry) => (
        <p
          key={entry.name}
          className="text-xs"
          style={{ color: entry.color }}
        >
          {entry.name}: {entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

export function EnrollmentAnalyticsDashboard({
  data,
  error,
}: EnrollmentAnalyticsDashboardProps) {
  if (error || !data) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/students">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Enrollment Analytics</h1>
            <p className="text-muted-foreground">Student enrollment trends and breakdown</p>
          </div>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
            <BarChart3 className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {error || "Failed to load enrollment analytics"}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalStudents =
    data.total_active +
    data.total_inactive +
    data.total_graduated +
    data.total_transferred +
    data.total_withdrawn +
    data.total_suspended;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/students">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Enrollment Analytics</h1>
          <p className="text-muted-foreground">
            Student enrollment trends and breakdown across academic years
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Active Students"
          value={data.total_active.toLocaleString()}
          icon={UserCheck}
          description={`${totalStudents > 0 ? ((data.total_active / totalStudents) * 100).toFixed(1) : 0}% of total`}
          className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
        />
        <StatCard
          title="Graduated"
          value={data.total_graduated.toLocaleString()}
          icon={GraduationCap}
          className="bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
        />
        <StatCard
          title="Transferred"
          value={data.total_transferred.toLocaleString()}
          icon={UserMinus}
          className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
        />
        <StatCard
          title="Withdrawn"
          value={data.total_withdrawn.toLocaleString()}
          icon={UserX}
          className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
        />
      </div>

      {/* Rates */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
        <Card>
          <CardContent className="flex items-center gap-4 pt-6">
            <div className="rounded-full p-3 bg-red-100 dark:bg-red-900/30">
              <TrendingDown className="h-5 w-5 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Attrition Rate</p>
              <p className="text-2xl font-bold">
                {data.attrition_rate.toFixed(1)}%
              </p>
              <p className="text-xs text-muted-foreground">
                Students lost through withdrawal, transfer, or suspension
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 pt-6">
            <div className="rounded-full p-3 bg-green-100 dark:bg-green-900/30">
              <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">New Enrollment Rate</p>
              <p className="text-2xl font-bold">
                {data.new_enrollment_rate.toFixed(1)}%
              </p>
              <p className="text-xs text-muted-foreground">
                New students enrolled relative to total active
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts and Tables Row */}
      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Enrollment Trends Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Enrollment Trends
            </CardTitle>
            <CardDescription>
              Student movement across academic years
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.trends.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center rounded-lg border border-dashed">
                <p className="text-sm text-muted-foreground">
                  No trend data available yet
                </p>
              </div>
            ) : (
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={data.trends}
                    margin={{ top: 5, right: 10, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                      dataKey="academic_year_name"
                      tick={{ fontSize: 11 }}
                      tickFormatter={(v: string) =>
                        v.length > 12 ? `${v.slice(0, 12)}...` : v
                      }
                    />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Legend
                      wrapperStyle={{ fontSize: "12px" }}
                    />
                    <Line
                      type="monotone"
                      dataKey="total_enrolled"
                      name="Total Enrolled"
                      stroke="var(--color-primary, #2563eb)"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="new_enrollments"
                      name="New Enrollments"
                      stroke="#16a34a"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="withdrawals"
                      name="Withdrawals"
                      stroke="#dc2626"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="transfers_out"
                      name="Transfers Out"
                      stroke="#2563eb"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Class Breakdown Table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-semibold">
              Enrollment by Class
            </CardTitle>
            <CardDescription>
              Student distribution across classes
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.by_class.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center rounded-lg border border-dashed">
                <p className="text-sm text-muted-foreground">
                  No class data available
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto max-h-[340px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Class</TableHead>
                      <TableHead className="text-right">Total</TableHead>
                      <TableHead className="text-right hidden sm:table-cell">Male</TableHead>
                      <TableHead className="text-right hidden sm:table-cell">Female</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Boarders</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Day</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.by_class.map((cls) => (
                      <TableRow key={cls.class_id}>
                        <TableCell className="font-medium">
                          {cls.class_name}
                          {/* Mobile: show gender breakdown inline */}
                          <div className="sm:hidden text-xs text-muted-foreground mt-0.5">
                            M: {cls.male} / F: {cls.female}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge variant="secondary">{cls.total}</Badge>
                        </TableCell>
                        <TableCell className="text-right hidden sm:table-cell">
                          {cls.male}
                        </TableCell>
                        <TableCell className="text-right hidden sm:table-cell">
                          {cls.female}
                        </TableCell>
                        <TableCell className="text-right hidden md:table-cell">
                          {cls.boarders}
                        </TableCell>
                        <TableCell className="text-right hidden md:table-cell">
                          {cls.day_students}
                        </TableCell>
                      </TableRow>
                    ))}
                    {/* Totals Row */}
                    <TableRow className="border-t-2 font-semibold">
                      <TableCell>Total</TableCell>
                      <TableCell className="text-right">
                        <Badge>{data.by_class.reduce((sum, c) => sum + c.total, 0)}</Badge>
                      </TableCell>
                      <TableCell className="text-right hidden sm:table-cell">
                        {data.by_class.reduce((sum, c) => sum + c.male, 0)}
                      </TableCell>
                      <TableCell className="text-right hidden sm:table-cell">
                        {data.by_class.reduce((sum, c) => sum + c.female, 0)}
                      </TableCell>
                      <TableCell className="text-right hidden md:table-cell">
                        {data.by_class.reduce((sum, c) => sum + c.boarders, 0)}
                      </TableCell>
                      <TableCell className="text-right hidden md:table-cell">
                        {data.by_class.reduce((sum, c) => sum + c.day_students, 0)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Suspended count if non-zero */}
      {data.total_suspended > 0 && (
        <Card>
          <CardContent className="flex items-center gap-3 pt-6">
            <Badge variant="outline" className="bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400">
              {data.total_suspended} Suspended
            </Badge>
            <p className="text-sm text-muted-foreground">
              Students currently under suspension
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
