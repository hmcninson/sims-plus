"use client";

import { useState, useEffect, useTransition, useCallback, useMemo, useRef } from "react";
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Loader2,
  Search,
  User,
  FileText,
  AlertCircle,
  Wallet,
  Receipt,
  PenLine,
  HelpCircle,
  Banknote,
  Info,
  CheckCircle2,
} from "lucide-react";
import {
  createCreditNote,
  getInvoices,
  getInvoice,
} from "@/actions/finance.action";
import { getStudents, getStudent } from "@/actions/students.action";
import type { StudentListItem, InvoiceWithDetails } from "@/types";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";


const creditNoteSchema = z.object({
  credit_note_type: z.enum([
    "overpayment",
    "fee_reduction",
    "error_correction",
    "other",
  ]),
  student_id: z.string().min(1, "Student is required"),
  original_invoice_id: z.string().optional(),
  amount: z.number().positive("Amount must be greater than 0"),
  currency: z.string(),
  reason: z.string().min(1, "Reason is required").max(500),
  notes: z.string().optional(),
});

type CreditNoteFormData = z.infer<typeof creditNoteSchema>;

// Credit note type configuration with dark mode support
const CREDIT_NOTE_TYPES = [
  {
    value: "overpayment",
    label: "Overpayment",
    icon: Wallet,
    description: "Student paid more than the invoice amount",
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-100 dark:bg-green-950",
    iconBgColor: "bg-green-200 dark:bg-green-900",
    borderColor: "border-green-300 dark:border-green-700",
    selectedBg: "bg-green-50 dark:bg-green-950/50",
  },
  {
    value: "fee_reduction",
    label: "Fee Reduction",
    icon: Receipt,
    description: "Reduce fees due to special circumstances",
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-950",
    iconBgColor: "bg-blue-200 dark:bg-blue-900",
    borderColor: "border-blue-300 dark:border-blue-700",
    selectedBg: "bg-blue-50 dark:bg-blue-950/50",
  },
  {
    value: "error_correction",
    label: "Error Correction",
    icon: PenLine,
    description: "Correct billing mistakes or wrong charges",
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-100 dark:bg-orange-950",
    iconBgColor: "bg-orange-200 dark:bg-orange-900",
    borderColor: "border-orange-300 dark:border-orange-700",
    selectedBg: "bg-orange-50 dark:bg-orange-950/50",
  },
  {
    value: "other",
    label: "Other",
    icon: HelpCircle,
    description: "Other adjustments not covered above",
    color: "text-gray-600 dark:text-gray-400",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    iconBgColor: "bg-gray-200 dark:bg-gray-700",
    borderColor: "border-gray-300 dark:border-gray-600",
    selectedBg: "bg-gray-50 dark:bg-gray-800/50",
  },
];

// Quick amount presets
const QUICK_AMOUNTS = [50, 100, 200, 500, 1000];

export default function NewCreditNotePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();

  // Student search state
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [studentSearch, setStudentSearch] = useState("");
  const [showStudentDropdown, setShowStudentDropdown] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<StudentListItem | null>(null);

  // Refs
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Invoice state
  const [invoices, setInvoices] = useState<InvoiceWithDetails[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceWithDetails | null>(null);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(false);

  // Initial loading state
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // Pre-fill from query params
  const prefilledStudentId = searchParams.get("student_id");
  const prefilledInvoiceId = searchParams.get("invoice_id");
  const prefilledType = searchParams.get("type");

  const form = useForm<CreditNoteFormData>({
    resolver: zodResolver(creditNoteSchema),
    defaultValues: {
      credit_note_type: (prefilledType as CreditNoteFormData["credit_note_type"]) || "overpayment",
      student_id: prefilledStudentId || "",
      original_invoice_id: prefilledInvoiceId || "",
      amount: 0,
      currency: "GHS",
      reason: "",
      notes: "",
    },
  });

  const selectedStudentId = form.watch("student_id");
  const selectedInvoiceId = form.watch("original_invoice_id");
  const selectedType = form.watch("credit_note_type");
  const currentAmount = form.watch("amount");
  const currentReason = form.watch("reason");

  // Get selected type config
  const selectedTypeConfig = useMemo(
    () => CREDIT_NOTE_TYPES.find((t) => t.value === selectedType),
    [selectedType]
  );

  // Calculate form completion percentage
  const formCompletion = useMemo(() => {
    let completed = 0;
    const total = 4; // type, student, amount, reason
    if (selectedType) completed++;
    if (selectedStudentId) completed++;
    if (currentAmount > 0) completed++;
    if (currentReason?.trim()) completed++;
    return Math.round((completed / total) * 100);
  }, [selectedType, selectedStudentId, currentAmount, currentReason]);

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
      const result = await getStudents({ search: query, page_size: 20 });
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

    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }

    searchTimeoutRef.current = setTimeout(() => {
      searchStudents(value);
    }, 300);
  }, [searchStudents]);

  // Fetch pre-filled student and invoice on mount
  useEffect(() => {
    const fetchPrefilledData = async () => {
      setIsInitialLoading(true);

      try {
        if (prefilledStudentId) {
          const studentResult = await getStudent(prefilledStudentId);
          if (studentResult.success && studentResult.data) {
            const student = studentResult.data;
            const studentListItem: StudentListItem = {
              id: student.id,
              student_id: student.student_id,
              first_name: student.first_name,
              middle_name: student.middle_name,
              last_name: student.last_name,
              class_name: student.class_name,
              section_name: student.section_name,
              status: student.status,
              photo_url: student.photo_url,
            };
            setSelectedStudent(studentListItem);
            setStudentSearch(`${student.first_name} ${student.last_name}`);
          }
        }

        if (prefilledInvoiceId) {
          const invoiceResult = await getInvoice(prefilledInvoiceId);
          if (invoiceResult.success && invoiceResult.data) {
            setSelectedInvoice(invoiceResult.data);
          }
        }
      } finally {
        setIsInitialLoading(false);
      }
    };

    fetchPrefilledData();
  }, [prefilledStudentId, prefilledInvoiceId, selectedType, form]);

  
  // Fetch invoices when student is selected
  useEffect(() => {
    if (selectedStudentId) {
      setIsLoadingInvoices(true);
      startTransition(async () => {
        const result = await getInvoices({
          studentId: selectedStudentId,
          pageSize: 50,
        });
        if (result.success && result.data) {
          setInvoices(result.data.items);
        }
        setIsLoadingInvoices(false);
      });
    } else {
      setInvoices([]);
      setSelectedInvoice(null);
    }
  }, [selectedStudentId]);

  // Update selected invoice when invoice ID changes
  useEffect(() => {
    if (selectedInvoiceId && invoices.length > 0) {
      const invoice = invoices.find((i) => i.id === selectedInvoiceId);
      setSelectedInvoice(invoice || null);
    } else if (!selectedInvoiceId) {
      setSelectedInvoice(null);
    }
  }, [selectedInvoiceId, invoices]);

  const onSubmit = useCallback(
    (data: CreditNoteFormData) => {
      startTransition(async () => {
        const payload = {
          ...data,
          original_invoice_id: data.original_invoice_id || undefined,
          notes: data.notes || undefined,
        };

        const result = await createCreditNote(payload);

        if (result.success) {
          toast({
            title: "Credit note created",
            description: "The credit note has been created as a draft.",
          });
          router.push(`/finance/credit-notes/${result.data?.id}`);
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to create credit note",
            variant: "destructive",
          });
        }
      });
    },
    [toast, router]
  );

  // Handle student selection from dropdown
  const handleStudentSelectFromDropdown = useCallback(
    (student: StudentListItem) => {
      form.setValue("student_id", student.id);
      form.setValue("original_invoice_id", "");
      setStudentSearch(`${student.first_name} ${student.last_name}`);
      setSelectedStudent(student);
      setShowStudentDropdown(false);
      setSelectedInvoice(null);
    },
    [form]
  );

  const handleQuickAmount = useCallback(
    (amount: number) => {
      form.setValue("amount", amount);
    },
    [form]
  );

  if (isInitialLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-40" />
              </CardHeader>
              <CardContent className="space-y-4">
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </CardContent>
            </Card>
          </div>
          <div>
            <Card>
              <CardHeader>
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-40 w-full" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/finance/credit-notes">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">New Credit Note</h1>
            <p className="text-muted-foreground">
              Issue a credit for fee adjustments or refunds
            </p>
          </div>
        </div>
        {/* Progress indicator */}
        <div className="hidden md:flex items-center gap-3">
          <div className="text-sm text-muted-foreground">
            {formCompletion}% complete
          </div>
          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${formCompletion}%` }}
            />
          </div>
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-6 lg:grid-cols-3">
            {/* Main Form */}
            <div className="lg:col-span-2 space-y-6">
              {/* Credit Note Type Selection */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Credit Note Type</CardTitle>
                  <CardDescription>
                    Select the reason for issuing this credit note
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <FormField
                    control={form.control}
                    name="credit_note_type"
                    render={({ field }) => (
                      <FormItem>
                        <FormControl>
                          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                            {CREDIT_NOTE_TYPES.map((type) => {
                              const Icon = type.icon;
                              const isSelected = field.value === type.value;
                              return (
                                <button
                                  key={type.value}
                                  type="button"
                                  onClick={() => field.onChange(type.value)}
                                  className={cn(
                                    "relative flex flex-col items-start gap-2 rounded-lg border-2 p-4 text-left transition-all",
                                    isSelected
                                      ? `${type.borderColor} ${type.selectedBg}`
                                      : "border-border hover:border-muted-foreground/50 hover:bg-muted/50"
                                  )}
                                >
                                  {isSelected && (
                                    <CheckCircle2
                                      className={cn("absolute top-2 right-2 h-5 w-5", type.color)}
                                    />
                                  )}
                                  <div className={cn("p-2 rounded-md", type.iconBgColor)}>
                                    <Icon className={cn("h-5 w-5", type.color)} />
                                  </div>
                                  <div>
                                    <div className={cn("font-medium", isSelected && type.color)}>
                                      {type.label}
                                    </div>
                                    <div className="text-xs text-muted-foreground line-clamp-2">
                                      {type.description}
                                    </div>
                                  </div>
                                </button>
                              );
                            })}
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>

              {/* Student & Invoice */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Student & Invoice</CardTitle>
                  <CardDescription>
                    Select the student and optionally link to an invoice
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="student_id"
                    render={() => (
                      <FormItem>
                        <FormLabel>Search Student *</FormLabel>
                        <div className="relative" ref={dropdownRef}>
                          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                          <Input
                            placeholder="Type student name or ID to search..."
                            value={studentSearch}
                            onChange={(e) => handleSearchChange(e.target.value)}
                            onFocus={() => studentSearch.length >= 2 && setShowStudentDropdown(true)}
                            className="pl-9"
                            disabled={!!prefilledStudentId}
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
                                    onClick={() => handleStudentSelectFromDropdown(student)}
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
                    <div className="p-3 bg-muted rounded-lg">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                          <User className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium">
                            {selectedStudent.first_name} {selectedStudent.last_name}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {selectedStudent.student_id} {selectedStudent.class_name && `• ${selectedStudent.class_name}`}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  <FormField
                    control={form.control}
                    name="original_invoice_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Related Invoice (Optional)</FormLabel>
                        <Select
                          onValueChange={(value) => field.onChange(value === "_none_" ? "" : value)}
                          value={field.value || "_none_"}
                          disabled={!selectedStudentId || isLoadingInvoices}
                        >
                          <FormControl>
                            <SelectTrigger>
                              {isLoadingInvoices ? (
                                <span className="flex items-center gap-2 text-muted-foreground">
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                  Loading invoices...
                                </span>
                              ) : (
                                <SelectValue placeholder="Select an invoice (optional)" />
                              )}
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="_none_">
                              <span className="text-muted-foreground">No invoice selected</span>
                            </SelectItem>
                            {invoices.map((invoice) => (
                              <SelectItem key={invoice.id} value={invoice.id}>
                                <div className="flex items-center gap-2">
                                  <span>{invoice.invoice_number}</span>
                                  <span className="text-muted-foreground">
                                    {formatCurrency(invoice.total_amount)}
                                  </span>
                                  <Badge
                                    variant="outline"
                                    className={cn(
                                      "text-xs",
                                      invoice.status === "paid" && "bg-green-50 text-green-700 border-green-200",
                                      invoice.status === "issued" && "bg-blue-50 text-blue-700 border-blue-200",
                                      invoice.status === "partial" && "bg-yellow-50 text-yellow-700 border-yellow-200"
                                    )}
                                  >
                                    {invoice.status}
                                  </Badge>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Link this credit to an invoice for better tracking
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  {/* Selected Invoice Details */}
                  {selectedInvoice && (
                    <div className={cn(
                      "rounded-lg border p-4 transition-colors",
                      selectedTypeConfig?.selectedBg,
                      selectedTypeConfig?.borderColor
                    )}>
                      <div className="flex items-start gap-3">
                        <FileText className={cn("h-5 w-5 mt-0.5", selectedTypeConfig?.color)} />
                        <div className="flex-1 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">{selectedInvoice.invoice_number}</span>
                            <Badge variant="secondary">{selectedInvoice.status}</Badge>
                          </div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Total:</span>
                              <span className="font-medium">
                                {formatCurrency(selectedInvoice.total_amount)}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Balance:</span>
                              <span className="font-medium text-orange-600">
                                {formatCurrency(selectedInvoice.balance)}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Paid:</span>
                              <span className="font-medium text-green-600">
                                {formatCurrency(selectedInvoice.amount_paid)}
                              </span>
                            </div>
                            {Number(selectedInvoice.scholarship_discount) > 0 && (
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Scholarship:</span>
                                <span className="font-medium text-teal-600 dark:text-teal-400">
                                  -{formatCurrency(selectedInvoice.scholarship_discount)}
                                </span>
                              </div>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground pt-2 border-t">
                            {selectedInvoice.term_name} • {selectedInvoice.academic_year_name}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Amount & Reason */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Credit Details</CardTitle>
                  <CardDescription>
                    Specify the credit amount and provide a reason
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={form.control}
                    name="amount"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Amount *</FormLabel>
                        <FormControl>
                          <div className="space-y-3">
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground font-medium">
                                GHS
                              </span>
                              <Input
                                type="number"
                                step="0.01"
                                min="0"
                                placeholder="0.00"
                                className="pl-14 text-lg font-semibold h-12"
                                {...field}
                                onChange={(e) => field.onChange(e.target.valueAsNumber || 0)}
                              />
                            </div>
                            {/* Quick amount buttons */}
                            <div className="flex flex-wrap gap-2">
                              <span className="text-xs text-muted-foreground self-center mr-1">
                                Quick:
                              </span>
                              {QUICK_AMOUNTS.map((amount) => (
                                <Button
                                  key={amount}
                                  type="button"
                                  variant={currentAmount === amount ? "default" : "outline"}
                                  size="sm"
                                  onClick={() => handleQuickAmount(amount)}
                                  className="h-7 px-3 text-xs"
                                >
                                  {formatCurrency(amount)}
                                </Button>
                              ))}
                              {selectedInvoice && Number(selectedInvoice.balance) > 0 && (
                                <Button
                                  type="button"
                                  variant={currentAmount === Number(selectedInvoice.balance) ? "default" : "secondary"}
                                  size="sm"
                                  onClick={() => handleQuickAmount(Number(selectedInvoice.balance))}
                                  className="h-7 px-3 text-xs"
                                >
                                  Balance ({formatCurrency(selectedInvoice.balance)})
                                </Button>
                              )}
                            </div>
                          </div>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Separator />

                  <FormField
                    control={form.control}
                    name="reason"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Reason *</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Explain why this credit note is being issued..."
                            rows={3}
                            className="resize-none"
                            {...field}
                          />
                        </FormControl>
                        <div className="flex justify-between">
                          <FormDescription>
                            Be specific about why this credit is being issued
                          </FormDescription>
                          <span className="text-xs text-muted-foreground">
                            {field.value?.length || 0}/500
                          </span>
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Additional Notes (Optional)</FormLabel>
                        <FormControl>
                          <Textarea
                            placeholder="Any additional notes or references..."
                            rows={2}
                            className="resize-none"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Summary Card */}
              <Card className="sticky top-6">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Banknote className="h-5 w-5" />
                    Credit Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Type */}
                  <div className="flex items-start gap-3">
                    {selectedTypeConfig && (
                      <>
                        <div className={cn("p-2 rounded-md", selectedTypeConfig.iconBgColor)}>
                          <selectedTypeConfig.icon
                            className={cn("h-4 w-4", selectedTypeConfig.color)}
                          />
                        </div>
                        <div>
                          <div className={cn("text-sm font-medium", selectedTypeConfig.color)}>
                            {selectedTypeConfig.label}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {selectedTypeConfig.description}
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  <Separator />

                  {/* Student */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Student</div>
                    {selectedStudent ? (
                      <div className="font-medium">
                        {selectedStudent.first_name} {selectedStudent.last_name}
                        <div className="text-xs text-muted-foreground font-normal">
                          {selectedStudent.student_id}
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">Not selected</div>
                    )}
                  </div>

                  {/* Invoice */}
                  {selectedInvoice && (
                    <div>
                      <div className="text-xs text-muted-foreground mb-1">Linked Invoice</div>
                      <div className="font-medium">{selectedInvoice.invoice_number}</div>
                    </div>
                  )}

                  <Separator />

                  {/* Amount */}
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Credit Amount</div>
                    <div className={cn(
                      "text-2xl font-bold",
                      currentAmount > 0 ? selectedTypeConfig?.color : "text-muted-foreground"
                    )}>
                      {currentAmount > 0 ? formatCurrency(currentAmount) : "GHS 0.00"}
                    </div>
                  </div>

                  {/* Info message */}
                  <div className="rounded-md bg-blue-100 dark:bg-blue-950 border border-blue-300 dark:border-blue-800 p-3">
                    <div className="flex gap-2">
                      <Info className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" />
                      <p className="text-xs text-blue-700 dark:text-blue-300">
                        Credit notes are created as drafts. You'll need to issue it after creation
                        for it to take effect.
                      </p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="space-y-2 pt-2">
                    <Button
                      type="submit"
                      className="w-full"
                      size="lg"
                      disabled={isPending || formCompletion < 100}
                    >
                      {isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Receipt className="mr-2 h-4 w-4" />
                          Create Credit Note
                        </>
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="w-full"
                      asChild
                    >
                      <Link href="/finance/credit-notes">Cancel</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </form>
      </Form>
    </div>
  );
}
