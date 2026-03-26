"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Download,
  Loader2,
  AlertTriangle,
  Landmark,
  TrendingUp,
  TrendingDown,
  Banknote,
} from "lucide-react";
import {
  PieChart as RechartsPieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  getLoanPortfolio,
  getLoanAging,
  exportPortfolio,
  exportLoanAging,
} from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";
import type { LoanPortfolio, LoanAgingBucket, LoanAgingResponse } from "@/types/loan.type";

const PIE_COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16",
];

const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Pending",
  approved: "Approved",
  active: "Active",
  completed: "Completed",
  written_off: "Written Off",
  restructured: "Restructured",
  rejected: "Rejected",
};

export function LoanPortfolioDashboard() {
  const [portfolio, setPortfolio] = useState<LoanPortfolio | null>(null);
  const [aging, setAging] = useState<LoanAgingBucket[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isExporting, setIsExporting] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [portfolioResult, agingResult] = await Promise.all([
      getLoanPortfolio(),
      getLoanAging(),
    ]);
    if (portfolioResult.success) setPortfolio(portfolioResult.data);
    if (agingResult.success) setAging(agingResult.data.buckets);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleExportPortfolio() {
    setIsExporting(true);
    const result = await exportPortfolio();
    if (result.success && result.data.url) {
      window.open(result.data.url, "_blank");
    } else {
      toast.error(result.success ? "Export not available" : result.error);
    }
    setIsExporting(false);
  }

  async function handleExportAging() {
    const result = await exportLoanAging();
    if (result.success && result.data.url) {
      window.open(result.data.url, "_blank");
    } else {
      toast.error(result.success ? "Export not available" : result.error);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-32" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Landmark className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">Could not load portfolio data</p>
        <Button variant="outline" onClick={loadData}>
          Try again
        </Button>
      </div>
    );
  }

  const pieData = portfolio.by_type.map((bt) => ({
    name: bt.loan_type_name,
    value: bt.total_principal,
    count: bt.count,
  }));

  const barData = portfolio.monthly_disbursements || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/payroll/loans">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Loan Portfolio
            </h1>
            <p className="text-muted-foreground">
              {portfolio.total_loans} total loans &middot;{" "}
              {portfolio.active_loans} active
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          onClick={handleExportPortfolio}
          disabled={isExporting}
        >
          {isExporting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <Download className="h-4 w-4 mr-2" />
          )}
          Export
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Disbursed
            </CardTitle>
            <Banknote className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatGHS(portfolio.total_disbursed)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Outstanding</CardTitle>
            <TrendingDown className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">
              {formatGHS(portfolio.total_outstanding)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Collected</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatGHS(portfolio.total_collected)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Written Off</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formatGHS(portfolio.total_written_off)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Overdue Alert */}
      {portfolio.overdue_count > 0 && (
        <Card className="border-amber-200 dark:border-amber-800">
          <CardContent className="flex items-center gap-3 p-4">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />
            <div>
              <p className="font-medium text-amber-700 dark:text-amber-400">
                {portfolio.overdue_count} overdue loan
                {portfolio.overdue_count > 1 ? "s" : ""}
              </p>
              <p className="text-sm text-muted-foreground">
                Total overdue amount: {formatGHS(portfolio.overdue_amount)}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Charts & Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="aging">Aging Report</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Pie Chart: By Type */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By Loan Type</CardTitle>
              </CardHeader>
              <CardContent>
                {pieData.length === 0 ? (
                  <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                    No data available
                  </div>
                ) : (
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, percent }) =>
                            `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`
                          }
                          outerRadius={100}
                          fill="#8884d8"
                          dataKey="value"
                        >
                          {pieData.map((_, index) => (
                            <Cell
                              key={`cell-${index}`}
                              fill={PIE_COLORS[index % PIE_COLORS.length]}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          content={({ active, payload }) => {
                            if (!active || !payload?.[0]) return null;
                            const data = payload[0].payload as {
                              name: string;
                              value: number;
                              count: number;
                            };
                            return (
                              <div className="rounded-lg border bg-background p-3 shadow-md">
                                <p className="font-medium">{data.name}</p>
                                <p className="text-sm">
                                  {formatGHS(data.value)} ({data.count} loans)
                                </p>
                              </div>
                            );
                          }}
                        />
                      </RechartsPieChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Bar Chart: Monthly Disbursements */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  Monthly Disbursements
                </CardTitle>
              </CardHeader>
              <CardContent>
                {barData.length === 0 ? (
                  <div className="flex items-center justify-center h-[300px] text-muted-foreground">
                    No data available
                  </div>
                ) : (
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={barData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis />
                        <Tooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload?.[0]) return null;
                            return (
                              <div className="rounded-lg border bg-background p-3 shadow-md">
                                <p className="font-medium">{label}</p>
                                <p className="text-sm">
                                  {formatGHS(payload[0].value as number)}
                                </p>
                              </div>
                            );
                          }}
                        />
                        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Status Breakdown */}
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">By Status</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                {Object.entries(portfolio.by_status).map(([status, count]) => (
                  <div
                    key={status}
                    className="flex items-center gap-2 text-sm"
                  >
                    <span className="font-medium">
                      {STATUS_LABELS[status] || status}:
                    </span>
                    <Badge variant="secondary">{count}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* By Type Table */}
          {portfolio.by_type.length > 0 && (
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="text-base">
                  Type Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Loan Type</TableHead>
                        <TableHead className="text-right">Count</TableHead>
                        <TableHead className="text-right">
                          Total Amount
                        </TableHead>
                        <TableHead className="text-right">
                          Outstanding
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {portfolio.by_type.map((bt) => (
                        <TableRow key={bt.loan_type_name}>
                          <TableCell className="font-medium">
                            {bt.loan_type_name}
                          </TableCell>
                          <TableCell className="text-right">
                            {bt.count}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatGHS(bt.total_principal)}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatGHS(bt.total_outstanding)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Aging Report Tab */}
        <TabsContent value="aging">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Loan Aging Report</CardTitle>
              <Button variant="outline" size="sm" onClick={handleExportAging}>
                <Download className="h-4 w-4 mr-1" />
                Export
              </Button>
            </CardHeader>
            <CardContent className="p-0">
              {aging.length === 0 ? (
                <div className="flex flex-col items-center py-12 gap-2 text-muted-foreground">
                  <Landmark className="h-8 w-8" />
                  <p>No overdue loans</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Aging Bucket</TableHead>
                        <TableHead className="text-right">
                          Loan Count
                        </TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {aging.map((bucket) => (
                        <TableRow key={bucket.bucket}>
                          <TableCell className="font-medium">
                            {bucket.bucket}
                          </TableCell>
                          <TableCell className="text-right">
                            {bucket.count}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatGHS(bucket.total_amount)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
