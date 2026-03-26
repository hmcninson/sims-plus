import { Suspense } from "react";
import Link from "next/link";
import { ChevronRight, Loader2 } from "lucide-react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

import { getStudent } from "@/actions/students.action";
import { getCurriculumProfiles } from "@/actions/curriculum.action";
import { TranscriptPageClient } from "./transcript-page-client";

export const metadata = {
  title: "Student Transcript",
  description: "View and print student academic transcript.",
};

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function Page({ params }: PageProps) {
  const { id } = await params;

  const [studentResult, profilesResult] = await Promise.all([
    getStudent(id),
    getCurriculumProfiles(),
  ]);

  if (!studentResult.success || !studentResult.data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <p className="text-lg font-semibold">Student not found</p>
        <p className="text-sm text-muted-foreground">
          {studentResult.success ? "No data returned." : studentResult.error}
        </p>
      </div>
    );
  }

  const student = studentResult.data;
  const profiles = profilesResult.success ? profilesResult.data ?? [] : [];
  const creditProfiles = profiles.filter((p) => p.use_credits);

  const studentName = `${student.first_name} ${student.last_name}`;

  return (
    <div className="space-y-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href="/students">Students</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator>
            <ChevronRight className="size-4" />
          </BreadcrumbSeparator>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link href={`/students/${id}`}>{studentName}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator>
            <ChevronRight className="size-4" />
          </BreadcrumbSeparator>
          <BreadcrumbItem>
            <BreadcrumbPage>Transcript</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <TranscriptPageClient
          studentId={id}
          studentName={studentName}
          creditProfiles={creditProfiles}
        />
      </Suspense>
    </div>
  );
}
