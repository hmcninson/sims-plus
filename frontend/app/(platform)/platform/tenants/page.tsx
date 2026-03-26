import { Suspense } from "react";
import { listTenants } from "@/actions/platform.action";
import { TenantsPage } from "@/components/platform/tenants-page";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

function TenantsLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-4 w-72" />
      </div>
      <div className="flex gap-3">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 w-32" />
      </div>
      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

async function TenantsContent() {
  const result = await listTenants({ page: 1, page_size: 20 });

  const initialData = result.success
    ? result.data
    : { items: [], total: 0, page: 1, page_size: 20 };

  return <TenantsPage initialData={initialData} />;
}

export default function PlatformTenantsPage() {
  return (
    <Suspense fallback={<TenantsLoading />}>
      <TenantsContent />
    </Suspense>
  );
}
