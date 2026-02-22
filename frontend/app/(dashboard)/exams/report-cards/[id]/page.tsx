import { notFound } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  User,
  Calendar,
  GraduationCap,
  Trophy,
  Medal,
  Award,
  BarChart3,
  Clock,
  CheckCircle,
  Pencil,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { getTermReport } from "@/actions/exams.action";
import { getAssessmentWeights } from "@/actions/academic.action";
import { PrintButton } from "./print-button";

interface PageProps {
  params: Promise<{ id: string }>;
}

const POSITION_ICONS: Record<number, { icon: React.ElementType; color: string }> = {
  1: { icon: Trophy, color: "text-yellow-500" },
  2: { icon: Medal, color: "text-gray-400" },
  3: { icon: Award, color: "text-amber-600" },
};

export default async function ReportCardDetailPage({ params }: PageProps) {
  const { id } = await params;
  const [result, weightsResult] = await Promise.all([
    getTermReport(id),
    getAssessmentWeights(),
  ]);

  if (!result.success || !result.data) {
    notFound();
  }

  const report = result.data;

  // Get configured weights or use defaults
  const caWeight = weightsResult.success && weightsResult.data?.ca_total_weight
    ? Number(weightsResult.data.ca_total_weight)
    : 50;
  const examWeight = weightsResult.success && weightsResult.data?.exam_total_weight
    ? Number(weightsResult.data.exam_total_weight)
    : 50;

  const getPositionBadge = (position: number | undefined) => {
    if (!position) return "-";
    const config = POSITION_ICONS[position];
    if (config) {
      const Icon = config.icon;
      return (
        <div className="flex items-center gap-1">
          <Icon className={`h-5 w-5 ${config.color}`} />
          <span className="font-bold text-lg">{position}</span>
        </div>
      );
    }
    return <span className="font-bold text-lg">{position}</span>;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/exams/report-cards">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Report Card
            </h1>
            <p className="text-muted-foreground">
              {report.academic_year_name} - {report.term_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            className={`${
              report.is_published ? "bg-green-500" : "bg-gray-500"
            } text-white`}
          >
            {report.is_published ? (
              <><CheckCircle className="mr-1 h-3 w-3" /> Published</>
            ) : (
              <><Clock className="mr-1 h-3 w-3" /> Draft</>
            )}
          </Badge>
          <Link href={`/exams/report-cards/${id}/edit`}>
            <Button variant="outline">
              <Pencil className="mr-2 h-4 w-4" />
              Edit Remarks
            </Button>
          </Link>
          <PrintButton reportId={id} />
        </div>
      </div>

      {/* Student Info */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full bg-muted flex items-center justify-center">
                <User className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <CardTitle className="text-xl">{report.student_name}</CardTitle>
                <CardDescription className="text-base">
                  {report.student_id_number}
                </CardDescription>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 text-muted-foreground">
                <GraduationCap className="h-4 w-4" />
                <span>{report.class_name}</span>
                {report.section_name && (
                  <span className="text-muted-foreground">({report.section_name})</span>
                )}
              </div>
              <div className="flex items-center gap-2 text-muted-foreground mt-1">
                <Calendar className="h-4 w-4" />
                <span>{report.term_name}, {report.academic_year_name}</span>
              </div>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Summary Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Score</CardDescription>
            <CardTitle className="text-3xl">
              {Number(report.total_score || 0).toFixed(0)}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Average</CardDescription>
            <CardTitle className="text-3xl flex items-center gap-2">
              <Badge
                variant={
                  Number(report.average_score) >= 70
                    ? "default"
                    : Number(report.average_score) >= 50
                    ? "secondary"
                    : "destructive"
                }
                className="text-lg px-3 py-1"
              >
                {Number(report.average_score || 0).toFixed(1)}%
              </Badge>
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Class Position</CardDescription>
            <CardTitle className="text-3xl flex items-center gap-2">
              {getPositionBadge(report.class_position)}
              <span className="text-sm font-normal text-muted-foreground">
                / {report.class_size || "-"}
              </span>
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Attendance</CardDescription>
            <CardTitle className="text-3xl">
              {report.attendance_percentage
                ? `${Number(report.attendance_percentage).toFixed(0)}%`
                : "-"}
              <span className="text-sm font-normal text-muted-foreground ml-2">
                ({report.days_present || 0}/{report.total_school_days || 0} days)
              </span>
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Subject Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Subject Results
          </CardTitle>
          <CardDescription>
            {report.subjects_count || 0} subjects
          </CardDescription>
        </CardHeader>
        <CardContent>
          {report.subject_results && report.subject_results.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject</TableHead>
                  <TableHead className="text-center">Class Score ({caWeight}%)</TableHead>
                  <TableHead className="text-center">Exams Score ({examWeight}%)</TableHead>
                  <TableHead className="text-center">Total (100%)</TableHead>
                  <TableHead className="text-center">Grade</TableHead>
                  <TableHead className="text-center">Position</TableHead>
                  <TableHead>Remark</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {report.subject_results.map((subject) => (
                  <TableRow key={subject.subject_id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{subject.subject_name}</p>
                        {subject.subject_code && (
                          <p className="text-sm text-muted-foreground">
                            {subject.subject_code}
                          </p>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      {subject.class_score !== undefined
                        ? Number(subject.class_score).toFixed(1)
                        : "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      {subject.exams_score !== undefined
                        ? Number(subject.exams_score).toFixed(1)
                        : "-"}
                    </TableCell>
                    <TableCell className="text-center font-semibold">
                      {subject.total_score !== undefined
                        ? Number(subject.total_score).toFixed(1)
                        : "-"}
                    </TableCell>
                    <TableCell className="text-center">
                      {subject.grade ? (
                        <Badge variant="outline">{subject.grade}</Badge>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      {subject.subject_position || "-"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {subject.grade_remark || subject.teacher_remark || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-12">
              <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No subject results</h3>
              <p className="text-muted-foreground">
                Subject scores have not been entered for this term yet.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Remarks */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Class Teacher's Remark</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {report.class_teacher_remark || "No remark entered."}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Headmaster's Remark</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {report.headmaster_remark || "No remark entered."}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Additional Info */}
      {(report.conduct_grade || report.interest) && (
        <div className="grid gap-4 md:grid-cols-2">
          {report.conduct_grade && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Conduct</CardTitle>
              </CardHeader>
              <CardContent>
                <Badge variant="outline" className="text-base">
                  {report.conduct_grade}
                </Badge>
              </CardContent>
            </Card>
          )}
          {report.interest && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Interest / Activities</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground">{report.interest}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
