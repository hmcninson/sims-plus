import { Skeleton } from "@/components/ui/skeleton";

export default function CSSPSLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="h-[500px]" />
    </div>
  );
}
