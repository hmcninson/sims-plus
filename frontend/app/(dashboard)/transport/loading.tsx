import { Skeleton } from "@/components/ui/skeleton";

export default function TransportLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-[260px]" />
        <Skeleton className="mt-2 h-4 w-[340px]" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[110px] rounded-lg" />
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Skeleton className="h-[300px] rounded-lg" />
        <Skeleton className="h-[300px] rounded-lg lg:col-span-2" />
      </div>
    </div>
  );
}
