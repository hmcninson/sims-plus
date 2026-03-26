import { Skeleton } from "@/components/ui/skeleton";

export default function ChecklistLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Skeleton className="h-[200px]" />
        <Skeleton className="h-[200px]" />
      </div>
      <Skeleton className="h-[400px]" />
      <Skeleton className="h-[160px]" />
    </div>
  );
}
