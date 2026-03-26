import { Suspense } from "react";
import { notFound } from "next/navigation";
import { getTenantDetail } from "@/actions/platform.action";
import { TenantDetailPage } from "@/components/platform/tenant-detail-page";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

function TenantDetailLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-8 w-8" />
        <div>
          <Skeleton className="h-8 w-64" />
          <Skeleton className="mt-2 h-4 w-48" />
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i} className="border-zinc-800 bg-zinc-900">
            <CardContent className="p-6">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="mt-2 h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

async function TenantDetailContent({ id }: { id: string }) {
  const result = await getTenantDetail(id);

  if (!result.success) {
    notFound();
  }

  return <TenantDetailPage tenant={result.data} />;
}

export default async function PlatformTenantDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <Suspense fallback={<TenantDetailLoading />}>
      <TenantDetailContent id={id} />
    </Suspense>
  );
}
