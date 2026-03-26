"use client";

import { useRef, useState, useTransition } from "react";
import {
  CheckCircle2,
  Download,
  FileUp,
  Loader2,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { previewUserImport, importUsers } from "@/actions/users.action";
import type { UserImportResult } from "@/types";

type Step = "upload" | "preview" | "importing" | "result";

const ROLE_LABELS: Record<string, string> = {
  school_admin: "School Admin",
  academic_head: "Academic Head",
  finance_officer: "Finance Officer",
  hr_officer: "HR Officer",
  teacher: "Teacher",
  house_parent: "House Parent",
};

interface ImportUsersDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ImportUsersDialog({ open, onClose, onSuccess }: ImportUsersDialogProps) {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<UserImportResult | null>(null);
  const [importResult, setImportResult] = useState<UserImportResult | null>(null);
  const [isPending, startTransition] = useTransition();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = () => {
    setStep("upload");
    setFile(null);
    setPreviewData(null);
    setImportResult(null);
  };

  const handleClose = () => {
    // If import was successful, notify parent to refresh
    if (importResult && importResult.created > 0) {
      onSuccess();
    }
    resetState();
    onClose();
  };

  const handleDownloadTemplate = () => {
    // Build template client-side to avoid an extra server round-trip
    const csv = [
      "email,first_name,last_name,role,phone",
      "john.doe@example.com,John,Doe,teacher,+233241234567",
      "jane.smith@example.com,Jane,Smith,finance_officer,",
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "user_import_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected) {
      if (!selected.name.toLowerCase().endsWith(".csv")) {
        toast.error("Invalid file type", {
          description: "Please upload a CSV file.",
        });
        return;
      }
      if (selected.size > 1_048_576) {
        toast.error("File too large", {
          description: "Maximum file size is 1MB.",
        });
        return;
      }
      setFile(selected);
    }
  };

  const handlePreview = () => {
    if (!file) return;

    startTransition(async () => {
      const formData = new FormData();
      formData.append("file", file);

      const result = await previewUserImport(formData);

      if (result.success && result.data) {
        setPreviewData(result.data);
        setStep("preview");
      } else {
        toast.error("Preview failed", {
          description: result.error,
        });
      }
    });
  };

  const handleImport = () => {
    if (!file) return;

    setStep("importing");
    startTransition(async () => {
      const formData = new FormData();
      formData.append("file", file);

      const result = await importUsers(formData);

      if (result.success && result.data) {
        setImportResult(result.data);
        setStep("result");
      } else {
        toast.error("Import failed", {
          description: result.error,
        });
        // Go back to preview so user can retry
        setStep("preview");
      }
    });
  };

  const handleDownloadCredentials = () => {
    if (!importResult?.credentials) return;

    const csv = [
      "email,temporary_password",
      ...importResult.credentials.map(
        (c) => `${c.email},${c.temporary_password}`,
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `user_credentials_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => { if (!isOpen) handleClose(); }}>
      <DialogContent className="max-w-2xl max-sm:max-w-full max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {step === "upload" && "Import Users from CSV"}
            {step === "preview" && "Preview Import"}
            {step === "importing" && "Importing Users..."}
            {step === "result" && "Import Complete"}
          </DialogTitle>
          {step === "upload" && (
            <DialogDescription>
              Upload a CSV file with user details. Maximum 200 rows per import.
            </DialogDescription>
          )}
        </DialogHeader>

        {/* Step 1: Upload */}
        {step === "upload" && (
          <div className="space-y-4">
            <Button variant="link" className="px-0 h-auto" onClick={handleDownloadTemplate}>
              <Download className="mr-2 h-4 w-4" />
              Download CSV template
            </Button>

            <div
              className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileSelect}
              />
              <FileUp className="mx-auto h-10 w-10 text-muted-foreground mb-3" />
              {file ? (
                <div>
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-medium">Click to select a CSV file</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    or drag and drop here
                  </p>
                </div>
              )}
            </div>

            <div className="text-xs text-muted-foreground space-y-1 bg-muted/50 rounded-md p-3">
              <p className="font-medium">CSV format:</p>
              <p>Required columns: email, first_name, last_name, role</p>
              <p>Optional columns: phone</p>
              <p>
                Valid roles: school_admin, academic_head, finance_officer,
                hr_officer, teacher, house_parent
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handlePreview} disabled={!file || isPending}>
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                <Upload className="mr-2 h-4 w-4" />
                Preview Import
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 2: Preview */}
        {step === "preview" && previewData && (
          <div className="space-y-4">
            <div className="flex gap-2 flex-wrap">
              <Badge variant="outline">{previewData.total} total</Badge>
              <Badge variant="default" className="bg-green-600">
                {previewData.valid} valid
              </Badge>
              {previewData.total - previewData.valid > 0 && (
                <Badge variant="destructive">
                  {previewData.total - previewData.valid} errors
                </Badge>
              )}
            </div>

            <div className="border rounded-md max-h-[50vh] overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">Row</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead className="hidden sm:table-cell">Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Role</TableHead>
                    <TableHead className="w-16 text-center">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewData.preview.map((row) => (
                    <TableRow
                      key={row.row_number}
                      className={row.valid ? "" : "bg-destructive/5"}
                    >
                      <TableCell className="text-muted-foreground">
                        {row.row_number}
                      </TableCell>
                      <TableCell className="font-mono text-xs">
                        {row.email}
                        <span className="sm:hidden block text-muted-foreground mt-0.5">
                          {row.first_name} {row.last_name} - {ROLE_LABELS[row.role] || row.role}
                        </span>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {row.first_name} {row.last_name}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {ROLE_LABELS[row.role] || row.role}
                      </TableCell>
                      <TableCell className="text-center">
                        {row.valid ? (
                          <CheckCircle2 className="h-4 w-4 text-green-500 mx-auto" />
                        ) : (
                          <Tooltip>
                            <TooltipTrigger>
                              <XCircle className="h-4 w-4 text-red-500 mx-auto" />
                            </TooltipTrigger>
                            <TooltipContent side="left" className="max-w-xs">
                              <ul className="text-xs space-y-0.5">
                                {row.errors.map((err, idx) => (
                                  <li key={idx}>{err}</li>
                                ))}
                              </ul>
                            </TooltipContent>
                          </Tooltip>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <DialogFooter className="flex gap-2 sm:gap-0">
              <Button variant="outline" onClick={() => setStep("upload")}>
                Back
              </Button>
              <Button
                onClick={handleImport}
                disabled={previewData.valid === 0 || isPending}
              >
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Import {previewData.valid} User{previewData.valid !== 1 ? "s" : ""}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Importing (loading state) */}
        {step === "importing" && (
          <div className="flex flex-col items-center justify-center py-12 space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Creating user accounts... This may take a moment.
            </p>
          </div>
        )}

        {/* Step 4: Result */}
        {step === "result" && importResult && (
          <div className="space-y-4">
            <div className="text-center py-4">
              <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
              <p className="mt-3 text-lg font-medium">
                {importResult.created} user{importResult.created !== 1 ? "s" : ""} imported
                successfully
              </p>
              {importResult.errors.length > 0 && (
                <p className="text-sm text-muted-foreground mt-1">
                  {importResult.errors.length} row{importResult.errors.length !== 1 ? "s" : ""} skipped
                  due to errors
                </p>
              )}
            </div>

            {importResult.credentials && importResult.credentials.length > 0 && (
              <>
                <Button
                  onClick={handleDownloadCredentials}
                  className="w-full"
                  variant="default"
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download Credentials CSV
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Save this file securely. Credentials cannot be retrieved again.
                  Users will also receive a welcome email with a password reset link.
                </p>
              </>
            )}

            <Button variant="outline" onClick={handleClose} className="w-full">
              Done
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
