"use client";

import { useEffect, useState, useTransition } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  ArrowLeft,
  Send,
  CheckCircle,
  RefreshCw,
  XCircle,
  AlertCircle,
  CreditCard,
  User,
  FileText,
  Calendar,
  DollarSign,
  Loader2,
} from "lucide-react";
import {
  getCreditNote,
  issueCreditNote,
  applyCreditNote,
  refundCreditNote,
  cancelCreditNote,
  getInvoices,
} from "@/actions/finance.action";
import type { CreditNoteWithDetails, InvoiceWithDetails, CreditNoteStatus, CreditNoteType } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

export default function CreditNoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [creditNote, setCreditNote] = useState<CreditNoteWithDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [showApplyDialog, setShowApplyDialog] = useState(searchParams.get("action") === "apply");
  const [showRefundDialog, setShowRefundDialog] = useState(searchParams.get("action") === "refund");
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showIssueConfirm, setShowIssueConfirm] = useState(false);

  // Apply dialog state
  const [invoices, setInvoices] = useState<InvoiceWithDetails[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState("");
  const [applyAmount, setApplyAmount] = useState("");

  // Refund dialog state
  const [refundMethod, setRefundMethod] = useState("");
  const [refundReference, setRefundReference] = useState("");

  // Cancel dialog state
  const [cancelReason, setCancelReason] = useState("");

  const creditNoteId = params.id as string;

  const fetchData = () => {
    startTransition(async () => {
      const result = await getCreditNote(creditNoteId);
      if (result.success && result.data) {
        setCreditNote(result.data);
        // Fetch invoices for apply dialog
        if (result.data.status === "issued") {
          const invoicesResult = await getInvoices({
            studentId: result.data.student_id,
            status: "issued", // Only unpaid/partial invoices
            pageSize: 50,
          });
          if (invoicesResult.success && invoicesResult.data) {
            // Filter to invoices with balance
            setInvoices(invoicesResult.data.items.filter(inv => inv.balance > 0));
          }
        }
      } else {
        setError(result.error || "Failed to load credit note");
      }
    });
  };

  useEffect(() => {
    fetchData();
  }, [creditNoteId]);

  const handleIssue = () => {
    startTransition(async () => {
      const result = await issueCreditNote(creditNoteId);
      if (result.success) {
        toast({
          title: "Credit note issued",
          description: "The credit note has been issued and added to the student's credit balance.",
        });
        fetchData();
        setShowIssueConfirm(false);
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to issue credit note",
          variant: "destructive",
        });
      }
    });
  };

  const handleApply = () => {
    if (!selectedInvoiceId) {
      toast({
        title: "Error",
        description: "Please select an invoice to apply the credit to",
        variant: "destructive",
      });
      return;
    }

    startTransition(async () => {
      const result = await applyCreditNote(creditNoteId, {
        invoice_id: selectedInvoiceId,
        amount: applyAmount ? parseFloat(applyAmount) : undefined,
      });
      if (result.success) {
        toast({
          title: "Credit note applied",
          description: "The credit has been applied to the selected invoice.",
        });
        fetchData();
        setShowApplyDialog(false);
        setSelectedInvoiceId("");
        setApplyAmount("");
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to apply credit note",
          variant: "destructive",
        });
      }
    });
  };

  const handleRefund = () => {
    if (!refundMethod) {
      toast({
        title: "Error",
        description: "Please select a refund method",
        variant: "destructive",
      });
      return;
    }

    startTransition(async () => {
      const result = await refundCreditNote(creditNoteId, {
        refund_method: refundMethod,
        refund_reference: refundReference || undefined,
      });
      if (result.success) {
        toast({
          title: "Credit note refunded",
          description: "The refund has been recorded successfully.",
        });
        fetchData();
        setShowRefundDialog(false);
        setRefundMethod("");
        setRefundReference("");
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to record refund",
          variant: "destructive",
        });
      }
    });
  };

  const handleCancel = () => {
    if (!cancelReason) {
      toast({
        title: "Error",
        description: "Please provide a reason for cancellation",
        variant: "destructive",
      });
      return;
    }

    startTransition(async () => {
      const result = await cancelCreditNote(creditNoteId, { reason: cancelReason });
      if (result.success) {
        toast({
          title: "Credit note cancelled",
          description: "The credit note has been cancelled.",
        });
        fetchData();
        setShowCancelDialog(false);
        setCancelReason("");
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to cancel credit note",
          variant: "destructive",
        });
      }
    });
  };

  const getStatusColor = (status: CreditNoteStatus) => {
    switch (status) {
      case "draft":
        return "bg-gray-100 text-gray-800";
      case "issued":
        return "bg-blue-100 text-blue-800";
      case "applied":
        return "bg-green-100 text-green-800";
      case "refunded":
        return "bg-cyan-100 text-cyan-800";
      case "cancelled":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getTypeColor = (type: CreditNoteType) => {
    switch (type) {
      case "overpayment":
        return "bg-green-100 text-green-800";
      case "fee_reduction":
        return "bg-blue-100 text-blue-800";
      case "error_correction":
        return "bg-orange-100 text-orange-800";
      case "scholarship_adjustment":
        return "bg-teal-100 text-teal-800";
      case "other":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const formatType = (type: CreditNoteType) => {
    return type.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  };

  if (isPending && !creditNote) {
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
        <Button onClick={() => router.push("/finance/credit-notes")}>
          Back to Credit Notes
        </Button>
      </div>
    );
  }

  if (!creditNote) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/credit-notes">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                {creditNote.credit_note_number}
              </h1>
              <Badge variant="secondary" className={getStatusColor(creditNote.status)}>
                {creditNote.status.charAt(0).toUpperCase() + creditNote.status.slice(1)}
              </Badge>
            </div>
            <p className="text-muted-foreground">
              <Badge variant="secondary" className={getTypeColor(creditNote.credit_note_type)}>
                {formatType(creditNote.credit_note_type)}
              </Badge>
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {creditNote.status === "draft" && (
            <>
              <Button variant="outline" onClick={() => setShowCancelDialog(true)}>
                <XCircle className="mr-2 h-4 w-4" />
                Cancel
              </Button>
              <Button onClick={() => setShowIssueConfirm(true)}>
                <Send className="mr-2 h-4 w-4" />
                Issue Credit Note
              </Button>
            </>
          )}
          {creditNote.status === "issued" && (
            <>
              <Button variant="outline" onClick={() => setShowRefundDialog(true)}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refund
              </Button>
              <Button onClick={() => setShowApplyDialog(true)}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Apply to Invoice
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Amount</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{formatCurrency(creditNote.amount)}</div>
            <p className="text-xs text-muted-foreground">{creditNote.currency}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Student</CardTitle>
            <User className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">
              <Link
                href={`/students/${creditNote.student_id}`}
                className="hover:underline"
              >
                {creditNote.student_name}
              </Link>
            </div>
            <p className="text-xs text-muted-foreground">{creditNote.student_id_number}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Created</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-semibold">{formatDate(creditNote.created_at)}</div>
            {creditNote.issued_at && (
              <p className="text-xs text-muted-foreground">
                Issued: {formatDate(creditNote.issued_at)}
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Related Invoice</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {creditNote.original_invoice_number ? (
              <Link
                href={`/finance/invoices/${creditNote.original_invoice_id}`}
                className="text-lg font-semibold hover:underline"
              >
                {creditNote.original_invoice_number}
              </Link>
            ) : (
              <div className="text-lg font-semibold text-muted-foreground">None</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Details */}
      <Card>
        <CardHeader>
          <CardTitle>Credit Note Details</CardTitle>
          <CardDescription>Information about this credit note</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm text-muted-foreground">Reason</Label>
            <p className="mt-1">{creditNote.reason}</p>
          </div>

          {creditNote.notes && (
            <div>
              <Label className="text-sm text-muted-foreground">Additional Notes</Label>
              <p className="mt-1">{creditNote.notes}</p>
            </div>
          )}

          {creditNote.issued_by_name && (
            <div>
              <Label className="text-sm text-muted-foreground">Issued By</Label>
              <p className="mt-1">{creditNote.issued_by_name}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Applied/Refund Info */}
      {creditNote.status === "applied" && creditNote.applied_to_invoice_number && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Applied to Invoice
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Invoice:</span>
              <Link
                href={`/finance/invoices/${creditNote.applied_to_invoice_id}`}
                className="font-medium hover:underline"
              >
                {creditNote.applied_to_invoice_number}
              </Link>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Amount Applied:</span>
              <span className="font-medium">
                {formatCurrency(creditNote.applied_amount || creditNote.amount)}
              </span>
            </div>
            {creditNote.applied_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Applied On:</span>
                <span>{formatDate(creditNote.applied_at)}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {creditNote.status === "refunded" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5 text-cyan-600" />
              Refund Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Method:</span>
              <span className="font-medium capitalize">
                {creditNote.refund_method?.replace(/_/g, " ")}
              </span>
            </div>
            {creditNote.refund_reference && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Reference:</span>
                <span>{creditNote.refund_reference}</span>
              </div>
            )}
            {creditNote.refunded_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Refunded On:</span>
                <span>{formatDate(creditNote.refunded_at)}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {creditNote.status === "cancelled" && creditNote.cancel_reason && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Cancellation Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              <Label className="text-sm text-muted-foreground">Reason</Label>
              <p className="mt-1">{creditNote.cancel_reason}</p>
            </div>
            {creditNote.cancelled_at && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cancelled On:</span>
                <span>{formatDate(creditNote.cancelled_at)}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Issue Confirmation Dialog */}
      <AlertDialog open={showIssueConfirm} onOpenChange={setShowIssueConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Issue Credit Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to issue this credit note for{" "}
              <span className="font-semibold">{formatCurrency(creditNote.amount)}</span>?
              This will add the amount to {creditNote.student_name}'s credit balance.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleIssue} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Issue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Apply to Invoice Dialog */}
      <Dialog open={showApplyDialog} onOpenChange={setShowApplyDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply Credit to Invoice</DialogTitle>
            <DialogDescription>
              Select an invoice to apply this credit of {formatCurrency(creditNote.amount)} to.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Select Invoice</Label>
              <Select value={selectedInvoiceId} onValueChange={setSelectedInvoiceId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an invoice" />
                </SelectTrigger>
                <SelectContent>
                  {invoices.length === 0 ? (
                    <SelectItem value="no-invoices" disabled>
                      No unpaid invoices found
                    </SelectItem>
                  ) : (
                    invoices.map((invoice) => (
                      <SelectItem key={invoice.id} value={invoice.id}>
                        {invoice.invoice_number} - Balance: {formatCurrency(invoice.balance)}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Amount to Apply (Optional)</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max={creditNote.amount}
                placeholder={`Max: ${creditNote.amount}`}
                value={applyAmount}
                onChange={(e) => setApplyAmount(e.target.value)}
              />
              <p className="text-sm text-muted-foreground">
                Leave empty to apply the full credit amount
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowApplyDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleApply} disabled={isPending || !selectedInvoiceId}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Apply Credit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Refund Dialog */}
      <Dialog open={showRefundDialog} onOpenChange={setShowRefundDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record Refund</DialogTitle>
            <DialogDescription>
              Record a refund of {formatCurrency(creditNote.amount)} to the student/guardian.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Refund Method</Label>
              <Select value={refundMethod} onValueChange={setRefundMethod}>
                <SelectTrigger>
                  <SelectValue placeholder="Select method" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cash">Cash</SelectItem>
                  <SelectItem value="momo">Mobile Money</SelectItem>
                  <SelectItem value="bank_transfer">Bank Transfer</SelectItem>
                  <SelectItem value="cheque">Cheque</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Reference Number (Optional)</Label>
              <Input
                placeholder="e.g., Transaction ID, Cheque Number"
                value={refundReference}
                onChange={(e) => setRefundReference(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRefundDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleRefund} disabled={isPending || !refundMethod}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Record Refund
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Cancel Dialog */}
      <Dialog open={showCancelDialog} onOpenChange={setShowCancelDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Credit Note</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel this credit note? Please provide a reason.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Reason for Cancellation</Label>
              <Input
                placeholder="Enter reason..."
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCancelDialog(false)}>
              Keep Credit Note
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancel}
              disabled={isPending || !cancelReason}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Cancel Credit Note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
