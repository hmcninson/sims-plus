import { Suspense } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { getCurriculumProfile } from "@/actions/curriculum.action";
import { AssessmentEditorPage } from "./assessment-editor";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getCurriculumProfile(id);
  return {
    title: result.success
      ? `Assessment - ${result.data.name}`
      : "Assessment Editor",
  };
}

function LoadingSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-72" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-64 w-full" />
      </CardContent>
    </Card>
  );
}

async function AssessmentContent({ id }: { id: string }) {
  const result = await getCurriculumProfile(id);

  if (!result.success) {
    notFound();
  }

  return <AssessmentEditorPage profile={result.data} />;
}

export default async function AssessmentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/settings/curriculum/profiles/${id}`}>
            <ChevronLeft className="h-4 w-4" />
            <span className="sr-only">Back to profile</span>
          </Link>
        </Button>
        <div>
          <h2 className="text-xl font-semibold">Assessment Structure</h2>
          <p className="text-sm text-muted-foreground">
            Edit the assessment components and their weights.
          </p>
        </div>
      </div>

      <Suspense fallback={<LoadingSkeleton />}>
        <AssessmentContent id={id} />
      </Suspense>
    </div>
  );
}
