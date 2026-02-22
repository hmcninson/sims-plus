import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, User, GraduationCap, Calendar } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { getTermReport } from "@/actions/exams.action";
import { EditRemarksForm } from "./edit-remarks-form";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function EditReportCardPage({ params }: PageProps) {
  const { id } = await params;
  const result = await getTermReport(id);

  if (!result.success || !result.data) {
    notFound();
  }

  const report = result.data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/exams/report-cards/${id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Edit Report Card Remarks
          </h1>
          <p className="text-muted-foreground">
            {report.academic_year_name} - {report.term_name}
          </p>
        </div>
      </div>

      {/* Student Info */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                <User className="h-6 w-6 text-muted-foreground" />
              </div>
              <div>
                <CardTitle>{report.student_name}</CardTitle>
                <CardDescription>{report.student_id_number}</CardDescription>
              </div>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <GraduationCap className="h-4 w-4" />
                <span>{report.class_name}</span>
                {report.section_name && <span>({report.section_name})</span>}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <Calendar className="h-4 w-4" />
                <span>{report.term_name}</span>
              </div>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Edit Form */}
      <EditRemarksForm
        reportId={id}
        initialData={{
          class_teacher_remark: report.class_teacher_remark || "",
          headmaster_remark: report.headmaster_remark || "",
          conduct_grade: report.conduct_grade || "",
          interest: report.interest || "",
        }}
      />
    </div>
  );
}
