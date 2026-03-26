"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import Link from "next/link";
import {
  Loader2,
  Pencil,
  ArrowLeft,
  DollarSign,
  Plus,
  Trash2,
  Clock,
  CreditCard,
  Smartphone,
  Banknote,
  FileText,
} from "lucide-react";

import {
  getStaffSalary,
  updateStaffSalary,
  getSalaryGrades,
  getAllowanceTypes,
  getDeductionTypes,
  getStaffSalaryHistory,
} from "@/actions/payroll.action";
import type {
  StaffSalaryConfig,
  SalaryGrade,
  AllowanceType,
  DeductionType,
  SalaryHistoryEntry,
  StaffAllowanceInput,
  StaffDeductionInput,
  PayrollPaymentMethod,
  CalculationMethod,
} from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const PAYMENT_METHODS: { value: PayrollPaymentMethod; label: string; icon: typeof CreditCard }[] = [
  { value: "bank_transfer", label: "Bank Transfer", icon: CreditCard },
  { value: "mobile_money", label: "Mobile Money", icon: Smartphone },
  { value: "cash", label: "Cash", icon: Banknote },
];

const CALC_METHODS: { value: CalculationMethod; label: string }[] = [
  { value: "fixed", label: "Fixed" },
  { value: "percentage_basic", label: "% Basic" },
  { value: "percentage_gross", label: "% Gross" },
];

const salaryConfigSchema = z.object({
  salary_grade_id: z.string().optional(),
  basic_salary: z.coerce.number().min(0, "Must be 0 or more"),
  effective_date: z.string().min(1, "Effective date is required"),
  payment_method: z.enum(["bank_transfer", "cash", "mobile_money"], {
    message: "Select a payment method",
  }),
  bank_name: z.string().optional(),
  bank_branch: z.string().optional(),
  account_number: z.string().optional(),
  mobile_money_number: z.string().optional(),
  mobile_money_provider: z.string().optional(),
  tin_number: z.string().optional(),
  ssnit_number: z.string().optional(),
  notes: z.string().optional(),
});

type SalaryConfigFormValues = z.infer<typeof salaryConfigSchema>;

function formatGHS(amount: number): string {
  return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function maskAccount(account: string | null): string {
  if (!account) return "-";
  if (account.length <= 4) return account;
  return `****${account.slice(-4)}`;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function StaffSalaryPage() {
  const params = useParams();
  const router = useRouter();
  const staffId = params.staffId as string;
  const { toast } = useToast();

  const [isPending, startTransition] = useTransition();
  const [config, setConfig] = useState<StaffSalaryConfig | null>(null);
  const [history, setHistory] = useState<SalaryHistoryEntry[]>([]);
  const [salaryGrades, setSalaryGrades] = useState<SalaryGrade[]>([]);
  const [allowanceTypes, setAllowanceTypes] = useState<AllowanceType[]>([]);
  const [deductionTypes, setDeductionTypes] = useState<DeductionType[]>([]);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [noConfig, setNoConfig] = useState(false);

  // Allowances/deductions state for dialog
  const [formAllowances, setFormAllowances] = useState<StaffAllowanceInput[]>([]);
  const [formDeductions, setFormDeductions] = useState<StaffDeductionInput[]>([]);

  const form = useForm<SalaryConfigFormValues>({
    resolver: zodResolver(salaryConfigSchema) as Resolver<SalaryConfigFormValues>,
    defaultValues: {
      salary_grade_id: "",
      basic_salary: 0,
      effective_date: "",
      payment_method: "bank_transfer",
      bank_name: "",
      bank_branch: "",
      account_number: "",
      mobile_money_number: "",
      mobile_money_provider: "",
      tin_number: "",
      ssnit_number: "",
      notes: "",
    },
  });

  const loadData = useCallback(() => {
    startTransition(async () => {
      const [salaryResult, historyResult, gradesResult, allowResult, deductResult] =
        await Promise.all([
          getStaffSalary(staffId),
          getStaffSalaryHistory(staffId),
          getSalaryGrades(true),
          getAllowanceTypes(true),
          getDeductionTypes(true),
        ]);

      if (salaryResult.success && salaryResult.data) {
        setConfig(salaryResult.data);
        setNoConfig(false);
      } else {
        setConfig(null);
        setNoConfig(true);
      }

      if (historyResult.success && historyResult.data) {
        setHistory(historyResult.data);
      }
      if (gradesResult.success && gradesResult.data) {
        setSalaryGrades(gradesResult.data);
      }
      if (allowResult.success && allowResult.data) {
        setAllowanceTypes(allowResult.data);
      }
      if (deductResult.success && deductResult.data) {
        setDeductionTypes(deductResult.data);
      }
    });
  }, [staffId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenEditDialog = () => {
    if (config) {
      form.reset({
        salary_grade_id: config.salary_grade_id || "",
        basic_salary: config.basic_salary,
        effective_date: config.effective_date,
        payment_method: config.payment_method,
        bank_name: config.bank_name || "",
        bank_branch: config.bank_branch || "",
        account_number: config.account_number || "",
        mobile_money_number: config.mobile_money_number || "",
        mobile_money_provider: config.mobile_money_provider || "",
        tin_number: config.tin_number || "",
        ssnit_number: config.ssnit_number || "",
        notes: config.notes || "",
      });
      setFormAllowances(
        config.allowances.map((a) => ({
          allowance_type_id: a.allowance_type_id,
          amount: a.amount,
          calculation_method: a.calculation_method || undefined,
        }))
      );
      setFormDeductions(
        config.deductions.map((d) => ({
          deduction_type_id: d.deduction_type_id,
          amount: d.amount,
          calculation_method: d.calculation_method || undefined,
        }))
      );
    } else {
      form.reset({
        salary_grade_id: "",
        basic_salary: 0,
        effective_date: new Date().toISOString().split("T")[0],
        payment_method: "bank_transfer",
        bank_name: "",
        bank_branch: "",
        account_number: "",
        mobile_money_number: "",
        mobile_money_provider: "",
        tin_number: "",
        ssnit_number: "",
        notes: "",
      });
      setFormAllowances([]);
      setFormDeductions([]);
    }
    setIsEditDialogOpen(true);
  };

  // Auto-fill basic salary when grade changes
  const watchedGradeId = form.watch("salary_grade_id");
  useEffect(() => {
    if (watchedGradeId) {
      const grade = salaryGrades.find((g) => g.id === watchedGradeId);
      if (grade) {
        form.setValue("basic_salary", grade.basic_salary);
      }
    }
  }, [watchedGradeId, salaryGrades, form]);

  const onSubmit = async (formData: SalaryConfigFormValues) => {
    setIsSubmitting(true);
    try {
      const data = {
        salary_grade_id: formData.salary_grade_id || undefined,
        basic_salary: formData.basic_salary,
        effective_date: formData.effective_date,
        payment_method: formData.payment_method,
        bank_name: formData.bank_name?.trim() || undefined,
        bank_branch: formData.bank_branch?.trim() || undefined,
        account_number: formData.account_number?.trim() || undefined,
        mobile_money_number: formData.mobile_money_number?.trim() || undefined,
        mobile_money_provider: formData.mobile_money_provider?.trim() || undefined,
        tin_number: formData.tin_number?.trim() || undefined,
        ssnit_number: formData.ssnit_number?.trim() || undefined,
        notes: formData.notes?.trim() || undefined,
        allowances: formAllowances,
        deductions: formDeductions,
      };

      const result = await updateStaffSalary(staffId, data);
      if (result.success) {
        toast({ title: "Salary configuration saved" });
        setIsEditDialogOpen(false);
        loadData();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const watchedPaymentMethod = form.watch("payment_method");

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Staff Salary</h1>
            <p className="text-muted-foreground">
              Manage salary configuration, allowances, and deductions
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {config && (
            <Button variant="outline" asChild className="gap-2">
              <Link href={`/payroll/staff/${staffId}/payslips`}>
                <FileText className="h-4 w-4" />
                Payslips / YTD
              </Link>
            </Button>
          )}
          <Button onClick={handleOpenEditDialog}>
            <Pencil className="mr-2 h-4 w-4" />
            {config ? "Edit Salary" : "Configure Salary"}
          </Button>
        </div>
      </div>

      {isPending ? (
        <div className="flex h-[300px] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : noConfig && !config ? (
        <Card>
          <CardContent className="flex h-[300px] flex-col items-center justify-center gap-4 text-muted-foreground">
            <DollarSign className="h-16 w-16" />
            <p className="text-lg font-medium">No salary configuration</p>
            <p className="text-sm text-center max-w-md">
              This staff member does not have a salary configuration yet. Click the button above to set one up.
            </p>
          </CardContent>
        </Card>
      ) : config ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Basic Salary</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{formatGHS(config.basic_salary)}</p>
                {config.salary_grade_name && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Grade: {config.salary_grade_name}
                  </p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Payment Method</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-semibold capitalize">
                  {config.payment_method.replace("_", " ")}
                </p>
                {config.bank_name && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {config.bank_name} {config.account_number ? `(${maskAccount(config.account_number)})` : ""}
                  </p>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Effective Date</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-semibold">{formatDate(config.effective_date)}</p>
                <Badge variant={config.is_active ? "default" : "secondary"} className="mt-1">
                  {config.is_active ? "Active" : "Inactive"}
                </Badge>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardDescription>Statutory IDs</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1">
                <p className="text-sm">
                  <span className="text-muted-foreground">TIN:</span>{" "}
                  {config.tin_number || "-"}
                </p>
                <p className="text-sm">
                  <span className="text-muted-foreground">SSNIT:</span>{" "}
                  {config.ssnit_number || "-"}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Allowances Table */}
          <Card>
            <CardHeader>
              <CardTitle>Allowances</CardTitle>
              <CardDescription>
                {config.allowances.length} allowance{config.allowances.length !== 1 ? "s" : ""} assigned
              </CardDescription>
            </CardHeader>
            <CardContent>
              {config.allowances.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead className="hidden sm:table-cell">Code</TableHead>
                      <TableHead className="hidden md:table-cell">Method</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {config.allowances.map((a) => (
                      <TableRow key={a.id}>
                        <TableCell className="font-medium">{a.allowance_type_name || "-"}</TableCell>
                        <TableCell className="hidden sm:table-cell font-mono text-sm">
                          {a.allowance_type_code || "-"}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm">
                          {a.calculation_method
                            ? CALC_METHODS.find((m) => m.value === a.calculation_method)?.label
                            : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {a.calculation_method && a.calculation_method !== "fixed"
                            ? `${a.amount}%`
                            : formatGHS(a.amount)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-6">
                  No allowances assigned to this staff member.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Deductions Table */}
          <Card>
            <CardHeader>
              <CardTitle>Deductions</CardTitle>
              <CardDescription>
                {config.deductions.length} deduction{config.deductions.length !== 1 ? "s" : ""} assigned
              </CardDescription>
            </CardHeader>
            <CardContent>
              {config.deductions.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead className="hidden sm:table-cell">Code</TableHead>
                      <TableHead className="hidden md:table-cell">Method</TableHead>
                      <TableHead className="text-right">Amount</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {config.deductions.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell className="font-medium">{d.deduction_type_name || "-"}</TableCell>
                        <TableCell className="hidden sm:table-cell font-mono text-sm">
                          {d.deduction_type_code || "-"}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm">
                          {d.calculation_method
                            ? CALC_METHODS.find((m) => m.value === d.calculation_method)?.label
                            : "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          {d.calculation_method && d.calculation_method !== "fixed"
                            ? `${d.amount}%`
                            : formatGHS(d.amount)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-6">
                  No deductions assigned to this staff member.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Salary History */}
          {history.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Salary History
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {history.map((entry, index) => (
                    <div key={entry.id} className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div
                          className={`h-3 w-3 rounded-full ${
                            index === 0 ? "bg-primary" : "bg-muted-foreground/30"
                          }`}
                        />
                        {index < history.length - 1 && (
                          <div className="w-px h-8 bg-border" />
                        )}
                      </div>
                      <div className="flex-1 pb-2">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium">
                            {formatGHS(entry.basic_salary)}
                          </p>
                          {entry.salary_grade_name && (
                            <Badge variant="outline" className="text-xs">
                              {entry.salary_grade_name}
                            </Badge>
                          )}
                          {entry.is_active && (
                            <Badge className="text-xs">Current</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Effective from {formatDate(entry.effective_date)}
                          {entry.end_date && ` to ${formatDate(entry.end_date)}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      {/* Edit Salary Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {config ? "Edit Salary Configuration" : "Set Up Salary"}
            </DialogTitle>
            <DialogDescription>
              Configure salary grade, payment details, allowances, and deductions.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              {/* Basic Info */}
              <div>
                <h3 className="text-sm font-semibold mb-3">Salary Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="salary_grade_id"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Salary Grade</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value || ""}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select grade (optional)" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="">No grade (manual)</SelectItem>
                            {salaryGrades.map((g) => (
                              <SelectItem key={g.id} value={g.id}>
                                {g.name} - {formatGHS(g.basic_salary)}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="basic_salary"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Basic Salary (GHS) *</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} step={0.01} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="effective_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Effective Date *</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <Separator />

              {/* Payment Info */}
              <div>
                <h3 className="text-sm font-semibold mb-3">Payment Details</h3>
                <FormField
                  control={form.control}
                  name="payment_method"
                  render={({ field }) => (
                    <FormItem className="mb-4">
                      <FormLabel>Payment Method *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {PAYMENT_METHODS.map((m) => (
                            <SelectItem key={m.value} value={m.value}>
                              {m.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                {watchedPaymentMethod === "bank_transfer" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      name="bank_branch"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Bank Branch</FormLabel>
                          <FormControl>
                            <Input placeholder="e.g., Accra Main" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="account_number"
                      render={({ field }) => (
                        <FormItem className="md:col-span-2">
                          <FormLabel>Account Number</FormLabel>
                          <FormControl>
                            <Input {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                )}
                {watchedPaymentMethod === "mobile_money" && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="mobile_money_provider"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Provider</FormLabel>
                          <Select onValueChange={field.onChange} value={field.value || ""}>
                            <FormControl>
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="Select provider" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="mtn">MTN MoMo</SelectItem>
                              <SelectItem value="vodafone">Vodafone Cash</SelectItem>
                              <SelectItem value="airteltigo">AirtelTigo</SelectItem>
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="mobile_money_number"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Phone Number</FormLabel>
                          <FormControl>
                            <Input placeholder="+233 XX XXX XXXX" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                )}
              </div>

              <Separator />

              {/* Statutory IDs */}
              <div>
                <h3 className="text-sm font-semibold mb-3">Statutory Identifiers</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="tin_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>TIN Number</FormLabel>
                        <FormControl>
                          <Input placeholder="Tax Identification Number" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="ssnit_number"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>SSNIT Number</FormLabel>
                        <FormControl>
                          <Input placeholder="Social Security Number" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              <Separator />

              {/* Allowances */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Allowances</h3>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setFormAllowances([
                        ...formAllowances,
                        { allowance_type_id: "", amount: 0 },
                      ])
                    }
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Add
                  </Button>
                </div>
                {formAllowances.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-3 border rounded-lg">
                    No allowances. Click &quot;Add&quot; to assign one.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {formAllowances.map((allowance, index) => (
                      <div key={index} className="flex items-center gap-2 rounded-lg border p-2">
                        <Select
                          value={allowance.allowance_type_id}
                          onValueChange={(v) => {
                            const updated = [...formAllowances];
                            updated[index] = { ...updated[index], allowance_type_id: v };
                            // Auto-fill amount from default
                            const at = allowanceTypes.find((t) => t.id === v);
                            if (at) {
                              updated[index].amount = at.default_amount;
                              updated[index].calculation_method = at.calculation_method;
                            }
                            setFormAllowances(updated);
                          }}
                        >
                          <SelectTrigger className="w-full sm:w-[180px]">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            {allowanceTypes.map((at) => (
                              <SelectItem key={at.id} value={at.id}>
                                {at.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input
                          type="number"
                          min={0}
                          step={0.01}
                          value={allowance.amount}
                          onChange={(e) => {
                            const updated = [...formAllowances];
                            updated[index] = {
                              ...updated[index],
                              amount: Number(e.target.value),
                            };
                            setFormAllowances(updated);
                          }}
                          className="w-28"
                          placeholder="Amount"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            setFormAllowances(formAllowances.filter((_, i) => i !== index))
                          }
                          className="shrink-0"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Deductions */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Deductions</h3>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setFormDeductions([
                        ...formDeductions,
                        { deduction_type_id: "", amount: 0 },
                      ])
                    }
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    Add
                  </Button>
                </div>
                {formDeductions.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-3 border rounded-lg">
                    No deductions. Click &quot;Add&quot; to assign one.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {formDeductions.map((deduction, index) => (
                      <div key={index} className="flex items-center gap-2 rounded-lg border p-2">
                        <Select
                          value={deduction.deduction_type_id}
                          onValueChange={(v) => {
                            const updated = [...formDeductions];
                            updated[index] = { ...updated[index], deduction_type_id: v };
                            const dt = deductionTypes.find((t) => t.id === v);
                            if (dt) {
                              updated[index].amount = dt.default_amount;
                              updated[index].calculation_method = dt.calculation_method;
                            }
                            setFormDeductions(updated);
                          }}
                        >
                          <SelectTrigger className="w-full sm:w-[180px]">
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            {deductionTypes.map((dt) => (
                              <SelectItem key={dt.id} value={dt.id}>
                                {dt.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Input
                          type="number"
                          min={0}
                          step={0.01}
                          value={deduction.amount}
                          onChange={(e) => {
                            const updated = [...formDeductions];
                            updated[index] = {
                              ...updated[index],
                              amount: Number(e.target.value),
                            };
                            setFormDeductions(updated);
                          }}
                          className="w-28"
                          placeholder="Amount"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() =>
                            setFormDeductions(formDeductions.filter((_, i) => i !== index))
                          }
                          className="shrink-0"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <Separator />

              {/* Notes */}
              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes</FormLabel>
                    <FormControl>
                      <Textarea rows={2} placeholder="Optional notes" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsEditDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save Configuration
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
