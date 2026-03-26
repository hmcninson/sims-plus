"use client";

import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { InquiryStatusBadge } from "./inquiry-status-badge";
import type { Inquiry, InquiryStatus } from "@/types/inquiry.type";

interface DuplicateWarningProps {
  matches: Inquiry[];
}

export function DuplicateWarning({ matches }: DuplicateWarningProps) {
  if (matches.length === 0) return null;

  return (
    <Alert variant="destructive" className="border-amber-500 bg-amber-50 text-amber-900 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-700">
      <AlertTriangle className="h-4 w-4 !text-amber-600 dark:!text-amber-400" />
      <AlertTitle>Possible Duplicate{matches.length > 1 ? "s" : ""} Found</AlertTitle>
      <AlertDescription>
        <p className="mb-2 text-sm">
          {matches.length} existing inquiry{matches.length > 1 ? " records match" : " record matches"} this guardian contact information. You can still proceed if this is a new inquiry.
        </p>
        <ul className="space-y-1">
          {matches.map((m) => (
            <li key={m.id} className="flex items-center gap-2 text-sm">
              <span className="font-medium">
                {m.first_name} {m.last_name}
              </span>
              <span className="text-muted-foreground">
                ({m.guardian_name} - {m.guardian_phone})
              </span>
              <InquiryStatusBadge status={m.status as InquiryStatus} />
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
