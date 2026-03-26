"use client";

import { useEffect, useState, useCallback } from "react";
import {
  TrendingUp,
  Plus,
  Edit,
  Trash2,
  Loader2,
  Check,
  X,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  getPromotionRules,
  createPromotionRule,
  updatePromotionRule,
  deletePromotionRule,
} from "@/actions/students.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import type { PromotionRule, AcademicYear, Class } from "@/types";

// Helper: accepts number or empty string from form inputs
const optionalNumber = z.union([
  z.coerce.number().min(0),
  z.literal(""),
]);

const formSchema = z.object({
  academic_year_id: z.string().min(1, "Academic year is required"),
  class_id: z.string().optional(),
  min_average: optionalNumber,
  min_attendance_percent: optionalNumber,
  core_passes_required: optionalNumber,
  pass_mark: optionalNumber,
  auto_apply: z.boolean(),
  is_active: z.boolean(),
}).refine(
  (data) =>
    data.min_average !== "" ||
    data.min_attendance_percent !== "" ||
    data.core_passes_required !== "" ||
    data.pass_mark !== "",
  { message: "At least one criterion is required", path: ["min_average"] }
);

type FormValues = z.infer<typeof formSchema>;

export function PromotionRulesPage() {
  const [rules, setRules] = useState<PromotionRule[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterYear, setFilterYear] = useState<string>("all");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<PromotionRule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PromotionRule | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      academic_year_id: "",
      class_id: "",
      min_average: "",
      min_attendance_percent: "",
      core_passes_required: "",
      pass_mark: "",
      auto_apply: false,
      is_active: true,
    },
  });

  const fetchRules = useCallback(async () => {
    setLoading(true);
    const yearFilter = filterYear !== "all" ? filterYear : undefined;
    const result = await getPromotionRules(yearFilter);
    if (result.success && result.data) {
      setRules(result.data.items);
    } else {
      toast.error(result.error || "Failed to load promotion rules");
    }
    setLoading(false);
  }, [filterYear]);

  const fetchLookups = useCallback(async () => {
    const [yearsRes, classesRes] = await Promise.all([
      getAcademicYears(false),
      getClasses(false),
    ]);
    if (yearsRes.success && yearsRes.data) {
      setAcademicYears(yearsRes.data);
    }
    if (classesRes.success && classesRes.data) {
      setClasses(classesRes.data.filter((c) => c.is_active));
    }
  }, []);

  useEffect(() => {
    fetchRules();
  }, [fetchRules]);

  useEffect(() => {
    fetchLookups();
  }, [fetchLookups]);

  const openCreate = () => {
    setEditingRule(null);
    form.reset({
      academic_year_id: "",
      class_id: "",
      min_average: "",
      min_attendance_percent: "",
      core_passes_required: "",
      pass_mark: "",
      auto_apply: false,
      is_active: true,
    });
    setDialogOpen(true);
  };

  const openEdit = (rule: PromotionRule) => {
    setEditingRule(rule);
    form.reset({
      academic_year_id: rule.academic_year_id,
      class_id: rule.class_id || "",
      min_average: rule.min_average ?? "",
      min_attendance_percent: rule.min_attendance_percent ?? "",
      core_passes_required: rule.core_passes_required ?? "",
      pass_mark: rule.pass_mark ?? "",
      auto_apply: rule.auto_apply,
      is_active: rule.is_active,
    });
    setDialogOpen(true);
  };

  const handleSubmit = async (values: FormValues) => {
    const data = {
      academic_year_id: values.academic_year_id,
      class_id: values.class_id && values.class_id !== "school_wide" ? values.class_id : null,
      min_average: values.min_average !== "" ? Number(values.min_average) : null,
      min_attendance_percent: values.min_attendance_percent !== "" ? Number(values.min_attendance_percent) : null,
      core_passes_required: values.core_passes_required !== "" ? Number(values.core_passes_required) : null,
      pass_mark: values.pass_mark !== "" ? Number(values.pass_mark) : null,
      auto_apply: values.auto_apply,
      is_active: values.is_active,
    };

    if (editingRule) {
      const result = await updatePromotionRule(editingRule.id, data);
      if (result.success) {
        toast.success("Promotion rule updated");
        setDialogOpen(false);
        fetchRules();
      } else {
        toast.error(result.error || "Failed to update rule");
      }
    } else {
      const result = await createPromotionRule(data);
      if (result.success) {
        toast.success("Promotion rule created");
        setDialogOpen(false);
        fetchRules();
      } else {
        toast.error(result.error || "Failed to create rule");
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    const result = await deletePromotionRule(deleteTarget.id);
    if (result.success) {
      toast.success("Promotion rule deleted");
      setDeleteTarget(null);
      fetchRules();
    } else {
      toast.error(result.error || "Failed to delete rule");
    }
    setIsDeleting(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Promotion Rules
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Configure criteria for student promotion to the next class.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Add Rule
        </Button>
      </div>

      {/* Filter by Academic Year */}
      <div className="flex items-center gap-2">
        <Select value={filterYear} onValueChange={setFilterYear}>
          <SelectTrigger className="w-full sm:w-[250px]">
            <SelectValue placeholder="All Academic Years" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Academic Years</SelectItem>
            {academicYears.map((ay) => (
              <SelectItem key={ay.id} value={ay.id}>
                {ay.name} {ay.is_current ? "(Current)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Rules Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : rules.length === 0 ? (
            <div className="text-center py-12 px-6">
              <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                <TrendingUp className="h-7 w-7 text-muted-foreground" />
              </div>
              <h3 className="font-semibold mb-1">No Promotion Rules</h3>
              <p className="text-muted-foreground mb-4">
                Create rules to define the criteria students must meet to be promoted.
              </p>
              <Button variant="outline" onClick={openCreate}>
                <Plus className="h-4 w-4 mr-2" />
                Create First Rule
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Academic Year</TableHead>
                    <TableHead>Class</TableHead>
                    <TableHead className="hidden sm:table-cell">Min Average</TableHead>
                    <TableHead className="hidden sm:table-cell">Min Attendance</TableHead>
                    <TableHead className="hidden md:table-cell">Core Passes</TableHead>
                    <TableHead className="hidden md:table-cell">Pass Mark</TableHead>
                    <TableHead>Auto-apply</TableHead>
                    <TableHead>Active</TableHead>
                    <TableHead className="w-[80px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rules.map((rule) => (
                    <TableRow key={rule.id}>
                      <TableCell className="font-medium">
                        {rule.academic_year_name || "—"}
                      </TableCell>
                      <TableCell>
                        {rule.class_name || (
                          <Badge variant="secondary" className="text-xs">
                            School-wide
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {rule.min_average != null ? `${rule.min_average}%` : "—"}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {rule.min_attendance_percent != null ? `${rule.min_attendance_percent}%` : "—"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {rule.core_passes_required ?? "—"}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {rule.pass_mark != null ? `${rule.pass_mark}%` : "—"}
                      </TableCell>
                      <TableCell>
                        {rule.auto_apply ? (
                          <Check className="h-4 w-4 text-green-600" />
                        ) : (
                          <X className="h-4 w-4 text-muted-foreground" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={rule.is_active ? "default" : "secondary"}
                          className={`text-xs ${rule.is_active ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-0" : ""}`}
                        >
                          {rule.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openEdit(rule)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() => setDeleteTarget(rule)}
                          >
                            <Trash2 className="h-4 w-4" />
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
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setEditingRule(null);
            form.reset();
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editingRule ? "Edit Promotion Rule" : "Create Promotion Rule"}
            </DialogTitle>
            <DialogDescription>
              Define the criteria students must meet to be promoted. At least one criterion is required.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Academic Year</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select academic year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((ay) => (
                          <SelectItem key={ay.id} value={ay.id}>
                            {ay.name} {ay.is_current ? "(Current)" : ""}
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
                name="class_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Class (optional)
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Info className="inline h-3 w-3 ml-1 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="max-w-[200px] text-xs">
                              Leave empty to apply school-wide. Select a class for class-specific criteria.
                            </p>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </FormLabel>
                    <Select onValueChange={field.onChange} value={field.value || ""}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="School-wide (all classes)" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="school_wide">School-wide (all classes)</SelectItem>
                        {classes.map((cls) => (
                          <SelectItem key={cls.id} value={cls.id}>
                            {cls.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="min_average"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Min Average (%)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step={0.1}
                          placeholder="e.g. 50"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="min_attendance_percent"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Min Attendance (%)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step={0.1}
                          placeholder="e.g. 75"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="core_passes_required"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Core Passes Required</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="e.g. 4"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="pass_mark"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Pass Mark (%)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={100}
                          step={0.1}
                          placeholder="e.g. 40"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="space-y-4 pt-2">
                <FormField
                  control={form.control}
                  name="auto_apply"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel>Auto-apply</FormLabel>
                        <FormDescription className="text-xs">
                          Automatically apply this rule during promotions
                        </FormDescription>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="is_active"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel>Active</FormLabel>
                        <FormDescription className="text-xs">
                          Only active rules are evaluated during promotions
                        </FormDescription>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editingRule ? "Updating..." : "Creating..."}
                    </>
                  ) : editingRule ? (
                    "Update Rule"
                  ) : (
                    "Create Rule"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Promotion Rule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this promotion rule for{" "}
              <strong>{deleteTarget?.academic_year_name}</strong>
              {deleteTarget?.class_name && (
                <> ({deleteTarget.class_name})</>
              )}
              ? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
