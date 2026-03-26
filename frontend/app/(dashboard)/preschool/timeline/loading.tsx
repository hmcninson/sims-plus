import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

export default function TimelineLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-44" />
        <Skeleton className="h-4 w-96 mt-2" />
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row">
        <Skeleton className="h-10 w-full md:w-[200px]" />
        <Skeleton className="h-10 w-full md:w-[260px]" />
        <div className="flex gap-2">
          <Skeleton className="h-10 w-[140px]" />
          <Skeleton className="h-10 w-[140px]" />
        </div>
      </div>

      {/* Timeline skeleton */}
      <div className="space-y-6">
        <Skeleton className="h-5 w-32" />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-4">
            <div className="flex flex-col items-center">
              <Skeleton className="h-3 w-3 rounded-full" />
              <Skeleton className="w-0.5 flex-1 mt-1" />
            </div>
            <Skeleton className="h-20 flex-1 rounded-lg" />
          </div>
        ))}
      </div>
    </div>
  );
}
