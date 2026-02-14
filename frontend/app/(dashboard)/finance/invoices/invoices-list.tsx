"use client";

import { useEffect, useState, useTransition, useCallback, useMemo, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  FileText,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Send,
  XCircle,
  AlertCircle,
  DollarSign,
  Clock,
  CheckCircle,
  Download,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import {
  getInvoices,
  issueInvoice,
  cancelInvoice as cancelInvoiceAction,
} from "@/actions/finance.action";
import { getAcademicYears, getTerms } from "@/actions/academic.action";
import type { InvoiceWithDetails, AcademicYear, Term } from "@/types";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// Status color mapping (outside component to avoid recreation)
const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  issued: "bg-blue-100 text-blue-800",
  partial: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  overdue: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
};

// CSV escape helper
function escapeCSV(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function InvoicesList() {
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Initialize state from URL params
  const [isPending, startTransition] = useTransition();
  const [invoices, setInvoices] = useState<InvoiceWithDetails[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [totalInvoices, setTotalInvoices] = useState(0);
  const [currentPage, setCurrentPage] = useState(
    parseInt(searchParams.get("page") || "1")
  );
  const [selectedYear, setSelectedYear] = useState<string>(
    searchParams.get("year") || "all"
  );
  const [selectedTerm, setSelectedTerm] = useState<string>(
    searchParams.get("term") || "all"
  );
  const [selectedStatus, setSelectedStatus] = useState<string>(
    searchParams.get("status") || "all"
  );
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const hasLoadedRef = useRef(false);

  // Bulk selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [selectAll, setSelectAll] = useState(false);

  // Dialog states
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelInvoice, setCancelInvoice] = useState<InvoiceWithDetails | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [issueDialogOpen, setIssueDialogOpen] = useState(false);
  const [issueInvoiceId, setIssueInvoiceId] = useState<string | null>(null);
  const [bulkIssueDialogOpen, setBulkIssueDialogOpen] = useState(false);
  const [bulkCancelDialogOpen, setBulkCancelDialogOpen] = useState(false);
  const [bulkCancelReason, setBulkCancelReason] = useState("");

  const pageSize = 20;
  const debouncedSearch = useDebounce(searchQuery, 300);
  const lastUrlRef = useRef<string>("");

  // Update URL when filters change
  const updateURL = useCallback(
    (updates: Record<string, string>) => {
      const params = new URLSearchParams();
      Object.entries(updates).forEach(([key, value]) => {
        if (value && value !== "all" && value !== "1" && value !== "") {
          params.set(key, value);
        }
      });
      const newUrl = params.toString() ? `?${params.toString()}` : "";

      // Only update if URL actually changed
      if (newUrl !== lastUrlRef.current) {
        lastUrlRef.current = newUrl;
        router.replace(newUrl, { scroll: false });
      }
    },
    [router]
  );

  const fetchInvoices = useCallback(() => {
    startTransition(async () => {
      const params: Record<string, string | number> = {
        page: currentPage,
        pageSize,
      };
      if (selectedYear !== "all") {
        params.academicYearId = selectedYear;
      }
      if (selectedTerm !== "all") {
        params.termId = selectedTerm;
      }
      if (selectedStatus !== "all") {
        params.status = selectedStatus;
      }
      // Server-side search
      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      const result = await getInvoices(params);
      if (result.success && result.data) {
        setInvoices(result.data.items);
        setTotalInvoices(result.data.total);
        setError(null);
      } else {
        setError(result.error || "Failed to load invoices");
      }
      setIsInitialLoad(false);
    });
  }, [currentPage, selectedYear, selectedTerm, selectedStatus, debouncedSearch]);

  // Load academic years and terms on mount (only once)
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    // Initialize lastUrlRef with current URL
    lastUrlRef.current = window.location.search;

    // Capture URL params at mount time
    const urlYear = searchParams.get("year");
    const urlTerm = searchParams.get("term");

    startTransition(async () => {
      const [yearsResult, termsResult] = await Promise.all([
        getAcademicYears(),
        getTerms(),
      ]);

      let currentYearId: string | null = null;

      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
        // Set current year if not specified in URL
        if (!urlYear) {
          const currentYear = yearsResult.data.find((y) => y.is_current);
          if (currentYear) {
            currentYearId = currentYear.id;
            setSelectedYear(currentYear.id);
          }
        } else {
          currentYearId = urlYear;
        }
      }

      if (termsResult.success && termsResult.data) {
        setTerms(termsResult.data);
        // Set current term if not specified in URL
        if (!urlTerm && currentYearId) {
          const currentTerm = termsResult.data.find(
            (t) => t.is_current && t.academic_year_id === currentYearId
          );
          if (currentTerm) {
            setSelectedTerm(currentTerm.id);
          }
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Fetch invoices when filters change
  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  // Update URL when filters change (after initial load)
  useEffect(() => {
    if (isInitialLoad) return;

    updateURL({
      year: selectedYear,
      term: selectedTerm,
      status: selectedStatus,
      page: String(currentPage),
      q: debouncedSearch,
    });
  }, [selectedYear, selectedTerm, selectedStatus, currentPage, debouncedSearch, isInitialLoad, updateURL]);

  // Reset page when filters change (but not on initial load)
  const prevFiltersRef = useRef({ selectedYear, selectedTerm, selectedStatus, debouncedSearch });
  useEffect(() => {
    const prev = prevFiltersRef.current;
    const filtersChanged =
      prev.selectedYear !== selectedYear ||
      prev.selectedTerm !== selectedTerm ||
      prev.selectedStatus !== selectedStatus ||
      prev.debouncedSearch !== debouncedSearch;

    if (filtersChanged && !isInitialLoad) {
      setCurrentPage(1);
      setSelectedIds(new Set());
      setSelectAll(false);
    }

    prevFiltersRef.current = { selectedYear, selectedTerm, selectedStatus, debouncedSearch };
  }, [selectedYear, selectedTerm, selectedStatus, debouncedSearch, isInitialLoad]);

  // Handle issue invoice
  const handleIssue = async (id: string) => {
    startTransition(async () => {
      const result = await issueInvoice(id);
      if (result.success) {
        toast({
          title: "Invoice issued",
          description: "The invoice has been issued successfully.",
        });
        fetchInvoices();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to issue invoice",
          variant: "destructive",
        });
      }
    });
    setIssueDialogOpen(false);
    setIssueInvoiceId(null);
  };

  // Handle cancel invoice
  const handleCancel = async () => {
    if (!cancelInvoice || !cancelReason.trim()) return;

    startTransition(async () => {
      const result = await cancelInvoiceAction(cancelInvoice.id, {
        reason: cancelReason,
      });
      if (result.success) {
        toast({
          title: "Invoice cancelled",
          description: "The invoice has been cancelled.",
        });
        fetchInvoices();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to cancel invoice",
          variant: "destructive",
        });
      }
    });
    setCancelDialogOpen(false);
    setCancelInvoice(null);
    setCancelReason("");
  };

  // Handle bulk issue (parallel execution)
  const handleBulkIssue = async () => {
    const draftIds = Array.from(selectedIds).filter(
      (id) => invoiceMap.get(id)?.status === "draft"
    );

    const results = await Promise.all(draftIds.map((id) => issueInvoice(id)));
    const successCount = results.filter((r) => r.success).length;

    toast({
      title: "Bulk issue complete",
      description: `${successCount} of ${draftIds.length} invoices issued successfully.`,
    });

    setSelectedIds(new Set());
    setSelectAll(false);
    setBulkIssueDialogOpen(false);
    fetchInvoices();
  };

  // Handle bulk cancel (parallel execution)
  const handleBulkCancel = async () => {
    if (!bulkCancelReason.trim()) return;

    const cancelableIds = Array.from(selectedIds).filter((id) => {
      const status = invoiceMap.get(id)?.status;
      return status !== "cancelled" && status !== "paid";
    });

    const results = await Promise.all(
      cancelableIds.map((id) => cancelInvoiceAction(id, { reason: bulkCancelReason }))
    );
    const successCount = results.filter((r) => r.success).length;

    toast({
      title: "Bulk cancel complete",
      description: `${successCount} of ${cancelableIds.length} invoices cancelled.`,
    });

    setSelectedIds(new Set());
    setSelectAll(false);
    setBulkCancelDialogOpen(false);
    setBulkCancelReason("");
    fetchInvoices();
  };

  // Handle select all
  const handleSelectAll = (checked: boolean) => {
    setSelectAll(checked);
    if (checked) {
      setSelectedIds(new Set(invoices.map((inv) => inv.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // Handle individual selection
  const handleSelect = (id: string, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedIds(newSet);
    setSelectAll(invoices.length > 0 && newSet.size === invoices.length);
  };

  // Export to CSV with proper escaping
  const handleExportCSV = useCallback(() => {
    const headers = [
      "Invoice #",
      "Student Name",
      "Student ID",
      "Class",
      "Due Date",
      "Total",
      "Paid",
      "Balance",
      "Status",
    ];
    const rows = invoices.map((inv) => [
      escapeCSV(inv.invoice_number),
      escapeCSV(inv.student_name),
      escapeCSV(inv.student_id_number),
      escapeCSV(inv.class_name),
      escapeCSV(inv.due_date),
      escapeCSV(inv.total_amount),
      escapeCSV(inv.amount_paid),
      escapeCSV(inv.balance),
      escapeCSV(inv.status),
    ]);

    const csvContent =
      [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `invoices-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
  }, [invoices]);

  // Use status color from constant
  const getStatusColor = (status: string) =>
    STATUS_COLORS[status] || "bg-gray-100 text-gray-800";

  // Calculate stats from current invoices (filtered)
  const stats = useMemo(() => {
    const totalAmount = invoices.reduce(
      (sum, inv) => sum + Number(inv.total_amount),
      0
    );
    const collected = invoices.reduce(
      (sum, inv) => sum + Number(inv.amount_paid),
      0
    );
    const outstanding = invoices.reduce(
      (sum, inv) => sum + Number(inv.balance),
      0
    );
    const overdue = invoices.filter((inv) => inv.status === "overdue").length;
    const collectionRate = totalAmount > 0 ? (collected / totalAmount) * 100 : 0;

    return {
      total: invoices.length,
      totalAmount,
      collected,
      outstanding,
      overdue,
      collectionRate,
    };
  }, [invoices]);

  // Create a lookup map for faster invoice access
  const invoiceMap = useMemo(() => {
    return new Map(invoices.map((inv) => [inv.id, inv]));
  }, [invoices]);

  // Count of selectable invoices for bulk actions
  const selectableDraftCount = useMemo(() => {
    return Array.from(selectedIds).filter((id) => {
      const inv = invoiceMap.get(id);
      return inv?.status === "draft";
    }).length;
  }, [selectedIds, invoiceMap]);

  const selectableCancelCount = useMemo(() => {
    return Array.from(selectedIds).filter((id) => {
      const inv = invoiceMap.get(id);
      return inv?.status !== "cancelled" && inv?.status !== "paid";
    }).length;
  }, [selectedIds, invoiceMap]);

  // Check if some (but not all) are selected for indeterminate state
  const isIndeterminate = selectedIds.size > 0 && selectedIds.size < invoices.length;

  // Memoize filtered terms for the dropdown
  const filteredTerms = useMemo(() => {
    if (selectedYear === "all") return terms;
    return terms.filter((t) => t.academic_year_id === selectedYear);
  }, [terms, selectedYear]);

  // Pagination
  const totalPages = Math.ceil(totalInvoices / pageSize);

  if (isInitialLoad && isPending) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Invoices</h1>
          <p className="text-muted-foreground">
            Manage student fee invoices
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExportCSV}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button asChild>
            <Link href="/finance/invoices/generate">
              <Plus className="mr-2 h-4 w-4" />
              Generate Invoices
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Invoiced</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(stats.totalAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.total} invoices
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Collected</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(stats.collected)}
            </div>
            <div className="mt-2 space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Collection rate</span>
                <span className="font-medium">{stats.collectionRate.toFixed(1)}%</span>
              </div>
              <Progress value={stats.collectionRate} className="h-1.5" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Outstanding</CardTitle>
            <Clock className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCurrency(stats.outstanding)}
            </div>
            <p className="text-xs text-muted-foreground">pending payment</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Overdue</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats.overdue}
            </div>
            <p className="text-xs text-muted-foreground">invoices overdue</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Table Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>All Invoices</CardTitle>
              <CardDescription>View and manage all student invoices</CardDescription>
            </div>
            {selectedIds.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  {selectedIds.size} selected
                </span>
                {selectableDraftCount > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setBulkIssueDialogOpen(true)}
                  >
                    <Send className="mr-2 h-4 w-4" />
                    Issue ({selectableDraftCount})
                  </Button>
                )}
                {selectableCancelCount > 0 && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-destructive"
                    onClick={() => setBulkCancelDialogOpen(true)}
                  >
                    <XCircle className="mr-2 h-4 w-4" />
                    Cancel ({selectableCancelCount})
                  </Button>
                )}
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {/* Filters */}
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by invoice #, student name, or ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedTerm} onValueChange={setSelectedTerm}>
              <SelectTrigger className="w-[120px]">
                <SelectValue placeholder="Term" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Terms</SelectItem>
                {filteredTerms.map((term) => (
                  <SelectItem key={term.id} value={term.id}>
                    {term.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger className="w-[130px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="issued">Issued</SelectItem>
                <SelectItem value="partial">Partial</SelectItem>
                <SelectItem value="paid">Paid</SelectItem>
                <SelectItem value="overdue">Overdue</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Loading Overlay */}
          <div className="relative">
            {isPending && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            )}

            {invoices.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]">
                          <Checkbox
                            checked={isIndeterminate ? "indeterminate" : selectAll}
                            onCheckedChange={handleSelectAll}
                            aria-label="Select all"
                          />
                        </TableHead>
                        <TableHead>Invoice #</TableHead>
                        <TableHead>Student</TableHead>
                        <TableHead className="hidden md:table-cell">Student ID</TableHead>
                        <TableHead className="hidden lg:table-cell">Class</TableHead>
                        <TableHead className="hidden sm:table-cell">Due Date</TableHead>
                        <TableHead className="text-right">Total (GHS)</TableHead>
                        <TableHead className="text-right hidden sm:table-cell">Paid (GHS)</TableHead>
                        <TableHead className="text-right">Balance (GHS)</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[70px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {invoices.map((invoice) => (
                        <TableRow
                          key={invoice.id}
                          className={selectedIds.has(invoice.id) ? "bg-muted/50" : ""}
                        >
                          <TableCell>
                            <Checkbox
                              checked={selectedIds.has(invoice.id)}
                              onCheckedChange={(checked) =>
                                handleSelect(invoice.id, checked as boolean)
                              }
                              aria-label={`Select ${invoice.invoice_number}`}
                            />
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            <Link
                              href={`/finance/invoices/${invoice.id}`}
                              className="hover:underline"
                            >
                              {invoice.invoice_number}
                            </Link>
                          </TableCell>
                          <TableCell className="font-medium">
                            <Link
                              href={`/students/${invoice.student_id}`}
                              className="hover:underline"
                            >
                              {invoice.student_name}
                            </Link>
                          </TableCell>
                          <TableCell className="hidden md:table-cell font-mono text-sm text-muted-foreground">
                            {invoice.student_id_number || "-"}
                          </TableCell>
                          <TableCell className="hidden lg:table-cell">
                            {invoice.class_name || "-"}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {invoice.due_date ? formatDate(invoice.due_date) : "-"}
                          </TableCell>
                          <TableCell className="text-right">
                            {formatNumber(invoice.total_amount)}
                          </TableCell>
                          <TableCell className="text-right text-green-600 hidden sm:table-cell">
                            {formatNumber(invoice.amount_paid)}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {Number(invoice.balance) > 0 ? (
                              <span className="text-orange-600">
                                {formatNumber(invoice.balance)}
                              </span>
                            ) : (
                              <span className="text-green-600">
                                {formatNumber(0)}
                              </span>
                            )}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={getStatusColor(invoice.status)}
                            >
                              {invoice.status}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon">
                                  <MoreHorizontal className="h-4 w-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem asChild>
                                  <Link href={`/finance/invoices/${invoice.id}`}>
                                    <Eye className="mr-2 h-4 w-4" />
                                    View Details
                                  </Link>
                                </DropdownMenuItem>
                                {invoice.status === "draft" && (
                                  <DropdownMenuItem
                                    onClick={() => {
                                      setIssueInvoiceId(invoice.id);
                                      setIssueDialogOpen(true);
                                    }}
                                  >
                                    <Send className="mr-2 h-4 w-4" />
                                    Issue Invoice
                                  </DropdownMenuItem>
                                )}
                                {Number(invoice.balance) > 0 &&
                                  invoice.status !== "cancelled" && (
                                    <DropdownMenuItem asChild>
                                      <Link
                                        href={`/finance/payments/record?invoice_id=${invoice.id}`}
                                      >
                                        <DollarSign className="mr-2 h-4 w-4" />
                                        Record Payment
                                      </Link>
                                    </DropdownMenuItem>
                                  )}
                                {invoice.status !== "cancelled" &&
                                  invoice.status !== "paid" && (
                                    <>
                                      <DropdownMenuSeparator />
                                      <DropdownMenuItem
                                        onClick={() => {
                                          setCancelInvoice(invoice);
                                          setCancelDialogOpen(true);
                                        }}
                                        className="text-destructive"
                                      >
                                        <XCircle className="mr-2 h-4 w-4" />
                                        Cancel Invoice
                                      </DropdownMenuItem>
                                    </>
                                  )}
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Showing {(currentPage - 1) * pageSize + 1} to{" "}
                      {Math.min(currentPage * pageSize, totalInvoices)} of{" "}
                      {totalInvoices} invoices
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1 || isPending}
                      >
                        <ChevronLeft className="h-4 w-4" />
                        Previous
                      </Button>
                      <span className="text-sm">
                        Page {currentPage} of {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          setCurrentPage((p) => Math.min(totalPages, p + 1))
                        }
                        disabled={currentPage === totalPages || isPending}
                      >
                        Next
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
                <FileText className="h-12 w-12" />
                <p>No invoices found</p>
                {(selectedStatus !== "all" ||
                  selectedYear !== "all" ||
                  selectedTerm !== "all" ||
                  searchQuery) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedStatus("all");
                      setSelectedYear("all");
                      setSelectedTerm("all");
                      setSearchQuery("");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
                <Button asChild variant="outline" size="sm">
                  <Link href="/finance/invoices/generate">
                    Generate invoices
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Issue Confirmation Dialog */}
      <AlertDialog open={issueDialogOpen} onOpenChange={setIssueDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Issue Invoice</AlertDialogTitle>
            <AlertDialogDescription>
              This will issue the invoice and send it to the student/guardian.
              This action cannot be undone. Are you sure you want to proceed?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setIssueInvoiceId(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => issueInvoiceId && handleIssue(issueInvoiceId)}
            >
              Issue Invoice
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Cancel Invoice Dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Invoice</DialogTitle>
            <DialogDescription>
              {cancelInvoice && cancelInvoice.amount_paid > 0
                ? "This invoice has payments that must be voided first."
                : "Please provide a reason for cancelling this invoice. This action cannot be undone."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {cancelInvoice && cancelInvoice.amount_paid > 0 ? (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-destructive">
                      Cannot cancel invoice with payments
                    </p>
                    <p className="text-sm text-muted-foreground">
                      This invoice has {formatCurrency(cancelInvoice.amount_paid)} in payments.
                      You must void all payments before cancelling the invoice.
                    </p>
                    <Link href="/finance/payments">
                      <Button variant="outline" size="sm" className="mt-2">
                        <DollarSign className="mr-2 h-4 w-4" />
                        Go to Payments
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid gap-2">
                <Label htmlFor="cancel-reason">Reason for cancellation</Label>
                <Textarea
                  id="cancel-reason"
                  placeholder="Enter the reason..."
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  rows={3}
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setCancelDialogOpen(false);
                setCancelInvoice(null);
                setCancelReason("");
              }}
            >
              {cancelInvoice && cancelInvoice.amount_paid > 0 ? "Close" : "Cancel"}
            </Button>
            {cancelInvoice && cancelInvoice.amount_paid === 0 && (
              <Button
                variant="destructive"
                onClick={handleCancel}
                disabled={!cancelReason.trim() || isPending}
              >
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Cancel Invoice
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Issue Dialog */}
      <AlertDialog open={bulkIssueDialogOpen} onOpenChange={setBulkIssueDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Issue {selectableDraftCount} Invoices</AlertDialogTitle>
            <AlertDialogDescription>
              This will issue {selectableDraftCount} draft invoice(s). This
              action cannot be undone. Are you sure you want to proceed?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleBulkIssue}>
              Issue Invoices
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk Cancel Dialog */}
      <Dialog open={bulkCancelDialogOpen} onOpenChange={setBulkCancelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel {selectableCancelCount} Invoices</DialogTitle>
            <DialogDescription>
              Please provide a reason for cancelling these invoices. This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="bulk-cancel-reason">Reason for cancellation</Label>
              <Textarea
                id="bulk-cancel-reason"
                placeholder="Enter the reason..."
                value={bulkCancelReason}
                onChange={(e) => setBulkCancelReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setBulkCancelDialogOpen(false);
                setBulkCancelReason("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleBulkCancel}
              disabled={!bulkCancelReason.trim() || isPending}
            >
              {isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Cancel {selectableCancelCount} Invoices
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
