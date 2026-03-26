"use client";

import { useEffect, useRef, useCallback } from "react";
import { Loader2, CheckCircle2, AlertCircle } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { getPayrollRun } from "@/actions/payroll.action";
import type { PayrollRunStatus } from "@/types/payroll.type";

interface PayrollCalculationStatusProps {
  runId: string;
  status: PayrollRunStatus;
  onStatusChange: (newStatus: PayrollRunStatus) => void;
}

export function PayrollCalculationStatus({
  runId,
  status,
  onStatusChange,
}: PayrollCalculationStatusProps) {
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollStatus = useCallback(async () => {
    const result = await getPayrollRun(runId);
    if (result.success && result.data.status !== "processing") {
      onStatusChange(result.data.status);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }
  }, [runId, onStatusChange]);

  useEffect(() => {
    if (status === "processing") {
      intervalRef.current = setInterval(pollStatus, 3000);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [status, pollStatus]);

  if (status !== "processing") return null;

  return (
    <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30">
      <CardContent className="p-6 flex items-center gap-4">
        <div className="relative">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <h3 className="font-semibold text-blue-900 dark:text-blue-100">
            Calculating Payroll...
          </h3>
          <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
            Processing salary calculations, tax deductions, and statutory contributions for all staff.
            This may take a moment.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export function PayrollCalculationComplete() {
  return (
    <Card className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/30">
      <CardContent className="p-4 flex items-center gap-3">
        <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
        <p className="text-sm text-green-700 dark:text-green-300">
          Payroll calculation completed successfully. Review the breakdown below.
        </p>
      </CardContent>
    </Card>
  );
}

export function PayrollCalculationError({ message }: { message?: string }) {
  return (
    <Card className="border-red-200 bg-red-50/50 dark:border-red-900 dark:bg-red-950/30">
      <CardContent className="p-4 flex items-center gap-3">
        <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
        <p className="text-sm text-red-700 dark:text-red-300">
          {message || "Payroll calculation encountered an error. Please try again."}
        </p>
      </CardContent>
    </Card>
  );
}
