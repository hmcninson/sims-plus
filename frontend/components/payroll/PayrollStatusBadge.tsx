"use client";

import { Loader2, Lock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { PayrollRunStatus } from "@/types/payroll.type";

const statusConfig: Record<
  PayrollRunStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline"; className: string; icon?: boolean }
> = {
  draft: {
    label: "Draft",
    variant: "secondary",
    className: "",
  },
  processing: {
    label: "Processing",
    variant: "default",
    className: "bg-blue-100 text-blue-700 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-300",
    icon: true,
  },
  calculated: {
    label: "Calculated",
    variant: "default",
    className: "bg-amber-100 text-amber-700 hover:bg-amber-100 dark:bg-amber-900 dark:text-amber-300",
  },
  pending_approval: {
    label: "Pending Approval",
    variant: "default",
    className: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-300",
  },
  approved: {
    label: "Approved",
    variant: "default",
    className: "bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900 dark:text-green-300",
  },
  paid: {
    label: "Paid",
    variant: "default",
    className: "bg-emerald-100 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300",
  },
  cancelled: {
    label: "Cancelled",
    variant: "destructive",
    className: "",
  },
};

interface PayrollStatusBadgeProps {
  status: PayrollRunStatus;
  className?: string;
}

export function PayrollStatusBadge({ status, className }: PayrollStatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge
      variant={config.variant}
      className={`${config.className} ${className || ""} gap-1`}
    >
      {status === "processing" && (
        <Loader2 className="h-3 w-3 animate-spin" />
      )}
      {status === "paid" && <Lock className="h-3 w-3" />}
      {config.label}
    </Badge>
  );
}
