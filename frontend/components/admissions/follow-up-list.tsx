"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  CalendarDays,
  Check,
  Clock,
  AlertTriangle,
  Plus,
  Loader2,
  ClipboardList,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { createFollowUp, completeFollowUp } from "@/actions/inquiries.action";
import type { FollowUp, FollowUpPriority } from "@/types/inquiry.type";

const PRIORITIES: { value: FollowUpPriority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

const PRIORITY_COLORS: Record<FollowUpPriority, string> = {
  low: "bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700",
  medium:
    "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300 dark:border-yellow-800",
  high: "bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800",
};

const followUpSchema = z.object({
  due_date: z.string().min(1, "Due date is required"),
  priority: z.enum(["low", "medium", "high"], { message: "Select priority" }),
  notes: z.string().optional(),
  assigned_to: z.string().min(1, "Assigned staff is required"),
});

type FollowUpFormValues = z.infer<typeof followUpSchema>;

interface FollowUpListProps {
  inquiryId: string;
  followUps: FollowUp[];
  /** List of staff members for assignment dropdown */
  staffMembers: Array<{ id: string; name: string }>;
  onRefresh: () => void;
}

function isOverdue(dueDateStr: string, completedAt: string | null): boolean {
  if (completedAt) return false;
  const due = new Date(dueDateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return due < today;
}

export function FollowUpList({
  inquiryId,
  followUps,
  staffMembers,
  onRefresh,
}: FollowUpListProps) {
  const [showForm, setShowForm] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);

  const form = useForm<FollowUpFormValues>({
    resolver: zodResolver(followUpSchema),
    defaultValues: {
      due_date: "",
      priority: "medium",
      notes: "",
      assigned_to: "",
    },
  });

  async function onSubmit(values: FollowUpFormValues) {
    const result = await createFollowUp(inquiryId, {
      due_date: values.due_date,
      priority: values.priority as FollowUpPriority,
      notes: values.notes || undefined,
      assigned_to: values.assigned_to,
    });
    if (result.success) {
      toast.success("Follow-up created");
      form.reset({ due_date: "", priority: "medium", notes: "", assigned_to: "" });
      setShowForm(false);
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  async function handleComplete(followUpId: string) {
    setCompletingId(followUpId);
    const result = await completeFollowUp(followUpId);
    if (result.success) {
      toast.success("Follow-up completed");
      onRefresh();
    } else {
      toast.error(result.error);
    }
    setCompletingId(null);
  }

  const pending = followUps.filter((f) => !f.completed_at);
  const completed = followUps.filter((f) => f.completed_at);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          {pending.length} pending, {completed.length} completed
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(!showForm)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Follow-up
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">New Follow-up Task</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <FormField
                    control={form.control}
                    name="due_date"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Due Date</FormLabel>
                        <FormControl>
                          <Input type="date" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="priority"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Priority</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {PRIORITIES.map((p) => (
                              <SelectItem key={p.value} value={p.value}>
                                {p.label}
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
                    name="assigned_to"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Assign To</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue placeholder="Select staff" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {staffMembers.map((s) => (
                              <SelectItem key={s.id} value={s.id}>
                                {s.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
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
                      <FormLabel>Notes (Optional)</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Task description..."
                          rows={2}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowForm(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={form.formState.isSubmitting}>
                    {form.formState.isSubmitting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : null}
                    Create
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      )}

      {followUps.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <ClipboardList className="h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            No follow-up tasks yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Create a follow-up to schedule tasks for this inquiry.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Pending follow-ups first */}
          {pending.map((f) => {
            const overdue = isOverdue(f.due_date, f.completed_at);
            return (
              <Card
                key={f.id}
                className={overdue ? "border-red-300 dark:border-red-700" : ""}
              >
                <CardContent className="flex items-start gap-3 py-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="flex items-center gap-1 text-sm">
                        <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className={overdue ? "text-red-600 font-medium dark:text-red-400" : ""}>
                          {new Date(f.due_date).toLocaleDateString("en-GB", {
                            day: "2-digit",
                            month: "short",
                            year: "numeric",
                          })}
                        </span>
                      </div>
                      <Badge
                        variant="outline"
                        className={PRIORITY_COLORS[f.priority as FollowUpPriority] || ""}
                      >
                        {f.priority}
                      </Badge>
                      {overdue && (
                        <Badge variant="outline" className="bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800">
                          <AlertTriangle className="mr-1 h-3 w-3" />
                          Overdue
                        </Badge>
                      )}
                    </div>
                    {f.notes && (
                      <p className="mt-1 text-sm text-muted-foreground">{f.notes}</p>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleComplete(f.id)}
                    disabled={completingId === f.id}
                  >
                    {completingId === f.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}

          {/* Completed follow-ups */}
          {completed.map((f) => (
            <Card key={f.id} className="opacity-60">
              <CardContent className="flex items-start gap-3 py-3">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="flex items-center gap-1 text-sm line-through">
                      <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
                      {new Date(f.due_date).toLocaleDateString("en-GB", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                    </div>
                    <Badge variant="outline" className="bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800">
                      <Check className="mr-1 h-3 w-3" />
                      Completed
                    </Badge>
                  </div>
                  {f.notes && (
                    <p className="mt-1 text-sm text-muted-foreground line-through">{f.notes}</p>
                  )}
                  {f.completed_at && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      Completed{" "}
                      {new Date(f.completed_at).toLocaleDateString("en-GB", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      })}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
