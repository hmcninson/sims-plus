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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Pencil, Trash2, DollarSign } from "lucide-react";

import {
  getSalaryGrades,
  createSalaryGrade,
  updateSalaryGrade,
  deleteSalaryGrade,
} from "@/actions/payroll.action";
import type { SalaryGrade } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

const salaryGradeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().max(20).optional(),
  basic_salary: z.coerce.number().min(0, "Must be 0 or more"),
  min_salary: z.coerce.number().min(0).optional().or(z.literal("")),
  max_salary: z.coerce.number().min(0).optional().or(z.literal("")),
  description: z.string().optional(),
});

type SalaryGradeFormValues = z.infer<typeof salaryGradeSchema>;

function formatGHS(amount: number): string {
  return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function SalaryGradesTab() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [grades, setGrades] = useState<SalaryGrade[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingGrade, setEditingGrade] = useState<SalaryGrade | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<SalaryGradeFormValues>({
    resolver: zodResolver(salaryGradeSchema) as Resolver<SalaryGradeFormValues>,
    defaultValues: {
      name: "",
      code: "",
      basic_salary: 0,
      min_salary: "",
      max_salary: "",
      description: "",
    },
  });

  const loadGrades = () => {
    startTransition(async () => {
      const result = await getSalaryGrades();
      if (result.success && result.data) {
        setGrades(result.data);
      }
    });
  };

  useEffect(() => {
    loadGrades();
  }, []);

  const handleOpenDialog = (grade?: SalaryGrade) => {
    if (grade) {
      setEditingGrade(grade);
      form.reset({
        name: grade.name,
        code: grade.code || "",
        basic_salary: grade.basic_salary,
        min_salary: grade.min_salary ?? "",
        max_salary: grade.max_salary ?? "",
        description: grade.description || "",
      });
    } else {
      setEditingGrade(null);
      form.reset({
        name: "",
        code: "",
        basic_salary: 0,
        min_salary: "",
        max_salary: "",
        description: "",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: SalaryGradeFormValues) => {
    setIsSubmitting(true);
    try {
      const data = {
        name: formData.name.trim(),
        code: formData.code?.trim().toUpperCase() || undefined,
        basic_salary: formData.basic_salary,
        min_salary: formData.min_salary !== "" ? Number(formData.min_salary) : undefined,
        max_salary: formData.max_salary !== "" ? Number(formData.max_salary) : undefined,
        description: formData.description?.trim() || undefined,
      };

      if (editingGrade) {
        const result = await updateSalaryGrade(editingGrade.id, data);
        if (result.success) {
          toast({ title: "Salary grade updated", description: `${formData.name} has been updated.` });
          setIsDialogOpen(false);
          loadGrades();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createSalaryGrade(data);
        if (result.success) {
          toast({ title: "Salary grade created", description: `${formData.name} has been created.` });
          setIsDialogOpen(false);
          loadGrades();
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
      const result = await deleteSalaryGrade(deleteId);
      if (result.success) {
        toast({ title: "Salary grade deleted" });
        loadGrades();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  const handleToggleActive = async (grade: SalaryGrade) => {
    const result = await updateSalaryGrade(grade.id, {
      is_active: !grade.is_active,
    });
    if (result.success) {
      toast({ title: grade.is_active ? "Grade deactivated" : "Grade activated" });
      loadGrades();
    } else {
      toast({ title: "Error", description: result.error, variant: "destructive" });
    }
  };

  return (
    <>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold">Salary Grades</h2>
          <p className="text-sm text-muted-foreground">
            Define salary scales and pay bands for staff
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Grade
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Salary Grades</CardTitle>
          <CardDescription>
            {grades.length} grade{grades.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : grades.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Code</TableHead>
                    <TableHead className="text-right">Basic Salary</TableHead>
                    <TableHead className="hidden md:table-cell text-right">Range</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {grades.map((grade) => (
                    <TableRow key={grade.id}>
                      <TableCell className="font-medium">{grade.name}</TableCell>
                      <TableCell className="hidden sm:table-cell font-mono text-sm">
                        {grade.code || "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatGHS(grade.basic_salary)}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right text-sm text-muted-foreground">
                        {grade.min_salary != null && grade.max_salary != null
                          ? `${formatGHS(grade.min_salary)} - ${formatGHS(grade.max_salary)}`
                          : "-"}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={grade.is_active ? "default" : "secondary"}
                          className="cursor-pointer"
                          onClick={() => handleToggleActive(grade)}
                        >
                          {grade.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => handleOpenDialog(grade)}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => setDeleteId(grade.id)}>
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
              <DollarSign className="h-12 w-12" />
              <p>No salary grades configured</p>
              <p className="text-sm text-center max-w-md">
                Create salary grades to define pay scales for staff members.
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
              {editingGrade ? "Edit Salary Grade" : "Create Salary Grade"}
            </DialogTitle>
            <DialogDescription>
              {editingGrade
                ? "Update salary grade configuration."
                : "Add a new salary grade for staff."}
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
                        <Input placeholder="e.g., Grade A" {...field} />
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
                        <Input
                          placeholder="e.g., GR-A"
                          {...field}
                          onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="min_salary"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Min Salary (GHS)</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.01} placeholder="Optional" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="max_salary"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Salary (GHS)</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.01} placeholder="Optional" {...field} />
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
                      <Textarea rows={2} placeholder="Optional notes about this grade" {...field} />
                    </FormControl>
                    <FormMessage />
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
                  {editingGrade ? "Save Changes" : "Create Grade"}
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
            <AlertDialogTitle>Delete Salary Grade?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate this salary grade. Staff currently assigned to it will not be affected.
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
