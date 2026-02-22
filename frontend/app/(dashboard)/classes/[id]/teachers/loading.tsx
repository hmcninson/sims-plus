import { Skeleton } from "@/components/ui/skeleton";

export default function ClassTeachersLoading() {
  return (
    <div className="space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-56" />
        </div>
      </div>

      {/* Section Tabs Skeleton */}
      <div className="space-y-4">
        <div className="flex gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-24" />
          ))}
        </div>

        {/* Stats Cards Skeleton */}
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="rounded-lg border bg-card p-6">
              <Skeleton className="h-4 w-28 mb-2" />
              <Skeleton className="h-9 w-12" />
            </div>
          ))}
        </div>

        {/* Assignment Table Card Skeleton */}
        <div className="rounded-lg border bg-card">
          <div className="p-6 flex items-center justify-between">
            <div className="space-y-2">
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-56" />
            </div>
            <Skeleton className="h-10 w-36" />
          </div>
          <div className="px-6 pb-6">
            <div className="rounded-md border">
              <div className="border-b p-3 flex gap-8">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-28" />
              </div>
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="border-b p-3 flex gap-8 items-center">
                  <div className="flex items-center gap-3">
                    <Skeleton className="h-9 w-9 rounded-full" />
                    <div className="space-y-1">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-40" />
                    </div>
                  </div>
                  <Skeleton className="h-5 w-32" />
                  <Skeleton className="h-5 w-10" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
