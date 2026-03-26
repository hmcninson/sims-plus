import { Suspense } from "react";
import Link from "next/link";
import {
  BookOpen,
  Plus,
  Layers,
  Star,
  AlertCircle,
  ArrowRightLeft,
  Link2,
} from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getCurriculumProfiles } from "@/actions/curriculum.action";
import type { CurriculumType } from "@/types/curriculum.type";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Curriculum Settings",
};

const CURRICULUM_TYPE_LABELS: Record<CurriculumType, string> = {
  ges: "GES",
  cambridge: "Cambridge",
  edexcel: "Edexcel",
  american: "American",
  ib: "IB",
  french: "French",
  montessori: "Montessori",
  custom: "Custom",
};

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
            </CardHeader>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    </div>
  );
}

async function CurriculumOverviewContent() {
  const result = await getCurriculumProfiles();

  if (!result.success) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/50 bg-destructive/10 p-8 gap-3">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-destructive">{result.error}</p>
      </div>
    );
  }

  const profiles = result.data;
  const activeProfiles = profiles.filter((p) => p.is_active);
  const defaultProfile = profiles.find((p) => p.is_default);
  const totalComponents = profiles.reduce(
    (sum, _p) => sum, // Components come from detail endpoint, show count of profiles
    0,
  );

  if (profiles.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
          <BookOpen className="h-12 w-12 text-muted-foreground" />
          <div className="text-center">
            <h3 className="text-lg font-semibold">
              No Curriculum Profiles Yet
            </h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Create a curriculum profile to define how your school handles
              grading, assessment, and report cards. Start from a template or
              build from scratch.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3">
            <Button asChild>
              <Link href="/settings/curriculum/profiles/new">
                <Plus className="mr-2 h-4 w-4" />
                Create from Template
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Layers className="h-4 w-4" />
              Curriculum Profiles
            </CardDescription>
            <CardTitle className="text-3xl">{profiles.length}</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {activeProfiles.length} active
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <Star className="h-4 w-4" />
              Default Profile
            </CardDescription>
            <CardTitle className="text-lg truncate">
              {defaultProfile?.name || "Not set"}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            {defaultProfile && (
              <Badge variant="secondary" className="text-xs">
                {CURRICULUM_TYPE_LABELS[defaultProfile.curriculum_type]}
              </Badge>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Curriculum Types
            </CardDescription>
            <CardTitle className="text-3xl">
              {new Set(profiles.map((p) => p.curriculum_type)).size}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-xs text-muted-foreground">
              {totalComponents} profiles configured
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick links */}
      <Card>
        <CardHeader>
          <CardTitle>Manage Curriculum</CardTitle>
          <CardDescription>
            Configure curriculum profiles, assessment structures, and report card
            settings for your school.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-3">
            <Button variant="outline" className="justify-start h-auto py-3" asChild>
              <Link href="/settings/curriculum/profiles">
                <Layers className="mr-3 h-5 w-5 text-muted-foreground" />
                <div className="text-left">
                  <p className="font-medium">All Profiles</p>
                  <p className="text-xs text-muted-foreground">
                    View and manage all curriculum profiles
                  </p>
                </div>
              </Link>
            </Button>
            <Button variant="outline" className="justify-start h-auto py-3" asChild>
              <Link href="/settings/curriculum/profiles/new">
                <Plus className="mr-3 h-5 w-5 text-muted-foreground" />
                <div className="text-left">
                  <p className="font-medium">Create Profile</p>
                  <p className="text-xs text-muted-foreground">
                    Set up a new curriculum profile
                  </p>
                </div>
              </Link>
            </Button>
            <Button variant="outline" className="justify-start h-auto py-3" asChild>
              <Link href="/settings/curriculum/grade-equivalencies">
                <ArrowRightLeft className="mr-3 h-5 w-5 text-muted-foreground" />
                <div className="text-left">
                  <p className="font-medium">Grade Equivalencies</p>
                  <p className="text-xs text-muted-foreground">
                    Map grades between grading scales
                  </p>
                </div>
              </Link>
            </Button>
            <Button variant="outline" className="justify-start h-auto py-3" asChild>
              <Link href="/settings/curriculum/subject-mappings">
                <Link2 className="mr-3 h-5 w-5 text-muted-foreground" />
                <div className="text-left">
                  <p className="font-medium">Subject Mappings</p>
                  <p className="text-xs text-muted-foreground">
                    Map subjects to external curricula
                  </p>
                </div>
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Recent profiles */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Profiles</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {activeProfiles.map((profile) => (
              <Link
                key={profile.id}
                href={`/settings/curriculum/profiles/${profile.id}`}
                className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div>
                    <p className="text-sm font-medium">{profile.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {profile.academic_calendar_type} &middot;{" "}
                      {profile.score_display_mode.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {CURRICULUM_TYPE_LABELS[profile.curriculum_type]}
                  </Badge>
                  {profile.is_default && (
                    <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                  )}
                </div>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function CurriculumSettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Curriculum</h2>
          <p className="text-sm text-muted-foreground">
            Manage curriculum profiles, assessment structures, and grading
            configurations.
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/settings/curriculum/profiles/new">
            <Plus className="mr-2 h-4 w-4" />
            New Profile
          </Link>
        </Button>
      </div>

      <Suspense fallback={<LoadingSkeleton />}>
        <CurriculumOverviewContent />
      </Suspense>
    </div>
  );
}
