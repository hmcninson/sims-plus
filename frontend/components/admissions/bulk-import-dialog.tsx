"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  Upload,
  FileSpreadsheet,
  AlertCircle,
  CheckCircle2,
  Loader2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { bulkImportInquiries } from "@/actions/inquiries.action";
import type { BulkInquiryImportRow, BulkImportResponse } from "@/types/inquiry.type";

interface BulkImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type ImportState = "upload" | "preview" | "importing" | "done";

export function BulkImportDialog({
  open,
  onOpenChange,
  onSuccess,
}: BulkImportDialogProps) {
  const [state, setState] = useState<ImportState>("upload");
  const [rows, setRows] = useState<BulkInquiryImportRow[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [result, setResult] = useState<BulkImportResponse | null>(null);

  const resetState = useCallback(() => {
    setState("upload");
    setRows([]);
    setParseErrors([]);
    setResult(null);
  }, []);

  function handleClose(isOpen: boolean) {
    if (!isOpen) resetState();
    onOpenChange(isOpen);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      parseCSV(text);
    };
    reader.readAsText(file);
  }

  function parseCSV(text: string) {
    const lines = text.split("\n").filter((line) => line.trim());
    if (lines.length < 2) {
      setParseErrors(["File must have a header row and at least one data row."]);
      return;
    }

    const headers = lines[0].split(",").map((h) => h.trim().toLowerCase().replace(/['"]/g, ""));
    const requiredHeaders = ["first_name", "last_name", "guardian_name", "guardian_phone"];
    const missing = requiredHeaders.filter((h) => !headers.includes(h));

    if (missing.length > 0) {
      setParseErrors([
        `Missing required columns: ${missing.join(", ")}. Required: first_name, last_name, guardian_name, guardian_phone`,
      ]);
      return;
    }

    const errors: string[] = [];
    const parsed: BulkInquiryImportRow[] = [];

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",").map((v) => v.trim().replace(/^['"]|['"]$/g, ""));
      if (values.every((v) => !v)) continue; // skip empty rows

      const row: Record<string, string> = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx] || "";
      });

      if (!row.first_name || !row.last_name || !row.guardian_name || !row.guardian_phone) {
        errors.push(`Row ${i}: Missing required field(s)`);
        continue;
      }

      parsed.push({
        first_name: row.first_name,
        last_name: row.last_name,
        guardian_name: row.guardian_name,
        guardian_phone: row.guardian_phone,
        guardian_email: row.guardian_email || undefined,
        source: (row.source as BulkInquiryImportRow["source"]) || undefined,
        notes: row.notes || undefined,
      });
    }

    if (parsed.length === 0) {
      setParseErrors(["No valid rows found in file."]);
      return;
    }

    if (parsed.length > 200) {
      setParseErrors([`Too many rows (${parsed.length}). Maximum is 200 per import.`]);
      return;
    }

    setParseErrors(errors);
    setRows(parsed);
    setState("preview");
  }

  async function handleImport() {
    setState("importing");
    const importResult = await bulkImportInquiries({ rows });
    if (importResult.success && importResult.data) {
      setResult(importResult.data);
      setState("done");
      if (importResult.data.imported > 0) {
        onSuccess();
      }
    } else {
      toast.error(importResult.error || "Import failed");
      setState("preview");
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Bulk Import Inquiries</DialogTitle>
          <DialogDescription>
            Upload a CSV file with inquiry data. Required columns: first_name, last_name,
            guardian_name, guardian_phone. Optional: guardian_email, source, notes.
          </DialogDescription>
        </DialogHeader>

        {/* Upload State */}
        {state === "upload" && (
          <div className="space-y-4">
            <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-8 gap-3">
              <FileSpreadsheet className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Select a CSV file to import
              </p>
              <label htmlFor="csv-upload">
                <Button variant="outline" asChild>
                  <span>
                    <Upload className="mr-2 h-4 w-4" />
                    Choose File
                  </span>
                </Button>
              </label>
              <input
                id="csv-upload"
                type="file"
                accept=".csv"
                className="sr-only"
                onChange={handleFileChange}
              />
            </div>

            {parseErrors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <ul className="list-disc pl-4 text-sm">
                    {parseErrors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Preview State */}
        {state === "preview" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {rows.length} row{rows.length !== 1 ? "s" : ""} ready to import
              </p>
              <Button variant="ghost" size="sm" onClick={resetState}>
                <X className="mr-1 h-4 w-4" />
                Clear
              </Button>
            </div>

            {parseErrors.length > 0 && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {parseErrors.length} row{parseErrors.length !== 1 ? "s" : ""} skipped
                  due to errors.
                </AlertDescription>
              </Alert>
            )}

            <div className="max-h-[300px] overflow-auto border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Guardian</TableHead>
                    <TableHead className="hidden sm:table-cell">Phone</TableHead>
                    <TableHead className="hidden md:table-cell">Source</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.slice(0, 50).map((row, i) => (
                    <TableRow key={i}>
                      <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                      <TableCell>
                        {row.first_name} {row.last_name}
                      </TableCell>
                      <TableCell>{row.guardian_name}</TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {row.guardian_phone}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {row.source || "walk_in"}
                      </TableCell>
                    </TableRow>
                  ))}
                  {rows.length > 50 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-sm text-muted-foreground">
                        ...and {rows.length - 50} more rows
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={resetState}>
                Back
              </Button>
              <Button onClick={handleImport}>
                Import {rows.length} Row{rows.length !== 1 ? "s" : ""}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Importing State */}
        {state === "importing" && (
          <div className="flex flex-col items-center justify-center py-12 gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">
              Importing {rows.length} inquiries...
            </p>
          </div>
        )}

        {/* Done State */}
        {state === "done" && result && (
          <div className="space-y-4">
            <div className="flex flex-col items-center py-6 gap-3">
              <CheckCircle2 className="h-10 w-10 text-green-500" />
              <h3 className="text-lg font-semibold">Import Complete</h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="text-center p-3 rounded-lg bg-green-50 dark:bg-green-950">
                <p className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {result.imported}
                </p>
                <p className="text-sm text-muted-foreground">Imported</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-yellow-50 dark:bg-yellow-950">
                <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-300">
                  {result.skipped}
                </p>
                <p className="text-sm text-muted-foreground">Skipped</p>
              </div>
              <div className="text-center p-3 rounded-lg bg-red-50 dark:bg-red-950">
                <p className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {result.errors.length}
                </p>
                <p className="text-sm text-muted-foreground">Errors</p>
              </div>
            </div>

            {result.errors.length > 0 && (
              <div className="max-h-[200px] overflow-auto">
                <ul className="space-y-1 text-sm">
                  {result.errors.map((err, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <Badge variant="outline" className="shrink-0 bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800">
                        Row {err.row}
                      </Badge>
                      <span className="text-muted-foreground">{err.error}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <DialogFooter>
              <Button onClick={() => handleClose(false)}>Done</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
