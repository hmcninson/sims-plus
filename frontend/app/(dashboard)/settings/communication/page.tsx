import { Suspense } from "react";
import { getCommunicationSettings } from "@/actions/communication.action";
import { CommunicationSettingsForm } from "./communication-settings-form";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

// Force dynamic rendering to ensure fresh data on each request
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Communication Settings | SIMS Plus",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      {/* SMS card skeleton */}
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-16 w-full rounded-lg" />
        </CardContent>
      </Card>
      {/* Email card skeleton */}
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full rounded-lg" />
          <div className="grid gap-4 sm:grid-cols-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
      {/* Notification card skeleton */}
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-52" />
          <Skeleton className="h-4 w-48" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-16 w-full rounded-lg" />
          <Skeleton className="h-16 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  );
}

async function CommunicationSettingsContent() {
  const result = await getCommunicationSettings();

  if (!result.success) {
    // If the endpoint returns an error (e.g., 404 for a school that hasn't
    // configured settings yet), render the form with defaults so the user
    // can save their initial configuration.
    return <CommunicationSettingsForm />;
  }

  return <CommunicationSettingsForm initialData={result.data} />;
}

export default function CommunicationSettingsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <CommunicationSettingsContent />
    </Suspense>
  );
}
