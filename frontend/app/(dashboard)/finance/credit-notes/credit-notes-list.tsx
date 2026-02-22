"use client";

import { useEffect, useState, useRef, useTransition, useCallback, useMemo } from "react";
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
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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
import { Skeleton } from "@/components/ui/skeleton";
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
import {
  CreditCard,
  Plus,
  Search,
  MoreHorizontal,
  Eye,
  CheckCircle,
  Send,
  RefreshCw,
  XCircle,
  AlertCircle,
  FileText,
  Wallet,
  TrendingUp,
  ArrowDownRight,
  ReceiptText,
  GraduationCap,
  AlertTriangle,
  HelpCircle,
  Loader2,
} from "lucide-react";
import {
  getCreditNotes,
  issueCreditNote,
  cancelCreditNote,
} from "@/actions/finance.action";
import type { CreditNoteWithDetails, CreditNoteStatus, CreditNoteType } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// Status configuration with colors (no purple)
const STATUS_CONFIG: Record<CreditNoteStatus, { label: string; color: string; icon: typeof FileText }> = {
  draft: {
    label: "Draft",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: FileText,
  },
  issued: {
    label: "Issued",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    icon: Send,
  },
  applied: {
    label: "Applied",
    color: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
    icon: CheckCircle,
  },
  refunded: {
    label: "Refunded",
    color: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300",
    icon: RefreshCw,
  },
  cancelled: {
    label: "Cancelled",
    color: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
    icon: XCircle,
  },
};

// Type configuration with colors (no purple - using teal for scholarship)
const TYPE_CONFIG: Record<CreditNoteType, { label: string; color: string; icon: typeof CreditCard }> = {
  overpayment: {
    label: "Overpayment",
    color: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
    icon: TrendingUp,
  },
  fee_reduction: {
    label: "Fee Reduction",
    color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    icon: ArrowDownRight,
  },
  error_correction: {
    label: "Error Correction",
    color: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    icon: AlertTriangle,
  },
  scholarship_adjustment: {
    label: "Scholarship",
    color: "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
    icon: GraduationCap,
  },
  other: {
    label: "Other",
    color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    icon: HelpCircle,
  },
};

export function CreditNotesList() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [creditNotes, setCreditNotes] = useState<CreditNoteWithDetails[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // Dialog states
  const [issueDialogOpen, setIssueDialogOpen] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [selectedCreditNote, setSelectedCreditNote] = useState<CreditNoteWithDetails | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [autoApplyToInvoice, setAutoApplyToInvoice] = useState(true);

  const [debouncedSearch, setDebouncedSearch] = useState("");
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Debounce search input
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, [searchQuery]);

  const fetchCreditNotes = useCallback(() => {
    startTransition(async () => {
      const params: Record<string, string> = {};
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      if (typeFilter !== "all") {
        params.type = typeFilter;
      }
      if (debouncedSearch) {
        params.search = debouncedSearch;
      }

      const result = await getCreditNotes(params);
      if (result.success && result.data) {
        setCreditNotes(result.data.items);
        setTotalCount(result.data.total);
      } else {
        setError(result.error || "Failed to load credit notes");
      }
      setIsInitialLoad(false);
    });
  }, [statusFilter, typeFilter, debouncedSearch]);

  useEffect(() => {
    fetchCreditNotes();
  }, [fetchCreditNotes]);

  // Open issue confirmation dialog
  const openIssueDialog = useCallback((cn: CreditNoteWithDetails) => {
    setSelectedCreditNote(cn);
    setAutoApplyToInvoice(true); // Default to auto-apply
    setIssueDialogOpen(true);
  }, []);

  // Open cancel dialog
  const openCancelDialog = useCallback((cn: CreditNoteWithDetails) => {
    setSelectedCreditNote(cn);
    setCancelReason("");
    setCancelDialogOpen(true);
  }, []);

  // Confirm issue
  const handleConfirmIssue = useCallback(async () => {
    if (!selectedCreditNote) return;

    setIsProcessing(true);
    const result = await issueCreditNote(selectedCreditNote.id, autoApplyToInvoice);
    setIsProcessing(false);

    if (result.success) {
      const wasApplied = result.data?.status === "applied";
      toast({
        title: "Credit note issued",
        description: wasApplied
          ? `Credit note issued and applied to invoice ${result.data?.applied_to_invoice_id ? "successfully" : ""}.`
          : "The credit note has been issued. Credit is now available for the student.",
      });
      setIssueDialogOpen(false);
      setSelectedCreditNote(null);
      fetchCreditNotes();
    } else {
      toast({
        title: "Error",
        description: result.error || "Failed to issue credit note",
        variant: "destructive",
      });
    }
  }, [selectedCreditNote, autoApplyToInvoice, toast, fetchCreditNotes]);

  // Confirm cancel
  const handleConfirmCancel = useCallback(async () => {
    if (!selectedCreditNote || !cancelReason.trim()) return;

    setIsProcessing(true);
    const result = await cancelCreditNote(selectedCreditNote.id, { reason: cancelReason.trim() });
    setIsProcessing(false);

    if (result.success) {
      toast({
        title: "Credit note cancelled",
        description: "The credit note has been cancelled successfully.",
      });
      setCancelDialogOpen(false);
      setSelectedCreditNote(null);
      setCancelReason("");
      fetchCreditNotes();
    } else {
      toast({
        title: "Error",
        description: result.error || "Failed to cancel credit note",
        variant: "destructive",
      });
    }
  }, [selectedCreditNote, cancelReason, toast, fetchCreditNotes]);

  // Summary calculations - memoized
  const summaryStats = useMemo(() => {
    const draftNotes = creditNotes.filter((cn) => cn.status === "draft");
    const issuedNotes = creditNotes.filter((cn) => cn.status === "issued");
    const appliedNotes = creditNotes.filter((cn) => cn.status === "applied");

    return {
      draftCount: draftNotes.length,
      draftAmount: draftNotes.reduce((sum, cn) => sum + Number(cn.amount), 0),
      issuedCount: issuedNotes.length,
      issuedAmount: issuedNotes.reduce((sum, cn) => sum + Number(cn.amount), 0),
      appliedCount: appliedNotes.length,
      appliedAmount: appliedNotes.reduce((sum, cn) => sum + Number(cn.applied_amount || cn.amount), 0),
    };
  }, [creditNotes]);

  // Loading skeleton
  if (isInitialLoad && isPending) {
    return (
      <div className="space-y-6">
        {/* Header Skeleton */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-72" />
          </div>
          <Skeleton className="h-10 w-40" />
        </div>

        {/* Summary Cards Skeleton */}
        <div className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-4" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-8 w-32 mb-1" />
                <Skeleton className="h-3 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Table Skeleton */}
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-64" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex gap-4">
                <Skeleton className="h-10 flex-1" />
                <Skeleton className="h-10 w-[150px]" />
                <Skeleton className="h-10 w-[150px]" />
              </div>
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
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
          <h1 className="text-2xl font-bold tracking-tight">Credit Notes</h1>
          <p className="text-muted-foreground">
            Manage credit notes, refunds, and fee adjustments
          </p>
        </div>
        <Button asChild>
          <Link href="/finance/credit-notes/new">
            <Plus className="mr-2 h-4 w-4" />
            New Credit Note
          </Link>
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Credit Notes</CardTitle>
            <ReceiptText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCount}</div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>

        <Card className="border-gray-200 dark:border-gray-800">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending Draft</CardTitle>
            <FileText className="h-4 w-4 text-gray-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(summaryStats.draftAmount)}</div>
            <p className="text-xs text-muted-foreground">
              {summaryStats.draftCount} note{summaryStats.draftCount !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>

        <Card className="border-blue-200 dark:border-blue-900">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Issued (Available)</CardTitle>
            <Wallet className="h-4 w-4 text-blue-600 dark:text-blue-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {formatCurrency(summaryStats.issuedAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summaryStats.issuedCount} note{summaryStats.issuedCount !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>

        <Card className="border-green-200 dark:border-green-900">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Applied to Invoices</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formatCurrency(summaryStats.appliedAmount)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summaryStats.appliedCount} note{summaryStats.appliedCount !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters & Table */}
      <Card>
        <CardHeader>
          <CardTitle>Credit Notes</CardTitle>
          <CardDescription>
            View and manage all credit notes for fee adjustments and refunds
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-4 sm:flex-row sm:items-center">
            <div className="relative flex-1 min-w-0">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by credit note number or student..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full sm:w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                    <SelectItem key={key} value={key}>
                      {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger className="w-full sm:w-[150px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {Object.entries(TYPE_CONFIG).map(([key, config]) => (
                    <SelectItem key={key} value={key}>
                      {config.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {creditNotes.length > 0 ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Credit Note #</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="hidden sm:table-cell">Status</TableHead>
                    <TableHead className="hidden md:table-cell">Created</TableHead>
                    <TableHead className="w-[70px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {creditNotes.map((cn) => {
                    const statusConfig = STATUS_CONFIG[cn.status] || STATUS_CONFIG.draft;
                    const typeConfig = TYPE_CONFIG[cn.credit_note_type] || TYPE_CONFIG.other;
                    const TypeIcon = typeConfig.icon;

                    return (
                      <TableRow key={cn.id} className="group">
                        <TableCell className="font-medium">
                          <Link
                            href={`/finance/credit-notes/${cn.id}`}
                            className="hover:underline text-primary"
                          >
                            {cn.credit_note_number}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <div>
                            <div className="font-medium">{cn.student_name}</div>
                            <div className="text-sm text-muted-foreground">
                              {cn.student_id_number}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="secondary" className={`gap-1 ${typeConfig.color}`}>
                            <TypeIcon className="h-3 w-3" />
                            {typeConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums">
                          {formatCurrency(cn.amount)}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="secondary" className={statusConfig.color}>
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-muted-foreground">
                          {formatDate(cn.created_at)}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link href={`/finance/credit-notes/${cn.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              {cn.status === "draft" && (
                                <>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem onClick={() => openIssueDialog(cn)}>
                                    <Send className="mr-2 h-4 w-4" />
                                    Issue Credit Note
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onClick={() => openCancelDialog(cn)}
                                    className="text-destructive focus:text-destructive"
                                  >
                                    <XCircle className="mr-2 h-4 w-4" />
                                    Cancel
                                  </DropdownMenuItem>
                                </>
                              )}
                              {cn.status === "issued" && (
                                <>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem asChild>
                                    <Link href={`/finance/credit-notes/${cn.id}?action=apply`}>
                                      <CheckCircle className="mr-2 h-4 w-4" />
                                      Apply to Invoice
                                    </Link>
                                  </DropdownMenuItem>
                                  <DropdownMenuItem asChild>
                                    <Link href={`/finance/credit-notes/${cn.id}?action=refund`}>
                                      <RefreshCw className="mr-2 h-4 w-4" />
                                      Refund
                                    </Link>
                                  </DropdownMenuItem>
                                </>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[300px] flex-col items-center justify-center gap-4 rounded-lg border border-dashed">
              <div className="rounded-full bg-muted p-4">
                <CreditCard className="h-8 w-8 text-muted-foreground" />
              </div>
              <div className="text-center">
                <p className="font-medium">No credit notes found</p>
                <p className="text-sm text-muted-foreground">
                  {searchQuery || statusFilter !== "all" || typeFilter !== "all"
                    ? "Try adjusting your filters"
                    : "Create your first credit note to get started"}
                </p>
              </div>
              {!searchQuery && statusFilter === "all" && typeFilter === "all" && (
                <Button asChild>
                  <Link href="/finance/credit-notes/new">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Credit Note
                  </Link>
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Issue Confirmation Dialog */}
      <Dialog open={issueDialogOpen} onOpenChange={setIssueDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Issue Credit Note</DialogTitle>
            <DialogDescription>
              Issue credit note{" "}
              <span className="font-medium">{selectedCreditNote?.credit_note_number}</span>{" "}
              for <span className="font-medium">{selectedCreditNote && formatCurrency(selectedCreditNote.amount)}</span>{" "}
              to {selectedCreditNote?.student_name}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-start space-x-3 rounded-lg border p-4">
              <Checkbox
                id="autoApply"
                checked={autoApplyToInvoice}
                onCheckedChange={(checked) => setAutoApplyToInvoice(checked === true)}
              />
              <div className="space-y-1">
                <Label
                  htmlFor="autoApply"
                  className="text-sm font-medium leading-none cursor-pointer"
                >
                  Auto-apply to oldest unpaid invoice
                </Label>
                <p className="text-sm text-muted-foreground">
                  Automatically apply this credit to the student's oldest outstanding invoice.
                  If unchecked, the credit will be added to the student's balance for later use.
                </p>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIssueDialogOpen(false)}
              disabled={isProcessing}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirmIssue} disabled={isProcessing}>
              {isProcessing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Issue Credit Note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Credit Note</DialogTitle>
            <DialogDescription>
              Cancel credit note{" "}
              <span className="font-medium">{selectedCreditNote?.credit_note_number}</span>{" "}
              for {selectedCreditNote?.student_name}. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="cancelReason">Reason for cancellation *</Label>
              <Textarea
                id="cancelReason"
                placeholder="Enter the reason for cancelling this credit note..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCancelDialogOpen(false)}
              disabled={isProcessing}
            >
              Close
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmCancel}
              disabled={isProcessing || !cancelReason.trim()}
            >
              {isProcessing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Cancel Credit Note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
