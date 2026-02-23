"use client";

/**
 * SIMS Plus - Teacher Score Entry
 *
 * Score entry interface for a specific class and subject.
 * Features:
 * - Spreadsheet-like table with inline editing (desktop)
 * - Card-per-student view on mobile (below md breakpoint)
 * - Auto-save with debounce (saves 2 seconds after last edit)
 * - Mark student as absent
 * - Visual feedback for saved/unsaved states
 * - Max score validation
 */

import { useEffect, useState, useCallback, useRef, useTransition } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Save,
  Check,
  XCircle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  getTeacherScoreSheet,
  saveTeacherScores,
} from "@/actions/teacher.action";
import type { TeacherScoreSheet, TeacherScoreEntry } from "@/types/teacher.type";
import { toast } from "sonner";

interface EditableScore {
  student_id: string;
  score: string;
  is_absent: boolean;
  remark: string;
  dirty: boolean;
}

export default function TeacherScoreEntryPage() {
  const params = useParams();
  const classId = params.classId as string;
  const subjectId = params.subjectId as string;

  const [sheet, setSheet] = useState<TeacherScoreSheet | null>(null);
  const [scores, setScores] = useState<Map<string, EditableScore>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Load score sheet
  useEffect(() => {
    async function load() {
      const result = await getTeacherScoreSheet(classId, subjectId);
      if (result.success) {
        setSheet(result.data);
        // Initialize editable scores
        const initial = new Map<string, EditableScore>();
        result.data.students.forEach((s: TeacherScoreEntry) => {
          initial.set(s.student_id, {
            student_id: s.student_id,
            score: s.score !== null ? String(s.score) : "",
            is_absent: s.is_absent,
            remark: s.remark || "",
            dirty: false,
          });
        });
        setScores(initial);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, [classId, subjectId]);

  // Auto-save with debounce
  const triggerAutoSave = useCallback(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      handleSave();
    }, 2000);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Update a student's score
  const updateScore = useCallback(
    (studentId: string, field: keyof EditableScore, value: string | boolean) => {
      setScores((prev) => {
        const next = new Map(prev);
        const entry = next.get(studentId);
        if (!entry) return prev;
        next.set(studentId, { ...entry, [field]: value, dirty: true });
        return next;
      });
      setSaveStatus("idle");
      triggerAutoSave();
    },
    [triggerAutoSave]
  );

  // Save all dirty scores
  const handleSave = () => {
    if (!sheet) return;

    const dirtyScores: { student_id: string; score: number | null; is_absent: boolean; remark?: string }[] = [];
    scores.forEach((entry) => {
      if (entry.dirty) {
        const scoreNum = entry.score === "" ? null : Number(entry.score);
        // Validate score range
        if (scoreNum !== null && (isNaN(scoreNum) || scoreNum < 0 || scoreNum > sheet.max_score)) {
          return; // Skip invalid
        }
        dirtyScores.push({
          student_id: entry.student_id,
          score: entry.is_absent ? null : scoreNum,
          is_absent: entry.is_absent,
          remark: entry.remark || undefined,
        });
      }
    });

    if (dirtyScores.length === 0) {
      setSaveStatus("saved");
      return;
    }

    setSaveStatus("saving");
    startTransition(async () => {
      const result = await saveTeacherScores(
        sheet.exam_subject_id,
        dirtyScores.map((s) => ({
          student_id: s.student_id,
          score: s.score,
          is_absent: s.is_absent,
          teacher_remark: s.remark,
        })),
      );

      if (result.success) {
        setSaveStatus("saved");
        // Mark all as clean
        setScores((prev) => {
          const next = new Map(prev);
          next.forEach((entry, key) => {
            if (entry.dirty) {
              next.set(key, { ...entry, dirty: false });
            }
          });
          return next;
        });
        if (result.data.failed > 0) {
          toast.warning(`${result.data.successful} saved, ${result.data.failed} failed`);
        }
      } else {
        setSaveStatus("error");
        toast.error(result.error);
      }
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !sheet) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load score sheet"}</AlertDescription>
      </Alert>
    );
  }

  const hasDirty = Array.from(scores.values()).some((s) => s.dirty);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild className="mt-1">
          <Link href="/teacher/grading">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold tracking-tight">
            {sheet.subject_name} - Score Entry
          </h1>
          <p className="text-muted-foreground text-sm">
            {sheet.class_name}
            {sheet.section_name ? ` - ${sheet.section_name}` : ""}
            {" | "}Max: {sheet.max_score} | Pass: {sheet.pass_mark}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {saveStatus === "saving" && (
            <Badge variant="outline" className="text-muted-foreground">
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Saving...
            </Badge>
          )}
          {saveStatus === "saved" && !hasDirty && (
            <Badge variant="outline" className="text-green-600 border-green-300">
              <Check className="h-3 w-3 mr-1" />
              Saved
            </Badge>
          )}
          {saveStatus === "error" && (
            <Badge variant="outline" className="text-red-600 border-red-300">
              <XCircle className="h-3 w-3 mr-1" />
              Error
            </Badge>
          )}
          <Button
            size="sm"
            onClick={handleSave}
            disabled={isPending || !hasDirty}
          >
            <Save className="h-3.5 w-3.5 mr-1" />
            Save
          </Button>
        </div>
      </div>

      {/* Desktop: Score entry table */}
      <Card className="hidden md:block">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground w-8">#</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Student</th>
                  <th className="p-3 text-center text-xs font-medium text-muted-foreground w-24">Score</th>
                  <th className="p-3 text-center text-xs font-medium text-muted-foreground w-20">Absent</th>
                  <th className="p-3 text-left text-xs font-medium text-muted-foreground">Remark</th>
                </tr>
              </thead>
              <tbody>
                {sheet.students.map((student: TeacherScoreEntry, idx: number) => {
                  const entry = scores.get(student.student_id);
                  if (!entry) return null;

                  const scoreNum = entry.score === "" ? null : Number(entry.score);
                  const isInvalid =
                    scoreNum !== null &&
                    (isNaN(scoreNum) || scoreNum < 0 || scoreNum > sheet.max_score);

                  return (
                    <tr
                      key={student.student_id}
                      className={`border-b last:border-0 ${entry.dirty ? "bg-amber-50/50" : ""}`}
                    >
                      <td className="p-3 text-xs text-muted-foreground">{idx + 1}</td>
                      <td className="p-3">
                        <p className="text-sm font-medium">
                          {student.first_name} {student.last_name}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {student.student_number}
                        </p>
                      </td>
                      <td className="p-3 text-center">
                        <Input
                          type="number"
                          min={0}
                          max={sheet.max_score}
                          step="0.5"
                          value={entry.score}
                          onChange={(e) =>
                            updateScore(student.student_id, "score", e.target.value)
                          }
                          disabled={entry.is_absent}
                          className={`h-8 w-20 mx-auto text-center ${isInvalid ? "border-red-500" : ""}`}
                          placeholder="--"
                        />
                      </td>
                      <td className="p-3 text-center">
                        <Checkbox
                          checked={entry.is_absent}
                          onCheckedChange={(checked) =>
                            updateScore(student.student_id, "is_absent", !!checked)
                          }
                        />
                      </td>
                      <td className="p-3">
                        <Input
                          type="text"
                          value={entry.remark}
                          onChange={(e) =>
                            updateScore(student.student_id, "remark", e.target.value)
                          }
                          className="h-8 text-xs"
                          placeholder="Optional remark"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Mobile: Card-per-student view */}
      <div className="md:hidden space-y-3">
        {sheet.students.map((student: TeacherScoreEntry, idx: number) => {
          const entry = scores.get(student.student_id);
          if (!entry) return null;

          const scoreNum = entry.score === "" ? null : Number(entry.score);
          const isInvalid =
            scoreNum !== null &&
            (isNaN(scoreNum) || scoreNum < 0 || scoreNum > sheet.max_score);

          return (
            <Card
              key={student.student_id}
              className={entry.dirty ? "border-amber-300 bg-amber-50/30" : ""}
            >
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">
                      {idx + 1}. {student.first_name} {student.last_name}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {student.student_number}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id={`absent-mobile-${student.student_id}`}
                      checked={entry.is_absent}
                      onCheckedChange={(checked) =>
                        updateScore(student.student_id, "is_absent", !!checked)
                      }
                    />
                    <label
                      htmlFor={`absent-mobile-${student.student_id}`}
                      className="text-xs text-muted-foreground"
                    >
                      Absent
                    </label>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                      Score (max {sheet.max_score})
                    </label>
                    <Input
                      type="number"
                      min={0}
                      max={sheet.max_score}
                      step="0.5"
                      value={entry.score}
                      onChange={(e) =>
                        updateScore(student.student_id, "score", e.target.value)
                      }
                      disabled={entry.is_absent}
                      className={`h-9 ${isInvalid ? "border-red-500" : ""}`}
                      placeholder="--"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1 block">
                      Remark
                    </label>
                    <Input
                      type="text"
                      value={entry.remark}
                      onChange={(e) =>
                        updateScore(student.student_id, "remark", e.target.value)
                      }
                      className="h-9 text-xs"
                      placeholder="Optional"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary footer */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">Entered: </span>
              <span className="font-medium">
                {Array.from(scores.values()).filter((s) => s.score !== "" || s.is_absent).length}
              </span>
              <span className="text-muted-foreground"> / {sheet.students.length}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Absent: </span>
              <span className="font-medium">
                {Array.from(scores.values()).filter((s) => s.is_absent).length}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">Average: </span>
              <span className="font-medium">
                {(() => {
                  const validScores = Array.from(scores.values())
                    .filter((s) => !s.is_absent && s.score !== "")
                    .map((s) => Number(s.score))
                    .filter((n) => !isNaN(n));
                  if (validScores.length === 0) return "--";
                  return (validScores.reduce((a, b) => a + b, 0) / validScores.length).toFixed(1);
                })()}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
