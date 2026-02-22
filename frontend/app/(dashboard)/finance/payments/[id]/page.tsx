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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Printer,
  XCircle,
  AlertCircle,
  Receipt,
  User,
  CreditCard,
  Calendar,
  FileText,
  CheckCircle,
  Loader2,
  Smartphone,
  Banknote,
  Building2,
} from "lucide-react";
import { getPayment, voidPayment, getPaymentReceipt } from "@/actions/finance.action";
import type { PaymentWithDetails, PaymentReceipt } from "@/types";
import { formatCurrency, formatDate } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Constants (outside component)
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
      return <CreditCard className="h-4 w-4" />;
  }
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
          ${receipt.notes ? `<div class="detail-row"><span class="detail-label">Notes</span><span class="detail-value">${receipt.notes}</span></div>` : ''}
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

// Extended type for payment detail view with optional class name
interface PaymentDetailData extends PaymentWithDetails {
  class_name?: string;
}

// ============================================
// Main Component
// ============================================

export default function PaymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [payment, setPayment] = useState<PaymentDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPrinting, setIsPrinting] = useState(false);
  const [isVoidDialogOpen, setIsVoidDialogOpen] = useState(false);
  const [voidReason, setVoidReason] = useState("");
  const [isVoiding, setIsVoiding] = useState(false);

  const paymentId = params.id as string;

  // Memoized fetch function
  const fetchPayment = useCallback(() => {
    startTransition(async () => {
      const result = await getPayment(paymentId);
      if (result.success && result.data) {
        setPayment(result.data);
        setError(null);
      } else {
        setError(result.error || "Failed to load payment");
      }
    });
  }, [paymentId]);

  useEffect(() => {
    fetchPayment();
  }, [fetchPayment]);

  // Memoized void handler
  const handleVoid = useCallback(async () => {
    if (!voidReason.trim()) {
      toast({
        title: "Reason required",
        description: "Please provide a reason for voiding this payment.",
        variant: "destructive",
      });
      return;
    }

    setIsVoiding(true);
    try {
      const result = await voidPayment(paymentId, { reason: voidReason });
      if (result.success) {
        toast({
          title: "Payment voided",
          description: "The payment has been voided successfully.",
        });
        setIsVoidDialogOpen(false);
        setVoidReason("");
        fetchPayment();
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
  }, [paymentId, voidReason, toast, fetchPayment]);

  // Memoized print handler
  const handlePrintReceipt = useCallback(async () => {
    setIsPrinting(true);
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
    } finally {
      setIsPrinting(false);
    }
  }, [paymentId, toast]);

  // Memoized payment method display
  const paymentMethodDisplay = useMemo(() => {
    if (!payment) return "";
    return PAYMENT_METHOD_LABELS[payment.payment_method] ||
      payment.payment_method.replace("_", " ");
  }, [payment]);

  // Memoized status check
  const canVoid = useMemo(() => {
    return payment?.status === "completed" && !payment?.is_voided;
  }, [payment?.status, payment?.is_voided]);

  // Loading state
  if (isPending && !payment) {
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
        <Button onClick={() => router.push("/finance/payments")}>
          Back to Payments
        </Button>
      </div>
    );
  }

  if (!payment) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/payments">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                Receipt: {payment.receipt_number}
              </h1>
              <Badge
                variant="secondary"
                className={STATUS_COLORS[payment.status] || "bg-gray-100 text-gray-800"}
              >
                {payment.status}
              </Badge>
              {payment.is_voided && (
                <Badge variant="destructive">Voided</Badge>
              )}
            </div>
            <p className="text-muted-foreground">
              {formatDate(payment.payment_date)}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handlePrintReceipt} disabled={isPrinting}>
            {isPrinting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Printer className="mr-2 h-4 w-4" />
            )}
            {isPrinting ? "Loading..." : "Print Receipt"}
          </Button>
          {canVoid && (
            <Dialog open={isVoidDialogOpen} onOpenChange={setIsVoidDialogOpen}>
              <DialogTrigger asChild>
                <Button variant="destructive">
                  <XCircle className="mr-2 h-4 w-4" />
                  Void Payment
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Void Payment</DialogTitle>
                  <DialogDescription>
                    Are you sure you want to void this payment of{" "}
                    <span className="font-semibold">{formatCurrency(payment.amount)}</span>?
                    This will update the related invoice balance. This action cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <div className="rounded-md bg-muted p-3 text-sm">
                  <p><span className="text-muted-foreground">Receipt:</span> {payment.receipt_number}</p>
                  <p><span className="text-muted-foreground">Student:</span> {payment.student_name}</p>
                  <p><span className="text-muted-foreground">Date:</span> {formatDate(payment.payment_date)}</p>
                </div>
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
                      setIsVoidDialogOpen(false);
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
          )}
        </div>
      </div>

      {/* Receipt Card */}
      <Card className="mx-auto max-w-2xl">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <CheckCircle className="h-8 w-8 text-green-600" />
          </div>
          <CardTitle className="text-3xl">
            {formatCurrency(payment.amount)}
          </CardTitle>
          <CardDescription>Payment {payment.status}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Receipt Details */}
          <div className="space-y-4 rounded-lg bg-muted/50 p-4">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-muted-foreground">
                <Receipt className="h-4 w-4" />
                Receipt Number
              </span>
              <span className="font-mono font-medium">
                {payment.receipt_number}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                Payment Date
              </span>
              <span>{formatDate(payment.payment_date)}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-muted-foreground">
                <PaymentMethodIcon method={payment.payment_method} />
                Payment Method
              </span>
              <span>{paymentMethodDisplay}</span>
            </div>
            {payment.invoice_id && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  Invoice
                </span>
                <Link
                  href={`/finance/invoices/${payment.invoice_id}`}
                  className="font-mono text-primary hover:underline"
                >
                  {payment.invoice_number || "View Invoice"}
                </Link>
              </div>
            )}
          </div>

          {/* Student Info */}
          {payment.student_id && (
            <div className="space-y-4 rounded-lg border p-4">
              <h3 className="flex items-center gap-2 font-medium">
                <User className="h-4 w-4" />
                Student Information
              </h3>
              <div className="grid gap-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Name</span>
                  <Link
                    href={`/students/${payment.student_id}`}
                    className="font-medium hover:underline"
                  >
                    {payment.student_name}
                  </Link>
                </div>
                {payment.student_id_number && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Student ID</span>
                    <span className="font-mono">{payment.student_id_number}</span>
                  </div>
                )}
                {payment.class_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Class</span>
                    <span>{payment.class_name}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Payer Info */}
          {(payment.payer_name || payment.payer_phone) && (
            <div className="space-y-4 rounded-lg border p-4">
              <h3 className="font-medium">Payer Information</h3>
              <div className="grid gap-2">
                {payment.payer_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Name</span>
                    <span>{payment.payer_name}</span>
                  </div>
                )}
                {payment.payer_phone && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Phone</span>
                    <span>{payment.payer_phone}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* MoMo Details */}
          {payment.payment_method.startsWith("momo") && (
            <div className="space-y-4 rounded-lg border p-4">
              <h3 className="font-medium">Mobile Money Details</h3>
              <div className="grid gap-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Provider</span>
                  <span>
                    {PAYMENT_METHOD_LABELS[payment.payment_method] ||
                      payment.momo_provider?.replace("_", " ") ||
                      payment.payment_method.replace("momo_", "")}
                  </span>
                </div>
                {payment.momo_phone && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Phone</span>
                    <span>{payment.momo_phone}</span>
                  </div>
                )}
                {payment.momo_transaction_id && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Transaction ID</span>
                    <span className="font-mono">
                      {payment.momo_transaction_id}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Bank Transfer Details */}
          {payment.payment_method === "bank_transfer" && (payment.bank_name || payment.bank_reference) && (
            <div className="space-y-4 rounded-lg border p-4">
              <h3 className="font-medium">Bank Transfer Details</h3>
              <div className="grid gap-2">
                {payment.bank_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Bank</span>
                    <span>{payment.bank_name}</span>
                  </div>
                )}
                {payment.bank_reference && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Reference</span>
                    <span className="font-mono">{payment.bank_reference}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Cheque Details */}
          {payment.payment_method === "cheque" && payment.cheque_number && (
            <div className="space-y-4 rounded-lg border p-4">
              <h3 className="font-medium">Cheque Details</h3>
              <div className="grid gap-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Cheque Number</span>
                  <span className="font-mono">{payment.cheque_number}</span>
                </div>
              </div>
            </div>
          )}

          {/* Notes */}
          {payment.notes && (
            <div className="space-y-2 rounded-lg border p-4">
              <h3 className="font-medium">Notes</h3>
              <p className="text-muted-foreground">{payment.notes}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
