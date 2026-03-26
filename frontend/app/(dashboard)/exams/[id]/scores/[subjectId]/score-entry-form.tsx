"use client";

import { useState, useTransition, useCallback, useEffect, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Save,
  Loader2,
  CheckCircle,
  Send,
  Search,
  X,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Progress } from "@/components/ui/progress";

import {
  bulkEnterScores,
  submitExamSubjectScores,
} from "@/actions/exams.action";
import type {
  ExamWithContext,
  ScoreEntryForm as ScoreEntryFormType,
  ScoreEntry,
  GradingScale,
  Grade,
} from "@/types";

interface ScoreEntryFormProps {
  exam: ExamWithContext;
  scoreForm: ScoreEntryFormType;
  gradingScales: GradingScale[];
}

interface StudentScoreEntry {
  student_id: string;
  score: string;
  is_absent: boolean;
  teacher_remark: string;
  grade?: string;
  effort_grade: string;
}

export function ScoreEntryForm({
  exam,
  scoreForm,
  gradingScales,
}: ScoreEntryFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Defensive: ensure students is always an array
  const students = scoreForm.students || [];

  // Find default grading scale
  const defaultScale = gradingScales.find((s) => s.is_default) || gradingScales[0];
  const [selectedScaleId, setSelectedScaleId] = useState(
    scoreForm.grading_scale_id || defaultScale?.id || ""
  );
  const selectedScale = gradingScales.find((s) => s.id === selectedScaleId);

  // Determine if effort grade column should be shown
  const showEffortGrade = scoreForm.show_effort_grade === true;

  // Initialize scores from form data
  const [scores, setScores] = useState<Record<string, StudentScoreEntry>>(() => {
    const initial: Record<string, StudentScoreEntry> = {};
    for (const student of students) {
      initial[student.student_id] = {
        student_id: student.student_id,
        score: student.current_score?.toString() || "",
        is_absent: student.is_absent,
        teacher_remark: student.teacher_remark || "",
        grade: student.current_grade,
        effort_grade: student.effort_grade || "",
      };
    }
    return initial;
  });

  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSection, setSelectedSection] = useState<string>("all");

  // Get unique sections from students
  const sections = useMemo(() => {
    const sectionMap = new Map<string, string>();
    for (const student of students) {
      if (student.section_id && student.section_name) {
        sectionMap.set(student.section_id, student.section_name);
      }
    }
    return Array.from(sectionMap.entries()).map(([id, name]) => ({ id, name }));
  }, [students]);

  // Filter students by section and search query
  const filteredStudents = students.filter((student) => {
    // Section filter
    if (selectedSection !== "all" && student.section_id !== selectedSection) {
      return false;
    }
    // Search filter
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const fullName = `${student.first_name} ${student.last_name}`.toLowerCase();
    return (
      fullName.includes(query) ||
      student.student_number.toLowerCase().includes(query)
    );
  });

  // Calculate grade from score
  const calculateGrade = useCallback(
    (score: number): { grade: string; gradePoint?: number; remark?: string } | null => {
      if (!selectedScale?.grades || selectedScale.grades.length === 0) return null;

      const percentage = (score / scoreForm.max_score) * 100;

      // Sort grades by min_score descending
      const sortedGrades = [...selectedScale.grades].sort(
        (a, b) => b.min_score - a.min_score
      );

      for (const grade of sortedGrades) {
        if (percentage >= grade.min_score) {
          return {
            grade: grade.grade,
            gradePoint: grade.grade_point,
            remark: grade.remark,
          };
        }
      }

      return null;
    },
    [selectedScale, scoreForm.max_score]
  );

  const updateScore = (studentId: string, field: keyof StudentScoreEntry, value: string | boolean) => {
    setScores((prev) => {
      const updated = { ...prev };
      const studentScore = { ...updated[studentId] };

      if (field === "score" && typeof value === "string") {
        // Validate and update score
        const numValue = parseFloat(value);
        studentScore.score = value;

        // Calculate grade if valid score
        if (!isNaN(numValue) && numValue >= 0 && numValue <= scoreForm.max_score) {
          const gradeInfo = calculateGrade(numValue);
          studentScore.grade = gradeInfo?.grade;
        } else {
          studentScore.grade = undefined;
        }
      } else if (field === "is_absent" && typeof value === "boolean") {
        studentScore.is_absent = value;
        if (value) {
          studentScore.score = "";
          studentScore.grade = undefined;
          studentScore.effort_grade = "";
        }
      } else if (field === "teacher_remark" && typeof value === "string") {
        studentScore.teacher_remark = value;
      } else if (field === "effort_grade" && typeof value === "string") {
        studentScore.effort_grade = value;
      }

      updated[studentId] = studentScore;
      return updated;
    });
    setHasUnsavedChanges(true);
  };

  const handleSave = async () => {
    // Prepare score entries
    const scoreEntries: ScoreEntry[] = Object.values(scores)
      .filter((s) => s.score !== "" || s.is_absent)
      .map((s) => ({
        student_id: s.student_id,
        score: s.score !== "" ? parseFloat(s.score) : undefined,
        is_absent: s.is_absent,
        teacher_remark: s.teacher_remark || undefined,
        effort_grade: s.effort_grade || null,
      }));

    if (scoreEntries.length === 0) {
      toast.error("No scores to save");
      return;
    }

    startTransition(async () => {
      const result = await bulkEnterScores(exam.id, scoreForm.exam_subject_id, {
        grading_scale_id: selectedScaleId || undefined,
        scores: scoreEntries,
      });

      if (result.success && result.data) {
        const { created, updated, failed } = result.data;
        toast.success("Scores saved", {
          description: `${created + updated} scores saved${failed > 0 ? `, ${failed} failed` : ""}`,
        });
        setHasUnsavedChanges(false);
      } else {
        toast.error("Failed to save scores", {
          description: result.error,
        });
      }
    });
  };

  const handleSubmit = async () => {
    startTransition(async () => {
      // First save any unsaved changes
      await handleSave();

      // Then submit
      const result = await submitExamSubjectScores(exam.id, scoreForm.exam_subject_id);

      if (result.success) {
        toast.success("Scores submitted", {
          description: "Scores have been submitted and locked for review.",
        });
        setSubmitDialogOpen(false);
        router.push(`/exams/${exam.id}/scores`);
      } else {
        toast.error("Failed to submit scores", {
          description: result.error,
        });
      }
    });
  };

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Stats
  const enteredCount = Object.values(scores).filter(
    (s) => s.score !== "" || s.is_absent
  ).length;
  const absentCount = Object.values(scores).filter((s) => s.is_absent).length;
  const progressPercentage = students.length > 0
    ? Math.round((enteredCount / students.length) * 100)
    : 0;
  const scoresWithValues = Object.values(scores).filter((s) => s.score !== "" && !s.is_absent);
  const avgScore = scoresWithValues.length > 0
    ? scoresWithValues.reduce((sum, s) => sum + parseFloat(s.score), 0) / scoresWithValues.length
    : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/exams/${exam.id}/scores`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {scoreForm.subject_name} - Score Entry
          </h1>
          <p className="text-muted-foreground">
            {exam.name} - {scoreForm.class_name}
            {scoreForm.section_name && ` (${scoreForm.section_name})`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleSave}
            disabled={isPending || !hasUnsavedChanges}
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Draft
          </Button>
          <Button onClick={() => setSubmitDialogOpen(true)} disabled={isPending}>
            <Send className="mr-2 h-4 w-4" />
            Submit Scores
          </Button>
        </div>
      </div>

      {/* Progress Bar */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Progress</span>
            <span className="text-sm text-muted-foreground">
              {enteredCount} of {students.length} students ({progressPercentage}%)
            </span>
          </div>
          <Progress value={progressPercentage} className="h-2" />
          {hasUnsavedChanges && (
            <div className="flex items-center gap-2 mt-3 text-amber-600">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm">You have unsaved changes</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Students</CardDescription>
            <CardTitle className="text-2xl">{students.length}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Scores Entered</CardDescription>
            <CardTitle className="text-2xl text-blue-600">
              {enteredCount - absentCount}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Marked Absent</CardDescription>
            <CardTitle className="text-2xl text-amber-600">{absentCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Class Average</CardDescription>
            <CardTitle className="text-2xl text-green-600">
              {avgScore.toFixed(1)}%
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Grading Scale Selection */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-lg">Score Entry</CardTitle>
          <CardDescription>
            Max Score: {scoreForm.max_score} | Pass Mark: {scoreForm.pass_mark}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4 mb-6">
            <div className="flex items-center gap-2">
              <Label>Grading Scale:</Label>
              <Select value={selectedScaleId} onValueChange={setSelectedScaleId}>
                <SelectTrigger className="w-full sm:w-[280px]">
                  <SelectValue placeholder="Select grading scale" />
                </SelectTrigger>
                <SelectContent>
                  {gradingScales.map((scale) => (
                    <SelectItem key={scale.id} value={scale.id}>
                      {scale.name}
                      {scale.is_default && " (Default)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {sections.length > 0 && (
              <div className="flex items-center gap-2">
                <Label>Section:</Label>
                <Select value={selectedSection} onValueChange={setSelectedSection}>
                  <SelectTrigger className="w-full sm:w-[150px]">
                    <SelectValue placeholder="All Sections" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Sections</SelectItem>
                    {sections.map((section) => (
                      <SelectItem key={section.id} value={section.id}>
                        {section.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {selectedScale && (
              <div className="flex items-center gap-1">
                {selectedScale.grades
                  ?.sort((a, b) => b.min_score - a.min_score)
                  .slice(0, 5)
                  .map((grade) => (
                    <Badge key={grade.id} variant="outline" className="text-xs">
                      {grade.grade}: {grade.min_score}%+
                    </Badge>
                  ))}
              </div>
            )}
          </div>

          {/* Score Entry Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">#</TableHead>
                  <TableHead>
                    <div className="flex items-center gap-2">
                      <span>Student</span>
                      <div className="relative ml-2">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                        <Input
                          placeholder="Search..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="h-7 pl-7 pr-7 w-full sm:w-[180px] text-sm"
                        />
                        {searchQuery && (
                          <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  </TableHead>
                  <TableHead className="w-[120px]">
                    Score (/{scoreForm.max_score})
                  </TableHead>
                  <TableHead className="w-[100px]">Grade</TableHead>
                  {showEffortGrade && (
                    <TableHead className="hidden sm:table-cell w-[120px]">Effort</TableHead>
                  )}
                  <TableHead className="w-[80px]">Absent</TableHead>
                  <TableHead>Remark</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredStudents.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={showEffortGrade ? 7 : 6} className="text-center py-8 text-muted-foreground">
                      {searchQuery ? "No students match your search" : "No students found"}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredStudents.map((student, index) => {
                    const scoreEntry = scores[student.student_id];
                    const isPassing =
                      scoreEntry?.score !== "" &&
                      parseFloat(scoreEntry?.score || "0") >= scoreForm.pass_mark;

                    if (!scoreEntry) return null;

                    const hasScore = scoreEntry.score !== "" || scoreEntry.is_absent;

                    return (
                      <TableRow
                        key={student.student_id}
                        className={
                          scoreEntry.is_absent
                            ? "bg-muted/50"
                            : hasScore
                            ? "bg-green-50/50 dark:bg-green-950/20"
                            : ""
                        }
                      >
                        <TableCell className="text-muted-foreground">
                          <div className="flex items-center gap-2">
                            {hasScore && (
                              <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                            )}
                            <span>{index + 1}</span>
                          </div>
                        </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-8 w-8">
                            <AvatarFallback>
                              {student.first_name[0]}
                              {student.last_name[0]}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-medium">
                              {student.first_name} {student.last_name}
                              {student.section_name && (
                                <span className="ml-2 text-xs font-normal text-muted-foreground">
                                  ({student.section_name})
                                </span>
                              )}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {student.student_number}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          min={0}
                          max={scoreForm.max_score}
                          step={0.5}
                          value={scoreEntry.score}
                          onChange={(e) =>
                            updateScore(student.student_id, "score", e.target.value)
                          }
                          disabled={scoreEntry.is_absent}
                          className="w-20"
                          placeholder="-"
                        />
                      </TableCell>
                      <TableCell>
                        {scoreEntry.grade ? (
                          <Badge
                            variant={isPassing ? "default" : "destructive"}
                          >
                            {scoreEntry.grade}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      {showEffortGrade && (
                        <TableCell className="hidden sm:table-cell">
                          <Select
                            value={scoreEntry.effort_grade || ""}
                            onValueChange={(val) =>
                              updateScore(student.student_id, "effort_grade", val)
                            }
                            disabled={scoreEntry.is_absent}
                          >
                            <SelectTrigger className="w-20">
                              <SelectValue placeholder="-" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="1">1 - Excellent</SelectItem>
                              <SelectItem value="2">2 - Good</SelectItem>
                              <SelectItem value="3">3 - Satisfactory</SelectItem>
                              <SelectItem value="4">4 - Needs Improvement</SelectItem>
                              <SelectItem value="5">5 - Unacceptable</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                      )}
                      <TableCell>
                        <Checkbox
                          checked={scoreEntry.is_absent}
                          onCheckedChange={(checked) =>
                            updateScore(
                              student.student_id,
                              "is_absent",
                              checked === true
                            )
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          placeholder="Optional remark..."
                          value={scoreEntry.teacher_remark}
                          onChange={(e) =>
                            updateScore(
                              student.student_id,
                              "teacher_remark",
                              e.target.value
                            )
                          }
                          disabled={scoreEntry.is_absent}
                          className="max-w-[200px]"
                        />
                      </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
          {searchQuery && filteredStudents.length > 0 && (
            <p className="text-sm text-muted-foreground mt-2">
              Showing {filteredStudents.length} of {students.length} students
            </p>
          )}
        </CardContent>
      </Card>

      {/* Submit Confirmation Dialog */}
      <AlertDialog open={submitDialogOpen} onOpenChange={setSubmitDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Submit Scores</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p className="text-muted-foreground text-sm">
                  Are you sure you want to submit these scores? Once submitted, the
                  scores will be locked and cannot be changed without admin approval.
                </p>
                <div className="mt-4 p-4 bg-muted rounded-md">
                  <p className="font-medium">Summary:</p>
                  <ul className="mt-2 text-sm space-y-1">
                    <li>
                      Total Students: {students.length}
                    </li>
                    <li>
                      Scores Entered: {enteredCount}
                    </li>
                    <li>
                      Absent: {absentCount}
                    </li>
                    <li>
                      Missing:{" "}
                      {students.length - enteredCount}
                    </li>
                  </ul>
                </div>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleSubmit}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Submit Scores
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
