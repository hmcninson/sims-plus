import { Skeleton } from "@/components/ui/skeleton";

export default function SubscriptionLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-7 w-48" />
        <Skeleton className="mt-1 h-4 w-72" />
      </div>
      {/* Current plan card skeleton */}
      <Skeleton className="h-52 w-full rounded-lg" />
      {/* Upgrade plans skeleton */}
      <div className="space-y-4">
        <Skeleton className="h-6 w-36" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Skeleton className="h-96 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
          <Skeleton className="h-96 rounded-lg" />
        </div>
      </div>
    </div>
  );
}
