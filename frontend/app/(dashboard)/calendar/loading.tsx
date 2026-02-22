import { Skeleton } from "@/components/ui/skeleton";

export default function CalendarLoading() {
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-80" />
      </div>

      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main Calendar Area */}
        <div className="flex-1 space-y-4">
          {/* Controls Bar */}
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <Skeleton className="h-9 w-[180px]" />
              <Skeleton className="h-9 w-[250px]" />
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-9" />
                <Skeleton className="h-5 w-[180px]" />
                <Skeleton className="h-9 w-9" />
                <Skeleton className="h-9 w-16" />
              </div>
              <div className="flex items-center gap-2">
                <Skeleton className="h-9 w-28" />
                <Skeleton className="h-9 w-24" />
              </div>
            </div>
          </div>

          {/* Term Legend */}
          <div className="flex flex-wrap gap-4 px-1">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <Skeleton className="h-3 w-3 rounded-sm" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="rounded-lg border bg-card overflow-hidden">
            {/* Weekday headers */}
            <div className="grid grid-cols-7 bg-muted/50 border-b">
              {[...Array(7)].map((_, i) => (
                <div key={i} className="p-2 flex justify-center">
                  <Skeleton className="h-4 w-8" />
                </div>
              ))}
            </div>

            {/* Calendar cells (6 rows x 7 cols) */}
            <div className="grid grid-cols-7">
              {[...Array(42)].map((_, i) => (
                <div key={i} className="h-24 p-1 border border-border/50">
                  <Skeleton className="h-5 w-5 rounded-full" />
                  {i % 7 === 2 && (
                    <Skeleton className="h-3 w-full mt-auto rounded-sm" />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="hidden lg:block w-80 space-y-4">
          {/* School Days Counter */}
          <div className="rounded-lg border bg-card p-4 space-y-4">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-5 w-24" />
            </div>
            <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 space-y-3">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-2 w-full rounded-full" />
              <div className="grid grid-cols-2 gap-2">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center justify-between py-2">
                <div className="space-y-1">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-3 w-28" />
                </div>
                <div className="text-right space-y-1">
                  <Skeleton className="h-4 w-8 ml-auto" />
                  <Skeleton className="h-3 w-20" />
                </div>
              </div>
            ))}
          </div>

          {/* Upcoming Events */}
          <div className="rounded-lg border bg-card p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-5 w-32" />
            </div>
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-lg border">
                <Skeleton className="h-4 w-12" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-3 w-20" />
                </div>
                <Skeleton className="h-5 w-14 rounded-full" />
              </div>
            ))}
          </div>

          {/* Event Sidebar */}
          <div className="rounded-lg border bg-card p-4 space-y-3">
            <Skeleton className="h-5 w-36" />
            <div className="flex flex-col items-center py-6">
              <Skeleton className="h-8 w-8 rounded-full mb-2" />
              <Skeleton className="h-4 w-40" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
