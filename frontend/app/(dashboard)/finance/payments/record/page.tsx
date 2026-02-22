"use client";

import { useState, useEffect, useTransition, useRef, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  ArrowLeft,
  Loader2,
  Search,
  Banknote,
  Smartphone,
  Building2,
  Receipt,
  CreditCard,
  CheckCircle,
  User,
} from "lucide-react";
import { recordPayment, getInvoice, getStudentInvoices } from "@/actions/finance.action";
import { getStudents } from "@/actions/students.action";
import type { StudentListItem, InvoiceWithDetails } from "@/types";
import { formatCurrency, formatNumber } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Constants (outside component)
// ============================================

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash", icon: <Banknote className="h-4 w-4" /> },
  { value: "momo_mtn", label: "MTN MoMo", icon: <Smartphone className="h-4 w-4 text-yellow-500" /> },
  { value: "momo_vodafone", label: "Vodafone Cash", icon: <Smartphone className="h-4 w-4 text-red-500" /> },
  { value: "bank_transfer", label: "Bank Transfer", icon: <Building2 className="h-4 w-4" /> },
] as const;

const paymentSchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  invoice_id: z.string().optional(),
  amount: z.number().min(0.01, "Amount must be greater than 0"),
  payment_method: z.enum([
    "cash",
    "momo_mtn",
    "momo_vodafone",
    "momo_airteltigo",
    "bank_transfer",
    "cheque",
    "card",
    "other",
  ]),
  payer_name: z.string().optional(),
  payer_phone: z.string().optional(),
  momo_phone: z.string().optional(),
  momo_transaction_id: z.string().optional(),
  bank_name: z.string().optional(),
  bank_reference: z.string().optional(),
  cheque_number: z.string().optional(),
  notes: z.string().optional(),
});

type PaymentFormData = z.output<typeof paymentSchema>;

// ============================================
// Main Component
// ============================================

export default function RecordPaymentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialInvoiceId = searchParams.get("invoice_id");
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(!!initialInvoiceId);

  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [studentInvoices, setStudentInvoices] = useState<InvoiceWithDetails[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceWithDetails | null>(null);
  const [selectedStudent, setSelectedStudent] = useState<StudentListItem | null>(null);
  const [studentSearch, setStudentSearch] = useState("");
  const [showStudentDropdown, setShowStudentDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const form = useForm<PaymentFormData>({
    resolver: zodResolver(paymentSchema),
    defaultValues: {
      student_id: "",
      invoice_id: "",
      amount: 0,
      payment_method: "cash",
      payer_name: "",
      payer_phone: "",
      momo_phone: "",
      momo_transaction_id: "",
      bank_name: "",
      bank_reference: "",
      cheque_number: "",
      notes: "",
    },
  });

  const selectedStudentId = form.watch("student_id");
  const paymentMethod = form.watch("payment_method");
  const amount = form.watch("amount");

  // Memoized payment method flags
  const { isMoMo, isBankTransfer, isCheque } = useMemo(() => ({
    isMoMo: paymentMethod.startsWith("momo"),
    isBankTransfer: paymentMethod === "bank_transfer",
    isCheque: paymentMethod === "cheque",
  }), [paymentMethod]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowStudentDropdown(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Debounced student search
  const searchStudents = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      setStudents([]);
      return;
    }

    setIsSearching(true);
    try {
      const result = await getStudents({ search: query, status: "active", page_size: 20 });
      if (result.success && result.data) {
        setStudents(result.data.items);
      }
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Handle search input change with debounce
  const handleSearchChange = useCallback((value: string) => {
    setStudentSearch(value);
    setShowStudentDropdown(true);

    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    // Debounce search
    searchTimeoutRef.current = setTimeout(() => {
      searchStudents(value);
    }, 300);
  }, [searchStudents]);

  // Load initial invoice if provided
  useEffect(() => {
    if (initialInvoiceId) {
      setIsInitialLoading(true);
      startTransition(async () => {
        try {
          const result = await getInvoice(initialInvoiceId);
          if (result.success && result.data) {
            const invoice = result.data;
            setSelectedInvoice(invoice);
            form.setValue("student_id", invoice.student_id);
            form.setValue("invoice_id", invoice.id);
            form.setValue("amount", Number(invoice.balance));
            setStudentSearch(invoice.student_name || "");
            // Create a minimal student object for display
            setSelectedStudent({
              id: invoice.student_id,
              student_id: invoice.student_id_number || "",
              first_name: invoice.student_name?.split(" ")[0] || "",
              last_name: invoice.student_name?.split(" ").slice(1).join(" ") || "",
              class_name: invoice.class_name,
            } as StudentListItem);
          }
        } finally {
          setIsInitialLoading(false);
        }
      });
    }
  }, [initialInvoiceId, form]);

  // Load student invoices when student changes
  useEffect(() => {
    if (selectedStudentId && !initialInvoiceId) {
      setIsLoadingInvoices(true);
      startTransition(async () => {
        try {
          const result = await getStudentInvoices(selectedStudentId);
          if (result.success && result.data) {
            // Filter to only unpaid invoices
            const unpaid = result.data.items.filter((inv) => Number(inv.balance) > 0);
            setStudentInvoices(unpaid);
          }
        } finally {
          setIsLoadingInvoices(false);
        }
      });
    }
  }, [selectedStudentId, initialInvoiceId]);

  // Handle student select
  const handleStudentSelect = useCallback((student: StudentListItem) => {
    form.setValue("student_id", student.id);
    setStudentSearch(`${student.first_name} ${student.last_name}`);
    setSelectedStudent(student);
    setShowStudentDropdown(false);
    setSelectedInvoice(null);
    setStudentInvoices([]);
    form.setValue("invoice_id", "");
    form.setValue("amount", 0);
  }, [form]);

  // Handle invoice select
  const handleInvoiceSelect = useCallback((invoice: InvoiceWithDetails) => {
    setSelectedInvoice(invoice);
    form.setValue("invoice_id", invoice.id);
    form.setValue("amount", Number(invoice.balance));
  }, [form]);

  // Handle pay full balance
  const handlePayFullBalance = useCallback(() => {
    if (selectedInvoice) {
      form.setValue("amount", Number(selectedInvoice.balance));
    }
  }, [selectedInvoice, form]);

  // Handle form submit
  const onSubmit = useCallback(async (data: PaymentFormData) => {
    setIsSubmitting(true);

    try {
      const payload = {
        ...data,
        invoice_id: data.invoice_id || undefined,
        payer_name: data.payer_name || undefined,
        payer_phone: data.payer_phone || undefined,
        momo_phone: isMoMo ? data.momo_phone : undefined,
        momo_transaction_id: isMoMo ? data.momo_transaction_id : undefined,
        bank_name: isBankTransfer ? data.bank_name : undefined,
        bank_reference: isBankTransfer ? data.bank_reference : undefined,
        cheque_number: isCheque ? data.cheque_number : undefined,
        notes: data.notes || undefined,
      };

      const result = await recordPayment(payload);

      if (result.success && result.data) {
        toast({
          title: "Payment recorded",
          description: `Receipt: ${result.data.receipt_number}`,
        });
        router.push(`/finance/payments/${result.data.id}`);
      } else {
        toast({
          title: "Error",
          description: result.error || "Failed to record payment",
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [isMoMo, isBankTransfer, isCheque, toast, router]);

  // Memoized payment summary
  const paymentSummary = useMemo(() => {
    if (!selectedStudentId || amount <= 0) return null;

    return {
      amount,
      method: paymentMethod.replace("_", " "),
      invoiceNumber: selectedInvoice?.invoice_number,
      studentName: selectedStudent ? `${selectedStudent.first_name} ${selectedStudent.last_name}` : null,
    };
  }, [selectedStudentId, amount, paymentMethod, selectedInvoice, selectedStudent]);

  // Loading skeleton for initial invoice load
  if (isInitialLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-4 w-48" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/finance/payments">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Record Payment</h1>
          <p className="text-muted-foreground">
            Record a new payment from a student
          </p>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Student Selection */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="h-4 w-4" />
                Student
              </CardTitle>
              <CardDescription>Select the student making payment</CardDescription>
            </CardHeader>
            <CardContent>
              <FormField
                control={form.control}
                name="student_id"
                render={() => (
                  <FormItem>
                    <FormLabel>Search Student</FormLabel>
                    <div className="relative" ref={dropdownRef}>
                      <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        placeholder="Type student name or ID to search..."
                        value={studentSearch}
                        onChange={(e) => handleSearchChange(e.target.value)}
                        onFocus={() => studentSearch.length >= 2 && setShowStudentDropdown(true)}
                        className="pl-9"
                        disabled={!!initialInvoiceId}
                      />
                      {isSearching && (
                        <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
                      )}
                      {showStudentDropdown && studentSearch.length >= 2 && (
                        <div className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover p-1 shadow-md">
                          {isSearching ? (
                            <div className="flex items-center justify-center py-4">
                              <Loader2 className="h-4 w-4 animate-spin mr-2" />
                              <span className="text-sm text-muted-foreground">Searching...</span>
                            </div>
                          ) : students.length > 0 ? (
                            students.map((student) => (
                              <div
                                key={student.id}
                                className="cursor-pointer rounded px-3 py-2 hover:bg-accent"
                                onClick={() => handleStudentSelect(student)}
                              >
                                <div className="font-medium">
                                  {student.first_name} {student.last_name}
                                </div>
                                <div className="text-sm text-muted-foreground">
                                  {student.student_id} - {student.class_name || "No class"}
                                </div>
                              </div>
                            ))
                          ) : (
                            <div className="py-4 text-center text-sm text-muted-foreground">
                              No students found for &quot;{studentSearch}&quot;
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                    {studentSearch.length > 0 && studentSearch.length < 2 && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Type at least 2 characters to search
                      </p>
                    )}
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Selected Student Info */}
              {selectedStudent && (
                <div className="mt-4 p-3 bg-muted rounded-lg">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <User className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">
                        {selectedStudent.first_name} {selectedStudent.last_name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {selectedStudent.student_id} {selectedStudent.class_name && `- ${selectedStudent.class_name}`}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Outstanding Invoices */}
          {selectedStudentId && !initialInvoiceId && (
            <Card>
              <CardHeader>
                <CardTitle>Outstanding Invoices</CardTitle>
                <CardDescription>
                  Select an invoice to apply payment (optional)
                </CardDescription>
              </CardHeader>
              <CardContent>
                {isLoadingInvoices ? (
                  <div className="space-y-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : studentInvoices.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[50px]"></TableHead>
                        <TableHead>Invoice #</TableHead>
                        <TableHead>Term</TableHead>
                        <TableHead className="text-right">Total (GHS)</TableHead>
                        <TableHead className="text-right">Balance (GHS)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {studentInvoices.map((invoice) => (
                        <TableRow
                          key={invoice.id}
                          className="cursor-pointer"
                          onClick={() => handleInvoiceSelect(invoice)}
                        >
                          <TableCell>
                            <input
                              type="radio"
                              name="invoice"
                              checked={selectedInvoice?.id === invoice.id}
                              onChange={() => handleInvoiceSelect(invoice)}
                            />
                          </TableCell>
                          <TableCell className="font-mono">
                            {invoice.invoice_number}
                          </TableCell>
                          <TableCell>{invoice.term_name || "-"}</TableCell>
                          <TableCell className="text-right">
                            {formatNumber(invoice.total_amount)}
                          </TableCell>
                          <TableCell className="text-right font-medium text-orange-600">
                            {formatNumber(invoice.balance)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <CheckCircle className="h-8 w-8 text-green-600 mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No outstanding invoices for this student
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Selected Invoice Summary */}
          {selectedInvoice && (
            <Card className="border-primary/50">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Selected Invoice</span>
                  <Badge variant="outline">{selectedInvoice.invoice_number}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-4">
                  <div>
                    <Label className="text-muted-foreground text-xs">Total Amount</Label>
                    <p className="font-medium">
                      {formatCurrency(selectedInvoice.total_amount)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground text-xs">Amount Paid</Label>
                    <p className="font-medium text-green-600">
                      {formatCurrency(selectedInvoice.amount_paid)}
                    </p>
                  </div>
                  <div>
                    <Label className="text-muted-foreground text-xs">Balance Due</Label>
                    <p className="text-lg font-bold text-orange-600">
                      {formatCurrency(selectedInvoice.balance)}
                    </p>
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handlePayFullBalance}
                    >
                      Pay Full Balance
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Payment Details */}
          <Card>
            <CardHeader>
              <CardTitle>Payment Details</CardTitle>
              <CardDescription>Enter payment information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Payment Method */}
              <FormField
                control={form.control}
                name="payment_method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Payment Method</FormLabel>
                    <FormControl>
                      <RadioGroup
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        className="grid gap-3 md:grid-cols-4"
                      >
                        {PAYMENT_METHODS.map((method) => (
                          <div key={method.value}>
                            <RadioGroupItem
                              value={method.value}
                              id={method.value}
                              className="peer sr-only"
                            />
                            <Label
                              htmlFor={method.value}
                              className="flex items-center gap-2 rounded-md border-2 border-muted bg-popover p-3 hover:bg-accent hover:text-accent-foreground peer-data-[state=checked]:border-primary cursor-pointer"
                            >
                              {method.icon}
                              {method.label}
                            </Label>
                          </div>
                        ))}
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Amount */}
              <div className="grid gap-4 md:grid-cols-2">
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
                          min="0.01"
                          placeholder="0.00"
                          {...field}
                          onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {isMoMo && (
                  <FormField
                    control={form.control}
                    name="momo_phone"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>MoMo Phone Number</FormLabel>
                        <FormControl>
                          <Input placeholder="024 XXX XXXX" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                )}
              </div>

              {isMoMo && (
                <FormField
                  control={form.control}
                  name="momo_transaction_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Transaction ID (Optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Transaction reference" {...field} />
                      </FormControl>
                      <FormDescription>
                        Enter the MoMo transaction reference if available
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {isBankTransfer && (
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="bank_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Bank Name</FormLabel>
                        <FormControl>
                          <Input placeholder="e.g., GCB Bank" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="bank_reference"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Reference Number</FormLabel>
                        <FormControl>
                          <Input placeholder="Bank transfer reference" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {isCheque && (
                <FormField
                  control={form.control}
                  name="cheque_number"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cheque Number</FormLabel>
                      <FormControl>
                        <Input placeholder="Cheque number" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}

              {/* Payer Info */}
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="payer_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Payer Name (Optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="Name of person paying" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="payer_phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Payer Phone (Optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="024 XXX XXXX" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Notes */}
              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (Optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Additional notes about this payment..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* Payment Summary */}
          {paymentSummary && (
            <Alert>
              <Receipt className="h-4 w-4" />
              <AlertDescription>
                <span className="font-medium">Payment Summary: </span>
                Recording {formatCurrency(paymentSummary.amount)} via {paymentSummary.method}
                {paymentSummary.invoiceNumber && ` for invoice ${paymentSummary.invoiceNumber}`}
                {paymentSummary.studentName && ` from ${paymentSummary.studentName}`}
              </AlertDescription>
            </Alert>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-4">
            <Button type="button" variant="outline" asChild>
              <Link href="/finance/payments">Cancel</Link>
            </Button>
            <Button type="submit" disabled={isSubmitting || !selectedStudentId || amount <= 0}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Record Payment
            </Button>
          </div>
        </form>
      </Form>
    </div>
  );
}
