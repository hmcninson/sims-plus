"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2, Save } from "lucide-react";
import type { ExamResult, ExamResultEntry } from "@/types/admissions.type";

interface ExamResultsTableProps {
  examId: string;
  results: ExamResult[];
  editable: boolean;
  onSave: (results: ExamResultEntry[]) => Promise<void>;
}

interface EditableResult {
  application_id: string;
  applicant_name: string;
  score: number;
  max_score: number;
  grade: string;
  passed: boolean;
  remarks: string;
}

export function ExamResultsTable({
  results,
  editable,
  onSave,
}: ExamResultsTableProps) {
  const [editableResults, setEditableResults] = useState<EditableResult[]>(
    results.map((r) => ({
      application_id: r.application_id,
      applicant_name: r.applicant_name || "Unknown",
      score: r.score,
      max_score: r.max_score,
      grade: r.grade || "",
      passed: r.passed,
      remarks: r.remarks || "",
    }))
  );
  const [saving, setSaving] = useState(false);

  function updateResult(index: number, field: keyof EditableResult, value: string | number | boolean) {
    setEditableResults((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const entries: ExamResultEntry[] = editableResults.map((r) => ({
        application_id: r.application_id,
        score: r.score,
        max_score: r.max_score,
        grade: r.grade || undefined,
        passed: r.passed,
        remarks: r.remarks || undefined,
      }));
      await onSave(entries);
    } finally {
      setSaving(false);
    }
  }

  if (editableResults.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        No exam results yet. Register applicants first, then enter scores.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Applicant</TableHead>
              <TableHead className="w-[100px]">Score</TableHead>
              <TableHead className="w-[100px]">Max Score</TableHead>
              <TableHead className="w-[80px]">Grade</TableHead>
              <TableHead className="w-[80px]">Passed</TableHead>
              <TableHead className="hidden sm:table-cell">Remarks</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {editableResults.map((result, index) => (
              <TableRow key={result.application_id}>
                <TableCell className="font-medium">
                  {result.applicant_name}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      type="number"
                      min={0}
                      value={result.score}
                      onChange={(e) =>
                        updateResult(index, "score", Number(e.target.value))
                      }
                      className="h-8 w-20"
                    />
                  ) : (
                    result.score
                  )}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      type="number"
                      min={0}
                      value={result.max_score}
                      onChange={(e) =>
                        updateResult(index, "max_score", Number(e.target.value))
                      }
                      className="h-8 w-20"
                    />
                  ) : (
                    result.max_score
                  )}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Input
                      value={result.grade}
                      onChange={(e) =>
                        updateResult(index, "grade", e.target.value)
                      }
                      className="h-8 w-16"
                    />
                  ) : (
                    result.grade || "-"
                  )}
                </TableCell>
                <TableCell>
                  {editable ? (
                    <Checkbox
                      checked={result.passed}
                      onCheckedChange={(checked) =>
                        updateResult(index, "passed", Boolean(checked))
                      }
                    />
                  ) : result.passed ? (
                    "Yes"
                  ) : (
                    "No"
                  )}
                </TableCell>
                <TableCell className="hidden sm:table-cell">
                  {editable ? (
                    <Input
                      value={result.remarks}
                      onChange={(e) =>
                        updateResult(index, "remarks", e.target.value)
                      }
                      className="h-8"
                      placeholder="Optional remarks"
                    />
                  ) : (
                    result.remarks || "-"
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {editable && (
        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving}>
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save All Results
          </Button>
        </div>
      )}
    </div>
  );
}
