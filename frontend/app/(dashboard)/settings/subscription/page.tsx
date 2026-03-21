import { Suspense } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { getSubscriptionStatus } from "@/actions/subscription.action";
import { SubscriptionPage } from "./subscription-page";

export default async function SubscriptionSettingsPage() {
  const result = await getSubscriptionStatus();

  const status = result.success ? result.data : null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Subscription</h2>
        <p className="text-sm text-muted-foreground">
          Manage your plan, billing, and add-ons.
        </p>
      </div>
      <Suspense
        fallback={
          <div className="space-y-4">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        }
      >
        <SubscriptionPage initialStatus={status} />
      </Suspense>
    </div>
  );
}
