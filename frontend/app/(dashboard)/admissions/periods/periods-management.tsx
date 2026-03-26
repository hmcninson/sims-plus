"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Plus,
  MoreHorizontal,
  Loader2,
  Calendar,
  Eye,
} from "lucide-react";
import {
  getAdmissionPeriods,
  createAdmissionPeriod,
  changeAdmissionPeriodStatus,
} from "@/actions/admissions.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import type {
  AdmissionPeriod,
  AdmissionPeriodStatus,
} from "@/types/admissions.type";
import type { AcademicYear, Class } from "@/types";

const periodSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  academic_year_id: z.string().min(1, "Academic year is required"),
  start_date: z.string().min(1, "Start date is required"),
  end_date: z.string().min(1, "End date is required"),
  application_fee_amount: z.coerce.number().min(0).optional(),
  application_fee_required: z.boolean().optional(),
  entrance_exam_required: z.boolean().optional(),
  require_applicant_account: z.boolean().default(false),
  max_applications: z.coerce.number().min(0).optional(),
  target_classes: z.array(z.string()).optional(),
});

type PeriodFormValues = z.infer<typeof periodSchema>;

const STATUS_CONFIG: Record<
  AdmissionPeriodStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  open: {
    label: "Open",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  closed: {
    label: "Closed",
    className:
      "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
  archived: {
    label: "Archived",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  },
};

const VALID_TRANSITIONS: Record<AdmissionPeriodStatus, AdmissionPeriodStatus[]> =
  {
    draft: ["open"],
    open: ["closed"],
    closed: ["archived", "open"],
    archived: [],
  };

export function PeriodsManagement() {
  const router = useRouter();
  const [periods, setPeriods] = useState<AdmissionPeriod[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [isPending, startTransition] = useTransition();

  const form = useForm<PeriodFormValues>({
    resolver: zodResolver(periodSchema) as Resolver<PeriodFormValues>,
    defaultValues: {
      name: "",
      description: "",
      academic_year_id: "",
      start_date: "",
      end_date: "",
      application_fee_amount: 0,
      application_fee_required: false,
      entrance_exam_required: false,
      require_applicant_account: false,
      max_applications: undefined,
      target_classes: [],
    },
  });

  const loadData = useCallback(async () => {
    const [periodsResult, yearsResult, classesResult] = await Promise.all([
      getAdmissionPeriods({ page_size: 50 }),
      getAcademicYears(),
      getClasses(),
    ]);

    if (periodsResult.success && periodsResult.data) {
      setPeriods(periodsResult.data.items);
    }
    if (yearsResult.success && yearsResult.data) {
      setAcademicYears(yearsResult.data);
    }
    if (classesResult.success && classesResult.data) {
      setClasses(classesResult.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function onSubmit(values: PeriodFormValues) {
    const result = await createAdmissionPeriod({
      name: values.name,
      description: values.description || undefined,
      academic_year_id: values.academic_year_id,
      start_date: values.start_date,
      end_date: values.end_date,
      application_fee_amount: values.application_fee_amount || undefined,
      application_fee_required: values.application_fee_required,
      entrance_exam_required: values.entrance_exam_required,
      require_applicant_account: values.require_applicant_account,
      max_applications: values.max_applications || undefined,
      target_classes: values.target_classes,
    });

    if (result.success) {
      toast.success("Admission period created");
      setShowCreateDialog(false);
      form.reset();
      loadData();
    } else {
      toast.error(result.error);
    }
  }

  async function handleStatusChange(
    periodId: string,
    newStatus: AdmissionPeriodStatus
  ) {
    startTransition(async () => {
      const result = await changeAdmissionPeriodStatus(periodId, newStatus);
      if (result.success) {
        toast.success(`Period status changed to ${newStatus}`);
        loadData();
      } else {
        toast.error(result.error);
      }
    });
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Admission Periods</h1>
          <p className="text-sm text-muted-foreground">
            Manage admission windows and application periods
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Period
        </Button>
      </div>

      {/* Periods Table */}
      <Card>
        <CardContent className="p-0">
          {periods.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Calendar className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No admission periods yet</p>
              <p className="text-sm text-muted-foreground">
                Create your first admission period to start accepting
                applications
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowCreateDialog(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                Create Period
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Dates
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Applications
                    </TableHead>
                    <TableHead className="w-[60px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {periods.map((period) => {
                    const statusConfig = STATUS_CONFIG[period.status];
                    const transitions = VALID_TRANSITIONS[period.status];

                    return (
                      <TableRow
                        key={period.id}
                        className="cursor-pointer"
                        onClick={() =>
                          router.push(`/admissions/periods/${period.id}`)
                        }
                      >
                        <TableCell>
                          <div>
                            <p className="font-medium">{period.name}</p>
                            {period.description && (
                              <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                                {period.description}
                              </p>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                          {formatDate(period.start_date)} -{" "}
                          {formatDate(period.end_date)}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusConfig.className}
                          >
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          {period.application_count ?? 0}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              asChild
                              onClick={(e) => e.stopPropagation()}
                            >
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={(e) => {
                                  e.stopPropagation();
                                  router.push(
                                    `/admissions/periods/${period.id}`
                                  );
                                }}
                              >
                                <Eye className="mr-2 h-4 w-4" />
                                View Details
                              </DropdownMenuItem>
                              {transitions.map((status) => (
                                <DropdownMenuItem
                                  key={status}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleStatusChange(period.id, status);
                                  }}
                                  disabled={isPending}
                                >
                                  Change to {STATUS_CONFIG[status].label}
                                </DropdownMenuItem>
                              ))}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Period Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Admission Period</DialogTitle>
            <DialogDescription>
              Define a new admission window for accepting applications.
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Period Name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., 2026/2027 Admissions"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Academic Year</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select academic year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name}
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
                    <FormLabel>Description (Optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Brief description of this admission period"
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
                  name="start_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Start Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="end_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>End Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="application_fee_amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Application Fee (GHS)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          step={0.01}
                          placeholder="0.00"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="max_applications"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Applications (Optional)</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="Unlimited"
                          {...field}
                          value={field.value ?? ""}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="flex flex-col gap-3">
                <FormField
                  control={form.control}
                  name="application_fee_required"
                  render={({ field }) => (
                    <FormItem className="flex items-center space-x-2 space-y-0">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormLabel className="font-normal cursor-pointer">
                        Application fee required
                      </FormLabel>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="entrance_exam_required"
                  render={({ field }) => (
                    <FormItem className="flex items-center space-x-2 space-y-0">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormLabel className="font-normal cursor-pointer">
                        Entrance exam required
                      </FormLabel>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="require_applicant_account"
                  render={({ field }) => (
                    <FormItem className="flex items-center space-x-2 space-y-0">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormLabel className="font-normal cursor-pointer">
                        Require applicant account before submitting
                      </FormLabel>
                    </FormItem>
                  )}
                />
              </div>

              {/* Target Classes */}
              <FormField
                control={form.control}
                name="target_classes"
                render={() => (
                  <FormItem>
                    <FormLabel>Target Classes (Optional)</FormLabel>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-md border p-3 max-h-[200px] overflow-y-auto">
                      {classes.map((cls) => (
                        <FormField
                          key={cls.id}
                          control={form.control}
                          name="target_classes"
                          render={({ field }) => (
                            <FormItem className="flex items-center space-x-2 space-y-0">
                              <FormControl>
                                <Checkbox
                                  checked={field.value?.includes(cls.id)}
                                  onCheckedChange={(checked) => {
                                    const current = field.value || [];
                                    if (checked) {
                                      field.onChange([...current, cls.id]);
                                    } else {
                                      field.onChange(
                                        current.filter(
                                          (v: string) => v !== cls.id
                                        )
                                      );
                                    }
                                  }}
                                />
                              </FormControl>
                              <FormLabel className="text-sm font-normal cursor-pointer">
                                {cls.name}
                              </FormLabel>
                            </FormItem>
                          )}
                        />
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Create Period
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
