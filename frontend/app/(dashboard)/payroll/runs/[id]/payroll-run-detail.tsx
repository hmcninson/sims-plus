"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Calculator,
  Send,
  Banknote,
  XCircle,
  RefreshCw,
  Lock,
  AlertCircle,
  FileText,
  FileSpreadsheet,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { PayrollSummaryCards } from "@/components/payroll/PayrollSummaryCards";
import { PayrollItemsTable } from "@/components/payroll/PayrollItemsTable";
import { PayrollCalculationStatus } from "@/components/payroll/PayrollCalculationStatus";
import { PayrollApprovalFlow } from "@/components/payroll/PayrollApprovalFlow";
import {
  getPayrollRun,
  getPayrollRunItems,
  calculatePayrollRun,
  submitPayrollRun,
  markPayrollRunPaid,
  cancelPayrollRun,
} from "@/actions/payroll.action";
import { getCurrentUser } from "@/actions/auth.action";
import type { PayrollRun, PayrollItem, PayrollRunStatus } from "@/types/payroll.type";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

interface PayrollRunDetailProps {
  runId: string;
}

export function PayrollRunDetail({ runId }: PayrollRunDetailProps) {
  const router = useRouter();
  const [run, setRun] = useState<PayrollRun | null>(null);
  const [items, setItems] = useState<PayrollItem[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isItemsLoading, setIsItemsLoading] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    const [runResult, userResult] = await Promise.all([
      getPayrollRun(runId),
      getCurrentUser(),
    ]);

    if (runResult.success) {
      setRun(runResult.data);
      if (userResult) {
        setCurrentUserId(userResult.id);
      }

      // Load items if run has been calculated
      if (
        runResult.data.status !== "draft" &&
        runResult.data.status !== "processing" &&
        runResult.data.status !== "cancelled"
      ) {
        setIsItemsLoading(true);
        const itemsResult = await getPayrollRunItems(runId);
        if (itemsResult.success) {
          setItems(itemsResult.data);
        }
        setIsItemsLoading(false);
      }
    } else {
      toast.error(runResult.error);
    }
    setIsLoading(false);
  }, [runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStatusChange = useCallback(
    (newStatus: PayrollRunStatus) => {
      // Reload all data when status changes (e.g., calculation completes)
      loadData();
    },
    [loadData]
  );

  async function handleCalculate() {
    setIsActionLoading(true);
    const result = await calculatePayrollRun(runId);
    setIsActionLoading(false);
    if (result.success) {
      setRun(result.data);
      toast.success("Payroll calculation started");
      // If immediately calculated (small staff), reload
      if (result.data.status === "calculated") {
        loadData();
      }
    } else {
      toast.error(result.error);
    }
  }

  async function handleSubmit() {
    setIsActionLoading(true);
    const result = await submitPayrollRun(runId);
    setIsActionLoading(false);
    if (result.success) {
      setRun(result.data);
      toast.success("Payroll run submitted for approval");
    } else {
      toast.error(result.error);
    }
  }

  async function handleMarkPaid() {
    setIsActionLoading(true);
    const result = await markPayrollRunPaid(runId);
    setIsActionLoading(false);
    if (result.success) {
      setRun(result.data);
      toast.success("Payroll run marked as paid");
    } else {
      toast.error(result.error);
    }
  }

  async function handleCancel() {
    setIsActionLoading(true);
    const result = await cancelPayrollRun(runId);
    setIsActionLoading(false);
    if (result.success) {
      setRun(result.data);
      toast.success("Payroll run cancelled");
    } else {
      toast.error(result.error);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4 space-y-2">
                <Skeleton className="h-8 w-8 rounded-md" />
                <Skeleton className="h-3 w-16" />
                <Skeleton className="h-6 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
        <Skeleton className="h-[400px] w-full" />
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

  const runTitle = `${MONTH_NAMES[run.month - 1]} ${run.year}${
    run.run_number > 1 ? ` (Run #${run.run_number})` : ""
  }`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/payroll/runs">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">{runTitle}</h1>
              <PayrollStatusBadge status={run.status} />
            </div>
            <p className="text-muted-foreground text-sm mt-0.5">
              {run.run_type !== "regular" && (
                <span className="capitalize">{run.run_type} run - </span>
              )}
              {run.currency} currency
              {run.notes && <span> - {run.notes}</span>}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-2">
          {run.status === "draft" && (
            <>
              <Button
                onClick={handleCalculate}
                disabled={isActionLoading}
                className="gap-1"
              >
                <Calculator className="h-4 w-4" />
                {isActionLoading ? "Starting..." : "Calculate"}
              </Button>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm" className="gap-1">
                    <XCircle className="h-4 w-4" />
                    Cancel Run
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Cancel Payroll Run?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently cancel the payroll run for {runTitle}.
                      This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Keep Run</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleCancel}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Cancel Run
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </>
          )}

          {run.status === "calculated" && (
            <>
              <Button
                onClick={handleSubmit}
                disabled={isActionLoading}
                className="gap-1"
              >
                <Send className="h-4 w-4" />
                {isActionLoading ? "Submitting..." : "Submit for Approval"}
              </Button>
              <Button
                variant="outline"
                onClick={handleCalculate}
                disabled={isActionLoading}
                className="gap-1"
              >
                <RefreshCw className="h-4 w-4" />
                Recalculate
              </Button>
            </>
          )}

          {run.status === "approved" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button className="gap-1">
                  <Banknote className="h-4 w-4" />
                  Mark as Paid
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Mark as Paid?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This confirms that payments for {runTitle} have been disbursed.
                    The run will be locked and no further changes will be possible.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleMarkPaid}>
                    Confirm Payment
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}

          {run.status === "paid" && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Lock className="h-4 w-4" />
              This run is locked (paid)
            </div>
          )}
        </div>
      </div>

      {/* Calculation Status (polling) */}
      {run.status === "processing" && (
        <PayrollCalculationStatus
          runId={runId}
          status={run.status}
          onStatusChange={handleStatusChange}
        />
      )}

      {/* Summary Cards */}
      {run.status !== "draft" && run.status !== "processing" && run.status !== "cancelled" && (
        <PayrollSummaryCards run={run} />
      )}

      {/* Draft empty state */}
      {run.status === "draft" && (
        <Card>
          <CardContent className="p-8 text-center">
            <Calculator className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-1">Ready to Calculate</h3>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              This payroll run is in draft status. Click "Calculate" to process salary
              calculations, tax deductions, and statutory contributions for all eligible staff.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Cancelled state */}
      {run.status === "cancelled" && (
        <Card className="border-red-200 dark:border-red-900">
          <CardContent className="p-8 text-center">
            <XCircle className="h-12 w-12 text-red-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-1">Run Cancelled</h3>
            <p className="text-sm text-muted-foreground">
              This payroll run has been cancelled and cannot be processed.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Approval Flow */}
      {(run.status === "pending_approval" || run.status === "approved" || run.status === "paid") && (
        <PayrollApprovalFlow
          run={run}
          currentUserId={currentUserId}
          onActionComplete={loadData}
        />
      )}

      {/* Quick Links: Payslips & Bank File */}
      {run.status !== "draft" && run.status !== "processing" && run.status !== "cancelled" && (
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" asChild className="gap-2">
            <Link href={`/payroll/runs/${runId}/payslips`}>
              <FileText className="h-4 w-4" />
              Payslips
            </Link>
          </Button>
          {(run.status === "approved" || run.status === "paid") && (
            <Button variant="outline" asChild className="gap-2">
              <Link href={`/payroll/runs/${runId}/bank-file`}>
                <FileSpreadsheet className="h-4 w-4" />
                Bank File
              </Link>
            </Button>
          )}
        </div>
      )}

      {/* Staff Breakdown Table */}
      {run.status !== "draft" && run.status !== "processing" && run.status !== "cancelled" && (
        <Card>
          <CardHeader>
            <CardTitle>Staff Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <PayrollItemsTable
              items={items}
              runId={runId}
              isLoading={isItemsLoading}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
