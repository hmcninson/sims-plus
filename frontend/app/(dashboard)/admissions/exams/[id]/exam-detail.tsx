"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExamResultsTable } from "@/components/admissions/exam-results-table";
import {
  ArrowLeft,
  Calendar,
  MapPin,
  Users,
  Clock,
  GraduationCap,
  Loader2,
} from "lucide-react";
import {
  getEntranceExamDetail,
  getExamRegistrations,
  getExamResults,
  markExamAttendance,
  recordExamResults,
} from "@/actions/admissions.action";
import type {
  EntranceExam,
  EntranceExamStatus,
  ExamRegistration,
  ExamResult,
  ExamResultEntry,
} from "@/types/admissions.type";

interface ExamDetailProps {
  examId: string;
}

const STATUS_CONFIG: Record<
  EntranceExamStatus,
  { label: string; className: string }
> = {
  scheduled: {
    label: "Scheduled",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  in_progress: {
    label: "In Progress",
    className:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  },
  completed: {
    label: "Completed",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
};

export function ExamDetail({ examId }: ExamDetailProps) {
  const router = useRouter();
  const [exam, setExam] = useState<EntranceExam | null>(null);
  const [registrations, setRegistrations] = useState<ExamRegistration[]>([]);
  const [results, setResults] = useState<ExamResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [markingAttendance, setMarkingAttendance] = useState<string | null>(
    null
  );

  const loadData = useCallback(async () => {
    const [examResult, regsResult, resultsResult] = await Promise.all([
      getEntranceExamDetail(examId),
      getExamRegistrations(examId),
      getExamResults(examId),
    ]);

    if (examResult.success && examResult.data) {
      setExam(examResult.data);
    }
    if (regsResult.success && regsResult.data) {
      setRegistrations(regsResult.data);
    }
    if (resultsResult.success && resultsResult.data) {
      setResults(resultsResult.data);
    }
    setLoading(false);
  }, [examId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function handleMarkAttendance(
    registrationId: string,
    attended: boolean
  ) {
    setMarkingAttendance(registrationId);
    try {
      const result = await markExamAttendance(examId, registrationId, attended);
      if (result.success) {
        toast.success(`Attendance ${attended ? "marked" : "unmarked"}`);
        // Update local state
        setRegistrations((prev) =>
          prev.map((r) =>
            r.id === registrationId ? { ...r, attended } : r
          )
        );
      } else {
        toast.error(result.error);
      }
    } finally {
      setMarkingAttendance(null);
    }
  }

  async function handleSaveResults(entries: ExamResultEntry[]) {
    const result = await recordExamResults(examId, entries);
    if (result.success) {
      toast.success("Results saved successfully");
      loadData();
    } else {
      toast.error(result.error);
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-[200px]" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  if (!exam) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 p-6">
        <GraduationCap className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">Exam session not found</p>
        <Button variant="outline" asChild>
          <Link href="/admissions/exams">Back to Exams</Link>
        </Button>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[exam.status];
  const attendedCount = registrations.filter((r) => r.attended).length;

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/admissions/exams")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold">{exam.name}</h1>
            <Badge variant="outline" className={statusConfig.className}>
              {statusConfig.label}
            </Badge>
          </div>
        </div>
      </div>

      {/* Exam Info Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <Calendar className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm font-medium">{formatDate(exam.exam_date)}</p>
            {exam.start_time && (
              <p className="text-xs text-muted-foreground">
                {exam.start_time}
                {exam.end_time && ` - ${exam.end_time}`}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <MapPin className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm font-medium">{exam.venue}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <Users className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm font-medium">
              {exam.registered_count ?? registrations.length} / {exam.capacity}
            </p>
            <p className="text-xs text-muted-foreground">Registered</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <Clock className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm font-medium">{attendedCount}</p>
            <p className="text-xs text-muted-foreground">Attended</p>
          </CardContent>
        </Card>
      </div>

      {exam.instructions && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Instructions</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{exam.instructions}</p>
          </CardContent>
        </Card>
      )}

      {/* Tabs: Registrations + Results */}
      <Tabs defaultValue="registrations">
        <TabsList>
          <TabsTrigger value="registrations">
            Registrations ({registrations.length})
          </TabsTrigger>
          <TabsTrigger value="results">
            Results ({results.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="registrations" className="mt-4">
          <Card>
            <CardContent className="p-0">
              {registrations.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <Users className="h-10 w-10 text-muted-foreground" />
                  <p className="text-sm font-medium">No registrations yet</p>
                  <p className="text-sm text-muted-foreground">
                    Applicants will appear here when registered for this exam
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Applicant</TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Seat #
                        </TableHead>
                        <TableHead className="w-[100px]">Attended</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {registrations.map((reg) => (
                        <TableRow key={reg.id}>
                          <TableCell className="font-medium">
                            {reg.applicant_name || "Unknown"}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                            {reg.seat_number || "-"}
                          </TableCell>
                          <TableCell>
                            {markingAttendance === reg.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Checkbox
                                checked={reg.attended}
                                onCheckedChange={(checked) =>
                                  handleMarkAttendance(
                                    reg.id,
                                    Boolean(checked)
                                  )
                                }
                              />
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="results" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Score Entry</CardTitle>
            </CardHeader>
            <CardContent>
              <ExamResultsTable
                examId={examId}
                results={results}
                editable={exam.status !== "cancelled"}
                onSave={handleSaveResults}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
