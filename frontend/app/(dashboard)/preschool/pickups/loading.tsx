import { Skeleton } from "@/components/ui/skeleton";

export default function PickupsLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-80 mt-2" />
      </div>
      <Skeleton className="h-10 w-full max-w-md" />
      <Skeleton className="h-96 rounded-lg" />
    </div>
  );
}
