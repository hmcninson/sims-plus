"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { toast } from "sonner";
import { Loader2, Save, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  getPredictedGrades,
  bulkSetPredictedGrades,
} from "@/actions/curriculum.action";
import { getClasses } from "@/actions/academic.action";
import type { PredictedGrade, PredictedGradeCreate } from "@/types/curriculum.type";
import type { AcademicYear, Class } from "@/types";

interface StudentRow {
  student_id: string;
  student_name: string;
  current_average?: number;
  predicted_grade: string;
  target_grade: string;
  notes: string;
  existing_id?: string;
  dirty: boolean;
}

interface PredictedGradeEntryProps {
  academicYears: AcademicYear[];
  gradeOptions: string[];
  subjects: { id: string; name: string }[];
  students: { id: string; name: string; class_id?: string; section_id?: string }[];
}

export function PredictedGradeEntry({
  academicYears,
  gradeOptions,
  subjects,
  students,
}: PredictedGradeEntryProps) {
  const [academicYearId, setAcademicYearId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [classFilter, setClassFilter] = useState("");
  const [classes, setClasses] = useState<Class[]>([]);
  const [rows, setRows] = useState<StudentRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const hasUnsavedChanges = rows.some((r) => r.dirty);

  // Load classes
  useEffect(() => {
    async function loadClasses() {
      const result = await getClasses();
      if (result.success && result.data) {
        setClasses(result.data);
      }
    }
    loadClasses();
  }, []);

  // Load existing predicted grades when context changes
  const loadPredictions = useCallback(async () => {
    if (!academicYearId || !subjectId) return;

    setIsLoading(true);
    try {
      const result = await getPredictedGrades({
        subject_id: subjectId,
        academic_year_id: academicYearId,
      });

      const existingMap = new Map<string, PredictedGrade>();
      if (result.success && result.data.items) {
        for (const pg of result.data.items) {
          existingMap.set(pg.student_id, pg);
        }
      }

      // Filter students by class if selected
      const filteredStudents = classFilter
        ? students.filter((s) => s.class_id === classFilter)
        : students;

      const newRows: StudentRow[] = filteredStudents.map((s) => {
        const existing = existingMap.get(s.id);
        return {
          student_id: s.id,
          student_name: s.name,
          predicted_grade: existing?.predicted_grade ?? "",
          target_grade: existing?.target_grade ?? "",
          notes: existing?.notes ?? "",
          existing_id: existing?.id,
          predicted_score: existing?.predicted_score,
          dirty: false,
        };
      });

      setRows(newRows);
    } finally {
      setIsLoading(false);
    }
  }, [academicYearId, subjectId, classFilter, students]);

  useEffect(() => {
    loadPredictions();
  }, [loadPredictions]);

  function updateRow(index: number, field: keyof StudentRow, value: string) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value, dirty: true } : row)),
    );
  }

  async function handleSaveAll() {
    const dirtyRows = rows.filter((r) => r.dirty);
    if (dirtyRows.length === 0) {
      toast.info("No changes to save");
      return;
    }

    setIsSaving(true);
    try {
      const entries: PredictedGradeCreate[] = dirtyRows.map((r) => ({
        student_id: r.student_id,
        subject_id: subjectId,
        academic_year_id: academicYearId,
        predicted_grade: r.predicted_grade || undefined,
        target_grade: r.target_grade || undefined,
        notes: r.notes || undefined,
      }));

      const result = await bulkSetPredictedGrades({ predictions: entries });
      if (result.success) {
        toast.success(
          `Saved ${result.data.length} prediction(s)`,
        );
        // Mark all as clean
        setRows((prev) => prev.map((r) => ({ ...r, dirty: false })));
      } else {
        toast.error(result.error);
      }
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Context Selectors */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        <div className="space-y-1">
          <label className="text-sm font-medium">Academic Year</label>
          <Select value={academicYearId} onValueChange={setAcademicYearId}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select year" />
            </SelectTrigger>
            <SelectContent>
              {academicYears.map((y) => (
                <SelectItem key={y.id} value={y.id}>
                  {y.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Subject</label>
          <Select value={subjectId} onValueChange={setSubjectId}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select subject" />
            </SelectTrigger>
            <SelectContent>
              {subjects.map((s) => (
                <SelectItem key={s.id} value={s.id}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Class</label>
          <Select value={classFilter} onValueChange={setClassFilter}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="All classes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-end">
          <Button
            onClick={handleSaveAll}
            disabled={!hasUnsavedChanges || isSaving}
            className="w-full"
          >
            {isSaving ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Save className="mr-2 size-4" />
            )}
            Save All
          </Button>
        </div>
      </div>

      {hasUnsavedChanges && (
        <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <AlertCircle className="size-4" />
          You have unsaved changes
        </div>
      )}

      {/* Content */}
      {!academicYearId || !subjectId ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="mb-3 size-10 text-muted-foreground" />
            <CardTitle className="mb-1 text-lg">Select Context</CardTitle>
            <CardDescription>
              Choose an academic year and subject to enter predicted grades.
            </CardDescription>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-12">
            <Loader2 className="size-8 animate-spin text-muted-foreground" />
          </CardContent>
        </Card>
      ) : rows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="mb-3 size-10 text-muted-foreground" />
            <CardTitle className="mb-1 text-lg">No Students Found</CardTitle>
            <CardDescription>
              No students found for the selected class and subject.
            </CardDescription>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-[180px]">Student</TableHead>
                <TableHead className="hidden sm:table-cell">Current Avg</TableHead>
                <TableHead className="min-w-[130px]">Predicted Grade</TableHead>
                <TableHead className="min-w-[130px]">Target Grade</TableHead>
                <TableHead className="hidden md:table-cell min-w-[200px]">Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, index) => (
                <TableRow
                  key={row.student_id}
                  className={row.dirty ? "bg-amber-50/30 dark:bg-amber-950/10" : ""}
                >
                  <TableCell className="font-medium">
                    {row.student_name}
                    {row.dirty && (
                      <Badge variant="outline" className="ml-2 text-[10px]">
                        modified
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {row.current_average != null ? (
                      <span className="font-mono">{row.current_average.toFixed(1)}</span>
                    ) : (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={row.predicted_grade}
                      onValueChange={(v) => updateRow(index, "predicted_grade", v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Grade" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">--</SelectItem>
                        {gradeOptions.map((g) => (
                          <SelectItem key={g} value={g}>
                            {g}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={row.target_grade}
                      onValueChange={(v) => updateRow(index, "target_grade", v)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Grade" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">--</SelectItem>
                        {gradeOptions.map((g) => (
                          <SelectItem key={g} value={g}>
                            {g}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Input
                      value={row.notes}
                      onChange={(e) => updateRow(index, "notes", e.target.value)}
                      placeholder="Optional notes"
                      className="h-8"
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
