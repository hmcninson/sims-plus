"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { ArrowLeft, Plus, Pencil, Trash2, Loader2, Settings2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  getLoanTypes,
  createLoanType,
  updateLoanType,
  deleteLoanType,
} from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";
import type { LoanType, InterestMethod } from "@/types/loan.type";

const loanTypeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20),
  description: z.string().optional(),
  default_interest_rate: z.coerce.number().min(0).max(100),
  default_interest_method: z.enum(["flat", "reducing_balance"]),
  max_amount: z.coerce.number().min(0).optional().or(z.literal("")),
  max_tenure_months: z.coerce.number().int().min(1).optional().or(z.literal("")),
  max_active_loans: z.coerce.number().int().min(1),
  requires_guarantor: z.boolean(),
  min_service_months: z.coerce.number().int().min(0),
  max_deduction_pct: z.coerce.number().min(0).max(100),
});

type LoanTypeFormValues = z.infer<typeof loanTypeSchema>;

export default function LoanTypeSettingsPage() {
  const [isPending, startTransition] = useTransition();
  const [loanTypes, setLoanTypes] = useState<LoanType[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState<LoanType | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LoanTypeFormValues>({
    resolver: zodResolver(loanTypeSchema) as Resolver<LoanTypeFormValues>,
    defaultValues: {
      name: "",
      code: "",
      description: "",
      default_interest_rate: 0,
      default_interest_method: "flat",
      max_amount: "",
      max_tenure_months: "",
      max_active_loans: 1,
      requires_guarantor: false,
      min_service_months: 0,
      max_deduction_pct: 50,
    },
  });

  const loadData = () => {
    startTransition(async () => {
      const result = await getLoanTypes();
      if (result.success) setLoanTypes(result.data);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenDialog = (lt?: LoanType) => {
    if (lt) {
      setEditingType(lt);
      form.reset({
        name: lt.name,
        code: lt.code,
        description: lt.description || "",
        default_interest_rate: lt.default_interest_rate,
        default_interest_method: lt.default_interest_method,
        max_amount: lt.max_amount ?? "",
        max_tenure_months: lt.max_tenure_months ?? "",
        max_active_loans: lt.max_active_loans,
        requires_guarantor: lt.requires_guarantor,
        min_service_months: lt.min_service_months,
        max_deduction_pct: lt.max_deduction_pct,
      });
    } else {
      setEditingType(null);
      form.reset({
        name: "",
        code: "",
        description: "",
        default_interest_rate: 0,
        default_interest_method: "flat",
        max_amount: "",
        max_tenure_months: "",
        max_active_loans: 1,
        requires_guarantor: false,
        min_service_months: 0,
        max_deduction_pct: 50,
      });
    }
    setIsDialogOpen(true);
  };

  const handleSubmit = async (values: LoanTypeFormValues) => {
    setIsSubmitting(true);

    const payload = {
      name: values.name,
      code: values.code,
      description: values.description || undefined,
      default_interest_rate: values.default_interest_rate,
      default_interest_method: values.default_interest_method as InterestMethod,
      max_amount:
        values.max_amount !== "" && values.max_amount !== undefined
          ? Number(values.max_amount)
          : undefined,
      max_tenure_months:
        values.max_tenure_months !== "" && values.max_tenure_months !== undefined
          ? Number(values.max_tenure_months)
          : undefined,
      max_active_loans: values.max_active_loans,
      requires_guarantor: values.requires_guarantor,
      min_service_months: values.min_service_months,
      max_deduction_pct: values.max_deduction_pct,
    };

    const result = editingType
      ? await updateLoanType(editingType.id, payload)
      : await createLoanType(payload);

    if (result.success) {
      toast.success(
        editingType ? "Loan type updated" : "Loan type created"
      );
      setIsDialogOpen(false);
      loadData();
    } else {
      toast.error(result.error);
    }
    setIsSubmitting(false);
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    const result = await deleteLoanType(deleteId);
    if (result.success) {
      toast.success("Loan type deleted");
      loadData();
    } else {
      toast.error(result.error);
    }
    setDeleteId(null);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/payroll/loans">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Loan Type Settings
            </h1>
            <p className="text-muted-foreground">
              Configure loan categories with interest rates, limits, and rules
            </p>
          </div>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="h-4 w-4 mr-2" />
          Add Loan Type
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isPending ? (
            <div className="p-6 space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : loanTypes.length === 0 ? (
            <div className="flex flex-col items-center py-16 gap-3">
              <Settings2 className="h-10 w-10 text-muted-foreground" />
              <h3 className="text-lg font-semibold">No loan types configured</h3>
              <p className="text-sm text-muted-foreground">
                Add loan types to start processing loan applications
              </p>
              <Button size="sm" onClick={() => handleOpenDialog()}>
                <Plus className="h-4 w-4 mr-1" />
                Add Loan Type
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Code</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Interest
                    </TableHead>
                    <TableHead className="hidden md:table-cell">
                      Max Amount
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Max Tenure
                    </TableHead>
                    <TableHead className="hidden lg:table-cell">
                      Guarantor
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[100px]" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loanTypes.map((lt) => (
                    <TableRow key={lt.id}>
                      <TableCell className="font-medium">{lt.name}</TableCell>
                      <TableCell className="font-mono text-sm">
                        {lt.code}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {lt.default_interest_rate}%{" "}
                        {lt.default_interest_method === "flat"
                          ? "Flat"
                          : "Reducing"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {lt.max_amount ? formatGHS(lt.max_amount) : "No limit"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {lt.max_tenure_months
                          ? `${lt.max_tenure_months} months`
                          : "No limit"}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {lt.requires_guarantor ? (
                          <Badge variant="outline">Required</Badge>
                        ) : (
                          "No"
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={lt.is_active ? "default" : "secondary"}
                          className={
                            lt.is_active
                              ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                              : ""
                          }
                        >
                          {lt.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleOpenDialog(lt)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(lt.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingType ? "Edit Loan Type" : "Add Loan Type"}
            </DialogTitle>
            <DialogDescription>
              {editingType
                ? "Update the loan type configuration"
                : "Create a new loan type category"}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleSubmit)}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Salary Advance" {...field} />
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
                      <FormLabel>Code</FormLabel>
                      <FormControl>
                        <Input placeholder="SAL_ADV" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Brief description..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="default_interest_rate"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Default Interest Rate (%)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          max="100"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="default_interest_method"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Interest Method</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger className="w-full">
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="flat">Flat Rate</SelectItem>
                          <SelectItem value="reducing_balance">
                            Reducing Balance
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="max_amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Amount (GHS, optional)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="No limit"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="max_tenure_months"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Tenure (months, optional)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min="1"
                          placeholder="No limit"
                          {...field}
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
                  name="max_active_loans"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Active Loans</FormLabel>
                      <FormControl>
                        <Input type="number" min="1" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="min_service_months"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Min Service (months)</FormLabel>
                      <FormControl>
                        <Input type="number" min="0" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="max_deduction_pct"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Max Deduction (% of net salary)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        max="100"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="requires_guarantor"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-2 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">
                      Requires guarantor
                    </FormLabel>
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  )}
                  {editingType ? "Update" : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteId}
        onOpenChange={(open) => !open && setDeleteId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Loan Type</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this loan type? Existing loans of
              this type will not be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
