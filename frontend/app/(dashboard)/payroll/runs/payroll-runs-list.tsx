"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, ArrowRight, Filter } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import type { PayrollRun, PayrollRunStatus, PayrollRunType } from "@/types/payroll.type";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "processing", label: "Processing" },
  { value: "calculated", label: "Calculated" },
  { value: "pending_approval", label: "Pending Approval" },
  { value: "approved", label: "Approved" },
  { value: "paid", label: "Paid" },
  { value: "cancelled", label: "Cancelled" },
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

export function PayrollRunsList() {
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [yearFilter, setYearFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - i);

  const loadRuns = useCallback(async () => {
    setIsLoading(true);
    const params: { year?: number; status?: string } = {};
    if (yearFilter !== "all") params.year = parseInt(yearFilter);
    if (statusFilter !== "all") params.status = statusFilter;
    const result = await getPayrollRuns(params);
    if (result.success) {
      setRuns(result.data);
    }
    setIsLoading(false);
  }, [yearFilter, statusFilter]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Payroll Runs</h1>
          <p className="text-muted-foreground">
            View and manage all payroll processing runs
          </p>
        </div>
        <Button asChild>
          <Link href="/payroll/runs/new">
            <Plus className="h-4 w-4 mr-2" />
            Create Run
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <Select value={yearFilter} onValueChange={setYearFilter}>
          <SelectTrigger className="w-full md:w-[140px]">
            <SelectValue placeholder="Year" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Years</SelectItem>
            {yearOptions.map((y) => (
              <SelectItem key={y} value={String(y)}>
                {y}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Filter className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-lg font-medium">No payroll runs found</p>
              <p className="text-sm text-muted-foreground mt-1 mb-4">
                {yearFilter !== "all" || statusFilter !== "all"
                  ? "Try adjusting your filters"
                  : "Create your first payroll run to get started"}
              </p>
              <Button asChild>
                <Link href="/payroll/runs/new">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Run
                </Link>
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
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
