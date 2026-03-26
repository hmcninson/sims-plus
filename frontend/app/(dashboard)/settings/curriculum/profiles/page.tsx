import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getCurriculumProfiles } from "@/actions/curriculum.action";
import { ProfileList } from "./profile-list";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Curriculum Profiles",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-9 w-32" />
      </div>
      <Card>
        <CardHeader>
          <div className="flex gap-4">
            <Skeleton className="h-9 flex-1" />
            <Skeleton className="h-9 w-[150px]" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

async function ProfileListContent() {
  const result = await getCurriculumProfiles();

  return (
    <ProfileList
      initialProfiles={result.success ? result.data : []}
      error={result.success ? undefined : result.error}
    />
  );
}

export default function CurriculumProfilesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <ProfileListContent />
    </Suspense>
  );
}
