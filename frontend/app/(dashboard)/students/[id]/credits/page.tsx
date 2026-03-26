import { Suspense } from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
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
import { CreditsPageClient } from "./credits-page-client";

export const metadata = {
  title: "Credits & GPA",
  description: "View student credit accumulation and GPA progress.",
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
  const creditProfiles = profiles.filter((p) => p.use_credits || p.use_gpa);

  // If no applicable profile, redirect to student detail
  if (creditProfiles.length === 0) {
    redirect(`/students/${id}`);
  }

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
            <BreadcrumbPage>Credits & GPA</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Credits & GPA &mdash; {studentName}
        </h1>
        <p className="text-sm text-muted-foreground">
          Credit accumulation and GPA progress dashboard
        </p>
      </div>

      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        }
      >
        <CreditsPageClient
          studentId={id}
          creditProfiles={creditProfiles}
        />
      </Suspense>
    </div>
  );
}
