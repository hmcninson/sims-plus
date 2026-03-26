import { Suspense } from "react";
import Link from "next/link";
import { ChevronLeft, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SubjectMappingTable } from "@/components/curriculum/SubjectMappingTable";
import { getCurriculumProfiles } from "@/actions/curriculum.action";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Subject Mappings",
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
            <Skeleton className="h-9 w-[200px]" />
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

async function SubjectMappingContent() {
  const result = await getCurriculumProfiles();

  if (!result.success) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/50 bg-destructive/10 p-8 gap-3">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-destructive">{result.error}</p>
      </div>
    );
  }

  const activeProfiles = result.data.filter((p) => p.is_active);

  if (activeProfiles.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          <AlertCircle className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground text-center">
            You need at least one active curriculum profile before mapping subjects.
            <br />
            Create a profile first in Curriculum Settings.
          </p>
          <Button asChild size="sm" variant="outline">
            <Link href="/settings/curriculum/profiles/new">Create Profile</Link>
          </Button>
        </CardContent>
      </Card>
    );
  }

  return <SubjectMappingTable profiles={activeProfiles} />;
}

export default function SubjectMappingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings/curriculum">
            <ChevronLeft className="h-4 w-4" />
            <span className="sr-only">Back</span>
          </Link>
        </Button>
        <div>
          <h2 className="text-xl font-semibold">Subject Mappings</h2>
          <p className="text-sm text-muted-foreground">
            Map school subjects to external curriculum standards and codes.
          </p>
        </div>
      </div>

      <Suspense fallback={<LoadingSkeleton />}>
        <SubjectMappingContent />
      </Suspense>
    </div>
  );
}
