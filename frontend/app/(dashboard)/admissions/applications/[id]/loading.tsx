import { Skeleton } from "@/components/ui/skeleton";

export default function ApplicationDetailLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Skeleton className="h-[200px]" />
          <Skeleton className="h-[150px]" />
          <Skeleton className="h-[200px]" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-[300px]" />
          <Skeleton className="h-[200px]" />
        </div>
      </div>
    </div>
  );
}
