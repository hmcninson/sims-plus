"use client";

import { useEffect, useState, useTransition } from "react";
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
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Pencil, Trash2, MinusCircle } from "lucide-react";

import {
  getDeductionTypes,
  createDeductionType,
  updateDeductionType,
  deleteDeductionType,
} from "@/actions/payroll.action";
import type { DeductionType, CalculationMethod, DeductionCategory } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const CALC_METHODS: { value: CalculationMethod; label: string }[] = [
  { value: "fixed", label: "Fixed Amount" },
  { value: "percentage_basic", label: "% of Basic" },
  { value: "percentage_gross", label: "% of Gross" },
];

const DEDUCTION_CATEGORIES: { value: DeductionCategory; label: string }[] = [
  { value: "statutory", label: "Statutory" },
  { value: "voluntary", label: "Voluntary" },
  { value: "loan", label: "Loan" },
  { value: "union", label: "Union" },
  { value: "other", label: "Other" },
];

const CATEGORY_COLORS: Record<DeductionCategory, string> = {
  statutory: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  voluntary: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  loan: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  union: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  other: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const deductionTypeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20),
  calculation_method: z.enum(["fixed", "percentage_basic", "percentage_gross"], {
    message: "Select a calculation method",
  }),
  default_amount: z.coerce.number().min(0, "Must be 0 or more"),
  is_statutory: z.boolean(),
  is_employer_portion: z.boolean(),
  deduction_category: z.enum(["statutory", "voluntary", "loan", "union", "other"], {
    message: "Select a category",
  }),
  description: z.string().optional(),
});

type DeductionTypeFormValues = z.infer<typeof deductionTypeSchema>;

function formatAmount(amount: number, method: CalculationMethod): string {
  if (method === "fixed") {
    return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${amount}%`;
}

export function DeductionTypesTab() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [deductions, setDeductions] = useState<DeductionType[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState<DeductionType | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<DeductionTypeFormValues>({
    resolver: zodResolver(deductionTypeSchema) as Resolver<DeductionTypeFormValues>,
    defaultValues: {
      name: "",
      code: "",
      calculation_method: "fixed",
      default_amount: 0,
      is_statutory: false,
      is_employer_portion: false,
      deduction_category: "voluntary",
      description: "",
    },
  });

  const loadDeductions = () => {
    startTransition(async () => {
      const result = await getDeductionTypes();
      if (result.success && result.data) {
        setDeductions(result.data);
      }
    });
  };

  useEffect(() => {
    loadDeductions();
  }, []);

  const handleOpenDialog = (deduction?: DeductionType) => {
    if (deduction) {
      setEditingType(deduction);
      form.reset({
        name: deduction.name,
        code: deduction.code,
        calculation_method: deduction.calculation_method,
        default_amount: deduction.default_amount,
        is_statutory: deduction.is_statutory,
        is_employer_portion: deduction.is_employer_portion,
        deduction_category: deduction.deduction_category,
        description: deduction.description || "",
      });
    } else {
      setEditingType(null);
      form.reset({
        name: "",
        code: "",
        calculation_method: "fixed",
        default_amount: 0,
        is_statutory: false,
        is_employer_portion: false,
        deduction_category: "voluntary",
        description: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: DeductionTypeFormValues) => {
    setIsSubmitting(true);
    try {
      const data = {
        name: formData.name.trim(),
        code: formData.code.trim().toUpperCase(),
        calculation_method: formData.calculation_method,
        default_amount: formData.default_amount,
        is_statutory: formData.is_statutory,
        is_employer_portion: formData.is_employer_portion,
        deduction_category: formData.deduction_category,
        description: formData.description?.trim() || undefined,
      };

      if (editingType) {
        const result = await updateDeductionType(editingType.id, data);
        if (result.success) {
          toast({ title: "Deduction type updated", description: `${formData.name} has been updated.` });
          setIsDialogOpen(false);
          loadDeductions();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createDeductionType(data);
        if (result.success) {
          toast({ title: "Deduction type created", description: `${formData.name} has been created.` });
          setIsDialogOpen(false);
          loadDeductions();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteDeductionType(deleteId);
      if (result.success) {
        toast({ title: "Deduction type deleted" });
        loadDeductions();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  const handleToggleActive = async (deduction: DeductionType) => {
    const result = await updateDeductionType(deduction.id, {
      is_active: !deduction.is_active,
    });
    if (result.success) {
      toast({ title: deduction.is_active ? "Deduction deactivated" : "Deduction activated" });
      loadDeductions();
    } else {
      toast({ title: "Error", description: result.error, variant: "destructive" });
    }
  };

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Deduction Types</h2>
          <p className="text-sm text-muted-foreground">
            Configure deduction categories including statutory and voluntary deductions
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Deduction
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Deduction Types</CardTitle>
          <CardDescription>
            {deductions.length} deduction{deductions.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : deductions.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Code</TableHead>
                    <TableHead className="hidden md:table-cell">Method</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="hidden sm:table-cell">Category</TableHead>
                    <TableHead className="hidden md:table-cell">Statutory</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deductions.map((d) => (
                    <TableRow key={d.id}>
                      <TableCell className="font-medium">
                        {d.name}
                        {d.is_employer_portion && (
                          <span className="ml-1 text-xs text-muted-foreground">(Employer)</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell font-mono text-sm">{d.code}</TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {CALC_METHODS.find((m) => m.value === d.calculation_method)?.label}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatAmount(d.default_amount, d.calculation_method)}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge className={CATEGORY_COLORS[d.deduction_category]}>
                          {DEDUCTION_CATEGORIES.find((c) => c.value === d.deduction_category)?.label}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {d.is_statutory ? (
                          <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
                            Yes
                          </Badge>
                        ) : (
                          <span className="text-sm text-muted-foreground">No</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={d.is_active ? "default" : "secondary"}
                          className="cursor-pointer"
                          onClick={() => handleToggleActive(d)}
                        >
                          {d.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(d)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(d.id)}>
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <MinusCircle className="h-12 w-12" />
              <p>No deduction types configured</p>
              <p className="text-sm text-center max-w-md">
                Create deduction types like SSNIT, PAYE, staff welfare, and loan repayments.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingType ? "Edit Deduction Type" : "Create Deduction Type"}
            </DialogTitle>
            <DialogDescription>
              {editingType
                ? "Update deduction type configuration."
                : "Add a new deduction type for payroll."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., SSNIT Employee" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Code *</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., SSNIT_EE"
                          {...field}
                          onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="calculation_method"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Calculation Method *</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select method" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {CALC_METHODS.map((m) => (
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
                <FormField
                  control={form.control}
                  name="default_amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        Default Amount {form.watch("calculation_method") !== "fixed" ? "(%)" : "(GHS)"} *
                      </FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.01} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="deduction_category"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Category *</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select category" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {DEDUCTION_CATEGORIES.map((c) => (
                          <SelectItem key={c.value} value={c.value}>
                            {c.label}
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
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="is_statutory"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <FormLabel className="text-sm font-medium">Statutory</FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Required by law (SSNIT, PAYE)
                        </p>
                      </div>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="is_employer_portion"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <FormLabel className="text-sm font-medium">Employer Portion</FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Not deducted from staff pay
                        </p>
                      </div>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingType ? "Save Changes" : "Create Deduction"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Deduction Type?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate this deduction type. Existing payroll records will not be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
