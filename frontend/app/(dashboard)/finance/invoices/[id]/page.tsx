"use client";

import { useEffect, useState, useTransition, useCallback, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ArrowLeft,
  Send,
  DollarSign,
  XCircle,
  Printer,
  AlertCircle,
  FileText,
  User,
  Calendar,
  Download,
  Mail,
  Banknote,
  Smartphone,
  Building2,
  CreditCard,
  Receipt,
  Ban,
  Loader2,
  Wallet,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getInvoice, issueInvoice, cancelInvoice, getInvoicePdfAuthContext, emailInvoice, syncSingleInvoice, getStudentScholarships, getStudentCreditBalance, applyCreditNote, getCreditNotes } from "@/actions/finance.action";
import type { InvoiceWithDetails, CreditNoteWithDetails } from "@/types";
import type { StudentScholarshipWithDetails, StudentCreditBalance } from "@/types/finance.type";
import { RefreshCw, Award } from "lucide-react";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { Progress } from "@/components/ui/progress";
import { useToast } from "@/hooks/use-toast";

// Status color mapping (outside component)
const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-800",
  issued: "bg-blue-100 text-blue-800",
  partial: "bg-yellow-100 text-yellow-800",
  paid: "bg-green-100 text-green-800",
  overdue: "bg-red-100 text-red-800",
  cancelled: "bg-gray-100 text-gray-500",
};

// Payment method labels (outside component)
const PAYMENT_METHOD_LABELS: Record<string, string> = {
  cash: "Cash",
  momo_mtn: "MTN MoMo",
  momo_vodafone: "Vodafone Cash",
  momo_airteltigo: "AirtelTigo Money",
  bank_transfer: "Bank Transfer",
  card: "Card",
  cheque: "Cheque",
  other: "Other",
};

// Payment method icon component (outside component)
function PaymentMethodIcon({ method }: { method: string }) {
  switch (method) {
    case "cash":
      return <Banknote className="h-4 w-4" />;
    case "momo_mtn":
    case "momo_vodafone":
    case "momo_airteltigo":
      return <Smartphone className="h-4 w-4" />;
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

export default function InvoiceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [invoice, setInvoice] = useState<InvoiceWithDetails | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Cancel dialog state
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");

  // Student scholarships state
  const [studentScholarships, setStudentScholarships] = useState<StudentScholarshipWithDetails[]>([]);
  const [isSyncing, setIsSyncing] = useState(false);

  // Email dialog state
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [emailAddress, setEmailAddress] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [ccEmails, setCcEmails] = useState("");
  const [isSendingEmail, setIsSendingEmail] = useState(false);

  // Credit balance state
  const [creditBalance, setCreditBalance] = useState<StudentCreditBalance | null>(null);
  const [availableCreditNotes, setAvailableCreditNotes] = useState<CreditNoteWithDetails[]>([]);
  const [applyCreditDialogOpen, setApplyCreditDialogOpen] = useState(false);
  const [selectedCreditNoteId, setSelectedCreditNoteId] = useState<string>("");
  const [applyAmount, setApplyAmount] = useState<string>("");
  const [isApplyingCredit, setIsApplyingCredit] = useState(false);

  const invoiceId = params.id as string;

  // Memoized fetch function
  const fetchInvoice = useCallback(() => {
    startTransition(async () => {
      const result = await getInvoice(invoiceId);
      if (result.success && result.data) {
        setInvoice(result.data);
      } else {
        setError(result.error || "Failed to load invoice");
      }
    });
  }, [invoiceId]);

  useEffect(() => {
    fetchInvoice();
  }, [fetchInvoice]);

  // Fetch student scholarships and credit balance when invoice is loaded
  useEffect(() => {
    if (invoice?.student_id) {
      // Fetch scholarships
      getStudentScholarships(invoice.student_id).then((result) => {
        if (result.success && result.data) {
          // Filter for active scholarships
          const activeScholarships = result.data.items.filter(
            (s) => s.status === "active"
          );
          setStudentScholarships(activeScholarships);
        }
      });

      // Fetch credit balance
      getStudentCreditBalance(invoice.student_id).then((result) => {
        if (result.success && result.data) {
          setCreditBalance(result.data);
        }
      });

      // Fetch issued credit notes (available for applying)
      getCreditNotes({ studentId: invoice.student_id, status: "issued" }).then((result) => {
        if (result.success && result.data) {
          setAvailableCreditNotes(result.data.items);
        }
      });
    }
  }, [invoice?.student_id]);

  // Memoized handlers
  const handleIssue = useCallback(() => {
    startTransition(async () => {
      const result = await issueInvoice(invoiceId);
      if (result.success) {
        toast({
          title: "Invoice issued",
          description: "The invoice has been issued successfully.",
        });
        fetchInvoice();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to issue invoice",
          variant: "destructive",
        });
      }
    });
  }, [invoiceId, toast, fetchInvoice]);

  const handleCancel = useCallback(() => {
    if (!cancelReason.trim()) return;

    startTransition(async () => {
      const result = await cancelInvoice(invoiceId, { reason: cancelReason });
      if (result.success) {
        toast({
          title: "Invoice cancelled",
          description: "The invoice has been cancelled.",
        });
        setCancelDialogOpen(false);
        setCancelReason("");
        fetchInvoice();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to cancel invoice",
          variant: "destructive",
        });
      }
    });
  }, [invoiceId, cancelReason, toast, fetchInvoice]);

  const handleSync = useCallback(async () => {
    if (!invoice?.fee_structure_id) {
      toast({
        title: "Error",
        description: "No fee structure linked to this invoice",
        variant: "destructive",
      });
      return;
    }

    setIsSyncing(true);
    try {
      const result = await syncSingleInvoice(invoiceId, invoice.fee_structure_id);
      if (result.success) {
        toast({
          title: "Invoice synced",
          description: `Invoice updated successfully. ${result.data?.synced_count || 1} invoice(s) synced.`,
        });
        fetchInvoice();
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to sync invoice",
          variant: "destructive",
        });
      }
    } finally {
      setIsSyncing(false);
    }
  }, [invoiceId, invoice?.fee_structure_id, toast, fetchInvoice]);

  const handleDownloadPdf = useCallback(async () => {
    const authResult = await getInvoicePdfAuthContext();
    if (!authResult.success || !authResult.data) {
      toast({
        title: "Error",
        description: authResult.error || "Failed to get authorization",
        variant: "destructive",
      });
      return;
    }

    const { token, subdomain } = authResult.data;
    // NEXT_PUBLIC_API_URL already includes /api/v1
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

    try {
      const response = await fetch(`${apiUrl}/finance/invoices/${invoiceId}/pdf`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to download PDF");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;

      // Get filename from Content-Disposition header or default
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = `Invoice_${invoice?.invoice_number || invoiceId}.pdf`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+?)"?$/);
        if (match) {
          filename = match[1];
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast({
        title: "Download started",
        description: "Invoice PDF is being downloaded.",
      });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to download PDF",
        variant: "destructive",
      });
    }
  }, [invoiceId, invoice?.invoice_number, toast]);

  const handlePrint = useCallback(async () => {
    const authResult = await getInvoicePdfAuthContext();
    if (!authResult.success || !authResult.data) {
      toast({
        title: "Error",
        description: authResult.error || "Failed to get authorization",
        variant: "destructive",
      });
      return;
    }

    const { token, subdomain } = authResult.data;
    // NEXT_PUBLIC_API_URL already includes /api/v1
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

    try {
      const response = await fetch(`${apiUrl}/finance/invoices/${invoiceId}/pdf`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
      });

      if (!response.ok) {
        throw new Error("Failed to load PDF for printing");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      // Open PDF in new window and trigger print
      const printWindow = window.open(url, "_blank");
      if (printWindow) {
        printWindow.onload = () => {
          printWindow.print();
        };
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to print invoice",
        variant: "destructive",
      });
    }
  }, [invoiceId, toast]);

  const handleOpenEmailDialog = useCallback(() => {
    setEmailAddress("");
    setRecipientName("");
    setCcEmails("");
    setEmailDialogOpen(true);
  }, []);

  const handleSendEmail = useCallback(async () => {
    if (!emailAddress.trim()) {
      toast({
        title: "Error",
        description: "Please enter an email address",
        variant: "destructive",
      });
      return;
    }

    // Parse CC emails (comma-separated)
    const ccEmailList = ccEmails
      .split(",")
      .map((e) => e.trim())
      .filter((e) => e.length > 0);

    setIsSendingEmail(true);
    try {
      const result = await emailInvoice(invoiceId, {
        email: emailAddress.trim(),
        recipient_name: recipientName.trim() || undefined,
        cc_emails: ccEmailList.length > 0 ? ccEmailList : undefined,
      });

      if (result.success) {
        toast({
          title: "Email sent",
          description: result.data?.message || `Invoice sent to ${emailAddress}`,
        });
        setEmailDialogOpen(false);
        setEmailAddress("");
        setRecipientName("");
        setCcEmails("");
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to send email",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to send email",
        variant: "destructive",
      });
    } finally {
      setIsSendingEmail(false);
    }
  }, [invoiceId, emailAddress, recipientName, ccEmails, toast]);

  const handleOpenApplyCreditDialog = useCallback(() => {
    if (availableCreditNotes.length > 0) {
      setSelectedCreditNoteId(availableCreditNotes[0].id);
      // Default to applying the minimum of credit note amount and invoice balance
      const firstNote = availableCreditNotes[0];
      const maxApply = Math.min(Number(firstNote.remaining_amount || firstNote.amount), Number(invoice?.balance || 0));
      setApplyAmount(maxApply.toString());
    }
    setApplyCreditDialogOpen(true);
  }, [availableCreditNotes, invoice?.balance]);

  const handleApplyCredit = useCallback(async () => {
    if (!selectedCreditNoteId || !applyAmount) return;

    setIsApplyingCredit(true);
    try {
      const result = await applyCreditNote(selectedCreditNoteId, {
        invoice_id: invoiceId,
        amount: parseFloat(applyAmount),
      });

      if (result.success) {
        toast({
          title: "Credit applied",
          description: `${formatCurrency(parseFloat(applyAmount))} credit has been applied to this invoice.`,
        });
        setApplyCreditDialogOpen(false);
        setSelectedCreditNoteId("");
        setApplyAmount("");
        // Refresh invoice and credit data
        fetchInvoice();
        if (invoice?.student_id) {
          getStudentCreditBalance(invoice.student_id).then((result) => {
            if (result.success && result.data) {
              setCreditBalance(result.data);
            }
          });
          getCreditNotes({ studentId: invoice.student_id, status: "issued" }).then((result) => {
            if (result.success && result.data) {
              setAvailableCreditNotes(result.data.items);
            }
          });
        }
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to apply credit",
          variant: "destructive",
        });
      }
    } finally {
      setIsApplyingCredit(false);
    }
  }, [selectedCreditNoteId, applyAmount, invoiceId, toast, fetchInvoice, invoice?.student_id]);

  // Memoized computed values
  const { totalAmount, amountPaid, paymentProgress } = useMemo(() => {
    const total = Number(invoice?.total_amount || 0);
    const paid = Number(invoice?.amount_paid || 0);
    const progress = total > 0 ? (paid / total) * 100 : 0;
    return { totalAmount: total, amountPaid: paid, paymentProgress: progress };
  }, [invoice?.total_amount, invoice?.amount_paid]);

  // Check if invoice has payments (for cancel validation)
  const hasPayments = amountPaid > 0;

  // Scholarship status for this invoice
  const scholarshipCreditStatus = useMemo(() => {
    if (!invoice) return null;

    const hasActiveScholarships = studentScholarships.length > 0;
    const hasScholarshipDiscount = Number(invoice.scholarship_discount || 0) > 0;

    if (hasScholarshipDiscount) {
      return {
        type: "scholarship_applied" as const,
        message: "Scholarship discount has been applied to this invoice.",
      };
    }

    if (hasActiveScholarships) {
      return {
        type: "scholarship_not_applied" as const,
        message: "This student has active scholarship(s) that were awarded after this invoice was generated.",
      };
    }

    return null;
  }, [invoice, studentScholarships]);


  if (isPending && !invoice) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => router.push("/finance/invoices")}>
          Back to Invoices
        </Button>
      </div>
    );
  }

  if (!invoice) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/invoices">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                {invoice.invoice_number}
              </h1>
              <Badge
                variant="secondary"
                className={STATUS_COLORS[invoice.status] || STATUS_COLORS.draft}
              >
                {invoice.status}
              </Badge>
              {invoice.adjustment_type && (
                <Badge variant="outline" className="bg-orange-50 text-orange-700 border-orange-300">
                  Adjustment
                </Badge>
              )}
            </div>
            <p className="text-muted-foreground">
              Issued: {invoice.issue_date ? formatDate(invoice.issue_date) : "Not issued"}
            </p>
            {invoice.adjustment_for_invoice_id && (
              <p className="text-sm text-orange-600">
                Adjustment for invoice (Scholarship revoked)
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={handleDownloadPdf} disabled={isPending}>
            <Download className="mr-2 h-4 w-4" />
            Download PDF
          </Button>
          <Button variant="outline" onClick={handleOpenEmailDialog} disabled={isPending}>
            <Mail className="mr-2 h-4 w-4" />
            Email
          </Button>
          <Button variant="outline" onClick={handlePrint} disabled={isPending}>
            <Printer className="mr-2 h-4 w-4" />
            Print
          </Button>
          {invoice.status === "draft" && invoice.fee_structure_id && (
            <Button
              variant="outline"
              onClick={handleSync}
              disabled={isSyncing || isPending}
            >
              {isSyncing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Sync with Fee Structure
            </Button>
          )}
          {invoice.status === "draft" && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button disabled={isPending}>
                  {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Issue Invoice
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Issue Invoice</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will issue the invoice to the student/guardian. The invoice
                    will be marked as issued and can no longer be edited.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={handleIssue}>
                    Issue Invoice
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}
          {Number(invoice.balance) > 0 && invoice.status !== "cancelled" && invoice.status !== "draft" && (
            <Button asChild>
              <Link href={`/finance/payments/record?invoice_id=${invoiceId}`}>
                <DollarSign className="mr-2 h-4 w-4" />
                Record Payment
              </Link>
            </Button>
          )}
          {invoice.status !== "cancelled" && invoice.status !== "paid" && (
            <Button
              variant="destructive"
              onClick={() => setCancelDialogOpen(true)}
              disabled={isPending}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Cancel
            </Button>
          )}
        </div>
      </div>

      {/* Scholarship Status Banner */}
      {scholarshipCreditStatus && invoice.status !== "draft" && (
        <Card className={
          scholarshipCreditStatus.type === "scholarship_applied"
            ? "border-green-300 dark:border-green-800 bg-green-50 dark:bg-green-950/30"
            : "border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30"
        }>
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <Award className={
                scholarshipCreditStatus.type === "scholarship_applied"
                  ? "h-5 w-5 text-green-600 dark:text-green-400 mt-0.5"
                  : "h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5"
              } />
              <div className="flex-1">
                {scholarshipCreditStatus.type === "scholarship_applied" && (
                  <>
                    <h4 className="font-medium text-green-800 dark:text-green-200">
                      Scholarship Applied
                    </h4>
                    <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                      {scholarshipCreditStatus.message}
                    </p>
                  </>
                )}

                {scholarshipCreditStatus.type === "scholarship_not_applied" && (
                  <>
                    <h4 className="font-medium text-amber-800 dark:text-amber-200">
                      Active Scholarship Not Applied
                    </h4>
                    <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                      This student has {studentScholarships.length} active scholarship(s) that were awarded after this invoice was generated:
                    </p>
                    <ul className="list-disc list-inside text-sm text-amber-700 dark:text-amber-300 mt-2">
                      {studentScholarships.map((s) => (
                        <li key={s.id}>
                          <Link
                            href={`/finance/scholarships/${s.scholarship_id}`}
                            className="hover:underline font-medium"
                          >
                            {s.scholarship_name}
                          </Link>
                          {" "}({s.coverage_type === "percentage" ? `${s.coverage_value}%` : formatCurrency(s.coverage_value)})
                        </li>
                      ))}
                    </ul>
                    <p className="text-sm text-amber-700 dark:text-amber-300 mt-3">
                      To apply the scholarship discount, cancel this invoice and regenerate it from the fee structure. The scholarship will be applied automatically.
                    </p>
                  </>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Payment Progress */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">Payment Progress</span>
            <span className="text-sm text-muted-foreground">
              {formatNumber(paymentProgress, 1)}% paid
            </span>
          </div>
          <Progress value={paymentProgress} className="h-2" />
          <div className="flex justify-between mt-2 text-sm">
            <span className="text-green-600">
              Paid: {formatCurrency(invoice.amount_paid)}
            </span>
            <span className="text-orange-600">
              Balance: {formatCurrency(invoice.balance)}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Student Credit Balance */}
      {creditBalance &&
       Number(creditBalance.available_balance) > 0 &&
       Number(invoice.balance) > 0 &&
       invoice.status !== "cancelled" &&
       invoice.status !== "draft" && (
        <Card className="border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="rounded-full bg-blue-100 dark:bg-blue-900 p-2">
                  <Wallet className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="font-medium">Student Has Available Credit</p>
                  <p className="text-sm text-muted-foreground">
                    {creditBalance.student_name} has{" "}
                    <span className="font-semibold text-blue-600 dark:text-blue-400">
                      {formatCurrency(creditBalance.available_balance ?? 0)}
                    </span>{" "}
                    in available credit from {availableCreditNotes.length} issued credit note{availableCreditNotes.length !== 1 ? "s" : ""}.
                  </p>
                </div>
              </div>
              <Button onClick={handleOpenApplyCreditDialog} disabled={availableCreditNotes.length === 0}>
                <CreditCard className="mr-2 h-4 w-4" />
                Apply Credit
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Amount</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(invoice.total_amount)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Amount Paid</CardTitle>
            <DollarSign className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatCurrency(invoice.amount_paid)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Balance Due</CardTitle>
            <AlertCircle className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {formatCurrency(invoice.balance)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Student & Invoice Info */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-4 w-4" />
              Student Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2">
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Name
                </dt>
                <dd>
                  <Link
                    href={`/students/${invoice.student_id}`}
                    className="font-medium hover:underline"
                  >
                    {invoice.student_name}
                  </Link>
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Student ID
                </dt>
                <dd className="font-mono">{invoice.student_id_number || "-"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Class
                </dt>
                <dd>{invoice.class_name || "-"}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Invoice Details
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-2">
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Academic Year
                </dt>
                <dd>{invoice.academic_year_name || "-"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Term
                </dt>
                <dd>{invoice.term_name || "-"}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Issue Date
                </dt>
                <dd>
                  {invoice.issue_date ? formatDate(invoice.issue_date) : "Not issued"}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-muted-foreground">
                  Due Date
                </dt>
                <dd>
                  {invoice.due_date ? formatDate(invoice.due_date) : "-"}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Invoice Items */}
      <Card>
        <CardHeader>
          <CardTitle>Invoice Items</CardTitle>
          <CardDescription>Fee breakdown for this invoice</CardDescription>
        </CardHeader>
        <CardContent>
          {invoice.items && invoice.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Amount (GHS)</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoice.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.description}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatNumber(item.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Totals */}
              <div className="mt-4 border-t pt-4">
                <div className="flex flex-col items-end gap-1">
                  <div className="flex w-64 justify-between">
                    <span className="text-muted-foreground">Subtotal</span>
                    <span>{formatCurrency(invoice.subtotal)}</span>
                  </div>
                  {Number(invoice.discount_amount) > 0 && (
                    <div className="flex w-64 justify-between">
                      <span className="text-muted-foreground">Discount</span>
                      <span className="text-green-600">
                        -{formatCurrency(invoice.discount_amount)}
                      </span>
                    </div>
                  )}
                  {invoice.scholarship_discount &&
                    Number(invoice.scholarship_discount) > 0 && (
                      <div className="flex w-64 justify-between">
                        <span className="text-muted-foreground">
                          Scholarship
                        </span>
                        <span className="text-blue-600">
                          -{formatCurrency(invoice.scholarship_discount)}
                        </span>
                      </div>
                    )}
                  {Number(invoice.tax_amount) > 0 && (
                    <div className="flex w-64 justify-between">
                      <span className="text-muted-foreground">Tax</span>
                      <span>{formatCurrency(invoice.tax_amount)}</span>
                    </div>
                  )}
                  <div className="flex w-64 justify-between border-t pt-1 text-lg font-bold">
                    <span>Total</span>
                    <span>{formatCurrency(invoice.total_amount)}</span>
                  </div>
                  <div className="flex w-64 justify-between text-sm">
                    <span className="text-muted-foreground">Amount Paid</span>
                    <span className="text-green-600">
                      -{formatCurrency(invoice.amount_paid)}
                    </span>
                  </div>
                  <div className="flex w-64 justify-between border-t pt-1 text-lg font-bold">
                    <span>Balance Due</span>
                    <span className={Number(invoice.balance) > 0 ? "text-orange-600" : "text-green-600"}>
                      {formatCurrency(invoice.balance)}
                    </span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-[100px] items-center justify-center text-muted-foreground">
              No items on this invoice
            </div>
          )}
        </CardContent>
      </Card>

      {/* Scholarship Discounts Breakdown */}
      {invoice.scholarship_items && invoice.scholarship_items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-blue-600" />
              Scholarship Discounts
            </CardTitle>
            <CardDescription>
              Scholarships applied to this invoice with full traceability
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Scholarship</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>Coverage</TableHead>
                  <TableHead className="text-right">Applicable Amount</TableHead>
                  <TableHead className="text-right">Discount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.scholarship_items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">
                      {item.scholarship_id ? (
                        <Link
                          href={`/finance/scholarships/${item.scholarship_id}`}
                          className="hover:underline text-blue-600"
                        >
                          {item.scholarship_name}
                        </Link>
                      ) : (
                        item.scholarship_name
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {item.scholarship_code || "-"}
                    </TableCell>
                    <TableCell>
                      {item.coverage_type === "percentage" ? (
                        <Badge variant="secondary">{item.coverage_value}%</Badge>
                      ) : (
                        <Badge variant="outline">{formatCurrency(item.coverage_value)}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatCurrency(item.applicable_subtotal)}
                    </TableCell>
                    <TableCell className="text-right font-medium text-blue-600">
                      -{formatCurrency(item.calculated_amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <div className="mt-4 flex justify-end border-t pt-4">
              <div className="flex w-64 justify-between font-bold">
                <span>Total Scholarship Discount</span>
                <span className="text-blue-600">
                  -{formatCurrency(invoice.scholarship_discount)}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cancellation Reason */}
      {invoice.status === "cancelled" && invoice.cancel_reason && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <Ban className="h-4 w-4" />
              Invoice Cancelled
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{invoice.cancel_reason}</p>
            {invoice.cancelled_at && (
              <p className="mt-2 text-sm text-muted-foreground">
                Cancelled on {formatDate(invoice.cancelled_at)}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Payments */}
      <Card>
        <CardHeader>
          <CardTitle>Payment History</CardTitle>
          <CardDescription>Payments received for this invoice</CardDescription>
        </CardHeader>
        <CardContent>
          {invoice.payments && invoice.payments.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Receipt #</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead className="text-right">Amount (GHS)</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.payments.map((payment) => (
                  <TableRow key={payment.id}>
                    <TableCell className="font-mono text-sm">
                      <Link
                        href={`/finance/payments/${payment.id}`}
                        className="hover:underline"
                      >
                        {payment.receipt_number}
                      </Link>
                    </TableCell>
                    <TableCell>{formatDate(payment.payment_date)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <PaymentMethodIcon method={payment.payment_method} />
                        <span>{PAYMENT_METHOD_LABELS[payment.payment_method] || payment.payment_method}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {formatNumber(payment.amount)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={payment.status === "completed" ? "default" : "secondary"}
                      >
                        {payment.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[120px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Receipt className="h-8 w-8" />
              <p>No payments recorded yet</p>
              {Number(invoice.balance) > 0 && invoice.status !== "cancelled" && invoice.status !== "draft" && (
                <Button asChild variant="outline" size="sm">
                  <Link href={`/finance/payments/record?invoice_id=${invoiceId}`}>
                    <DollarSign className="mr-2 h-4 w-4" />
                    Record Payment
                  </Link>
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notes */}
      {invoice.notes && (
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">{invoice.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Cancel Invoice Dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Invoice</DialogTitle>
            <DialogDescription>
              {hasPayments
                ? "This invoice has payments that must be voided first."
                : "Please provide a reason for cancelling this invoice. This action cannot be undone."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {hasPayments ? (
              <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-destructive mt-0.5" />
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-destructive">
                      Cannot cancel invoice with payments
                    </p>
                    <p className="text-sm text-muted-foreground">
                      This invoice has {formatCurrency(invoice.amount_paid)} in payments.
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
                setCancelReason("");
              }}
            >
              {hasPayments ? "Close" : "Cancel"}
            </Button>
            {!hasPayments && (
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

      {/* Email Invoice Dialog */}
      <Dialog open={emailDialogOpen} onOpenChange={setEmailDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Email Invoice</DialogTitle>
            <DialogDescription>
              Send this invoice as a PDF attachment to the specified email address.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="email-address">Email Address *</Label>
              <Input
                id="email-address"
                type="email"
                placeholder="recipient@example.com"
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="recipient-name">Recipient Name (Optional)</Label>
              <Input
                id="recipient-name"
                type="text"
                placeholder="e.g., Mr. John Doe"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="cc-emails">CC (Optional)</Label>
              <Input
                id="cc-emails"
                type="text"
                placeholder="email1@example.com, email2@example.com"
                value={ccEmails}
                onChange={(e) => setCcEmails(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Separate multiple email addresses with commas
              </p>
            </div>
            <div className="rounded-md bg-muted p-3 text-sm">
              <p className="font-medium">Invoice Details</p>
              <p className="text-muted-foreground mt-1">
                Invoice: {invoice.invoice_number}<br />
                Student: {invoice.student_name}<br />
                Amount: {formatCurrency(invoice.total_amount)}<br />
                Balance: {formatCurrency(invoice.balance)}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEmailDialogOpen(false);
                setEmailAddress("");
                setRecipientName("");
                setCcEmails("");
              }}
              disabled={isSendingEmail}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSendEmail}
              disabled={!emailAddress.trim() || isSendingEmail}
            >
              {isSendingEmail ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Mail className="mr-2 h-4 w-4" />
                  Send Email
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Apply Credit Dialog */}
      <Dialog open={applyCreditDialogOpen} onOpenChange={setApplyCreditDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Apply Credit to Invoice</DialogTitle>
            <DialogDescription>
              Apply available credit from a credit note to reduce this invoice's balance.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {availableCreditNotes.length > 0 ? (
              <>
                <div className="grid gap-2">
                  <Label htmlFor="credit-note">Select Credit Note</Label>
                  <Select
                    value={selectedCreditNoteId}
                    onValueChange={(value) => {
                      setSelectedCreditNoteId(value);
                      const note = availableCreditNotes.find((n) => n.id === value);
                      if (note && invoice) {
                        const maxApply = Math.min(
                          Number(note.remaining_amount || note.amount),
                          Number(invoice.balance)
                        );
                        setApplyAmount(maxApply.toString());
                      }
                    }}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select a credit note" />
                    </SelectTrigger>
                    <SelectContent>
                      {availableCreditNotes.map((note) => (
                        <SelectItem key={note.id} value={note.id}>
                          {note.credit_note_number} - {formatCurrency(note.remaining_amount || note.amount)} available
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="apply-amount">Amount to Apply (GHS)</Label>
                  <Input
                    id="apply-amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={Math.min(
                      Number(availableCreditNotes.find((n) => n.id === selectedCreditNoteId)?.remaining_amount || 0),
                      Number(invoice?.balance || 0)
                    )}
                    placeholder="0.00"
                    value={applyAmount}
                    onChange={(e) => setApplyAmount(e.target.value)}
                  />
                  {selectedCreditNoteId && (
                    <p className="text-xs text-muted-foreground">
                      Max available:{" "}
                      {formatCurrency(
                        Math.min(
                          Number(availableCreditNotes.find((n) => n.id === selectedCreditNoteId)?.remaining_amount || 0),
                          Number(invoice?.balance || 0)
                        )
                      )}
                    </p>
                  )}
                </div>
                <div className="rounded-md bg-muted p-3 text-sm">
                  <div className="flex justify-between mb-1">
                    <span>Current Balance</span>
                    <span className="font-medium">{formatCurrency(invoice?.balance || 0)}</span>
                  </div>
                  <div className="flex justify-between mb-1 text-blue-600">
                    <span>Credit to Apply</span>
                    <span className="font-medium">-{formatCurrency(parseFloat(applyAmount) || 0)}</span>
                  </div>
                  <div className="flex justify-between border-t pt-1 mt-1 font-medium">
                    <span>New Balance</span>
                    <span className={Number(invoice?.balance || 0) - (parseFloat(applyAmount) || 0) <= 0 ? "text-green-600" : ""}>
                      {formatCurrency(Math.max(0, Number(invoice?.balance || 0) - (parseFloat(applyAmount) || 0)))}
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-4 text-muted-foreground">
                <Wallet className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No available credit notes for this student.</p>
                <Button asChild variant="outline" size="sm" className="mt-2">
                  <Link href={`/finance/credit-notes/new?student_id=${invoice?.student_id}`}>
                    Create Credit Note
                  </Link>
                </Button>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setApplyCreditDialogOpen(false);
                setSelectedCreditNoteId("");
                setApplyAmount("");
              }}
              disabled={isApplyingCredit}
            >
              Cancel
            </Button>
            {availableCreditNotes.length > 0 && (
              <Button
                onClick={handleApplyCredit}
                disabled={!selectedCreditNoteId || !applyAmount || parseFloat(applyAmount) <= 0 || isApplyingCredit}
              >
                {isApplyingCredit ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Applying...
                  </>
                ) : (
                  <>
                    <CreditCard className="mr-2 h-4 w-4" />
                    Apply Credit
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
