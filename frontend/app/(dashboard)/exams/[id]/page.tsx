import { Suspense } from "react";
import { notFound } from "next/navigation";
import Link from "next/link";
import { format } from "date-fns";
import {
  ArrowLeft,
  ClipboardList,
  BarChart3,
  Loader2,
  PieChart,
  Calendar,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { getExam, getExamSubjects } from "@/actions/exams.action";
import type { ExamType, ExamStatus } from "@/types";
import { AddSubjectsDialog } from "./add-subjects-dialog";
import { ExamSubjects } from "./exam-subjects";

interface PageProps {
  params: Promise<{ id: string }>;
}

const EXAM_TYPE_CONFIG: Record<ExamType, { label: string; color: string }> = {
  quiz: { label: "Quiz", color: "bg-purple-500" },
  midterm: { label: "Mid-Term", color: "bg-blue-500" },
  end_term: { label: "End of Term", color: "bg-green-500" },
  mock: { label: "Mock", color: "bg-amber-500" },
  practical: { label: "Practical", color: "bg-cyan-500" },
  project: { label: "Project", color: "bg-rose-500" },
};

const EXAM_STATUS_CONFIG: Record<ExamStatus, { label: string; color: string }> = {
  draft: { label: "Draft", color: "bg-gray-500" },
  scheduled: { label: "Scheduled", color: "bg-blue-500" },
  ongoing: { label: "Ongoing", color: "bg-amber-500" },
  completed: { label: "Completed", color: "bg-green-500" },
  results_published: { label: "Published", color: "bg-green-700" },
  cancelled: { label: "Cancelled", color: "bg-red-500" },
};

export default async function ExamDetailPage({ params }: PageProps) {
  const { id } = await params;

  const [examResult, subjectsResult] = await Promise.all([
    getExam(id),
    getExamSubjects(id),
  ]);

  if (!examResult.success || !examResult.data) {
    notFound();
  }

  const exam = examResult.data;
  const subjects = subjectsResult.success ? subjectsResult.data || [] : [];

  return (
    <Suspense
      fallback={
        <div className="flex h-96 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link href="/exams">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight">{exam.name}</h1>
              <Badge className={`${EXAM_TYPE_CONFIG[exam.exam_type]?.color} text-white`}>
                {EXAM_TYPE_CONFIG[exam.exam_type]?.label}
              </Badge>
              <Badge className={`${EXAM_STATUS_CONFIG[exam.status]?.color} text-white`}>
                {EXAM_STATUS_CONFIG[exam.status]?.label}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              {exam.academic_year_name} - {exam.term_name}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <AddSubjectsDialog examId={id} variant="outline" />
            <Link href={`/exams/${id}/timetable`}>
              <Button variant="outline">
                <Calendar className="mr-2 h-4 w-4" />
                Timetable
              </Button>
            </Link>
            <Link href={`/exams/${id}/scores`}>
              <Button variant="outline">
                <ClipboardList className="mr-2 h-4 w-4" />
                Enter Scores
              </Button>
            </Link>
            <Link href={`/exams/${id}/analytics`}>
              <Button variant="outline">
                <PieChart className="mr-2 h-4 w-4" />
                Analytics
              </Button>
            </Link>
            <Link href={`/exams/${id}/results`}>
              <Button>
                <BarChart3 className="mr-2 h-4 w-4" />
                View Results
              </Button>
            </Link>
          </div>
        </div>

        {/* Exam Details */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Start Date</CardDescription>
              <CardTitle className="text-lg">
                {exam.start_date
                  ? format(new Date(exam.start_date), "MMMM d, yyyy")
                  : "Not set"}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>End Date</CardDescription>
              <CardTitle className="text-lg">
                {exam.end_date
                  ? format(new Date(exam.end_date), "MMMM d, yyyy")
                  : "Not set"}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Subjects</CardDescription>
              <CardTitle className="text-lg">{subjects.length}</CardTitle>
            </CardHeader>
          </Card>
        </div>

        {exam.description && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">{exam.description}</p>
            </CardContent>
          </Card>
        )}

        {/* Subjects by Class */}
        <ExamSubjects examId={id} subjects={subjects} />
      </div>
    </Suspense>
  );
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  const result = await getExam(id);
  const examName = result.success && result.data ? result.data.name : "Exam";
  return {
    title: `${examName}`,
    description: `View details for ${examName}`,
  };
}
