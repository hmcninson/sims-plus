import { Skeleton } from "@/components/ui/skeleton";

export default function SubjectsLoading() {
  return (
    <div className="space-y-6">
      {/* Header Skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-10 w-32" />
      </div>

      {/* Stats Cards Skeleton */}
      <div className="grid gap-4 md:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card p-6">
            <Skeleton className="h-4 w-20 mb-2" />
            <Skeleton className="h-9 w-12" />
          </div>
        ))}
      </div>

      {/* Subject List Card Skeleton */}
      <div className="rounded-lg border bg-card">
        <div className="p-6 space-y-2">
          <Skeleton className="h-6 w-28" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="px-6 pb-6">
          {/* Search and Filter */}
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <Skeleton className="h-10 flex-1" />
            <Skeleton className="h-10 w-[180px]" />
          </div>

          {/* Table Skeleton */}
          <div className="rounded-md border">
            <div className="border-b p-3 flex gap-8">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-16" />
            </div>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="border-b p-3 flex gap-8 items-center">
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-5 w-16" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
