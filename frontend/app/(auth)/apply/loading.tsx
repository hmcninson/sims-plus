import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function ApplyLoading() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:py-12">
      {/* School header skeleton */}
      <div className="mb-10 flex flex-col items-center gap-3">
        <Skeleton className="h-20 w-20 rounded-full" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-6 w-40" />
      </div>

      {/* Period cards skeleton */}
      <Skeleton className="mb-4 h-6 w-40" />
      <div className="space-y-4">
        {[1, 2].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-wrap gap-3">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-5 w-32" />
              </div>
              <div className="mb-4 flex gap-2">
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-5 w-20" />
              </div>
              <Skeleton className="h-10 w-28" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
