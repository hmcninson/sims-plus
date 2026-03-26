"use client";

import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSpreadsheet,
  Loader2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import {
  previewCSSPSImport,
  executeCSSPSImport,
  getAdmissionPeriods,
} from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type { CSSPSPreviewResponse, CSSPSPreviewRow, CSSPSImportResponse } from "@/types/admissions.type";
import type { Class } from "@/types";

// Standard CSSPS fields that must be mapped
const STANDARD_FIELDS = [
  { key: "index_number", label: "Index Number", required: true },
  { key: "first_name", label: "First Name", required: true },
  { key: "last_name", label: "Last Name", required: true },
  { key: "other_names", label: "Other Names", required: false },
  { key: "gender", label: "Gender", required: true },
  { key: "date_of_birth", label: "Date of Birth", required: false },
  { key: "programme", label: "Programme", required: true },
  { key: "aggregate", label: "BECE Aggregate", required: false },
  { key: "jhs_school", label: "JHS School", required: false },
  { key: "jhs_district", label: "JHS District", required: false },
  { key: "region", label: "Region", required: false },
  { key: "parent_name", label: "Parent Name", required: false },
  { key: "parent_phone", label: "Parent Phone", required: false },
  { key: "residential_status", label: "Residential Status", required: false },
  { key: "house", label: "House", required: false },
] as const;

type WizardStep = "upload" | "mapping" | "programme" | "preview" | "import";

const STEPS: { key: WizardStep; label: string; number: number }[] = [
  { key: "upload", label: "Upload", number: 1 },
  { key: "mapping", label: "Column Mapping", number: 2 },
  { key: "programme", label: "Programme Mapping", number: 3 },
  { key: "preview", label: "Preview", number: 4 },
  { key: "import", label: "Import", number: 5 },
];

// Try to auto-detect column mappings from headers
function autoDetectMappings(
  headers: string[]
): Record<string, string> {
  const mappings: Record<string, string> = {};
  const lowerHeaders = headers.map((h) => h.toLowerCase().trim());

  const fieldPatterns: Record<string, string[]> = {
    index_number: ["index number", "index_number", "index no", "indexno", "bece index"],
    first_name: ["first name", "first_name", "firstname", "given name"],
    last_name: ["last name", "last_name", "lastname", "surname", "family name"],
    other_names: ["other names", "other_names", "middle name", "middle_name", "othernames"],
    gender: ["gender", "sex"],
    date_of_birth: ["date of birth", "date_of_birth", "dob", "birth date", "birthdate"],
    programme: ["programme", "program", "course", "shs programme"],
    aggregate: ["aggregate", "bece aggregate", "total aggregate"],
    jhs_school: ["jhs school", "jhs_school", "previous school", "jhs"],
    jhs_district: ["jhs district", "jhs_district", "district"],
    region: ["region", "home region"],
    parent_name: ["parent name", "parent_name", "guardian name", "guardian"],
    parent_phone: ["parent phone", "parent_phone", "guardian phone", "phone", "contact"],
    residential_status: ["residential status", "residential_status", "boarding/day", "boarding status", "residence"],
    house: ["house", "school house", "assigned house"],
  };

  for (const [field, patterns] of Object.entries(fieldPatterns)) {
    for (const pattern of patterns) {
      const idx = lowerHeaders.findIndex((h) => h === pattern || h.includes(pattern));
      if (idx !== -1) {
        mappings[field] = headers[idx];
        break;
      }
    }
  }

  return mappings;
}

export function CSSPSUpload() {
  const [step, setStep] = useState<WizardStep>("upload");
  const [isPending, startTransition] = useTransition();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 1: File upload
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  // Step 2: Column mapping
  const [detectedHeaders, setDetectedHeaders] = useState<string[]>([]);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});

  // Step 3: Programme mapping
  const [detectedProgrammes, setDetectedProgrammes] = useState<string[]>([]);
  const [programmeMapping, setProgrammeMapping] = useState<Record<string, string>>({});
  const [periodId, setPeriodId] = useState("");
  const [classes, setClasses] = useState<Class[]>([]);
  const [periods, setPeriods] = useState<Array<{ id: string; name: string }>>([]);

  // Step 4: Preview
  const [preview, setPreview] = useState<CSSPSPreviewResponse | null>(null);

  // Step 5: Import results
  const [importResult, setImportResult] = useState<CSSPSImportResponse | null>(null);

  // Load classes and periods
  useEffect(() => {
    async function loadLookups() {
      const [classResult, periodResult] = await Promise.all([
        getClasses(),
        getAdmissionPeriods(),
      ]);
      if (classResult.success) {
        setClasses(classResult.data);
      }
      if (periodResult.success) {
        setPeriods(
          periodResult.data.items.map((p) => ({ id: p.id, name: p.name }))
        );
      }
    }
    loadLookups();
  }, []);

  // File drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  }, []);

  function validateAndSetFile(f: File) {
    const validTypes = [
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ];
    const validExtensions = [".csv", ".xls", ".xlsx"];
    const extension = f.name.substring(f.name.lastIndexOf(".")).toLowerCase();

    if (!validTypes.includes(f.type) && !validExtensions.includes(extension)) {
      toast.error("Please upload a CSV or Excel file (.csv, .xls, .xlsx)");
      return;
    }

    if (f.size > 5 * 1024 * 1024) {
      toast.error("File size must be less than 5MB");
      return;
    }

    setFile(f);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0];
    if (selected) {
      validateAndSetFile(selected);
    }
  }

  // Step transitions
  function handleUploadNext() {
    if (!file) {
      toast.error("Please select a file first");
      return;
    }

    // Parse the file to detect headers via preview endpoint
    startTransition(async () => {
      const formData = new FormData();
      formData.append("file", file);
      // Send with empty mapping to detect columns
      formData.append("column_mapping", JSON.stringify({}));

      const result = await previewCSSPSImport(formData);
      if (result.success) {
        const headers = result.data.detected_columns;
        setDetectedHeaders(headers);
        const autoMapped = autoDetectMappings(headers);
        setColumnMapping(autoMapped);

        // Detect unique programmes from rows
        const programmes = new Set<string>();
        for (const row of result.data.rows) {
          if (row.programme) {
            programmes.add(row.programme);
          }
        }
        setDetectedProgrammes(Array.from(programmes).sort());
        setPreview(result.data);
        setStep("mapping");
      } else {
        toast.error(result.error);
      }
    });
  }

  function handleMappingNext() {
    // Validate required mappings
    const missing = STANDARD_FIELDS.filter(
      (f) => f.required && !columnMapping[f.key]
    );
    if (missing.length > 0) {
      toast.error(
        `Please map required fields: ${missing.map((f) => f.label).join(", ")}`
      );
      return;
    }
    setStep("programme");
  }

  function handleProgrammeNext() {
    if (!periodId) {
      toast.error("Please select an admission period");
      return;
    }

    // Validate all programmes are mapped
    const unmapped = detectedProgrammes.filter((p) => !programmeMapping[p]);
    if (unmapped.length > 0) {
      toast.error(
        `Please map all programmes. Unmapped: ${unmapped.join(", ")}`
      );
      return;
    }

    // Re-run preview with proper mappings
    startTransition(async () => {
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("column_mapping", JSON.stringify(columnMapping));

      const result = await previewCSSPSImport(formData);
      if (result.success) {
        setPreview(result.data);
        setStep("preview");
      } else {
        toast.error(result.error);
      }
    });
  }

  function handleImport() {
    startTransition(async () => {
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("admission_period_id", periodId);
      formData.append("column_mapping", JSON.stringify(columnMapping));
      formData.append("programme_to_class_mapping", JSON.stringify(programmeMapping));

      const result = await executeCSSPSImport(formData);
      if (result.success) {
        setImportResult(result.data);
        setStep("import");
        toast.success(`Imported ${result.data.imported} students`);
      } else {
        toast.error(result.error);
      }
    });
  }

  function handleReset() {
    setStep("upload");
    setFile(null);
    setDetectedHeaders([]);
    setColumnMapping({});
    setDetectedProgrammes([]);
    setProgrammeMapping({});
    setPeriodId("");
    setPreview(null);
    setImportResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  const currentStepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      <div className="hidden md:flex items-center gap-2">
        {STEPS.map((s, idx) => {
          const isActive = s.key === step;
          const isCompleted = idx < currentStepIndex;
          return (
            <div key={s.key} className="flex items-center gap-2">
              {idx > 0 && (
                <div
                  className={`h-px w-8 ${
                    isCompleted ? "bg-primary" : "bg-border"
                  }`}
                />
              )}
              <div className="flex items-center gap-2">
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : isCompleted
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {isCompleted ? <Check className="h-3 w-3" /> : s.number}
                </div>
                <span
                  className={`text-sm ${
                    isActive ? "font-medium" : "text-muted-foreground"
                  }`}
                >
                  {s.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Mobile step indicator */}
      <div className="md:hidden flex items-center justify-center gap-1">
        {STEPS.map((s, idx) => {
          const isActive = s.key === step;
          const isCompleted = idx < currentStepIndex;
          return (
            <div key={s.key} className="flex flex-col items-center gap-1">
              {idx > 0 && (
                <div
                  className={`h-px w-6 ${
                    isCompleted ? "bg-primary" : "bg-border"
                  }`}
                  style={{ position: "absolute", left: -12 }}
                />
              )}
              <div
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-medium ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : isCompleted
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {isCompleted ? <Check className="h-3 w-3" /> : s.number}
              </div>
              <span
                className={`text-[10px] max-w-[60px] text-center ${
                  isActive ? "font-medium" : "text-muted-foreground"
                }`}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* Step 1: Upload */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Upload CSSPS File</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
                dragOver
                  ? "border-primary bg-primary/5"
                  : file
                    ? "border-green-500 bg-green-50 dark:bg-green-950"
                    : "border-border hover:border-primary/50"
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={handleFileChange}
                className="hidden"
              />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <FileSpreadsheet className="h-10 w-10 text-green-600 dark:text-green-400" />
                  <p className="font-medium text-sm">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFile(null);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                  >
                    <X className="mr-1 h-3 w-3" />
                    Remove
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="h-10 w-10 text-muted-foreground" />
                  <p className="font-medium text-sm">
                    Drag and drop your CSSPS file here
                  </p>
                  <p className="text-xs text-muted-foreground">
                    or click to browse. Accepts CSV, XLS, XLSX (max 5MB)
                  </p>
                </div>
              )}
            </div>

            <div className="flex justify-end">
              <Button
                onClick={handleUploadNext}
                disabled={!file || isPending}
              >
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ChevronRight className="mr-2 h-4 w-4" />
                )}
                Next: Map Columns
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Column Mapping */}
      {step === "mapping" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Column Mapping</CardTitle>
            <p className="text-sm text-muted-foreground">
              Map the columns from your file to the standard CSSPS fields.
              Auto-detected mappings are pre-filled.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[200px]">Standard Field</TableHead>
                    <TableHead>File Column</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {STANDARD_FIELDS.map((field) => (
                    <TableRow key={field.key}>
                      <TableCell className="font-medium text-sm">
                        {field.label}
                        {field.required && (
                          <span className="text-destructive ml-1">*</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Select
                          value={columnMapping[field.key] ?? "__none__"}
                          onValueChange={(val) => {
                            setColumnMapping((prev) => ({
                              ...prev,
                              [field.key]: val === "__none__" ? "" : val,
                            }));
                          }}
                        >
                          <SelectTrigger className="w-full md:w-[250px]">
                            <SelectValue placeholder="Select column" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__none__">
                              -- Not mapped --
                            </SelectItem>
                            {detectedHeaders.map((h) => (
                              <SelectItem key={h} value={h}>
                                {h}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="flex justify-between">
              <Button
                variant="outline"
                onClick={() => setStep("upload")}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button onClick={handleMappingNext}>
                <ChevronRight className="mr-2 h-4 w-4" />
                Next: Map Programmes
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Programme Mapping */}
      {step === "programme" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Programme Mapping</CardTitle>
            <p className="text-sm text-muted-foreground">
              Map each detected programme name to a class in your school.
              Select the admission period these placements belong to.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Period selector */}
            <div className="space-y-2">
              <Label>Admission Period <span className="text-destructive">*</span></Label>
              <Select value={periodId} onValueChange={setPeriodId}>
                <SelectTrigger className="w-full md:w-[350px]">
                  <SelectValue placeholder="Select admission period" />
                </SelectTrigger>
                <SelectContent>
                  {periods.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Programme to class mapping */}
            {detectedProgrammes.length > 0 ? (
              <div className="rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[250px]">Programme (from file)</TableHead>
                      <TableHead>Target Class</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {detectedProgrammes.map((prog) => (
                      <TableRow key={prog}>
                        <TableCell className="font-medium text-sm">
                          {prog}
                        </TableCell>
                        <TableCell>
                          <Select
                            value={programmeMapping[prog] ?? "__none__"}
                            onValueChange={(val) => {
                              setProgrammeMapping((prev) => ({
                                ...prev,
                                [prog]: val === "__none__" ? "" : val,
                              }));
                            }}
                          >
                            <SelectTrigger className="w-full md:w-[300px]">
                              <SelectValue placeholder="Select class" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="__none__">
                                -- Not mapped --
                              </SelectItem>
                              {classes.map((c) => (
                                <SelectItem key={c.id} value={c.id}>
                                  {c.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <AlertTriangle className="h-8 w-8 mb-2" />
                <p className="text-sm">No programmes detected in the file.</p>
                <p className="text-xs">
                  Check your column mapping for the Programme field.
                </p>
              </div>
            )}

            <div className="flex justify-between">
              <Button
                variant="outline"
                onClick={() => setStep("mapping")}
              >
                <ChevronLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button
                onClick={handleProgrammeNext}
                disabled={isPending}
              >
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ChevronRight className="mr-2 h-4 w-4" />
                )}
                Next: Preview
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Preview */}
      {step === "preview" && preview && (
        <div className="space-y-4">
          {/* Stats cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{preview.total_rows}</p>
                    <p className="text-xs text-muted-foreground">Total Rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                  <div>
                    <p className="text-2xl font-bold">{preview.valid_rows}</p>
                    <p className="text-xs text-muted-foreground">Valid Rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                  <div>
                    <p className="text-2xl font-bold">{preview.error_rows}</p>
                    <p className="text-xs text-muted-foreground">Invalid Rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-8 w-8 text-amber-600 dark:text-amber-400" />
                  <div>
                    <p className="text-2xl font-bold">
                      {preview.total_rows - preview.valid_rows - preview.error_rows}
                    </p>
                    <p className="text-xs text-muted-foreground">Skipped</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Preview table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Preview ({preview.rows.length} sample rows)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[60px]">Row</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Index No.</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead className="hidden sm:table-cell">Gender</TableHead>
                      <TableHead className="hidden md:table-cell">Programme</TableHead>
                      <TableHead className="hidden lg:table-cell">Errors</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.rows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                          No rows to preview
                        </TableCell>
                      </TableRow>
                    ) : (
                      preview.rows.map((row) => (
                        <TableRow
                          key={row.row_number}
                          className={
                            row.errors.length > 0
                              ? "bg-red-50 dark:bg-red-950/30"
                              : ""
                          }
                        >
                          <TableCell className="text-xs">{row.row_number}</TableCell>
                          <TableCell>
                            {row.errors.length === 0 ? (
                              <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                            ) : (
                              <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
                            )}
                          </TableCell>
                          <TableCell className="text-sm">
                            {row.index_number ?? "--"}
                          </TableCell>
                          <TableCell className="text-sm">
                            {[row.first_name, row.last_name]
                              .filter(Boolean)
                              .join(" ") || "--"}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell text-sm">
                            {row.gender ?? "--"}
                          </TableCell>
                          <TableCell className="hidden md:table-cell text-sm">
                            {row.programme ?? "--"}
                          </TableCell>
                          <TableCell className="hidden lg:table-cell">
                            {row.errors.length > 0 && (
                              <div className="space-y-0.5">
                                {row.errors.map((err, i) => (
                                  <p
                                    key={i}
                                    className="text-xs text-red-600 dark:text-red-400"
                                  >
                                    {err}
                                  </p>
                                ))}
                              </div>
                            )}
                          </TableCell>
                        </TableRow>
                      ))
                    )}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {preview.error_rows > 0 && (
            <Card className="border-amber-200 dark:border-amber-800">
              <CardContent className="flex items-center gap-3 py-4">
                <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0" />
                <p className="text-sm">
                  <strong>{preview.error_rows}</strong> row{preview.error_rows !== 1 ? "s" : ""} have
                  validation errors and will be skipped during import.
                  Only the <strong>{preview.valid_rows}</strong> valid row{preview.valid_rows !== 1 ? "s" : ""} will
                  be imported.
                </p>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => setStep("programme")}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button
              onClick={handleImport}
              disabled={isPending || preview.valid_rows === 0}
            >
              {isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Download className="mr-2 h-4 w-4" />
              )}
              Import {preview.valid_rows} Student{preview.valid_rows !== 1 ? "s" : ""}
            </Button>
          </div>
        </div>
      )}

      {/* Step 5: Import Results */}
      {step === "import" && importResult && (
        <div className="space-y-4">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-8 w-8 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold">{importResult.total_rows}</p>
                    <p className="text-xs text-muted-foreground">Total Rows</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
                  <div>
                    <p className="text-2xl font-bold">{importResult.imported}</p>
                    <p className="text-xs text-muted-foreground">Imported</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-8 w-8 text-amber-600 dark:text-amber-400" />
                  <div>
                    <p className="text-2xl font-bold">{importResult.skipped}</p>
                    <p className="text-xs text-muted-foreground">Skipped</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                  <div>
                    <p className="text-2xl font-bold">{importResult.errors}</p>
                    <p className="text-xs text-muted-foreground">Errors</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Success message */}
          {importResult.imported > 0 && (
            <Card className="border-green-200 dark:border-green-800">
              <CardContent className="flex items-center gap-3 py-4">
                <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400 shrink-0" />
                <div>
                  <p className="font-semibold text-green-700 dark:text-green-300">
                    Import Successful
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {importResult.imported} student{importResult.imported !== 1 ? "s" : ""} have
                    been created as applications in the selected admission period.
                    You can view them in the Applications list.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error details */}
          {importResult.results.filter((r) => r.status === "error").length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base text-red-700 dark:text-red-400">
                  Import Errors
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[60px]">Row</TableHead>
                        <TableHead>Index No.</TableHead>
                        <TableHead>Error</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {importResult.results
                        .filter((r) => r.status === "error")
                        .map((r) => (
                          <TableRow key={r.row_number}>
                            <TableCell className="text-xs">{r.row_number}</TableCell>
                            <TableCell className="text-sm">{r.index_number}</TableCell>
                            <TableCell className="text-sm text-red-600 dark:text-red-400">
                              {r.error}
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="flex justify-end">
            <Button onClick={handleReset}>
              <Upload className="mr-2 h-4 w-4" />
              Import Another File
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
