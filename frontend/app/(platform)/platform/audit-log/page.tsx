import { Suspense } from "react";
import { getPlatformAuditLog } from "@/actions/platform.action";
import { AuditLogPage } from "@/components/platform/audit-log-page";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

function AuditLogLoading() {
  return (
    <div className="space-y-6">
      <div>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-2 h-4 w-64" />
      </div>
      <div className="flex gap-3">
        <Skeleton className="h-10 w-48" />
      </div>
      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

async function AuditLogContent() {
  const result = await getPlatformAuditLog({ page: 1, page_size: 25 });

  const initialData = result.success
    ? result.data
    : { items: [], total: 0, page: 1, page_size: 25 };

  return <AuditLogPage initialData={initialData} />;
}

export default function PlatformAuditLogPage() {
  return (
    <Suspense fallback={<AuditLogLoading />}>
      <AuditLogContent />
    </Suspense>
  );
}
