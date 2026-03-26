import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { InquiryStatus } from "@/types/inquiry.type";

interface InquiryStatusBadgeProps {
  status: InquiryStatus;
  className?: string;
}

const STATUS_CONFIG: Record<InquiryStatus, { label: string; className: string }> = {
  new: {
    label: "New",
    className:
      "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-800",
  },
  contacted: {
    label: "Contacted",
    className:
      "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300 dark:border-yellow-800",
  },
  interested: {
    label: "Interested",
    className:
      "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-300 dark:border-purple-800",
  },
  applied: {
    label: "Applied",
    className:
      "bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800",
  },
  enrolled: {
    label: "Enrolled",
    className:
      "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900 dark:text-emerald-300 dark:border-emerald-800",
  },
  lost: {
    label: "Lost",
    className:
      "bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800",
  },
};

export function InquiryStatusBadge({ status, className }: InquiryStatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  if (!config) {
    return (
      <Badge variant="outline" className={className}>
        {status.replace(/_/g, " ")}
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className={cn(config.className, className)}>
      {config.label}
    </Badge>
  );
}
