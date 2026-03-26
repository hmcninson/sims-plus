"use client";

import { Badge } from "@/components/ui/badge";
import type { LoanStatus } from "@/types/loan.type";

const statusConfig: Record<
  LoanStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className: "bg-gray-100 text-gray-700 hover:bg-gray-100 dark:bg-gray-800 dark:text-gray-300",
  },
  pending_approval: {
    label: "Pending Approval",
    className: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100 dark:bg-yellow-900 dark:text-yellow-300",
  },
  approved: {
    label: "Approved",
    className: "bg-blue-100 text-blue-700 hover:bg-blue-100 dark:bg-blue-900 dark:text-blue-300",
  },
  active: {
    label: "Active",
    className: "bg-green-100 text-green-700 hover:bg-green-100 dark:bg-green-900 dark:text-green-300",
  },
  completed: {
    label: "Completed",
    className: "bg-emerald-100 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900 dark:text-emerald-300",
  },
  written_off: {
    label: "Written Off",
    className: "bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900 dark:text-red-300",
  },
  restructured: {
    label: "Restructured",
    className: "bg-purple-100 text-purple-700 hover:bg-purple-100 dark:bg-purple-900 dark:text-purple-300",
  },
  rejected: {
    label: "Rejected",
    className: "bg-red-100 text-red-700 hover:bg-red-100 dark:bg-red-900 dark:text-red-300",
  },
};

interface LoanStatusBadgeProps {
  status: LoanStatus;
  className?: string;
}

export function LoanStatusBadge({ status, className }: LoanStatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge
      variant="default"
      className={`${config.className} ${className || ""}`}
    >
      {config.label}
    </Badge>
  );
}
