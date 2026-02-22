"use client";

import { useState, useRef, useTransition } from "react";
import {
  Upload,
  FileSpreadsheet,
  Download,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
} from "lucide-react";
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
  downloadImportTemplate,
  previewStaffImport,
  importStaff,
  type StaffImportPreviewResult,
  type StaffImportResult,
} from "@/actions/staff.action";

interface ImportStaffDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type ImportStep = "upload" | "preview" | "importing" | "complete";

export function ImportStaffDialog({
  open,
  onOpenChange,
  onSuccess,
}: ImportStaffDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [step, setStep] = useState<ImportStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<StaffImportPreviewResult | null>(null);
  const [importResult, setImportResult] = useState<StaffImportResult | null>(null);
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

  // Download template
  const handleDownloadTemplate = async () => {
    const result = await downloadImportTemplate();
    if (result.success && result.data) {
      const url = window.URL.createObjectURL(result.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "staff_import_template.csv";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      toast.success("Template downloaded");
    } else {
      toast.error(result.error || "Failed to download template");
    }
  };

  // Handle file selection
  const handleFileSelect = (selectedFile: File) => {
    const validTypes = [
      "text/csv",
      "application/vnd.ms-excel",
    ];

    if (!validTypes.includes(selectedFile.type) && !selectedFile.name.endsWith(".csv")) {
      toast.error("Please upload a CSV file");
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

      const result = await previewStaffImport(formData);
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

      const result = await importStaff(formData);
      if (result.success && result.data) {
        setImportResult(result.data);
        setStep("complete");
        if (result.data.success > 0) {
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
          accept=".csv"
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
              Drag and drop a CSV file, or{" "}
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
        <span className="text-muted-foreground">Need a template?</span>
        <Button variant="outline" size="sm" onClick={handleDownloadTemplate}>
          <Download className="mr-2 h-4 w-4" />
          Download Template
        </Button>
      </div>

      {/* Import Info */}
      <div className="space-y-2 rounded-lg border p-3 text-sm">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
          <p className="text-muted-foreground">
            Required fields: <strong className="text-foreground">first_name</strong>,{" "}
            <strong className="text-foreground">last_name</strong>,{" "}
            <strong className="text-foreground">email</strong>,{" "}
            <strong className="text-foreground">phone</strong>,{" "}
            <strong className="text-foreground">gender</strong>,{" "}
            <strong className="text-foreground">job_title</strong>,{" "}
            <strong className="text-foreground">employment_date</strong>
          </p>
        </div>
        <div className="flex items-start gap-2">
          <CheckCircle2 className="h-4 w-4 mt-0.5 text-green-600 shrink-0" />
          <p className="text-muted-foreground">
            <strong className="text-foreground">Staff ID</strong> will be auto-generated
          </p>
        </div>
      </div>
    </div>
  );

  // Render preview step
  const renderPreviewStep = () => (
    <div className="space-y-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium">Preview Results</p>
          <p className="text-sm text-muted-foreground">
            {previewData?.total_rows} rows found
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="secondary" className="bg-green-100 text-green-700">
            {previewData?.valid_rows} valid
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
              <TableHead className="whitespace-nowrap">Name</TableHead>
              <TableHead className="whitespace-nowrap">Email</TableHead>
              <TableHead className="whitespace-nowrap">Job Title</TableHead>
              <TableHead className="whitespace-nowrap">Type</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {previewData?.preview.map((row) => (
              <TableRow key={row.row}>
                <TableCell className="font-mono text-xs">{row.row}</TableCell>
                <TableCell className="whitespace-nowrap">{row.parsed.first_name} {row.parsed.last_name}</TableCell>
                <TableCell className="whitespace-nowrap">{row.parsed.email || "-"}</TableCell>
                <TableCell className="whitespace-nowrap">{row.parsed.job_title || "-"}</TableCell>
                <TableCell className="whitespace-nowrap capitalize">
                  {row.parsed.staff_type?.replace("_", " ") || "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );

  // Render importing step
  const renderImportingStep = () => (
    <div className="flex flex-col items-center justify-center py-8 space-y-4">
      <Loader2 className="h-12 w-12 animate-spin text-primary" />
      <p className="font-medium">Importing staff...</p>
      <p className="text-sm text-muted-foreground">
        Please wait while we process your file.
      </p>
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
          <p className="text-2xl font-bold text-green-600">{importResult?.success}</p>
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
        <div className="mt-4 w-full rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 text-red-600 shrink-0" />
            <div className="flex-1">
              <p className="font-medium text-red-600 mb-2">Errors:</p>
              <ul className="text-sm list-disc pl-4 text-red-600 max-h-32 overflow-y-auto">
                {importResult.errors.slice(0, 10).map((err, idx) => (
                  <li key={idx}>
                    Row {err.row}: {err.error}
                  </li>
                ))}
                {importResult.errors.length > 10 && (
                  <li>... and {importResult.errors.length - 10} more</li>
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
          <DialogTitle>Import Staff</DialogTitle>
          <DialogDescription>
            Upload a CSV file to import multiple staff members at once.
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
              <Button
                onClick={handleImport}
                disabled={isPending || previewData?.valid_rows === 0}
              >
                Import {previewData?.valid_rows} Staff
              </Button>
            </>
          )}

          {step === "complete" && (
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
