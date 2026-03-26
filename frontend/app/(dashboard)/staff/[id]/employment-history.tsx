"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Briefcase,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  FileText,
  Building2,
  UserCog,
  DollarSign,
  RefreshCw,
  Plus,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import {
  getStaffEmploymentHistory,
  createStaffEmploymentEvent,
} from "@/actions/staff.action";
import type { StaffEmploymentHistory, EmploymentEventType } from "@/types";

const EVENT_TYPES: { value: EmploymentEventType; label: string }[] = [
  { value: "hired", label: "Hired" },
  { value: "promoted", label: "Promoted" },
  { value: "demoted", label: "Demoted" },
  { value: "transferred", label: "Transferred" },
  { value: "title_changed", label: "Title Changed" },
  { value: "department_changed", label: "Department Changed" },
  { value: "status_changed", label: "Status Changed" },
  { value: "salary_changed", label: "Salary Changed" },
  { value: "contract_renewed", label: "Contract Renewed" },
];

type EventIconType = typeof Briefcase;

const EVENT_ICON_MAP: Record<EmploymentEventType, { icon: EventIconType; color: string }> = {
  hired: { icon: Briefcase, color: "bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400" },
  promoted: { icon: ArrowUp, color: "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400" },
  demoted: { icon: ArrowDown, color: "bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" },
  transferred: { icon: ArrowRight, color: "bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400" },
  title_changed: { icon: FileText, color: "bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400" },
  department_changed: { icon: Building2, color: "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400" },
  status_changed: { icon: UserCog, color: "bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400" },
  salary_changed: { icon: DollarSign, color: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400" },
  contract_renewed: { icon: RefreshCw, color: "bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400" },
};

const eventFormSchema = z.object({
  event_type: z.string().min(1, "Event type is required"),
  effective_date: z.string().min(1, "Date is required"),
  previous_value: z.string().optional(),
  new_value: z.string().optional(),
  notes: z.string().max(500, "Notes too long").optional(),
});

type EventFormValues = z.infer<typeof eventFormSchema>;

function getEventTypeLabel(type: string): string {
  const found = EVENT_TYPES.find((et) => et.value === type);
  return found ? found.label : type.replace(/_/g, " ");
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function buildEventDescription(event: StaffEmploymentHistory): string {
  const parts: string[] = [];

  switch (event.event_type) {
    case "hired":
      parts.push("Joined the organization");
      if (event.new_value) parts.push(`as ${event.new_value}`);
      break;
    case "promoted":
      if (event.previous_value && event.new_value) {
        parts.push(`Promoted from ${event.previous_value} to ${event.new_value}`);
      } else if (event.new_value) {
        parts.push(`Promoted to ${event.new_value}`);
      } else {
        parts.push("Received a promotion");
      }
      break;
    case "demoted":
      if (event.previous_value && event.new_value) {
        parts.push(`Moved from ${event.previous_value} to ${event.new_value}`);
      } else {
        parts.push("Position change");
      }
      break;
    case "transferred":
      if (event.previous_value && event.new_value) {
        parts.push(`Transferred from ${event.previous_value} to ${event.new_value}`);
      } else {
        parts.push("Transferred to a new department/school");
      }
      break;
    case "title_changed":
      if (event.previous_job_title && event.new_job_title) {
        parts.push(`Title changed from ${event.previous_job_title} to ${event.new_job_title}`);
      } else if (event.previous_value && event.new_value) {
        parts.push(`Title changed from ${event.previous_value} to ${event.new_value}`);
      } else {
        parts.push("Job title updated");
      }
      break;
    case "department_changed":
      if (event.previous_value && event.new_value) {
        parts.push(`Department changed from ${event.previous_value} to ${event.new_value}`);
      } else {
        parts.push("Department change");
      }
      break;
    case "status_changed":
      if (event.previous_value && event.new_value) {
        parts.push(`Status changed from ${event.previous_value} to ${event.new_value}`);
      } else {
        parts.push("Employment status updated");
      }
      break;
    case "salary_changed":
      parts.push("Salary adjustment");
      break;
    case "contract_renewed":
      parts.push("Contract renewed");
      if (event.new_value) parts.push(`until ${event.new_value}`);
      break;
    default:
      parts.push(getEventTypeLabel(event.event_type));
  }

  return parts.join(" ");
}

interface EmploymentHistoryProps {
  staffId: string;
}

export function EmploymentHistory({ staffId }: EmploymentHistoryProps) {
  const [history, setHistory] = useState<StaffEmploymentHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);

  const form = useForm<EventFormValues>({
    resolver: zodResolver(eventFormSchema),
    defaultValues: {
      event_type: "",
      effective_date: "",
      previous_value: "",
      new_value: "",
      notes: "",
    },
  });

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    const result = await getStaffEmploymentHistory(staffId);
    if (result.success && result.data) {
      setHistory(result.data);
    } else {
      toast.error(result.error || "Failed to load employment history");
    }
    setLoading(false);
  }, [staffId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleSubmit = async (values: EventFormValues) => {
    const result = await createStaffEmploymentEvent(staffId, {
      event_type: values.event_type as EmploymentEventType,
      effective_date: values.effective_date,
      previous_value: values.previous_value || undefined,
      new_value: values.new_value || undefined,
      notes: values.notes || undefined,
    });

    if (result.success) {
      toast.success("Employment event recorded");
      setDialogOpen(false);
      form.reset();
      fetchHistory();
    } else {
      toast.error(result.error || "Failed to record event");
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <CardTitle className="text-base flex items-center gap-2">
            <Briefcase className="h-4 w-4" />
            Employment History
          </CardTitle>
          <CardDescription>
            {history.length} event{history.length !== 1 ? "s" : ""} recorded
          </CardDescription>
        </div>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Event
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-10 w-10 rounded-full shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-12">
            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <Briefcase className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="font-semibold mb-1">No History</h3>
            <p className="text-muted-foreground mb-4">
              No employment events have been recorded yet.
            </p>
            <Button variant="outline" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Record Event
            </Button>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />

            <div className="space-y-6">
              {history.map((event, index) => {
                const iconConfig = EVENT_ICON_MAP[event.event_type] || EVENT_ICON_MAP.hired;
                const EventIcon = iconConfig.icon;
                const description = buildEventDescription(event);

                return (
                  <div key={event.id} className="relative flex gap-4 pl-0">
                    {/* Icon */}
                    <div className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${iconConfig.color}`}>
                      <EventIcon className="h-4 w-4" />
                    </div>

                    {/* Content */}
                    <div className={`flex-1 min-w-0 pb-2 ${index < history.length - 1 ? "" : ""}`}>
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                        <p className="font-medium text-sm">{getEventTypeLabel(event.event_type)}</p>
                        <time className="text-xs text-muted-foreground">
                          {formatDate(event.effective_date)}
                        </time>
                      </div>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {description}
                      </p>
                      {event.notes && (
                        <p className="text-xs text-muted-foreground mt-1 italic">
                          {event.notes}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>

      {/* Add Event Dialog */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) form.reset();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Record Employment Event</DialogTitle>
            <DialogDescription>
              Add a new event to this staff member&apos;s employment history.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="event_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Event Type *</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select event type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {EVENT_TYPES.map((et) => (
                            <SelectItem key={et.value} value={et.value}>
                              {et.label}
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

              <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="previous_value"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Previous Value</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Previous title, department" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="new_value"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New Value</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. New title, department" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Additional context about this event..."
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
                  onClick={() => setDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Event"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
