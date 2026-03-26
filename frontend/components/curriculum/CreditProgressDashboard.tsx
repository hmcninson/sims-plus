"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Loader2,
  TrendingUp,
  GraduationCap,
  Award,
  Download,
  FileText,
  RefreshCw,
  Star,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  getStudentCredits,
  getStudentGPA,
  getStudentTranscript,
  recalculateStudentCredits,
} from "@/actions/curriculum.action";
import type {
  CreditRecord,
  StudentGPA,
  TranscriptData,
} from "@/types/curriculum.type";

interface CreditProgressDashboardProps {
  studentId: string;
  profileId: string;
  isAdmin?: boolean;
}

function getGpaColor(gpa: number): string {
  if (gpa >= 3.5) return "text-green-700 dark:text-green-400";
  if (gpa >= 2.5) return "text-amber-700 dark:text-amber-400";
  return "text-red-700 dark:text-red-400";
}

export function CreditProgressDashboard({
  studentId,
  profileId,
  isAdmin = false,
}: CreditProgressDashboardProps) {
  const router = useRouter();
  const [creditRecords, setCreditRecords] = useState<CreditRecord[]>([]);
  const [gpa, setGpa] = useState<StudentGPA | null>(null);
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRecalculating, setIsRecalculating] = useState(false);

  useEffect(() => {
    async function load() {
      setIsLoading(true);
      try {
        const [creditsRes, gpaRes, transcriptRes] = await Promise.all([
          getStudentCredits(studentId, profileId),
          getStudentGPA(studentId, profileId),
          getStudentTranscript(studentId, profileId),
        ]);
        if (creditsRes.success) setCreditRecords(creditsRes.data.items);
        if (gpaRes.success) setGpa(gpaRes.data);
        if (transcriptRes.success) setTranscript(transcriptRes.data);
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [studentId, profileId]);

  async function handleRecalculate() {
    setIsRecalculating(true);
    const result = await recalculateStudentCredits(studentId, profileId);
    if (result.success) {
      toast.success(`Credits recalculated: ${result.data.records_updated} records updated`);
      // Reload data
      const [creditsRes, gpaRes] = await Promise.all([
        getStudentCredits(studentId, profileId),
        getStudentGPA(studentId, profileId),
      ]);
      if (creditsRes.success) setCreditRecords(creditsRes.data.items);
      if (gpaRes.success) setGpa(gpaRes.data);
    } else {
      toast.error(result.error);
    }
    setIsRecalculating(false);
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Build GPA trend data from transcript academic records
  const gpaTrendData =
    transcript?.academic_records.map((term) => ({
      name: `${term.academic_year}${term.term ? ` ${term.term}` : ""}`,
      gpa: term.term_gpa ?? 0,
    })) ?? [];

  // Group credits by academic year
  const creditsByYear = new Map<string, CreditRecord[]>();
  for (const record of creditRecords) {
    const yearKey = record.academic_year_id;
    if (!creditsByYear.has(yearKey)) {
      creditsByYear.set(yearKey, []);
    }
    creditsByYear.get(yearKey)!.push(record);
  }

  const creditsEarned = gpa?.total_credits_earned ?? 0;
  const graduationRequired = transcript?.graduation_credits_required;
  const creditProgress = graduationRequired
    ? Math.min(100, (creditsEarned / graduationRequired) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="flex flex-wrap gap-2 justify-end">
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/students/${studentId}/transcript`)}
        >
          <FileText className="mr-2 size-4" />
          View Transcript
        </Button>
        {isAdmin && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRecalculate}
            disabled={isRecalculating}
          >
            {isRecalculating ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 size-4" />
            )}
            Recalculate
          </Button>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cumulative GPA</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-3xl font-bold ${gpa?.cumulative_gpa != null ? getGpaColor(gpa.cumulative_gpa) : ""}`}>
              {gpa?.cumulative_gpa != null ? gpa.cumulative_gpa.toFixed(2) : "--"}
            </p>
            <p className="text-xs text-muted-foreground">4.0 scale</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Weighted GPA</CardTitle>
            <Star className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className={`text-3xl font-bold ${gpa?.cumulative_weighted_gpa != null ? getGpaColor(gpa.cumulative_weighted_gpa) : ""}`}>
              {gpa?.cumulative_weighted_gpa != null
                ? gpa.cumulative_weighted_gpa.toFixed(2)
                : "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {gpa?.cumulative_weighted_gpa != null ? "Includes AP/Honors" : "N/A"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Credits Earned</CardTitle>
            <GraduationCap className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {creditsEarned}
              {graduationRequired != null && (
                <span className="text-base text-muted-foreground font-normal">
                  /{graduationRequired}
                </span>
              )}
            </p>
            {graduationRequired != null && (
              <Progress value={creditProgress} className="mt-2 h-2" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Honor Roll</CardTitle>
            <Award className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {gpa?.honor_roll ? (
              <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 text-lg px-3 py-1">
                Honor Roll
              </Badge>
            ) : (
              <p className="text-3xl font-bold text-muted-foreground">&mdash;</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* GPA Trend Chart */}
      {gpaTrendData.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">GPA Trend</CardTitle>
            <CardDescription>GPA progression across terms</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={gpaTrendData}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="name"
                    className="text-xs"
                    tick={{ fontSize: 11 }}
                  />
                  <YAxis domain={[0, 4]} className="text-xs" tick={{ fontSize: 11 }} />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="text-sm font-medium">{label}</p>
                          {payload.map((p) => (
                            <p key={p.dataKey as string} className="text-sm" style={{ color: p.color }}>
                              {p.name}: {(p.value as number).toFixed(2)}
                            </p>
                          ))}
                        </div>
                      );
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="gpa"
                    name="GPA"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={{ r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Credit Breakdown Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Credit Breakdown</CardTitle>
          <CardDescription>
            Detailed record of credits attempted and earned
          </CardDescription>
        </CardHeader>
        <CardContent>
          {creditsByYear.size === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <GraduationCap className="mb-2 size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No credit records found.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Academic Year</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead className="text-right">Attempted</TableHead>
                    <TableHead className="text-right">Earned</TableHead>
                    <TableHead className="hidden sm:table-cell text-right">Grade Pts</TableHead>
                    <TableHead className="hidden md:table-cell">Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.from(creditsByYear.entries()).map(([year, records]) => (
                    <>
                      {records.map((record: CreditRecord) => (
                        <TableRow key={record.id}>
                          <TableCell className="text-sm">{year.slice(0, 8)}</TableCell>
                          <TableCell className="font-medium text-sm">
                            {record.subject_id.slice(0, 8)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {record.credits_attempted}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {record.credits_earned}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell text-right font-mono text-sm">
                            {record.grade_points?.toFixed(1) ?? "--"}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            {record.is_ap && (
                              <Badge variant="secondary" className="mr-1 bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200 text-[10px]">
                                AP
                              </Badge>
                            )}
                            {record.is_honors && (
                              <Badge variant="secondary" className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200 text-[10px]">
                                Honors
                              </Badge>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                      {/* Subtotal row */}
                      <TableRow className="bg-muted/50 font-medium">
                        <TableCell colSpan={2} className="text-sm">
                          Year Total
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {records.reduce((sum: number, r: CreditRecord) => sum + r.credits_attempted, 0)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {records.reduce((sum: number, r: CreditRecord) => sum + r.credits_earned, 0)}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell" />
                        <TableCell className="hidden md:table-cell" />
                      </TableRow>
                    </>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
