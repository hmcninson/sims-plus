import { Fragment } from "react";

import { Skeleton } from "@/components/ui/skeleton";

export default function TimetableLoading() {
  return (
    <div className="space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-9 w-40" />
      </div>

      {/* Filters Card Skeleton */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 space-y-2">
          <Skeleton className="h-6 w-28" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="px-6 pb-6">
          <div className="grid gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Timetable Grid Skeleton */}
      <div className="rounded-lg border bg-card p-6">
        <div className="space-y-4">
          <Skeleton className="h-6 w-48" />
          <div className="grid grid-cols-6 gap-2">
            {/* Header row */}
            <Skeleton className="h-10" />
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={`header-${i}`} className="h-10" />
            ))}
            {/* Period rows */}
            {Array.from({ length: 8 }).map((_, row) => (
              <Fragment key={`row-${row}`}>
                <Skeleton className="h-20" />
                {Array.from({ length: 5 }).map((_, col) => (
                  <Skeleton key={`cell-${row}-${col}`} className="h-20" />
                ))}
              </Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
