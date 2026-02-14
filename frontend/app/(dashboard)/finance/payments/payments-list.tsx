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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Wallet,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  Printer,
  XCircle,
  AlertCircle,
  DollarSign,
  CreditCard,
  Smartphone,
  Banknote,
  Building2,
  Receipt,
  Loader2,
  Download,
  ChevronLeft,
  ChevronRight,
  Calendar,
} from "lucide-react";
import { getPayments, voidPayment, getPaymentReceipt } from "@/actions/finance.action";
import { getAcademicYears, getTerms } from "@/actions/academic.action";
import type { PaymentWithDetails, PaymentReceipt, AcademicYear, Term } from "@/types";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Debounce Hook
// ============================================

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  return debouncedValue;
}

// ============================================
// Constants (outside component to prevent recreation)
// ============================================

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-100 text-green-800",
  pending: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
  refunded: "bg-purple-100 text-purple-800",
  cancelled: "bg-gray-100 text-gray-500",
};

const PAYMENT_METHOD_LABELS: Record<string, string> = {
  cash: "Cash",
  momo_mtn: "MTN MoMo",
  momo_vodafone: "Vodafone Cash",
  momo_airteltigo: "AirtelTigo Money",
  bank_transfer: "Bank Transfer",
  cheque: "Cheque",
  card: "Card",
  other: "Other",
};

const DATE_RANGE_OPTIONS = [
  { value: "all", label: "All Time" },
  { value: "today", label: "Today" },
  { value: "week", label: "This Week" },
  { value: "month", label: "This Month" },
];

// ============================================
// Helper Components (outside main component)
// ============================================

function PaymentMethodIcon({ method }: { method: string }) {
  if (method.startsWith("momo")) {
    return <Smartphone className="h-4 w-4" />;
  }
  switch (method) {
    case "cash":
      return <Banknote className="h-4 w-4" />;
    case "bank_transfer":
      return <Building2 className="h-4 w-4" />;
    case "card":
      return <CreditCard className="h-4 w-4" />;
    case "cheque":
      return <Receipt className="h-4 w-4" />;
    default:
      return <DollarSign className="h-4 w-4" />;
  }
}

// CSV escape helper
function escapeCSV(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

// ============================================
// Receipt HTML Generator (outside component)
// ============================================

function generateReceiptHTML(receipt: PaymentReceipt): string {
  const paymentMethodDisplay = PAYMENT_METHOD_LABELS[receipt.payment_method] ||
    receipt.payment_method.replace("_", " ").replace(/\b\w/g, (l) => l.toUpperCase());

  return `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Receipt - ${receipt.receipt_number}</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
          font-size: 14px; line-height: 1.5; color: #333;
          padding: 20px; max-width: 400px; margin: 0 auto;
        }
        .receipt { border: 2px solid #333; padding: 20px; }
        .header { text-align: center; border-bottom: 2px dashed #ccc; padding-bottom: 15px; margin-bottom: 15px; }
        .logo { max-width: 80px; max-height: 80px; margin-bottom: 10px; }
        .school-name { font-size: 18px; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; }
        .school-info { font-size: 12px; color: #666; }
        .receipt-title { text-align: center; font-size: 16px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px; margin: 15px 0; padding: 8px; background: #f5f5f5; }
        .receipt-number { text-align: center; font-family: monospace; font-size: 14px; margin-bottom: 15px; }
        .amount-section { text-align: center; padding: 15px; background: #f9f9f9; border-radius: 8px; margin-bottom: 15px; }
        .amount { font-size: 28px; font-weight: bold; color: #2e7d32; }
        .amount-words { font-size: 12px; color: #666; font-style: italic; margin-top: 5px; }
        .details { margin-bottom: 15px; }
        .detail-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dotted #ddd; }
        .detail-row:last-child { border-bottom: none; }
        .detail-label { color: #666; }
        .detail-value { font-weight: 500; text-align: right; }
        .footer { text-align: center; border-top: 2px dashed #ccc; padding-top: 15px; margin-top: 15px; font-size: 12px; color: #666; }
        .footer p { margin: 3px 0; }
        .thank-you { font-weight: bold; font-size: 14px; margin-bottom: 10px; }
        @media print { body { padding: 0; } .receipt { border: none; } @page { margin: 10mm; size: 80mm auto; } }
      </style>
    </head>
    <body>
      <div class="receipt">
        <div class="header">
          ${receipt.school_logo_url ? `<img src="${receipt.school_logo_url}" alt="School Logo" class="logo" />` : ''}
          <div class="school-name">${receipt.school_name}</div>
          ${receipt.school_address ? `<div class="school-info">${receipt.school_address}</div>` : ''}
          ${receipt.school_phone ? `<div class="school-info">Tel: ${receipt.school_phone}</div>` : ''}
          ${receipt.school_email ? `<div class="school-info">${receipt.school_email}</div>` : ''}
        </div>
        <div class="receipt-title">Payment Receipt</div>
        <div class="receipt-number">No: ${receipt.receipt_number}</div>
        <div class="amount-section">
          <div class="amount">${receipt.currency} ${Number(receipt.amount).toLocaleString('en-GH', { minimumFractionDigits: 2 })}</div>
          <div class="amount-words">${receipt.amount_in_words}</div>
        </div>
        <div class="details">
          <div class="detail-row"><span class="detail-label">Date</span><span class="detail-value">${new Date(receipt.payment_date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span></div>
          <div class="detail-row"><span class="detail-label">Student</span><span class="detail-value">${receipt.student_name}</span></div>
          <div class="detail-row"><span class="detail-label">Student ID</span><span class="detail-value">${receipt.student_id_number}</span></div>
          ${receipt.class_name ? `<div class="detail-row"><span class="detail-label">Class</span><span class="detail-value">${receipt.class_name}</span></div>` : ''}
          <div class="detail-row"><span class="detail-label">Payment Method</span><span class="detail-value">${paymentMethodDisplay}</span></div>
          ${receipt.payer_name ? `<div class="detail-row"><span class="detail-label">Paid By</span><span class="detail-value">${receipt.payer_name}</span></div>` : ''}
          ${receipt.invoice_number ? `<div class="detail-row"><span class="detail-label">Invoice</span><span class="detail-value">${receipt.invoice_number}</span></div>` : ''}
        </div>
        <div class="footer">
          <p class="thank-you">Thank You!</p>
          ${receipt.recorded_by_name ? `<p>Recorded by: ${receipt.recorded_by_name}</p>` : ''}
          <p>Printed: ${new Date().toLocaleString('en-GB')}</p>
          <p style="margin-top: 10px; font-size: 10px;">This is a computer-generated receipt.</p>
        </div>
      </div>
      <script>window.onload = function() { window.print(); }</script>
    </body>
    </html>
  `;
}

// ============================================
// Main Component
// ============================================

export function PaymentsList() {
  const { toast } = useToast();
  const router = useRouter();
  const searchParams = useSearchParams();

  // State
  const [isPending, startTransition] = useTransition();
  const [payments, setPayments] = useState<PaymentWithDetails[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [totalPayments, setTotalPayments] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const hasLoadedRef = useRef(false);

  // Filter state from URL params
  const [currentPage, setCurrentPage] = useState(
    parseInt(searchParams.get("page") || "1")
  );
  const [selectedYear, setSelectedYear] = useState<string>(
    searchParams.get("year") || "all"
  );
  const [selectedTerm, setSelectedTerm] = useState<string>(
    searchParams.get("term") || "all"
  );
  const [selectedMethod, setSelectedMethod] = useState<string>(
    searchParams.get("method") || "all"
  );
  const [selectedStatus, setSelectedStatus] = useState<string>(
    searchParams.get("status") || "all"
  );
  const [selectedDateRange, setSelectedDateRange] = useState<string>(
    searchParams.get("range") || "all"
  );
  const [searchQuery, setSearchQuery] = useState(searchParams.get("q") || "");

  // Void dialog state
  const [voidDialogOpen, setVoidDialogOpen] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [paymentToVoid, setPaymentToVoid] = useState<PaymentWithDetails | null>(null);
  const [isVoiding, setIsVoiding] = useState(false);

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

      if (newUrl !== lastUrlRef.current) {
        lastUrlRef.current = newUrl;
        router.replace(newUrl, { scroll: false });
      }
    },
    [router]
  );

  // Calculate date range
  const getDateRange = useCallback((range: string) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    switch (range) {
      case "today":
        return {
          from: today.toISOString().split("T")[0],
          to: today.toISOString().split("T")[0],
        };
      case "week": {
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() - today.getDay());
        return {
          from: weekStart.toISOString().split("T")[0],
          to: today.toISOString().split("T")[0],
        };
      }
      case "month": {
        const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
        return {
          from: monthStart.toISOString().split("T")[0],
          to: today.toISOString().split("T")[0],
        };
      }
      default:
        return null;
    }
  }, []);

  // Fetch payments
  const fetchPayments = useCallback(() => {
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
      if (selectedMethod !== "all") {
        params.paymentMethod = selectedMethod;
      }
      if (selectedStatus !== "all") {
        params.status = selectedStatus;
      }
      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      // Add date range
      const dateRange = getDateRange(selectedDateRange);
      if (dateRange) {
        params.dateFrom = dateRange.from;
        params.dateTo = dateRange.to;
      }

      const result = await getPayments(params);
      if (result.success && result.data) {
        setPayments(result.data.items);
        setTotalPayments(result.data.total);
        setError(null);
      } else {
        setError(result.error || "Failed to load payments");
      }
      setIsInitialLoad(false);
    });
  }, [currentPage, selectedYear, selectedTerm, selectedMethod, selectedStatus, selectedDateRange, debouncedSearch, getDateRange]);

  // Load academic years and terms on mount
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    lastUrlRef.current = window.location.search;

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
  }, []);

  // Fetch payments when filters change
  useEffect(() => {
    fetchPayments();
  }, [fetchPayments]);

  // Update URL when filters change (after initial load)
  useEffect(() => {
    if (isInitialLoad) return;

    updateURL({
      year: selectedYear,
      term: selectedTerm,
      method: selectedMethod,
      status: selectedStatus,
      range: selectedDateRange,
      page: String(currentPage),
      q: debouncedSearch,
    });
  }, [selectedYear, selectedTerm, selectedMethod, selectedStatus, selectedDateRange, currentPage, debouncedSearch, isInitialLoad, updateURL]);

  // Reset page when filters change
  const prevFiltersRef = useRef({
    selectedYear,
    selectedTerm,
    selectedMethod,
    selectedStatus,
    selectedDateRange,
    debouncedSearch,
  });

  useEffect(() => {
    const prev = prevFiltersRef.current;
    const filtersChanged =
      prev.selectedYear !== selectedYear ||
      prev.selectedTerm !== selectedTerm ||
      prev.selectedMethod !== selectedMethod ||
      prev.selectedStatus !== selectedStatus ||
      prev.selectedDateRange !== selectedDateRange ||
      prev.debouncedSearch !== debouncedSearch;

    if (filtersChanged && !isInitialLoad) {
      setCurrentPage(1);
    }

    prevFiltersRef.current = {
      selectedYear,
      selectedTerm,
      selectedMethod,
      selectedStatus,
      selectedDateRange,
      debouncedSearch,
    };
  }, [selectedYear, selectedTerm, selectedMethod, selectedStatus, selectedDateRange, debouncedSearch, isInitialLoad]);

  // Open void dialog
  const handleOpenVoidDialog = useCallback((payment: PaymentWithDetails) => {
    setPaymentToVoid(payment);
    setVoidReason("");
    setVoidDialogOpen(true);
  }, []);

  // Handle void
  const handleVoid = useCallback(async () => {
    if (!paymentToVoid || !voidReason.trim()) return;

    setIsVoiding(true);
    try {
      const result = await voidPayment(paymentToVoid.id, { reason: voidReason });
      if (result.success) {
        toast({
          title: "Payment voided",
          description: "The payment has been voided successfully.",
        });
        setVoidDialogOpen(false);
        setPaymentToVoid(null);
        setVoidReason("");
        fetchPayments();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to void payment",
          variant: "destructive",
        });
      }
    } finally {
      setIsVoiding(false);
    }
  }, [paymentToVoid, voidReason, toast, fetchPayments]);

  // Handle print receipt
  const handlePrintReceipt = useCallback(async (paymentId: string) => {
    try {
      const result = await getPaymentReceipt(paymentId);
      if (result.success && result.data) {
        const receiptHTML = generateReceiptHTML(result.data);
        const printWindow = window.open('', '_blank', 'width=450,height=600');
        if (printWindow) {
          printWindow.document.write(receiptHTML);
          printWindow.document.close();
        } else {
          toast({
            title: "Popup blocked",
            description: "Please allow popups to print the receipt.",
            variant: "destructive",
          });
        }
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to load receipt data",
          variant: "destructive",
        });
      }
    } catch {
      toast({
        title: "Error",
        description: "Failed to print receipt",
        variant: "destructive",
      });
    }
  }, [toast]);

  // Export to CSV
  const handleExportCSV = useCallback(() => {
    const headers = [
      "Receipt #",
      "Student Name",
      "Student ID",
      "Payer",
      "Payment Method",
      "Date",
      "Amount",
      "Status",
    ];
    const rows = payments.map((p) => [
      escapeCSV(p.receipt_number),
      escapeCSV(p.student_name),
      escapeCSV(p.student_id_number),
      escapeCSV(p.payer_name),
      escapeCSV(PAYMENT_METHOD_LABELS[p.payment_method] || p.payment_method),
      escapeCSV(p.payment_date),
      escapeCSV(p.amount),
      escapeCSV(p.status),
    ]);

    const csvContent =
      [headers.join(","), ...rows.map((row) => row.join(","))].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `payments-${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
  }, [payments]);

  // Memoized stats calculation
  const stats = useMemo(() => {
    const completedPayments = payments.filter((p) => p.status === "completed");
    const today = new Date().toISOString().split("T")[0];

    const todayPayments = payments.filter(
      (p) => p.payment_date.startsWith(today) && p.status === "completed"
    );

    return {
      total: completedPayments.length,
      totalAmount: completedPayments.reduce((sum, p) => sum + Number(p.amount), 0),
      cashPayments: completedPayments.filter((p) => p.payment_method === "cash").length,
      cashAmount: completedPayments
        .filter((p) => p.payment_method === "cash")
        .reduce((sum, p) => sum + Number(p.amount), 0),
      momoPayments: completedPayments.filter((p) => p.payment_method.startsWith("momo")).length,
      momoAmount: completedPayments
        .filter((p) => p.payment_method.startsWith("momo"))
        .reduce((sum, p) => sum + Number(p.amount), 0),
      todayCount: todayPayments.length,
      todayAmount: todayPayments.reduce((sum, p) => sum + Number(p.amount), 0),
    };
  }, [payments]);

  // Filtered terms for dropdown
  const filteredTerms = useMemo(() => {
    if (selectedYear === "all") return terms;
    return terms.filter((t) => t.academic_year_id === selectedYear);
  }, [terms, selectedYear]);

  // Pagination
  const totalPages = Math.ceil(totalPayments / pageSize);

  // Loading state
  if (isInitialLoad && isPending) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={fetchPayments}>Retry</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Payments</h1>
          <p className="text-muted-foreground">
            Track and manage payment transactions
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExportCSV}>
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
          <Button asChild>
            <Link href="/finance/payments/record">
              <Plus className="mr-2 h-4 w-4" />
              Record Payment
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Collected
            </CardTitle>
            <Wallet className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(stats.totalAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.total} transactions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Cash Payments</CardTitle>
            <Banknote className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(stats.cashAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.cashPayments} transactions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Mobile Money
            </CardTitle>
            <Smartphone className="h-4 w-4 text-yellow-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">
              {formatCurrency(stats.momoAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.momoPayments} transactions
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Today&apos;s Collection
            </CardTitle>
            <Calendar className="h-4 w-4 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {formatCurrency(stats.todayAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.todayCount} transactions
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>All Payments</CardTitle>
          <CardDescription>View and manage all payment records</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Filters Row 1 */}
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by receipt #, student name, or payer..."
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
          </div>

          {/* Filters Row 2 */}
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <Select value={selectedDateRange} onValueChange={setSelectedDateRange}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Date Range" />
              </SelectTrigger>
              <SelectContent>
                {DATE_RANGE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedMethod} onValueChange={setSelectedMethod}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Payment Method" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Methods</SelectItem>
                <SelectItem value="cash">Cash</SelectItem>
                <SelectItem value="momo_mtn">MTN MoMo</SelectItem>
                <SelectItem value="momo_vodafone">Vodafone Cash</SelectItem>
                <SelectItem value="momo_airteltigo">AirtelTigo</SelectItem>
                <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                <SelectItem value="cheque">Cheque</SelectItem>
                <SelectItem value="card">Card</SelectItem>
              </SelectContent>
            </Select>
            <Select value={selectedStatus} onValueChange={setSelectedStatus}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="refunded">Refunded</SelectItem>
                <SelectItem value="cancelled">Cancelled</SelectItem>
              </SelectContent>
            </Select>
            {(selectedYear !== "all" ||
              selectedTerm !== "all" ||
              selectedMethod !== "all" ||
              selectedStatus !== "all" ||
              selectedDateRange !== "all" ||
              searchQuery) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSelectedYear("all");
                  setSelectedTerm("all");
                  setSelectedMethod("all");
                  setSelectedStatus("all");
                  setSelectedDateRange("all");
                  setSearchQuery("");
                }}
              >
                Clear filters
              </Button>
            )}
          </div>

          {/* Loading Overlay */}
          <div className="relative">
            {isPending && (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            )}

            {payments.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Receipt #</TableHead>
                        <TableHead>Student</TableHead>
                        <TableHead className="hidden md:table-cell">Payer</TableHead>
                        <TableHead>Method</TableHead>
                        <TableHead className="hidden sm:table-cell">Date</TableHead>
                        <TableHead className="text-right">Amount (GHS)</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="w-[70px]"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payments.map((payment) => (
                        <TableRow key={payment.id}>
                          <TableCell className="font-mono text-sm">
                            <Link
                              href={`/finance/payments/${payment.id}`}
                              className="hover:underline"
                            >
                              {payment.receipt_number}
                            </Link>
                          </TableCell>
                          <TableCell className="font-medium">
                            {payment.student_name ? (
                              <Link
                                href={`/students/${payment.student_id}`}
                                className="hover:underline"
                              >
                                {payment.student_name}
                              </Link>
                            ) : (
                              "-"
                            )}
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            {payment.payer_name || "-"}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <PaymentMethodIcon method={payment.payment_method} />
                              <span className="hidden lg:inline">
                                {PAYMENT_METHOD_LABELS[payment.payment_method] || payment.payment_method}
                              </span>
                            </div>
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {formatDate(payment.payment_date)}
                          </TableCell>
                          <TableCell className="text-right font-medium">
                            {formatNumber(payment.amount)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={STATUS_COLORS[payment.status] || "bg-gray-100 text-gray-800"}
                            >
                              {payment.status}
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
                                  <Link href={`/finance/payments/${payment.id}`}>
                                    <Eye className="mr-2 h-4 w-4" />
                                    View Receipt
                                  </Link>
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => handlePrintReceipt(payment.id)}>
                                  <Printer className="mr-2 h-4 w-4" />
                                  Print Receipt
                                </DropdownMenuItem>
                                {payment.status === "completed" && !payment.is_voided && (
                                  <>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem
                                      onClick={() => handleOpenVoidDialog(payment)}
                                      className="text-destructive"
                                    >
                                      <XCircle className="mr-2 h-4 w-4" />
                                      Void Payment
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
                      {Math.min(currentPage * pageSize, totalPayments)} of{" "}
                      {totalPayments} payments
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
                <Wallet className="h-12 w-12" />
                <p>No payments found</p>
                {(selectedYear !== "all" ||
                  selectedTerm !== "all" ||
                  selectedMethod !== "all" ||
                  selectedStatus !== "all" ||
                  selectedDateRange !== "all" ||
                  searchQuery) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setSelectedYear("all");
                      setSelectedTerm("all");
                      setSelectedMethod("all");
                      setSelectedStatus("all");
                      setSelectedDateRange("all");
                      setSearchQuery("");
                    }}
                  >
                    Clear filters
                  </Button>
                )}
                <Button asChild variant="outline" size="sm">
                  <Link href="/finance/payments/record">Record a payment</Link>
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Void Payment Dialog */}
      <Dialog open={voidDialogOpen} onOpenChange={setVoidDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Void Payment</DialogTitle>
            <DialogDescription>
              Are you sure you want to void this payment of{" "}
              <span className="font-semibold">
                {paymentToVoid ? formatCurrency(paymentToVoid.amount) : ""}
              </span>
              ? This will update the related invoice balance. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {paymentToVoid && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <p><span className="text-muted-foreground">Receipt:</span> {paymentToVoid.receipt_number}</p>
              <p><span className="text-muted-foreground">Student:</span> {paymentToVoid.student_name}</p>
              <p><span className="text-muted-foreground">Date:</span> {formatDate(paymentToVoid.payment_date)}</p>
            </div>
          )}
          <div className="space-y-2">
            <Label htmlFor="void-reason">
              Reason for voiding <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="void-reason"
              placeholder="Enter the reason for voiding this payment..."
              value={voidReason}
              onChange={(e) => setVoidReason(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setVoidDialogOpen(false);
                setPaymentToVoid(null);
                setVoidReason("");
              }}
              disabled={isVoiding}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleVoid}
              disabled={isVoiding || !voidReason.trim()}
            >
              {isVoiding ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Voiding...
                </>
              ) : (
                "Void Payment"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
