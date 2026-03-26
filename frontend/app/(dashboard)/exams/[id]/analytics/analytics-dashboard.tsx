"use client";

import { useState, useTransition, useEffect } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  BarChart3,
  Users,
  Loader2,
  TrendingUp,
  TrendingDown,
  GraduationCap,
  Trophy,
  Medal,
  Award,
  CheckCircle2,
  XCircle,
  Minus,
  PieChart,
  Target,
  Layers,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart as RechartsPieChart,
  Pie,
  Legend,
} from "recharts";

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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";

import {
  getClassStatistics,
  getSubjectStatistics,
  getSubjectRankings,
  type ClassStatistics,
  type SubjectStatistics,
  type SubjectRankings,
} from "@/actions/exams.action";
import type { ExamWithContext } from "@/types";

interface AnalyticsDashboardProps {
  exam: ExamWithContext;
  classes: { id: string; name: string; sections: { id: string; name: string }[] }[];
  subjects: { id: string; name: string; code?: string }[];
}

const GRADE_COLORS: Record<string, string> = {
  "A1": "#22c55e",
  "B2": "#84cc16",
  "B3": "#a3e635",
  "C4": "#facc15",
  "C5": "#fbbf24",
  "C6": "#f97316",
  "D7": "#fb923c",
  "E8": "#ef4444",
  "F9": "#dc2626",
  "A": "#22c55e",
  "B": "#84cc16",
  "C": "#facc15",
  "D": "#f97316",
  "F": "#ef4444",
};

const POSITION_ICONS: Record<number, { icon: React.ElementType; color: string }> = {
  1: { icon: Trophy, color: "text-yellow-500" },
  2: { icon: Medal, color: "text-gray-400" },
  3: { icon: Award, color: "text-amber-600" },
};

/**
 * Format a score value based on the score_display_mode from the analytics response.
 * Falls back to percentage format when no display mode is specified (backward compat).
 */
function formatAnalyticsScore(
  value: number | null | undefined,
  displayMode: string | undefined
): string {
  if (value == null) return "N/A";
  const num = Number(value);

  switch (displayMode) {
    case "gpa":
      return num.toFixed(2);
    case "level":
      return `Level ${Math.round(num)}`;
    case "grade_only":
    case "narrative":
    case "mention":
      return num.toFixed(1);
    case "percentage":
    case "grade_and_score":
    default:
      return `${num.toFixed(1)}%`;
  }
}

/**
 * Get the score unit label for display in charts/headers.
 */
function getScoreUnitLabel(displayMode: string | undefined): string {
  switch (displayMode) {
    case "gpa":
      return "GPA";
    case "level":
      return "Level";
    case "narrative":
      return "Score";
    case "mention":
      return "Average";
    default:
      return "%";
  }
}

export function AnalyticsDashboard({ exam, classes, subjects }: AnalyticsDashboardProps) {
  const [isPending, startTransition] = useTransition();

  // Selection state
  const [selectedClassId, setSelectedClassId] = useState(classes[0]?.id || "");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("all");
  const [selectedSubjectId, setSelectedSubjectId] = useState(subjects[0]?.id || "");

  // Data state
  const [classStats, setClassStats] = useState<ClassStatistics | null>(null);
  const [subjectStats, setSubjectStats] = useState<SubjectStatistics[]>([]);
  const [subjectRankings, setSubjectRankings] = useState<SubjectRankings | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Get sections for selected class
  const selectedClass = classes.find(c => c.id === selectedClassId);
  const sections = selectedClass?.sections || [];

  // Load class statistics when class or section changes
  useEffect(() => {
    if (selectedClassId) {
      loadClassStats();
      loadSubjectStats();
    }
  }, [selectedClassId, selectedSectionId]);

  // Reset section when class changes
  useEffect(() => {
    setSelectedSectionId("all");
  }, [selectedClassId]);

  // Load subject rankings when subject or section changes
  useEffect(() => {
    if (selectedSubjectId && selectedClassId) {
      loadSubjectRankings();
    }
  }, [selectedSubjectId, selectedClassId, selectedSectionId]);

  const loadClassStats = async () => {
    startTransition(async () => {
      setError(null);
      const sectionId = selectedSectionId === "all" ? undefined : selectedSectionId;
      const result = await getClassStatistics(exam.id, selectedClassId, sectionId);
      if (result.success && result.data) {
        setClassStats(result.data);
      } else {
        setError(result.error || "Failed to load class statistics");
        setClassStats(null);
      }
    });
  };

  const loadSubjectStats = async () => {
    startTransition(async () => {
      const sectionId = selectedSectionId === "all" ? undefined : selectedSectionId;
      const result = await getSubjectStatistics(exam.id, selectedClassId, sectionId);
      if (result.success && result.data) {
        setSubjectStats(result.data);
      } else {
        setSubjectStats([]);
      }
    });
  };

  const loadSubjectRankings = async () => {
    startTransition(async () => {
      const sectionId = selectedSectionId === "all" ? undefined : selectedSectionId;
      const result = await getSubjectRankings(exam.id, selectedSubjectId, selectedClassId, sectionId);
      if (result.success && result.data) {
        setSubjectRankings(result.data);
      } else {
        setSubjectRankings(null);
      }
    });
  };

  const getPositionBadge = (position: number) => {
    const config = POSITION_ICONS[position];
    if (config) {
      const Icon = config.icon;
      return (
        <div className="flex items-center gap-1">
          <Icon className={`h-4 w-4 ${config.color}`} />
          <span className="font-bold">{position}</span>
        </div>
      );
    }
    return <span className="font-medium">{position}</span>;
  };

  // Prepare chart data
  const gradeChartData = classStats?.grade_distribution.map((g) => ({
    name: g.grade,
    count: g.count,
    percentage: g.percentage,
    fill: GRADE_COLORS[g.grade] || "#94a3b8",
  })) || [];

  const passFailData: Array<{ name: string; value: number; fill: string }> = classStats ? [
    { name: "Passed", value: classStats.pass_fail.passed, fill: "#22c55e" },
    { name: "Failed", value: classStats.pass_fail.failed, fill: "#ef4444" },
    { name: "Absent", value: classStats.pass_fail.absent, fill: "#94a3b8" },
  ].filter(d => d.value > 0) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/exams/${exam.id}`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{exam.name} - Analytics</h1>
          <p className="text-muted-foreground">
            {exam.academic_year_name} - {exam.term_name}
          </p>
        </div>
      </div>

      {/* Class & Section Selection */}
      <div className="flex flex-wrap items-center gap-4 p-4 rounded-lg border bg-card">
        <div className="flex items-center gap-2">
          <GraduationCap className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-medium">Class:</span>
        </div>
        <Select value={selectedClassId} onValueChange={setSelectedClassId}>
          <SelectTrigger className="w-full sm:w-[200px]">
            <SelectValue placeholder="Select a class" />
          </SelectTrigger>
          <SelectContent>
            {classes.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {sections.length > 0 && (
          <>
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm font-medium">Section:</span>
            </div>
            <Select value={selectedSectionId} onValueChange={setSelectedSectionId}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="All sections" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sections</SelectItem>
                {sections.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )}

        <span className="text-sm text-muted-foreground ml-auto">
          {classes.length} classes available
        </span>
      </div>

      {/* Loading State */}
      {isPending && (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Error State */}
      {error && !isPending && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* No Classes */}
      {classes.length === 0 && !isPending && (
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="mx-auto h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No subjects added</h3>
            <p className="text-muted-foreground">
              Add subjects to this exam to view analytics.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Analytics Content */}
      {classStats && !isPending && (
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList>
            <TabsTrigger value="overview">
              <BarChart3 className="h-4 w-4 mr-2" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="subjects">
              <PieChart className="h-4 w-4 mr-2" />
              Subjects
            </TabsTrigger>
            <TabsTrigger value="rankings">
              <Trophy className="h-4 w-4 mr-2" />
              Rankings
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-6">
            {/* Summary Stats */}
            <div className="grid gap-4 md:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Total Students</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2">
                    <Users className="h-5 w-5 text-muted-foreground" />
                    {classStats.total_students}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Class Average</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2 text-blue-600">
                    <BarChart3 className="h-5 w-5" />
                    {formatAnalyticsScore(classStats.class_average, classStats.score_display_mode)}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Highest Score</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2 text-green-600">
                    <TrendingUp className="h-5 w-5" />
                    {formatAnalyticsScore(classStats.highest_score, classStats.score_display_mode)}
                  </CardTitle>
                </CardHeader>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardDescription>Lowest Score</CardDescription>
                  <CardTitle className="text-2xl flex items-center gap-2 text-red-600">
                    <TrendingDown className="h-5 w-5" />
                    {formatAnalyticsScore(classStats.lowest_score, classStats.score_display_mode)}
                  </CardTitle>
                </CardHeader>
              </Card>
            </div>

            {/* Pass/Fail Stats + Grade Distribution */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* Pass/Fail Stats — hidden for Montessori (narrative-based, no pass/fail) */}
              {classStats.pass_mark !== null && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Pass/Fail Statistics
                  </CardTitle>
                  {classStats.curriculum_type && classStats.curriculum_type !== "ges" && (
                    <p className="text-xs text-muted-foreground">
                      Pass mark: {formatAnalyticsScore(classStats.pass_mark, classStats.score_display_mode)}
                    </p>
                  )}
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-green-600">
                        <CheckCircle2 className="h-5 w-5" />
                        <span className="text-2xl font-bold">{classStats.pass_fail.passed}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">Passed</p>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-red-600">
                        <XCircle className="h-5 w-5" />
                        <span className="text-2xl font-bold">{classStats.pass_fail.failed}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">Failed</p>
                    </div>
                    <div className="text-center">
                      <div className="flex items-center justify-center gap-1 text-gray-500">
                        <Minus className="h-5 w-5" />
                        <span className="text-2xl font-bold">{classStats.pass_fail.absent}</span>
                      </div>
                      <p className="text-sm text-muted-foreground">Absent</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Pass Rate</span>
                      <span className="font-medium">{Number(classStats.pass_fail.pass_rate).toFixed(1)}%</span>
                    </div>
                    <Progress value={Number(classStats.pass_fail.pass_rate)} className="h-2" />
                  </div>
                  {passFailData.length > 0 && (
                    <div className="mt-4 h-[200px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <RechartsPieChart>
                          <Pie
                            data={passFailData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={40}
                            outerRadius={70}
                            label
                          >
                            {passFailData.map((entry, index) => (
                              <Cell key={index} fill={entry.fill} />
                            ))}
                          </Pie>
                          <Legend />
                          <Tooltip />
                        </RechartsPieChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </CardContent>
              </Card>
              )}

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Grade Distribution
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {gradeChartData.length > 0 ? (
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={gradeChartData}>
                          <CartesianGrid strokeDasharray="3 3" className="opacity-50" />
                          <XAxis dataKey="name" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                            {gradeChartData.map((entry, index) => (
                              <Cell key={index} fill={entry.fill} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="flex h-[300px] items-center justify-center">
                      <p className="text-muted-foreground">No grade data available</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Subjects Tab */}
          <TabsContent value="subjects" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Subject-wise Performance</CardTitle>
                <CardDescription>
                  Performance breakdown for each subject in {classStats.class_name}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {subjectStats.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Subject</TableHead>
                        <TableHead className="text-center">Students</TableHead>
                        <TableHead className="text-center">Average</TableHead>
                        <TableHead className="text-center">Highest</TableHead>
                        <TableHead className="text-center">Lowest</TableHead>
                        <TableHead className="text-center">Pass Rate</TableHead>
                        <TableHead className="text-center">Grades</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {subjectStats.map((subject) => (
                        <TableRow key={subject.subject_id}>
                          <TableCell>
                            <div>
                              <p className="font-medium">{subject.subject_name}</p>
                              {subject.subject_code && (
                                <p className="text-xs text-muted-foreground">
                                  {subject.subject_code}
                                </p>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            {subject.students_with_scores}/{subject.total_students}
                          </TableCell>
                          <TableCell className="text-center">
                            <Badge
                              variant={
                                Number(subject.average_score || 0) >= 70
                                  ? "default"
                                  : Number(subject.average_score || 0) >= 50
                                  ? "secondary"
                                  : "destructive"
                              }
                            >
                              {formatAnalyticsScore(subject.average_score, classStats.score_display_mode)}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-center text-green-600 font-medium">
                            {formatAnalyticsScore(subject.highest_score, classStats.score_display_mode)}
                          </TableCell>
                          <TableCell className="text-center text-red-600 font-medium">
                            {formatAnalyticsScore(subject.lowest_score, classStats.score_display_mode)}
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex items-center gap-2">
                              <Progress
                                value={Number(subject.pass_rate)}
                                className="h-2 w-16"
                              />
                              <span className="text-sm">{Number(subject.pass_rate).toFixed(0)}%</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-center">
                            <div className="flex flex-wrap gap-1 justify-center">
                              {subject.grade_distribution.slice(0, 4).map((g) => (
                                <Badge
                                  key={g.grade}
                                  variant="outline"
                                  className="text-xs"
                                  style={{ borderColor: GRADE_COLORS[g.grade] }}
                                >
                                  {g.grade}: {g.count}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12">
                    <PieChart className="mx-auto h-12 w-12 text-muted-foreground/50" />
                    <h3 className="mt-4 text-lg font-semibold">No subject data</h3>
                    <p className="text-muted-foreground">
                      No scores have been entered for subjects in this class.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Rankings Tab */}
          <TabsContent value="rankings" className="space-y-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Subject Rankings</CardTitle>
                  <CardDescription>
                    Student rankings by subject performance
                  </CardDescription>
                </div>
                <Select value={selectedSubjectId} onValueChange={setSelectedSubjectId}>
                  <SelectTrigger className="w-full sm:w-[250px]">
                    <SelectValue placeholder="Select a subject" />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {s.code ? `${s.code} - ${s.name}` : s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardHeader>
              <CardContent>
                {subjectRankings && subjectRankings.rankings.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[80px]">Position</TableHead>
                        <TableHead>Student</TableHead>
                        <TableHead className="text-center">Score</TableHead>
                        <TableHead className="text-center">Grade</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {subjectRankings.rankings.map((student) => (
                        <TableRow key={student.student_id}>
                          <TableCell>{getPositionBadge(student.position)}</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback>
                                  {student.student_name
                                    .split(" ")
                                    .map((n) => n[0])
                                    .join("")
                                    .slice(0, 2)}
                                </AvatarFallback>
                              </Avatar>
                              <div>
                                <p className="font-medium text-sm">{student.student_name}</p>
                                <p className="text-xs text-muted-foreground">
                                  {student.student_id_number}
                                </p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="text-center font-semibold">
                            {formatAnalyticsScore(student.score, classStats?.score_display_mode)}
                          </TableCell>
                          <TableCell className="text-center">
                            {student.grade ? (
                              <Badge
                                style={{
                                  backgroundColor: GRADE_COLORS[student.grade] || "#94a3b8",
                                  color: "white",
                                }}
                              >
                                {student.grade}
                              </Badge>
                            ) : (
                              "-"
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12">
                    <Trophy className="mx-auto h-12 w-12 text-muted-foreground/50" />
                    <h3 className="mt-4 text-lg font-semibold">No rankings available</h3>
                    <p className="text-muted-foreground">
                      {subjects.length === 0
                        ? "No subjects available for ranking."
                        : "No scores have been entered for this subject."}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
