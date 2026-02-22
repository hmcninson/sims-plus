import { Skeleton } from "@/components/ui/skeleton";

export default function ClassDetailLoading() {
  return (
    <div className="space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-3">
            <Skeleton className="h-8 w-40" />
            <Skeleton className="h-5 w-12" />
            <Skeleton className="h-5 w-16" />
          </div>
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="hidden sm:flex items-center gap-2">
          <Skeleton className="h-9 w-36" />
          <Skeleton className="h-9 w-40" />
        </div>
      </div>

      {/* Stats Cards Skeleton */}
      <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-6 space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-9 w-12" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>

      {/* Tabs Skeleton */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-32" />
          <Skeleton className="h-9 w-32" />
        </div>

        {/* Table Card Skeleton */}
        <div className="rounded-lg border bg-card">
          <div className="p-6 space-y-2">
            <div className="flex items-center justify-between">
              <div className="space-y-2">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-4 w-56" />
              </div>
              <Skeleton className="h-9 w-32" />
            </div>
          </div>
          <div className="px-6 pb-6">
            <div className="rounded-md border">
              {/* Table Header */}
              <div className="border-b p-3 flex gap-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-20" />
                ))}
              </div>
              {/* Table Rows */}
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="border-b p-3 flex gap-4 items-center">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <Skeleton key={j} className="h-4 w-20" />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Quick Links Skeleton */}
      <div className="rounded-lg border bg-card">
        <div className="p-6">
          <Skeleton className="h-5 w-24 mb-4" />
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="rounded-lg border p-3 flex items-center gap-3">
                <Skeleton className="h-5 w-5" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
