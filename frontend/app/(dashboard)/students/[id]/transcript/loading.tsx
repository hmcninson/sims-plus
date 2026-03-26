import { Skeleton } from "@/components/ui/skeleton";

export default function TranscriptLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-64" />
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-2 h-4 w-48" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-[200px]" />
          <Skeleton className="h-9 w-24" />
        </div>
      </div>
      <div className="mx-auto max-w-[210mm] space-y-6">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-16 w-full" />
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full" />
        ))}
        <Skeleton className="h-24 w-full" />
      </div>
    </div>
  );
}
