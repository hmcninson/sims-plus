import { Skeleton } from "@/components/ui/skeleton";

export default function CapacityLoading() {
  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-10 w-[220px]" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-[350px]" />
      <Skeleton className="h-[300px]" />
    </div>
  );
}
