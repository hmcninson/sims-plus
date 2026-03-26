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
import { Loader2, Plus, Pencil, Trash2, Gift } from "lucide-react";

import {
  getAllowanceTypes,
  createAllowanceType,
  updateAllowanceType,
  deleteAllowanceType,
} from "@/actions/payroll.action";
import type { AllowanceType, CalculationMethod } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const CALC_METHODS: { value: CalculationMethod; label: string }[] = [
  { value: "fixed", label: "Fixed Amount" },
  { value: "percentage_basic", label: "% of Basic" },
  { value: "percentage_gross", label: "% of Gross" },
];

const allowanceTypeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20),
  calculation_method: z.enum(["fixed", "percentage_basic", "percentage_gross"], {
    message: "Select a calculation method",
  }),
  default_amount: z.coerce.number().min(0, "Must be 0 or more"),
  is_taxable: z.boolean(),
  description: z.string().optional(),
});

type AllowanceTypeFormValues = z.infer<typeof allowanceTypeSchema>;

function formatAmount(amount: number, method: CalculationMethod): string {
  if (method === "fixed") {
    return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${amount}%`;
}

export function AllowanceTypesTab() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [allowances, setAllowances] = useState<AllowanceType[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState<AllowanceType | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<AllowanceTypeFormValues>({
    resolver: zodResolver(allowanceTypeSchema) as Resolver<AllowanceTypeFormValues>,
    defaultValues: {
      name: "",
      code: "",
      calculation_method: "fixed",
      default_amount: 0,
      is_taxable: true,
      description: "",
    },
  });

  const loadAllowances = () => {
    startTransition(async () => {
      const result = await getAllowanceTypes();
      if (result.success && result.data) {
        setAllowances(result.data);
      }
    });
  };

  useEffect(() => {
    loadAllowances();
  }, []);

  const handleOpenDialog = (allowance?: AllowanceType) => {
    if (allowance) {
      setEditingType(allowance);
      form.reset({
        name: allowance.name,
        code: allowance.code,
        calculation_method: allowance.calculation_method,
        default_amount: allowance.default_amount,
        is_taxable: allowance.is_taxable,
        description: allowance.description || "",
      });
    } else {
      setEditingType(null);
      form.reset({
        name: "",
        code: "",
        calculation_method: "fixed",
        default_amount: 0,
        is_taxable: true,
        description: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: AllowanceTypeFormValues) => {
    setIsSubmitting(true);
    try {
      const data = {
        name: formData.name.trim(),
        code: formData.code.trim().toUpperCase(),
        calculation_method: formData.calculation_method,
        default_amount: formData.default_amount,
        is_taxable: formData.is_taxable,
        description: formData.description?.trim() || undefined,
      };

      if (editingType) {
        const result = await updateAllowanceType(editingType.id, data);
        if (result.success) {
          toast({ title: "Allowance type updated", description: `${formData.name} has been updated.` });
          setIsDialogOpen(false);
          loadAllowances();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createAllowanceType(data);
        if (result.success) {
          toast({ title: "Allowance type created", description: `${formData.name} has been created.` });
          setIsDialogOpen(false);
          loadAllowances();
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
      const result = await deleteAllowanceType(deleteId);
      if (result.success) {
        toast({ title: "Allowance type deleted" });
        loadAllowances();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  const handleToggleActive = async (allowance: AllowanceType) => {
    const result = await updateAllowanceType(allowance.id, {
      is_active: !allowance.is_active,
    });
    if (result.success) {
      toast({ title: allowance.is_active ? "Allowance deactivated" : "Allowance activated" });
      loadAllowances();
    } else {
      toast({ title: "Error", description: result.error, variant: "destructive" });
    }
  };

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Allowance Types</h2>
          <p className="text-sm text-muted-foreground">
            Configure allowance categories for payroll calculation
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Allowance
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Allowance Types</CardTitle>
          <CardDescription>
            {allowances.length} allowance{allowances.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : allowances.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Code</TableHead>
                    <TableHead className="hidden md:table-cell">Method</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="hidden sm:table-cell">Taxable</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allowances.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">{a.name}</TableCell>
                      <TableCell className="hidden sm:table-cell font-mono text-sm">{a.code}</TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {CALC_METHODS.find((m) => m.value === a.calculation_method)?.label}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatAmount(a.default_amount, a.calculation_method)}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {a.is_taxable ? (
                          <Badge variant="secondary">Taxable</Badge>
                        ) : (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                            Tax-free
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={a.is_active ? "default" : "secondary"}
                          className="cursor-pointer"
                          onClick={() => handleToggleActive(a)}
                        >
                          {a.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(a)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(a.id)}>
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
              <Gift className="h-12 w-12" />
              <p>No allowance types configured</p>
              <p className="text-sm text-center max-w-md">
                Create allowance types like housing, transport, and responsibility allowances.
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
              {editingType ? "Edit Allowance Type" : "Create Allowance Type"}
            </DialogTitle>
            <DialogDescription>
              {editingType
                ? "Update allowance type configuration."
                : "Add a new allowance type for payroll."}
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
                        <Input placeholder="e.g., Housing Allowance" {...field} />
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
                          placeholder="e.g., HOUS"
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
              <FormField
                control={form.control}
                name="is_taxable"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel className="text-sm font-medium">Taxable</FormLabel>
                      <p className="text-xs text-muted-foreground">
                        Include this allowance in PAYE taxable income
                      </p>
                    </div>
                    <FormControl>
                      <Switch checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                  </FormItem>
                )}
              />
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
                  {editingType ? "Save Changes" : "Create Allowance"}
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
            <AlertDialogTitle>Delete Allowance Type?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate this allowance type. Existing payroll records will not be affected.
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
