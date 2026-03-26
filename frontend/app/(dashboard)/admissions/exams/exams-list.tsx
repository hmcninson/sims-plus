"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm , type Resolver} from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import {
  Plus,
  Loader2,
  GraduationCap,
  MapPin,
  Users,
  Calendar,
} from "lucide-react";
import {
  getEntranceExams,
  createEntranceExam,
  getAdmissionPeriods,
} from "@/actions/admissions.action";
import type {
  EntranceExam,
  EntranceExamStatus,
} from "@/types/admissions.type";

const examSchema = z.object({
  admission_period_id: z.string().min(1, "Period is required"),
  name: z.string().min(1, "Name is required"),
  exam_date: z.string().min(1, "Date is required"),
  start_time: z.string().optional(),
  end_time: z.string().optional(),
  venue: z.string().min(1, "Venue is required"),
  capacity: z.coerce.number().min(1, "Capacity must be at least 1"),
  instructions: z.string().optional(),
});

type ExamFormValues = z.infer<typeof examSchema>;

const STATUS_CONFIG: Record<
  EntranceExamStatus,
  { label: string; className: string }
> = {
  scheduled: {
    label: "Scheduled",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  in_progress: {
    label: "In Progress",
    className:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  },
  completed: {
    label: "Completed",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  cancelled: {
    label: "Cancelled",
    className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
};

export function ExamsList() {
  const router = useRouter();
  const [exams, setExams] = useState<EntranceExam[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [periods, setPeriods] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [periodFilter, setPeriodFilter] = useState<string>("all");

  const form = useForm<ExamFormValues>({
    resolver: zodResolver(examSchema) as Resolver<ExamFormValues>,
    defaultValues: {
      admission_period_id: "",
      name: "",
      exam_date: "",
      start_time: "",
      end_time: "",
      venue: "",
      capacity: 50,
      instructions: "",
    },
  });

  const loadData = useCallback(async () => {
    const [examsResult, periodsResult] = await Promise.all([
      getEntranceExams({
        page_size: 50,
        status: statusFilter !== "all" ? statusFilter : undefined,
        admission_period_id:
          periodFilter !== "all" ? periodFilter : undefined,
      }),
      getAdmissionPeriods({ page_size: 50 }),
    ]);

    if (examsResult.success && examsResult.data) {
      setExams(examsResult.data.items);
    }
    if (periodsResult.success && periodsResult.data) {
      setPeriods(
        periodsResult.data.items.map((p) => ({ id: p.id, name: p.name }))
      );
    }
    setLoading(false);
  }, [statusFilter, periodFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  async function onSubmit(values: ExamFormValues) {
    const result = await createEntranceExam({
      admission_period_id: values.admission_period_id,
      name: values.name,
      exam_date: values.exam_date,
      start_time: values.start_time || undefined,
      end_time: values.end_time || undefined,
      venue: values.venue,
      capacity: values.capacity,
      instructions: values.instructions || undefined,
    });

    if (result.success) {
      toast.success("Exam session created");
      setShowCreateDialog(false);
      form.reset();
      loadData();
    } else {
      toast.error(result.error);
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  const activeFilterCount =
    (statusFilter !== "all" ? 1 : 0) + (periodFilter !== "all" ? 1 : 0);

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Entrance Exams</h1>
          <p className="text-sm text-muted-foreground">
            Manage entrance exam sessions
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Exam
        </Button>
      </div>

      {/* Filters */}
      <CollapsibleFilters activeFilterCount={activeFilterCount}>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {(Object.keys(STATUS_CONFIG) as EntranceExamStatus[]).map((s) => (
              <SelectItem key={s} value={s}>
                {STATUS_CONFIG[s].label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={periodFilter} onValueChange={setPeriodFilter}>
          <SelectTrigger className="w-full md:w-[200px]">
            <SelectValue placeholder="Period" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Periods</SelectItem>
            {periods.map((p) => (
              <SelectItem key={p.id} value={p.id}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </CollapsibleFilters>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {exams.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <GraduationCap className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No exam sessions</p>
              <p className="text-sm text-muted-foreground">
                Create an entrance exam session to get started
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden md:table-cell">Date</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Venue
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Registered
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {exams.map((exam) => {
                    const statusConfig = STATUS_CONFIG[exam.status];
                    return (
                      <TableRow
                        key={exam.id}
                        className="cursor-pointer"
                        onClick={() =>
                          router.push(`/admissions/exams/${exam.id}`)
                        }
                      >
                        <TableCell>
                          <p className="font-medium">{exam.name}</p>
                          <p className="text-xs text-muted-foreground md:hidden">
                            {formatDate(exam.exam_date)}
                          </p>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                            {formatDate(exam.exam_date)}
                          </div>
                          {exam.start_time && (
                            <span className="text-xs text-muted-foreground">
                              {exam.start_time}
                              {exam.end_time && ` - ${exam.end_time}`}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm">
                          <div className="flex items-center gap-1.5">
                            <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                            {exam.venue}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusConfig.className}
                          >
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm">
                          <div className="flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5 text-muted-foreground" />
                            {exam.registered_count ?? 0} / {exam.capacity}
                          </div>
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

      {/* Create Exam Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create Entrance Exam</DialogTitle>
            <DialogDescription>
              Schedule a new entrance exam session.
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="admission_period_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Admission Period</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select period" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {periods.map((p) => (
                          <SelectItem key={p.id} value={p.id}>
                            {p.name}
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
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exam Name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., Entrance Exam - Batch 1"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="exam_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="start_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Start Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="end_time"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>End Time</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="venue"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Venue</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Main Hall" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="capacity"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Capacity</FormLabel>
                      <FormControl>
                        <Input type="number" min={1} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="instructions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Instructions (Optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Instructions for examinees..."
                        rows={3}
                        {...field}
                      />
                    </FormControl>
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
                  Create Exam
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
