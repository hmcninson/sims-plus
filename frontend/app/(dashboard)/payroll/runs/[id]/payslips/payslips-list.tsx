"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Download,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Users,
  Search,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import {
  getPayrollRun,
  getPayrollRunItems,
  getPayslipUrl,
  generateBulkPayslips,
} from "@/actions/payroll.action";
import { formatGHS } from "@/lib/format";
import type { PayrollRun, PayrollItem, BulkPayslipStatus } from "@/types/payroll.type";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface PayslipsListProps {
  runId: string;
}

export function PayslipsList({ runId }: PayslipsListProps) {
  const [run, setRun] = useState<PayrollRun | null>(null);
  const [items, setItems] = useState<PayrollItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [downloadingStaffId, setDownloadingStaffId] = useState<string | null>(null);
  const [bulkStatus, setBulkStatus] = useState<BulkPayslipStatus | null>(null);
  const [isBulkGenerating, setIsBulkGenerating] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [runResult, itemsResult] = await Promise.all([
      getPayrollRun(runId),
      getPayrollRunItems(runId),
    ]);

    if (runResult.success) {
      setRun(runResult.data);
    } else {
      toast.error(runResult.error);
    }

    if (itemsResult.success) {
      setItems(itemsResult.data);
    } else {
      toast.error(itemsResult.error);
    }
    setIsLoading(false);
  }, [runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll bulk status when generating
  useEffect(() => {
    if (!bulkStatus || bulkStatus.status === "completed" || bulkStatus.status === "failed") {
      return;
    }

    const interval = setInterval(async () => {
      // Re-fetch to check progress (the backend updates Redis key)
      const result = await generateBulkPayslips(runId);
      if (result.success) {
        setBulkStatus(result.data);
        if (result.data.status === "completed") {
          toast.success(`All ${result.data.completed} payslips generated successfully`);
          setIsBulkGenerating(false);
        } else if (result.data.status === "failed") {
          toast.error("Bulk payslip generation failed");
          setIsBulkGenerating(false);
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [bulkStatus, runId]);

  async function handleViewPayslip(staffId: string) {
    setDownloadingStaffId(staffId);
    const result = await getPayslipUrl(runId, staffId);
    setDownloadingStaffId(null);
    if (result.success) {
      window.open(result.data.url, "_blank");
    } else {
      toast.error(result.error);
    }
  }

  async function handleBulkGenerate() {
    setIsBulkGenerating(true);
    const result = await generateBulkPayslips(runId);
    if (result.success) {
      setBulkStatus(result.data);
      toast.info("Bulk payslip generation started");
    } else {
      toast.error(result.error);
      setIsBulkGenerating(false);
    }
  }

  const filteredItems = items.filter((item) =>
    item.staff_name.toLowerCase().includes(search.toLowerCase()) ||
    item.staff_code.toLowerCase().includes(search.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-40" />
          </div>
        </div>
        <Card>
          <CardContent className="space-y-3 p-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <h2 className="text-lg font-semibold">Payroll run not found</h2>
        <Button variant="outline" asChild>
          <Link href="/payroll/runs">Back to Runs</Link>
        </Button>
      </div>
    );
  }

  const runTitle = `${MONTH_NAMES[run.month - 1]} ${run.year}`;
  const canGenerate = run.status === "calculated" || run.status === "pending_approval" ||
    run.status === "approved" || run.status === "paid";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/payroll/runs/${runId}`}>
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Payslips - {runTitle}</h1>
            <p className="text-sm text-muted-foreground">
              {items.length} staff members in this run
            </p>
          </div>
        </div>

        {canGenerate && (
          <Button
            onClick={handleBulkGenerate}
            disabled={isBulkGenerating}
            className="gap-2"
          >
            {isBulkGenerating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Users className="h-4 w-4" />
            )}
            {isBulkGenerating ? "Generating..." : "Generate All Payslips"}
          </Button>
        )}
      </div>

      {/* Bulk Progress */}
      {bulkStatus && bulkStatus.status !== "completed" && bulkStatus.status !== "failed" && (
        <Card className="border-blue-200 dark:border-blue-900">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-2">
              <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
              <span className="text-sm font-medium">
                Generating payslips... {bulkStatus.completed} of {bulkStatus.total}
              </span>
            </div>
            <Progress
              value={bulkStatus.total > 0 ? (bulkStatus.completed / bulkStatus.total) * 100 : 0}
              className="h-2"
            />
          </CardContent>
        </Card>
      )}

      {bulkStatus?.status === "completed" && (
        <Card className="border-green-200 dark:border-green-900">
          <CardContent className="p-4 flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5 text-green-600" />
            <span className="text-sm">
              All {bulkStatus.completed} payslips generated successfully.
              {bulkStatus.failed > 0 && (
                <span className="text-amber-600 ml-1">
                  {bulkStatus.failed} failed.
                </span>
              )}
            </span>
          </CardContent>
        </Card>
      )}

      {/* Staff Payslips Table */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Staff Payslips</CardTitle>
            <div className="relative w-full sm:w-[280px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search staff..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <FileText className="h-10 w-10 text-muted-foreground mb-3" />
              <h3 className="text-sm font-medium">No staff found</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {search ? "Try a different search term" : "No payroll items in this run"}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto -mx-6">
              <div className="min-w-[640px] px-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Staff</TableHead>
                      <TableHead className="hidden sm:table-cell">Department</TableHead>
                      <TableHead className="text-right">Gross</TableHead>
                      <TableHead className="text-right hidden md:table-cell">Deductions</TableHead>
                      <TableHead className="text-right">Net Pay</TableHead>
                      <TableHead className="text-right w-[100px]">Payslip</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <div>
                            <p className="font-medium text-sm">{item.staff_name}</p>
                            <p className="text-xs text-muted-foreground">{item.staff_code}</p>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm">
                          {item.department_name || "--"}
                        </TableCell>
                        <TableCell className="text-right text-sm">
                          {formatGHS(item.gross_salary)}
                        </TableCell>
                        <TableCell className="text-right text-sm hidden md:table-cell">
                          {formatGHS(item.total_deductions)}
                        </TableCell>
                        <TableCell className="text-right text-sm font-medium">
                          {formatGHS(item.net_salary)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewPayslip(item.staff_id)}
                            disabled={downloadingStaffId === item.staff_id || !canGenerate}
                            className="gap-1"
                          >
                            {downloadingStaffId === item.staff_id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Download className="h-3.5 w-3.5" />
                            )}
                            <span className="hidden sm:inline">View</span>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
