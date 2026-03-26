"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CreditCard,
  Smartphone,
  Loader2,
  Receipt,
  CheckCircle2,
} from "lucide-react";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
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
  TableFooter,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatGHS, formatGhanaDate } from "@/lib/format";
import { initiatePayment } from "@/actions/parent.action";
import type {
  ParentInvoiceDetail,
  ParentPaymentMethod,
} from "@/types/parent.type";

// =========================
// Zod Schema
// =========================

const paymentSchema = z
  .object({
    method: z.enum(["mobile_money", "card"], {
      message: "Please select a payment method",
    }),
    amount: z.coerce
      .number()
      .positive("Amount must be greater than 0"),
    phone: z.string().optional(),
  })
  .refine(
    (data) => {
      if (data.method === "mobile_money") {
        return !!data.phone && data.phone.length >= 10;
      }
      return true;
    },
    {
      message: "Phone number is required for Mobile Money",
      path: ["phone"],
    }
  );

type PaymentFormValues = z.infer<typeof paymentSchema>;

// =========================
// Status Styles
// =========================

const statusStyles: Record<string, string> = {
  paid: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  partial: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  issued: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  overdue: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  cancelled: "bg-muted text-muted-foreground",
  draft: "bg-muted text-muted-foreground",
  write_off: "bg-muted text-muted-foreground",
};

// =========================
// Main Component
// =========================

interface InvoiceDetailViewProps {
  studentId: string;
  invoice: ParentInvoiceDetail | null;
}

export function InvoiceDetailView({
  studentId,
  invoice,
}: InvoiceDetailViewProps) {
  const [payDialogOpen, setPayDialogOpen] = useState(false);

  if (!invoice) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Receipt className="h-10 w-10 text-muted-foreground" />
        <h2 className="text-lg font-semibold">Invoice not found</h2>
        <p className="text-sm text-muted-foreground">
          This invoice could not be found or you do not have access to it.
        </p>
        <Button variant="outline" asChild>
          <Link href={`/parent/children/${studentId}?tab=finance`}>
            Back to Finance
          </Link>
        </Button>
      </div>
    );
  }

  const canPay =
    invoice.balance > 0 &&
    invoice.status !== "cancelled" &&
    invoice.status !== "draft";

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href={`/parent/children/${studentId}?tab=finance`}
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Finance
      </Link>

      {/* Invoice header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl md:text-2xl font-bold tracking-tight">
              {invoice.invoice_number}
            </h1>
            <Badge
              variant="secondary"
              className={cn(
                "text-xs capitalize",
                statusStyles[invoice.status] || ""
              )}
            >
              {invoice.status.replace("_", " ")}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {invoice.term_name}
            {invoice.due_date
              ? ` | Due: ${formatGhanaDate(invoice.due_date)}`
              : ""}
          </p>
        </div>
        {canPay && (
          <Button onClick={() => setPayDialogOpen(true)} className="shrink-0">
            <CreditCard className="h-4 w-4 mr-2" />
            Pay Now
          </Button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard label="Total Amount" value={formatGHS(invoice.total_amount)} />
        <SummaryCard label="Amount Paid" value={formatGHS(invoice.amount_paid)} />
        <SummaryCard
          label="Balance"
          value={formatGHS(invoice.balance)}
          highlight={invoice.balance > 0}
        />
        <SummaryCard
          label="Created"
          value={formatGhanaDate(invoice.created_at)}
        />
      </div>

      {/* Discounts / Credits */}
      {(invoice.scholarship_discount > 0 ||
        invoice.credit_notes_applied > 0) && (
        <Card className="border-green-500/30 bg-green-50/50 dark:bg-green-950/20">
          <CardContent className="py-3">
            <div className="flex flex-wrap gap-4 text-sm">
              {invoice.scholarship_discount > 0 && (
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-muted-foreground">
                    Scholarship Discount:
                  </span>
                  <span className="font-semibold text-green-700 dark:text-green-300">
                    -{formatGHS(invoice.scholarship_discount)}
                  </span>
                </div>
              )}
              {invoice.credit_notes_applied > 0 && (
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  <span className="text-muted-foreground">
                    Credit Notes Applied:
                  </span>
                  <span className="font-semibold text-green-700 dark:text-green-300">
                    -{formatGHS(invoice.credit_notes_applied)}
                  </span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Line items */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Fee Items</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {invoice.items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      <p className="font-medium text-sm">
                        {item.fee_type_name}
                      </p>
                      {item.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {item.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-right font-medium text-sm">
                      {formatGHS(item.amount)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
              <TableFooter>
                <TableRow>
                  <TableCell className="font-semibold">Total</TableCell>
                  <TableCell className="text-right font-bold">
                    {formatGHS(invoice.total_amount)}
                  </TableCell>
                </TableRow>
              </TableFooter>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Payment history */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Payment History ({invoice.payments.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {invoice.payments.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              No payments have been made for this invoice yet.
            </p>
          ) : (
            <div className="overflow-x-auto -mx-6 sm:mx-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Receipt</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Method
                    </TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invoice.payments.map((payment) => (
                    <TableRow key={payment.id}>
                      <TableCell className="text-sm">
                        {formatGhanaDate(payment.date)}
                      </TableCell>
                      <TableCell className="text-sm font-medium">
                        {payment.receipt_number}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge
                          variant="outline"
                          className="text-xs capitalize"
                        >
                          {payment.method.replace("_", " ")}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-semibold text-sm">
                        {formatGHS(payment.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pay Now button for mobile (sticky bottom) */}
      {canPay && (
        <div className="sm:hidden fixed bottom-20 left-0 right-0 p-4 bg-background border-t">
          <Button
            onClick={() => setPayDialogOpen(true)}
            className="w-full"
            size="lg"
          >
            <CreditCard className="h-4 w-4 mr-2" />
            Pay {formatGHS(invoice.balance)}
          </Button>
        </div>
      )}

      {/* Payment dialog */}
      <PaymentDialog
        open={payDialogOpen}
        onOpenChange={setPayDialogOpen}
        studentId={studentId}
        invoiceId={invoice.id}
        invoiceNumber={invoice.invoice_number}
        balance={invoice.balance}
      />
    </div>
  );
}

// =========================
// Summary Card
// =========================

function SummaryCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <Card className={highlight ? "border-amber-500/30" : ""}>
      <CardContent className="p-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p
          className={cn(
            "text-lg font-bold mt-0.5",
            highlight ? "text-amber-600 dark:text-amber-400" : ""
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

// =========================
// Payment Dialog
// =========================

function PaymentDialog({
  open,
  onOpenChange,
  studentId,
  invoiceId,
  invoiceNumber,
  balance,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  studentId: string;
  invoiceId: string;
  invoiceNumber: string;
  balance: number;
}) {
  const [submitting, setSubmitting] = useState(false);

  const form = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentSchema) as Resolver<PaymentFormValues>,
    defaultValues: {
      method: "mobile_money",
      amount: balance,
      phone: "",
    },
  });

  const selectedMethod = form.watch("method");

  async function onSubmit(values: PaymentFormValues) {
    setSubmitting(true);
    const result = await initiatePayment(studentId, {
      invoice_id: invoiceId,
      amount: values.amount,
      method: values.method as ParentPaymentMethod,
      phone: values.method === "mobile_money" ? values.phone : undefined,
    });

    if (result.success) {
      toast.success("Redirecting to payment provider...");
      // Redirect to payment provider authorization URL
      window.location.href = result.data.authorization_url;
    } else {
      toast.error(result.error);
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Make Payment</DialogTitle>
          <DialogDescription>
            Pay for invoice {invoiceNumber}. Outstanding balance:{" "}
            {formatGHS(balance)}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-4"
          >
            {/* Payment method */}
            <FormField
              control={form.control}
              name="method"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Payment Method</FormLabel>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      type="button"
                      onClick={() => field.onChange("mobile_money")}
                      className={cn(
                        "flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-colors",
                        field.value === "mobile_money"
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50"
                      )}
                    >
                      <Smartphone
                        className={cn(
                          "h-6 w-6",
                          field.value === "mobile_money"
                            ? "text-primary"
                            : "text-muted-foreground"
                        )}
                      />
                      <span className="text-sm font-medium">Mobile Money</span>
                      <span className="text-[10px] text-muted-foreground">
                        MTN, Vodafone, AirtelTigo
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => field.onChange("card")}
                      className={cn(
                        "flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-colors",
                        field.value === "card"
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/50"
                      )}
                    >
                      <CreditCard
                        className={cn(
                          "h-6 w-6",
                          field.value === "card"
                            ? "text-primary"
                            : "text-muted-foreground"
                        )}
                      />
                      <span className="text-sm font-medium">Card</span>
                      <span className="text-[10px] text-muted-foreground">
                        Visa, Mastercard
                      </span>
                    </button>
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Amount */}
            <FormField
              control={form.control}
              name="amount"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Amount (GHS)</FormLabel>
                  <FormControl>
                    <Input
                      type="number"
                      step="0.01"
                      min="1"
                      max={balance}
                      placeholder="Enter amount"
                      {...field}
                    />
                  </FormControl>
                  <p className="text-xs text-muted-foreground">
                    Maximum: {formatGHS(balance)}. You can make a partial
                    payment.
                  </p>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Phone for Mobile Money */}
            {selectedMethod === "mobile_money" && (
              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Mobile Money Number</FormLabel>
                    <FormControl>
                      <Input
                        type="tel"
                        placeholder="e.g. 024 XXX XXXX"
                        {...field}
                      />
                    </FormControl>
                    <p className="text-xs text-muted-foreground">
                      You will receive a payment prompt on this number.
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Processing...
                  </>
                ) : (
                  <>
                    Pay {formatGHS(form.watch("amount") || 0)}
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
