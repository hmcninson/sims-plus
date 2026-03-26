import { Skeleton } from "@/components/ui/skeleton";

export default function WaitlistLoading() {
  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-48" />
        </div>
        <Skeleton className="h-10 w-[200px]" />
      </div>
      <Skeleton className="h-[500px]" />
    </div>
  );
}
