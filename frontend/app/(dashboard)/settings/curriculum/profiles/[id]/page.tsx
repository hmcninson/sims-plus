import { cache } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getCurriculumProfile } from "@/actions/curriculum.action";
import { ProfileDetail } from "./profile-detail";

// Deduplicate the fetch within a single request so generateMetadata
// and the page component share one result (avoids Turbopack perf.measure error)
const getProfile = cache(async (id: string) => {
  return getCurriculumProfile(id);
});

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getProfile(id);
  return {
    title: result.success ? result.data.name : "Profile Detail",
  };
}

export default async function CurriculumProfileDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await getProfile(id);

  if (!result.success) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings/curriculum/profiles">
            <ChevronLeft className="h-4 w-4" />
            <span className="sr-only">Back to profiles</span>
          </Link>
        </Button>
        <div>
          <h2 className="text-xl font-semibold">Profile Detail</h2>
          <p className="text-sm text-muted-foreground">
            View and edit curriculum profile settings.
          </p>
        </div>
      </div>

      <ProfileDetail profile={result.data} />
    </div>
  );
}
