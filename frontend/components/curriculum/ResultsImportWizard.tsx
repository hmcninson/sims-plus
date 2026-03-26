"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Loader2,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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

import { importExternalExamResults } from "@/actions/curriculum.action";
import type {
  ExternalExamBoard,
  ResultsImportPreview,
  ResultsImportCommit,
} from "@/types/curriculum.type";

const FORMAT_HINTS: Record<string, string> = {
  waec: "Expected columns: CandidateNumber, SubjectCode, SubjectName, Grade, Score",
  cambridge_international:
    "Expected columns: CandidateNumber, CenterNumber, ComponentCode, ComponentName, Grade, Mark, MaxMark",
  edexcel: "Expected columns: CandidateNumber, SubjectCode, SubjectName, Grade, Mark",
  college_board: "Expected columns: CandidateNumber, SubjectCode, SubjectName, Score",
  ibo: "Expected columns: CandidateNumber, SubjectCode, SubjectName, Level, Grade, Score",
};

function isPreviewResult(
  data: ResultsImportPreview | ResultsImportCommit,
): data is ResultsImportPreview {
  return "preview_rows" in data;
}

function isCommitResult(
  data: ResultsImportPreview | ResultsImportCommit,
): data is ResultsImportCommit {
  return "imported" in data;
}

export function ResultsImportWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [examBoard, setExamBoard] = useState<ExternalExamBoard | "">("");
  const [examSession, setExamSession] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [fileName, setFileName] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [preview, setPreview] = useState<ResultsImportPreview | null>(null);
  const [importResult, setImportResult] = useState<ResultsImportCommit | null>(null);

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".csv")) {
      toast.error("Please upload a CSV file");
      return;
    }
    setFileName(file.name);
    setCsvFile(file);
  }, []);

  const handleDryRun = async () => {
    if (!examBoard || !examSession || !csvFile) {
      toast.error("Please fill in all fields and upload a CSV file");
      return;
    }
    setIsProcessing(true);
    try {
      const result = await importExternalExamResults(
        examBoard,
        examSession,
        csvFile,
        true,
      );
      if (result.success && isPreviewResult(result.data)) {
        setPreview(result.data);
        setStep(2);
      } else if (!result.success) {
        toast.error(result.error);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const handleImport = async () => {
    if (!examBoard || !examSession || !csvFile) return;
    setIsProcessing(true);
    try {
      const result = await importExternalExamResults(
        examBoard,
        examSession,
        csvFile,
        false,
      );
      if (result.success && isCommitResult(result.data)) {
        setImportResult(result.data);
        setStep(3);
        toast.success("Results imported successfully");
      } else if (!result.success) {
        toast.error(result.error);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Step Indicator */}
      <div className="flex items-center justify-center gap-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`flex size-8 items-center justify-center rounded-full text-sm font-medium ${
                s === step
                  ? "bg-primary text-primary-foreground"
                  : s < step
                    ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {s < step ? <CheckCircle2 className="size-4" /> : s}
            </div>
            <span className="hidden text-sm sm:inline">
              {s === 1 ? "Configure" : s === 2 ? "Preview" : "Complete"}
            </span>
            {s < 3 && <div className="h-px w-8 bg-border" />}
          </div>
        ))}
      </div>

      {/* Step 1: Configuration */}
      {step === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Import Configuration</CardTitle>
            <CardDescription>
              Select the exam board, session, and upload the results CSV file.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Exam Board</Label>
                <Select
                  value={examBoard}
                  onValueChange={(v) => setExamBoard(v as ExternalExamBoard)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select exam board" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="waec">WAEC</SelectItem>
                    <SelectItem value="cambridge_international">
                      Cambridge International
                    </SelectItem>
                    <SelectItem value="edexcel">Edexcel</SelectItem>
                    <SelectItem value="college_board">College Board</SelectItem>
                    <SelectItem value="ibo">IBO</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Exam Session</Label>
                <Input
                  placeholder="e.g., Nov 2026"
                  value={examSession}
                  onChange={(e) => setExamSession(e.target.value)}
                />
              </div>
            </div>

            {examBoard && (
              <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200">
                <FileText className="mr-2 inline size-4" />
                {FORMAT_HINTS[examBoard]}
              </div>
            )}

            <div className="space-y-2">
              <Label>CSV File</Label>
              <div className="flex items-center gap-3">
                <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-muted-foreground/30 px-4 py-6 text-center hover:border-primary/50 hover:bg-accent/50 w-full transition-colors">
                  <Upload className="mx-auto size-6 text-muted-foreground" />
                  <div className="text-sm">
                    {fileName ? (
                      <span className="font-medium">{fileName}</span>
                    ) : (
                      <span className="text-muted-foreground">
                        Click to upload or drag and drop a CSV file
                      </span>
                    )}
                  </div>
                  <Input
                    type="file"
                    accept=".csv"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end">
              <Button
                onClick={handleDryRun}
                disabled={!examBoard || !examSession || !csvFile || isProcessing}
              >
                {isProcessing && <Loader2 className="mr-2 size-4 animate-spin" />}
                Preview Import
                <ArrowRight className="ml-2 size-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Preview */}
      {step === 2 && preview && (
        <Card>
          <CardHeader>
            <CardTitle>Import Preview</CardTitle>
            <CardDescription>
              Review the results below before confirming the import.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-md border p-3 text-center">
                <p className="text-2xl font-bold">{preview.total_rows}</p>
                <p className="text-xs text-muted-foreground">Total Rows</p>
              </div>
              <div className="rounded-md border border-green-200 bg-green-50 p-3 text-center dark:border-green-800 dark:bg-green-950">
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {preview.matched}
                </p>
                <p className="text-xs text-muted-foreground">Matched</p>
              </div>
              <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-center dark:border-amber-800 dark:bg-amber-950">
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">
                  {preview.unmatched}
                </p>
                <p className="text-xs text-muted-foreground">Unmatched</p>
              </div>
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-center dark:border-red-800 dark:bg-red-950">
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {preview.errors.length}
                </p>
                <p className="text-xs text-muted-foreground">Errors</p>
              </div>
            </div>

            {/* Errors */}
            {preview.errors.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-medium text-destructive">Errors:</p>
                <ul className="list-disc pl-5 text-sm text-destructive">
                  {preview.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Preview Table - backend returns list[dict] so we render keys dynamically */}
            {preview.preview_rows && preview.preview_rows.length > 0 && (
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {Object.keys(preview.preview_rows[0]).map((key) => (
                        <TableHead key={key} className="text-xs capitalize">
                          {key.replace(/_/g, " ")}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.preview_rows.map((row, i) => (
                      <TableRow key={i}>
                        {Object.values(row).map((val, j) => (
                          <TableCell key={j} className="text-sm">
                            {val != null ? String(val) : (
                              <span className="text-muted-foreground">&mdash;</span>
                            )}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>
                <ArrowLeft className="mr-2 size-4" />
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={isProcessing || preview.matched === 0}
              >
                {isProcessing && <Loader2 className="mr-2 size-4 animate-spin" />}
                Import {preview.matched} Result(s)
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Complete */}
      {step === 3 && importResult && (
        <Card>
          <CardHeader className="text-center">
            <div className="mx-auto mb-2">
              <CheckCircle2 className="size-12 text-green-600" />
            </div>
            <CardTitle>Import Complete</CardTitle>
            <CardDescription>
              {importResult.imported} result(s) were successfully imported.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div className="rounded-md border p-3 text-center">
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {importResult.imported}
                </p>
                <p className="text-xs text-muted-foreground">Imported</p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <p className="text-2xl font-bold text-amber-700 dark:text-amber-300">
                  {importResult.skipped}
                </p>
                <p className="text-xs text-muted-foreground">Skipped</p>
              </div>
              <div className="rounded-md border p-3 text-center">
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {importResult.errors.length}
                </p>
                <p className="text-xs text-muted-foreground">Errors</p>
              </div>
            </div>

            {importResult.errors.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-medium text-destructive">Import Errors:</p>
                <ul className="list-disc pl-5 text-sm text-destructive">
                  {importResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex justify-center">
              <Button onClick={() => router.push("/exams/external")}>
                Back to External Exams
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
