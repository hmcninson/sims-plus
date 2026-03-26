import { Skeleton } from "@/components/ui/skeleton";

export default function PeriodDetailLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Skeleton className="h-[200px]" />
        <Skeleton className="h-[200px]" />
      </div>
      <Skeleton className="h-[400px]" />
    </div>
  );
}
