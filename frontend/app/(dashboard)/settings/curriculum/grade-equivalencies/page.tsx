import { Suspense } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { GradeEquivalencyMatrix } from "@/components/curriculum/GradeEquivalencyMatrix";
import { getGradingScales } from "@/actions/academic.action";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Grade Equivalencies",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Skeleton className="h-9 flex-1" />
            <Skeleton className="h-9 flex-1" />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

async function GradeEquivalencyContent() {
  const result = await getGradingScales();
  const scales = result.success ? result.data : [];

  return <GradeEquivalencyMatrix initialScales={scales} />;
}

export default function GradeEquivalenciesPage() {
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
          <h2 className="text-xl font-semibold">Grade Equivalencies</h2>
          <p className="text-sm text-muted-foreground">
            Map grades between different grading scales for cross-curriculum comparisons.
          </p>
        </div>
      </div>

      <Suspense fallback={<LoadingSkeleton />}>
        <GradeEquivalencyContent />
      </Suspense>
    </div>
  );
}
