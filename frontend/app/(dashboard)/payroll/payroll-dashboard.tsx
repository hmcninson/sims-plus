"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  Plus,
  ListOrdered,
  DollarSign,
  Wallet,
  Receipt,
  Shield,
  Users,
  ArrowRight,
  CalendarDays,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { getPayrollRuns } from "@/actions/payroll.action";
import { formatGHS, formatGhanaDate } from "@/lib/format";
import type { PayrollRun, PayrollRunType } from "@/types/payroll.type";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function getRunTypeLabel(type: PayrollRunType): string {
  const labels: Record<PayrollRunType, string> = {
    regular: "Regular",
    supplementary: "Supplementary",
    bonus: "Bonus",
    arrears: "Arrears",
  };
  return labels[type];
}

export function PayrollDashboard() {
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const result = await getPayrollRuns({ limit: 12 });
      if (result.success) {
        setRuns(result.data);
      }
      setIsLoading(false);
    }
    load();
  }, []);

  const latestRun = runs.length > 0 ? runs[0] : null;
  const pendingCount = runs.filter((r) => r.status === "pending_approval").length;
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Payroll</h1>
          <p className="text-muted-foreground">
            Manage monthly payroll processing, approvals, and payments
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" asChild>
            <Link href="/payroll/runs">
              <ListOrdered className="h-4 w-4 mr-2" />
              All Runs
            </Link>
          </Button>
          <Button asChild>
            <Link href="/payroll/runs/new">
              <Plus className="h-4 w-4 mr-2" />
              Create Run
            </Link>
          </Button>
        </div>
      </div>

      {/* Current Month Status */}
      {isLoading ? (
        <Card>
          <CardContent className="p-6">
            <Skeleton className="h-20 w-full" />
          </CardContent>
        </Card>
      ) : latestRun ? (
        <Card>
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-primary/10 p-3">
                  <CalendarDays className="h-6 w-6 text-primary" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Latest Run</p>
                  <h3 className="text-lg font-semibold">
                    {MONTH_NAMES[latestRun.month - 1]} {latestRun.year}
                    {latestRun.run_number > 1 && (
                      <span className="text-sm font-normal text-muted-foreground ml-2">
                        (Run #{latestRun.run_number})
                      </span>
                    )}
                  </h3>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <PayrollStatusBadge status={latestRun.status} />
                {latestRun.status !== "paid" && latestRun.status !== "cancelled" && (
                  <Button size="sm" variant="outline" asChild>
                    <Link href={`/payroll/runs/${latestRun.id}`}>
                      Continue <ArrowRight className="h-4 w-4 ml-1" />
                    </Link>
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-muted-foreground mb-3">No payroll runs yet.</p>
            <Button asChild>
              <Link href="/payroll/runs/new">
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Payroll Run
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Summary Stats from Latest Run */}
      {latestRun && latestRun.status !== "draft" && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <StatCard
            icon={DollarSign}
            label="Total Gross"
            value={formatGHS(latestRun.total_gross)}
            iconClassName="text-blue-600 bg-blue-50 dark:bg-blue-950 dark:text-blue-400"
          />
          <StatCard
            icon={Wallet}
            label="Total Net"
            value={formatGHS(latestRun.total_net)}
            iconClassName="text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400"
          />
          <StatCard
            icon={Receipt}
            label="Total PAYE"
            value={formatGHS(latestRun.total_paye)}
            iconClassName="text-amber-600 bg-amber-50 dark:bg-amber-950 dark:text-amber-400"
          />
          <StatCard
            icon={Shield}
            label="Total SSNIT"
            value={formatGHS(latestRun.total_ssnit_ee + latestRun.total_ssnit_er)}
            iconClassName="text-purple-600 bg-purple-50 dark:bg-purple-950 dark:text-purple-400"
          />
          <StatCard
            icon={Users}
            label="Staff Count"
            value={String(latestRun.staff_count)}
            iconClassName="text-indigo-600 bg-indigo-50 dark:bg-indigo-950 dark:text-indigo-400"
          />
        </div>
      )}

      {/* Pending Approval Alert */}
      {pendingCount > 0 && (
        <Card className="border-yellow-200 bg-yellow-50/50 dark:border-yellow-900 dark:bg-yellow-950/30">
          <CardContent className="p-4 flex items-center justify-between">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              <span className="font-semibold">{pendingCount}</span> payroll run{pendingCount > 1 ? "s" : ""} pending approval
            </p>
            <Button size="sm" variant="outline" asChild>
              <Link href="/payroll/runs?status=pending_approval">Review</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Recent Runs Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Runs</CardTitle>
              <CardDescription>Last 12 payroll runs</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/payroll/runs">
                View All <ArrowRight className="h-4 w-4 ml-1" />
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No payroll runs found.
            </p>
          ) : (
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Period</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right hidden sm:table-cell">Gross</TableHead>
                    <TableHead className="text-right">Net</TableHead>
                    <TableHead className="text-right hidden md:table-cell">Staff</TableHead>
                    <TableHead className="hidden lg:table-cell">Created</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell>
                        <Link
                          href={`/payroll/runs/${run.id}`}
                          className="font-medium hover:underline"
                        >
                          {MONTH_NAMES[run.month - 1]} {run.year}
                          {run.run_number > 1 && (
                            <span className="text-xs text-muted-foreground ml-1">
                              #{run.run_number}
                            </span>
                          )}
                        </Link>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {getRunTypeLabel(run.run_type)}
                      </TableCell>
                      <TableCell>
                        <PayrollStatusBadge status={run.status} />
                      </TableCell>
                      <TableCell className="text-right hidden sm:table-cell">
                        {formatGHS(run.total_gross)}
                      </TableCell>
                      <TableCell className="text-right font-medium">
                        {formatGHS(run.total_net)}
                      </TableCell>
                      <TableCell className="text-right hidden md:table-cell">
                        {run.staff_count}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-muted-foreground text-sm">
                        {formatGhanaDate(run.created_at)}
                      </TableCell>
                      <TableCell>
                        <Button size="sm" variant="ghost" asChild>
                          <Link href={`/payroll/runs/${run.id}`}>
                            <ArrowRight className="h-4 w-4" />
                          </Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  iconClassName,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  iconClassName: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className={`rounded-md p-1.5 w-fit ${iconClassName}`}>
          <Icon className="h-4 w-4" />
        </div>
        <p className="text-xs text-muted-foreground mt-2">{label}</p>
        <p className="text-lg font-semibold tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}
