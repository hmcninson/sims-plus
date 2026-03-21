import { Suspense } from "react";
import { getCachedSchoolProfile } from "@/actions/school.action";
import { SchoolProfileForm } from "./school-profile-form";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

// Force dynamic rendering to ensure fresh data on each request
export const dynamic = "force-dynamic";

export const metadata = {
  title: "School Profile",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <Skeleton className="h-24 w-24 rounded-lg" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-9 w-28" />
            </div>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-56" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

async function SchoolProfileContent() {
  const result = await getCachedSchoolProfile();

  if (!result.success || !result.data) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4">
        <p className="text-destructive">
          Failed to load school profile: {result.error || "Unknown error"}
        </p>
        <p className="text-sm text-muted-foreground mt-2">
          Debug: success={String(result.success)}, data={result.data ? "present" : "missing"}
        </p>
      </div>
    );
  }

  return <SchoolProfileForm initialData={result.data} />;
}

export default function SchoolSettingsPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <SchoolProfileContent />
    </Suspense>
  );
}
