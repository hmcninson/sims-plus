"use client";

import { useState, useEffect, useTransition, useMemo, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle,
  FileText,
  Info,
  Users,
  UserCircle,
  RefreshCw,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getFeeStructures, getFeeStructure, bulkGenerateInvoices, getStudentsMissingInvoices, getInvoiceSyncPreview, syncInvoicesWithFeeStructure } from "@/actions/finance.action";
import {
  getAcademicYears,
  getTerms,
  getCurrentAcademicYear,
  getCurrentTerm,
} from "@/actions/academic.action";
import { getStudent } from "@/actions/students.action";
import type { FeeStructureWithItems, AcademicYear, Term, StudentMissingInvoice, InvoiceSyncPreview, InvoiceSyncResult } from "@/types";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

interface SingleStudentInfo {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  class_name?: string;
}

export default function GenerateInvoicesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialFeeStructureId = searchParams.get("fee_structure_id");
  const singleStudentId = searchParams.get("student_id");
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingFeeStructures, setIsLoadingFeeStructures] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isScanning, setIsScanning] = useState(false);

  // Track initial load to avoid re-running effects
  const hasInitialized = useRef(false);

  // Single student mode (when coming from student profile)
  const [singleStudent, setSingleStudent] = useState<SingleStudentInfo | null>(null);

  // Missing invoices state
  const [missingStudents, setMissingStudents] = useState<StudentMissingInvoice[]>([]);
  const [selectedMissingIds, setSelectedMissingIds] = useState<Set<string>>(new Set());
  const [hasScanned, setHasScanned] = useState(false);

  // Sync with fee structure state
  const [syncPreview, setSyncPreview] = useState<InvoiceSyncPreview | null>(null);
  const [syncResult, setSyncResult] = useState<InvoiceSyncResult | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isLoadingSyncPreview, setIsLoadingSyncPreview] = useState(false);

  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [feeStructures, setFeeStructures] = useState<FeeStructureWithItems[]>([]);
  const [preloadedFeeStructure, setPreloadedFeeStructure] = useState<FeeStructureWithItems | null>(null);

  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedTerm, setSelectedTerm] = useState<string>("");
  const [selectedFeeStructure, setSelectedFeeStructure] = useState<string>(
    initialFeeStructureId || ""
  );
  const [dueDate, setDueDate] = useState<string>("");
  const [issueImmediately, setIssueImmediately] = useState(true);

  const [result, setResult] = useState<{
    created: number;
    skipped: number;
    failed: number;
    errors: { student_id: string; error: string }[];
    invoice_ids: string[];
  } | null>(null);

  // Handle fee structure change - just update state, no URL navigation
  const handleFeeStructureChange = useCallback((feeStructureId: string) => {
    setSelectedFeeStructure(feeStructureId);

    // Clear dependent state when fee structure changes
    setHasScanned(false);
    setMissingStudents([]);
    setSelectedMissingIds(new Set());
    setSyncPreview(null);
    setSyncResult(null);
    setResult(null);

    // Update URL silently using history API to avoid re-render
    const params = new URLSearchParams(window.location.search);
    if (feeStructureId) {
      params.set("fee_structure_id", feeStructureId);
    } else {
      params.delete("fee_structure_id");
    }
    const newUrl = params.toString()
      ? `${window.location.pathname}?${params.toString()}`
      : window.location.pathname;
    window.history.replaceState(null, "", newUrl);
  }, []);

  // Load initial data only once on mount
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    const loadInitialData = async () => {
      setIsLoading(true);
      try {
        // If we have a student ID (coming from student profile), fetch student info
        if (singleStudentId) {
          const studentResult = await getStudent(singleStudentId);
          if (studentResult.success && studentResult.data) {
            setSingleStudent({
              id: studentResult.data.id,
              student_id: studentResult.data.student_id,
              first_name: studentResult.data.first_name,
              last_name: studentResult.data.last_name,
              class_name: studentResult.data.class_name,
            });
          }
        }

        // If we have an initial fee structure ID, fetch it first to get its academic year/term
        let initialFeeStructureData: FeeStructureWithItems | null = null;
        if (initialFeeStructureId) {
          const fsResult = await getFeeStructure(initialFeeStructureId);
          if (fsResult.success && fsResult.data) {
            initialFeeStructureData = fsResult.data;
            setPreloadedFeeStructure(fsResult.data);
          }
        }

        const [yearsResult, termsResult, currentYear, currentTerm] =
          await Promise.all([
            getAcademicYears(),
            getTerms(),
            getCurrentAcademicYear(),
            getCurrentTerm(),
          ]);

        if (yearsResult.success && yearsResult.data) {
          setAcademicYears(yearsResult.data);
        }

        if (termsResult.success && termsResult.data) {
          setTerms(termsResult.data);
        }

        // Use fee structure's year/term if available, otherwise use current
        if (initialFeeStructureData?.academic_year_id) {
          setSelectedYear(initialFeeStructureData.academic_year_id);
        } else if (currentYear.success && currentYear.data) {
          setSelectedYear(currentYear.data.id);
        }

        if (initialFeeStructureData?.term_id) {
          setSelectedTerm(initialFeeStructureData.term_id);
        } else if (currentTerm.success && currentTerm.data) {
          setSelectedTerm(currentTerm.data.id);
        }

        // Set default due date
        if (currentTerm.success && currentTerm.data?.end_date) {
          setDueDate(currentTerm.data.end_date.split("T")[0]);
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialData();
  }, [initialFeeStructureId, singleStudentId]);

  useEffect(() => {
    if (selectedYear && !isLoading) {
      const loadFeeStructures = async () => {
        setIsLoadingFeeStructures(true);
        try {
          const params: Record<string, string> = {
            academic_year_id: selectedYear,
            is_active: "true",
          };
          if (selectedTerm) {
            params.term_id = selectedTerm;
          }

          const result = await getFeeStructures(params);
          if (result.success && result.data) {
            setFeeStructures(result.data.items);
          }
        } finally {
          setIsLoadingFeeStructures(false);
        }
      };

      loadFeeStructures();
    }
  }, [selectedYear, selectedTerm, isLoading]);

  const handleGenerate = async () => {
    if (!selectedFeeStructure) {
      toast({
        title: "Missing fee structure",
        description: "Please select a fee structure.",
        variant: "destructive",
      });
      return;
    }

    setIsGenerating(true);
    setResult(null);

    try {
      const response = await bulkGenerateInvoices({
        fee_structure_id: selectedFeeStructure,
        academic_year_id: selectedYear,
        term_id: selectedTerm,
        due_date: dueDate || undefined,
        issue_immediately: issueImmediately,
        // If single student mode, only generate for that student
        student_ids: singleStudent ? [singleStudent.id] : undefined,
      });

      if (response.success && response.data) {
        setResult(response.data);
        if (response.data.created > 0) {
          toast({
            title: "Invoices generated",
            description: `Successfully generated ${response.data.created} invoice(s).`,
          });
        }
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to generate invoices",
          variant: "destructive",
        });
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const filteredTerms = useMemo(
    () => terms.filter((t) => t.academic_year_id === selectedYear),
    [terms, selectedYear]
  );

  const selectedFeeStructureData = useMemo(
    () =>
      feeStructures.find((fs) => fs.id === selectedFeeStructure) ||
      (selectedFeeStructure === preloadedFeeStructure?.id ? preloadedFeeStructure : null),
    [feeStructures, selectedFeeStructure, preloadedFeeStructure]
  );

  // Scan for missing invoices
  const handleScanMissing = async () => {
    if (!selectedFeeStructure || !selectedYear || !selectedTerm) {
      toast({
        title: "Missing selection",
        description: "Please select a fee structure, academic year, and term.",
        variant: "destructive",
      });
      return;
    }

    setIsScanning(true);
    setMissingStudents([]);
    setSelectedMissingIds(new Set());

    try {
      const response = await getStudentsMissingInvoices({
        feeStructureId: selectedFeeStructure,
        academicYearId: selectedYear,
        termId: selectedTerm,
      });

      if (response.success && response.data) {
        setMissingStudents(response.data.students);
        setHasScanned(true);
        if (response.data.students.length === 0) {
          toast({
            title: "No missing invoices",
            description: "All eligible students have invoices for this term.",
          });
        } else {
          toast({
            title: "Scan complete",
            description: `Found ${response.data.students.length} student(s) without invoices.`,
          });
        }
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to scan for missing invoices",
          variant: "destructive",
        });
      }
    } finally {
      setIsScanning(false);
    }
  };

  // Generate invoices for selected missing students
  const handleGenerateForSelected = async () => {
    if (selectedMissingIds.size === 0) {
      toast({
        title: "No students selected",
        description: "Please select at least one student.",
        variant: "destructive",
      });
      return;
    }

    setIsGenerating(true);
    setResult(null);

    try {
      const response = await bulkGenerateInvoices({
        fee_structure_id: selectedFeeStructure,
        academic_year_id: selectedYear,
        term_id: selectedTerm,
        due_date: dueDate || undefined,
        issue_immediately: issueImmediately,
        student_ids: Array.from(selectedMissingIds),
      });

      if (response.success && response.data) {
        setResult(response.data);
        if (response.data.created > 0) {
          toast({
            title: "Invoices generated",
            description: `Successfully generated ${response.data.created} invoice(s).`,
          });
          // Remove generated students from the list
          setMissingStudents((prev) =>
            prev.filter((s) => !selectedMissingIds.has(s.id))
          );
          setSelectedMissingIds(new Set());
        }
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to generate invoices",
          variant: "destructive",
        });
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // Toggle selection for missing students
  const toggleMissingSelection = (studentId: string) => {
    setSelectedMissingIds((prev) => {
      const next = new Set(prev);
      if (next.has(studentId)) {
        next.delete(studentId);
      } else {
        next.add(studentId);
      }
      return next;
    });
  };

  const toggleAllMissing = (checked: boolean) => {
    if (checked) {
      setSelectedMissingIds(new Set(missingStudents.map((s) => s.id)));
    } else {
      setSelectedMissingIds(new Set());
    }
  };

  // Load sync preview
  const handleLoadSyncPreview = async () => {
    if (!selectedFeeStructure || !selectedYear || !selectedTerm) {
      return;
    }

    setIsLoadingSyncPreview(true);
    setSyncPreview(null);
    setSyncResult(null);

    try {
      const response = await getInvoiceSyncPreview({
        feeStructureId: selectedFeeStructure,
        academicYearId: selectedYear,
        termId: selectedTerm,
      });

      if (response.success && response.data) {
        setSyncPreview(response.data);
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to load sync preview",
          variant: "destructive",
        });
      }
    } finally {
      setIsLoadingSyncPreview(false);
    }
  };

  // Sync invoices with fee structure
  const handleSync = async () => {
    if (!selectedFeeStructure || !selectedYear || !selectedTerm) {
      toast({
        title: "Missing selection",
        description: "Please select a fee structure, academic year, and term.",
        variant: "destructive",
      });
      return;
    }

    setIsSyncing(true);
    setSyncResult(null);

    try {
      const response = await syncInvoicesWithFeeStructure({
        fee_structure_id: selectedFeeStructure,
        academic_year_id: selectedYear,
        term_id: selectedTerm,
      });

      if (response.success && response.data) {
        setSyncResult(response.data);
        if (response.data.updated > 0) {
          toast({
            title: "Invoices synced",
            description: `Successfully updated ${response.data.updated} draft invoice(s).`,
          });
        } else if (response.data.skipped > 0 && response.data.updated === 0) {
          toast({
            title: "No invoices updated",
            description: `All ${response.data.skipped} invoice(s) were skipped (already issued/paid).`,
          });
        }
        // Refresh preview
        handleLoadSyncPreview();
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to sync invoices",
          variant: "destructive",
        });
      }
    } finally {
      setIsSyncing(false);
    }
  };

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>

        {/* Form Card Skeleton */}
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-10 w-full" />
              </div>
              <div className="flex items-center space-x-2 pt-8">
                <Skeleton className="h-4 w-4" />
                <Skeleton className="h-4 w-48" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Fee Structure Preview Skeleton */}
        {initialFeeStructureId && (
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-40" />
              <Skeleton className="h-4 w-64" />
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex justify-between items-center">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-20" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Actions Skeleton */}
        <div className="flex justify-end gap-4">
          <Skeleton className="h-10 w-24" />
          <Skeleton className="h-10 w-36" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={singleStudent ? `/students/${singleStudent.id}` : "/finance/invoices"}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {singleStudent ? "Generate Invoice" : "Generate Invoices"}
          </h1>
          <p className="text-muted-foreground">
            {singleStudent
              ? `Generate invoice for ${singleStudent.first_name} ${singleStudent.last_name}`
              : "Bulk generate invoices for students"}
          </p>
        </div>
      </div>

      {/* Single Student Mode Notice */}
      {singleStudent && (
        <Alert>
          <UserCircle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="font-medium">Generating invoice for:</span>
            <span className="flex items-center gap-2">
              <Badge variant="secondary">
                {singleStudent.student_id}
              </Badge>
              <span>{singleStudent.first_name} {singleStudent.last_name}</span>
              {singleStudent.class_name && (
                <span className="text-muted-foreground">({singleStudent.class_name})</span>
              )}
            </span>
            <Link
              href="/finance/invoices/generate"
              className="text-primary hover:underline text-sm ml-auto"
            >
              Generate for multiple students instead
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {/* Selection Form */}
      <Card>
        <CardHeader>
          <CardTitle>Invoice Settings</CardTitle>
          <CardDescription>
            Configure the invoice generation parameters
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Row 1: Academic Year + Term + Fee Structure */}
          <div className="grid gap-4 grid-cols-1 md:grid-cols-[1fr_1fr_1.5fr]">
            <div className="space-y-2 min-w-0">
              <Label>Academic Year</Label>
              <Select value={selectedYear} onValueChange={setSelectedYear}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select year" />
                </SelectTrigger>
                <SelectContent>
                  {academicYears.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      <span className="flex items-center gap-2">
                        {year.name}
                        {year.is_current && (
                          <Badge variant="secondary" className="text-xs">
                            Current
                          </Badge>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 min-w-0">
              <Label>Term</Label>
              <Select value={selectedTerm} onValueChange={setSelectedTerm}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select term" />
                </SelectTrigger>
                <SelectContent>
                  {filteredTerms.map((term) => (
                    <SelectItem key={term.id} value={term.id}>
                      <span className="flex items-center gap-2">
                        {term.name}
                        {term.is_current && (
                          <Badge variant="secondary" className="text-xs">
                            Current
                          </Badge>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2 min-w-0">
              <Label>Fee Structure</Label>
              <Select
                value={selectedFeeStructure}
                onValueChange={handleFeeStructureChange}
                disabled={isLoadingFeeStructures}
              >
                <SelectTrigger className="w-full">
                  {isLoadingFeeStructures ? (
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Loading fee structures...
                    </span>
                  ) : (
                    <SelectValue placeholder="Select fee structure" />
                  )}
                </SelectTrigger>
                <SelectContent>
                  {preloadedFeeStructure && !feeStructures.some(fs => fs.id === preloadedFeeStructure.id) && (
                    <SelectItem key={preloadedFeeStructure.id} value={preloadedFeeStructure.id}>
                      {preloadedFeeStructure.name} ({formatCurrency(preloadedFeeStructure.total_amount || 0)})
                    </SelectItem>
                  )}
                  {feeStructures.map((fs) => (
                    <SelectItem key={fs.id} value={fs.id}>
                      {fs.name} ({formatCurrency(fs.total_amount || 0)})
                    </SelectItem>
                  ))}
                  {!isLoadingFeeStructures && feeStructures.length === 0 && !preloadedFeeStructure && (
                    <div className="py-2 px-2 text-sm text-muted-foreground text-center">
                      No fee structures found for this term
                    </div>
                  )}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 2: Due Date + Issue Immediately */}
          <div className="grid gap-4 grid-cols-1 md:grid-cols-[1fr_1fr_1.5fr] items-end">
            <div className="space-y-2 min-w-0">
              <Label>Due Date</Label>
              <Input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full"
              />
            </div>

            <div className="flex items-center space-x-2 md:col-span-2 pb-2">
              <Checkbox
                id="issueImmediately"
                checked={issueImmediately}
                onCheckedChange={(checked) =>
                  setIssueImmediately(checked as boolean)
                }
              />
              <Label htmlFor="issueImmediately" className="font-normal">
                Issue invoices immediately (skip draft status)
              </Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Target Students Info - Hidden in single student mode */}
      {!singleStudent && (
        <div className={`transition-all duration-300 ${selectedFeeStructureData ? "opacity-100 max-h-40" : "opacity-0 max-h-0 overflow-hidden"}`}>
          {selectedFeeStructureData && (
            <Alert className="animate-in fade-in duration-200">
              <Users className="h-4 w-4" />
              <AlertDescription className="flex flex-wrap items-center gap-x-6 gap-y-2">
                <span className="font-medium">Invoices will be generated for:</span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">Level:</span>
                  <Badge variant="outline">
                    {selectedFeeStructureData.level_category
                      ? selectedFeeStructureData.level_category.charAt(0).toUpperCase() + selectedFeeStructureData.level_category.slice(1)
                      : "All Levels"}
                  </Badge>
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">Class:</span>
                  <Badge variant="outline">
                    {selectedFeeStructureData.class_name || "All Classes"}
                  </Badge>
                </span>
                <span className="flex items-center gap-2">
                  <span className="text-muted-foreground">Student Type:</span>
                  <Badge variant="outline">
                    {selectedFeeStructureData.student_type
                      ? selectedFeeStructureData.student_type.charAt(0).toUpperCase() + selectedFeeStructureData.student_type.slice(1)
                      : "All"}
                  </Badge>
                </span>
              </AlertDescription>
            </Alert>
          )}
        </div>
      )}

      {/* Scan for Missing Invoices - Hidden in single student mode */}
      {!singleStudent && (
        <Card className={`transition-all duration-300 ${selectedFeeStructureData ? "opacity-100" : "opacity-50 pointer-events-none"}`}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Students Missing Invoices
                </CardTitle>
                <CardDescription>
                  Find students who joined after invoices were generated
                </CardDescription>
              </div>
              <Button
                variant="outline"
                onClick={handleScanMissing}
                disabled={isScanning || !selectedFeeStructure}
              >
                {isScanning && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isScanning ? "Scanning..." : "Scan for Missing"}
              </Button>
            </div>
          </CardHeader>
          {hasScanned && (
            <CardContent>
              {missingStudents.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Found {missingStudents.length} student(s) without invoices
                    </p>
                    {selectedMissingIds.size > 0 && (
                      <Button
                        size="sm"
                        onClick={handleGenerateForSelected}
                        disabled={isGenerating}
                      >
                        {isGenerating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Generate for Selected ({selectedMissingIds.size})
                      </Button>
                    )}
                  </div>
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[40px]">
                            <Checkbox
                              checked={
                                missingStudents.length > 0 &&
                                selectedMissingIds.size === missingStudents.length
                              }
                              onCheckedChange={toggleAllMissing}
                              aria-label="Select all"
                            />
                          </TableHead>
                          <TableHead>Student ID</TableHead>
                          <TableHead>Name</TableHead>
                          <TableHead>Class</TableHead>
                          <TableHead>Section</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {missingStudents.map((student) => (
                          <TableRow key={student.id}>
                            <TableCell>
                              <Checkbox
                                checked={selectedMissingIds.has(student.id)}
                                onCheckedChange={() => toggleMissingSelection(student.id)}
                                aria-label={`Select ${student.first_name}`}
                              />
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {student.student_id}
                            </TableCell>
                            <TableCell>
                              {student.first_name} {student.middle_name ? `${student.middle_name} ` : ""}{student.last_name}
                            </TableCell>
                            <TableCell>{student.class_name || "-"}</TableCell>
                            <TableCell>{student.section_name || "-"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <CheckCircle className="h-12 w-12 text-green-600 mb-2" />
                  <p className="font-medium">All caught up!</p>
                  <p className="text-sm text-muted-foreground">
                    All eligible students have invoices for this term.
                  </p>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {/* Fee Structure Preview */}
      <Card className={`transition-all duration-300 ${selectedFeeStructureData ? "opacity-100" : "opacity-50"}`}>
        <CardHeader>
          <CardTitle>Fee Structure Preview</CardTitle>
          <CardDescription>
            {selectedFeeStructureData ? selectedFeeStructureData.name : "Select a fee structure to see preview"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!selectedFeeStructure ? (
            <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
              <FileText className="h-12 w-12 mb-2 opacity-50" />
              <p>No fee structure selected</p>
              <p className="text-sm">Select a fee structure above to preview its items</p>
            </div>
          ) : !selectedFeeStructureData ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex justify-between items-center">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : selectedFeeStructureData.items && selectedFeeStructureData.items.length > 0 ? (
            <div className="animate-in fade-in duration-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Item</TableHead>
                    <TableHead className="text-right">Amount (GHS)</TableHead>
                    <TableHead className="text-center">Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedFeeStructureData.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.name}</TableCell>
                      <TableCell className="text-right">
                        {Number(item.amount).toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant={item.is_optional ? "secondary" : "default"}
                        >
                          {item.is_optional ? "Optional" : "Required"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                  <TableRow className="border-t-2">
                    <TableCell className="font-bold">Total</TableCell>
                    <TableCell className="text-right font-bold">
                      {Number(selectedFeeStructureData.total_amount || 0).toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-muted-foreground">No fee items defined</p>
          )}
        </CardContent>
      </Card>

      {/* Sync with Fee Structure - Hidden in single student mode */}
      {!singleStudent && (
        <Card className={`transition-all duration-300 ${selectedFeeStructureData ? "opacity-100" : "opacity-50 pointer-events-none"}`}>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <RefreshCw className="h-5 w-5" />
                  Sync Existing Invoices
                </CardTitle>
                <CardDescription>
                  Update draft invoices to match the current fee structure
                </CardDescription>
              </div>
              <Button
                variant="outline"
                onClick={handleLoadSyncPreview}
                disabled={isLoadingSyncPreview || !selectedFeeStructure}
              >
                {isLoadingSyncPreview && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {isLoadingSyncPreview ? "Loading..." : "Check for Updates"}
              </Button>
            </div>
          </CardHeader>
          {syncPreview && (
            <CardContent className="space-y-4">
              {syncPreview.total_invoices === 0 ? (
                <div className="flex flex-col items-center justify-center py-6 text-center">
                  <Info className="h-10 w-10 text-muted-foreground mb-2" />
                  <p className="font-medium">No invoices found</p>
                  <p className="text-sm text-muted-foreground">
                    Generate invoices first before syncing.
                  </p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-900">
                      <p className="text-sm text-muted-foreground">Draft (can sync)</p>
                      <p className="text-2xl font-bold text-green-600">{syncPreview.draft_count}</p>
                    </div>
                    <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900">
                      <p className="text-sm text-muted-foreground">Issued</p>
                      <p className="text-2xl font-bold text-yellow-600">{syncPreview.issued_count}</p>
                    </div>
                    <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-900">
                      <p className="text-sm text-muted-foreground">Partial</p>
                      <p className="text-2xl font-bold text-blue-600">{syncPreview.partial_count}</p>
                    </div>
                    <div className="p-4 rounded-lg bg-gray-50 dark:bg-gray-950/20 border border-gray-200 dark:border-gray-800">
                      <p className="text-sm text-muted-foreground">Paid</p>
                      <p className="text-2xl font-bold">{syncPreview.paid_count}</p>
                    </div>
                  </div>

                  {syncPreview.cannot_sync_count > 0 && (
                    <Alert>
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        {syncPreview.cannot_sync_count} invoice(s) cannot be synced because they are already issued or have payments.
                        Only draft invoices can be updated.
                      </AlertDescription>
                    </Alert>
                  )}

                  {syncPreview.can_sync_count > 0 && (
                    <div className="flex items-center justify-between pt-2">
                      <div>
                        <p className="text-sm">
                          <span className="font-medium">{syncPreview.can_sync_count}</span> draft invoice(s) will be updated to{" "}
                          <span className="font-medium">{formatCurrency(syncPreview.new_fee_structure_total)}</span>
                        </p>
                      </div>
                      <Button onClick={handleSync} disabled={isSyncing}>
                        {isSyncing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {isSyncing ? "Syncing..." : "Sync Draft Invoices"}
                      </Button>
                    </div>
                  )}

                  {syncResult && (
                    <div className="pt-4 border-t">
                      <div className="flex items-center gap-2 mb-2">
                        {syncResult.updated > 0 ? (
                          <CheckCircle className="h-5 w-5 text-green-600" />
                        ) : (
                          <Info className="h-5 w-5 text-muted-foreground" />
                        )}
                        <span className="font-medium">Sync Result</span>
                      </div>
                      <div className="flex gap-6 text-sm">
                        <span>
                          <span className="font-medium text-green-600">{syncResult.updated}</span> updated
                        </span>
                        <span>
                          <span className="font-medium text-yellow-600">{syncResult.skipped}</span> skipped
                        </span>
                        {syncResult.failed > 0 && (
                          <span>
                            <span className="font-medium text-red-600">{syncResult.failed}</span> failed
                          </span>
                        )}
                      </div>
                      {syncResult.errors.length > 0 && (
                        <ul className="mt-2 text-sm text-red-600 list-disc list-inside">
                          {syncResult.errors.map((error, idx) => (
                            <li key={idx}>{error}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </>
              )}
            </CardContent>
          )}
        </Card>
      )}

      {/* Result */}
      {result && (
        <Card className="animate-in fade-in slide-in-from-bottom-4 duration-300">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {result.created > 0 ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : (
                <AlertCircle className="h-5 w-5 text-destructive" />
              )}
              Generation Result
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex gap-8">
                <div>
                  <p className="text-sm text-muted-foreground">Generated</p>
                  <p className="text-2xl font-bold text-green-600">
                    {result.created}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Failed</p>
                  <p className="text-2xl font-bold text-destructive">
                    {result.failed}
                  </p>
                </div>
              </div>

              {result.errors.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-medium">Errors:</p>
                  <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                    {result.errors.map((error, index) => (
                      <li key={index}>{error.error}</li>
                    ))}
                  </ul>
                </div>
              )}

              {result.created > 0 && (
                <Button asChild>
                  <Link href="/finance/invoices">
                    <FileText className="mr-2 h-4 w-4" />
                    View Invoices
                  </Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex justify-end gap-4">
        <Button variant="outline" asChild>
          <Link href={singleStudent ? `/students/${singleStudent.id}` : "/finance/invoices"}>
            Cancel
          </Link>
        </Button>
        <Button
          onClick={handleGenerate}
          disabled={isGenerating || !selectedFeeStructure}
        >
          {isGenerating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {singleStudent ? "Generate Invoice" : "Generate Invoices"}
        </Button>
      </div>
    </div>
  );
}
