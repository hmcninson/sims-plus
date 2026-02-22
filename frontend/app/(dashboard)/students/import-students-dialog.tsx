"use client";

import { useState, useRef, useTransition } from "react";
import { Upload, FileSpreadsheet, Download, AlertCircle, CheckCircle2, Loader2, X, Info } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  getImportTemplate,
  importStudentsPreview,
  importStudents,
  type ImportTemplate,
  type ImportPreviewResult,
  type ImportResult,
} from "@/actions/students.action";

interface ImportStudentsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type ImportStep = "upload" | "preview" | "importing" | "complete";

export function ImportStudentsDialog({
  open,
  onOpenChange,
  onSuccess,
}: ImportStudentsDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [template, setTemplate] = useState<ImportTemplate | null>(null);
  const [previewData, setPreviewData] = useState<ImportPreviewResult | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset state when dialog closes
  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setStep("upload");
      setFile(null);
      setPreviewData(null);
      setImportResult(null);
    }
    onOpenChange(open);
  };

  // Load template
  const loadTemplate = async () => {
    const result = await getImportTemplate();
    if (result.success && result.data) {
      setTemplate(result.data);
    }
  };

  // Download template as CSV
  const downloadTemplate = () => {
    if (!template) return;

    const csvContent = [
      template.headers.join(","),
      Object.values(template.example_row).join(","),
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "student_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  // Handle file selection
  const handleFileSelect = (selectedFile: File) => {
    const validTypes = [
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ];

    if (!validTypes.includes(selectedFile.type) &&
        !selectedFile.name.endsWith(".csv") &&
        !selectedFile.name.endsWith(".xlsx")) {
      toast.error("Please upload a CSV or Excel file");
      return;
    }

    setFile(selectedFile);
  };

  // Handle drag and drop
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  // Preview import
  const handlePreview = () => {
    if (!file) return;

    startTransition(async () => {
      const formData = new FormData();
      formData.append("file", file);

      // Always auto-generate student IDs
      const result = await importStudentsPreview(formData);
      if (result.success && result.data) {
        setPreviewData(result.data);
        setStep("preview");
      } else {
        toast.error(result.error || "Failed to preview file");
      }
    });
  };

  // Execute import
  const handleImport = () => {
    if (!file) return;

    startTransition(async () => {
      setStep("importing");

      const formData = new FormData();
      formData.append("file", file);

      // Always auto-generate student IDs
      const result = await importStudents(formData);
      if (result.success && result.data) {
        setImportResult(result.data);
        setStep("complete");
        if (result.data.created > 0) {
          onSuccess();
        }
      } else {
        toast.error(result.error || "Import failed");
        setStep("preview");
      }
    });
  };

  // Render upload step
  const renderUploadStep = () => (
    <div className="space-y-4">
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50"
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
        />

        {file ? (
          <div className="flex items-center justify-center gap-3">
            <FileSpreadsheet className="h-10 w-10 text-green-500" />
            <div className="text-left">
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setFile(null)}
              className="ml-2"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ) : (
          <>
            <Upload className="mx-auto h-12 w-12 text-muted-foreground" />
            <p className="mt-2 text-sm text-muted-foreground">
              Drag and drop a CSV or Excel file, or{" "}
              <button
                type="button"
                className="text-primary underline"
                onClick={() => fileInputRef.current?.click()}
              >
                browse
              </button>
            </p>
          </>
        )}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          Need a template?
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            if (!template) loadTemplate();
            downloadTemplate();
          }}
        >
          <Download className="mr-2 h-4 w-4" />
          Download Template
        </Button>
      </div>

      {/* Import Info */}
      <div className="space-y-2 rounded-lg border p-3 text-sm">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
          <p className="text-muted-foreground">
            Required fields: <strong className="text-foreground">first_name</strong>, <strong className="text-foreground">last_name</strong>,{" "}
            <strong className="text-foreground">date_of_birth</strong>, <strong className="text-foreground">gender</strong>
          </p>
        </div>
        <div className="flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 mt-0.5 text-green-600 shrink-0" />
          <p className="text-muted-foreground">
            <strong className="text-foreground">Student ID</strong> will be auto-generated (e.g., STU-2026-001)
          </p>
        </div>
        <div className="flex items-start gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Info className="h-4 w-4 mt-0.5 text-blue-600 shrink-0 cursor-help" />
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p>If migrating from another system, use the <strong>previous_student_id</strong> column to keep reference to old IDs.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <p className="text-muted-foreground">
            <strong className="text-foreground">previous_student_id</strong> (optional) - for IDs from previous/external systems
          </p>
        </div>
      </div>
    </div>
  );

  // Render preview step
  const renderPreviewStep = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">Preview Results</p>
          <p className="text-sm text-muted-foreground">
            {previewData?.total_rows} rows found
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="secondary" className="bg-green-100 text-green-700">
            {previewData?.valid_rows || previewData?.total_rows} valid
          </Badge>
          {(previewData?.invalid_rows || 0) > 0 && (
            <Badge variant="secondary" className="bg-red-100 text-red-700">
              {previewData?.invalid_rows} invalid
            </Badge>
          )}
        </div>
      </div>

      {previewData?.errors && previewData.errors.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm dark:border-red-900 dark:bg-red-950">
          <AlertCircle className="h-4 w-4 mt-0.5 text-red-600" />
          <p className="text-red-600">
            {previewData.errors.length} validation errors found. These rows will be skipped.
          </p>
        </div>
      )}

      <div className="h-[300px] overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[50px]">#</TableHead>
              <TableHead>First Name</TableHead>
              <TableHead>Last Name</TableHead>
              <TableHead>DOB</TableHead>
              <TableHead>Gender</TableHead>
              <TableHead>Prev. ID</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {previewData?.preview.map((row, idx) => {
              // API returns { parsed: {...}, raw: {...}, errors: [...] }
              const data = (row.parsed || row) as Record<string, unknown>;
              return (
                <TableRow key={idx}>
                  <TableCell className="font-mono text-xs">{idx + 1}</TableCell>
                  <TableCell>{String(data.first_name || "-")}</TableCell>
                  <TableCell>{String(data.last_name || "-")}</TableCell>
                  <TableCell>{String(data.date_of_birth || "-")}</TableCell>
                  <TableCell className="capitalize">{String(data.gender || "-")}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {String(data.previous_student_id || "-")}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );

  // Render importing step
  const renderImportingStep = () => (
    <div className="flex flex-col items-center justify-center py-8 space-y-4">
      <Loader2 className="h-12 w-12 animate-spin text-primary" />
      <p className="font-medium">Importing students...</p>
      <p className="text-sm text-muted-foreground">Please wait while we process your file.</p>
      <Progress value={66} className="w-[60%]" />
    </div>
  );

  // Render complete step
  const renderCompleteStep = () => (
    <div className="flex flex-col items-center justify-center py-8 space-y-4">
      <CheckCircle2 className="h-12 w-12 text-green-500" />
      <p className="font-medium">Import Complete!</p>
      <div className="flex gap-4 text-center">
        <div>
          <p className="text-2xl font-bold text-green-600">{importResult?.created}</p>
          <p className="text-sm text-muted-foreground">Created</p>
        </div>
        {(importResult?.failed || 0) > 0 && (
          <div>
            <p className="text-2xl font-bold text-red-600">{importResult?.failed}</p>
            <p className="text-sm text-muted-foreground">Failed</p>
          </div>
        )}
      </div>

      {importResult?.errors && importResult.errors.length > 0 && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 text-red-600" />
            <div>
              <p className="font-medium text-red-600 mb-2">Errors:</p>
              <ul className="text-sm list-disc pl-4 text-red-600">
                {importResult.errors.slice(0, 5).map((err, idx) => (
                  <li key={idx}>Row {err.row}: {err.error}</li>
                ))}
                {importResult.errors.length > 5 && (
                  <li>... and {importResult.errors.length - 5} more</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import Students</DialogTitle>
          <DialogDescription>
            Upload a CSV or Excel file to import multiple students at once.
          </DialogDescription>
        </DialogHeader>

        {step === "upload" && renderUploadStep()}
        {step === "preview" && renderPreviewStep()}
        {step === "importing" && renderImportingStep()}
        {step === "complete" && renderCompleteStep()}

        <DialogFooter>
          {step === "upload" && (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={handlePreview} disabled={!file || isPending}>
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Preview"
                )}
              </Button>
            </>
          )}

          {step === "preview" && (
            <>
              <Button variant="outline" onClick={() => setStep("upload")}>
                Back
              </Button>
              <Button onClick={handleImport} disabled={isPending}>
                Import {previewData?.total_rows} Students
              </Button>
            </>
          )}

          {step === "complete" && (
            <Button onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
