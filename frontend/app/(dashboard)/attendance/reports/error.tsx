"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function AttendanceReportsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Attendance reports error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle className="h-8 w-8 text-destructive" />
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-foreground">
            Failed to load attendance reports
          </h2>
          <p className="text-sm text-muted-foreground">
            {error.message || "An unexpected error occurred while loading the attendance reports."}
          </p>
          {error.digest && (
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              Error ID: {error.digest}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Button onClick={() => reset()} variant="default">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
          <Button variant="outline" asChild>
            <Link href="/attendance">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Attendance
            </Link>
          </Button>
        </div>

        <p className="text-sm text-muted-foreground">
          If this problem persists,{" "}
          <a
            href="mailto:support@simsplus.io"
            className="font-medium text-primary hover:underline"
          >
            contact support
          </a>
        </p>
      </div>
    </div>
  );
}
