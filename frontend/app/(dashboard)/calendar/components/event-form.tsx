"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CalendarPlus, Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import {
  createSchoolHoliday,
  updateSchoolHoliday,
  deleteSchoolHoliday,
} from "@/actions/timetable.action";
import type { SchoolHoliday, HolidayType, AcademicYear } from "@/types";

interface EventFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  event?: SchoolHoliday | null;
  defaultDate?: Date | null;
  academicYears: AcademicYear[];
  selectedAcademicYearId?: string;
  onSuccess: () => void;
}

const HOLIDAY_TYPES: { value: HolidayType; label: string }[] = [
  { value: "holiday", label: "Public Holiday" },
  { value: "vacation", label: "Vacation" },
  { value: "exam", label: "Exam Period" },
  { value: "event", label: "School Event" },
];

const eventFormSchema = z
  .object({
    name: z.string().min(1, "Event name is required").max(255, "Event name is too long"),
    date: z.string().min(1, "Date is required"),
    endDate: z.string().optional(),
    holiday_type: z.enum(["holiday", "vacation", "exam", "event"] as const),
    description: z.string().max(500, "Description must be 500 characters or fewer").optional(),
    academic_year_id: z.string().optional(),
    is_recurring: z.boolean(),
    isMultiDay: z.boolean(),
  })
  .refine(
    (data) => {
      if (data.isMultiDay && data.endDate) {
        return new Date(data.endDate) >= new Date(data.date);
      }
      return true;
    },
    {
      message: "End date must be on or after the start date",
      path: ["endDate"],
    }
  )
  .refine(
    (data) => {
      if (data.isMultiDay) {
        return !!data.endDate;
      }
      return true;
    },
    {
      message: "End date is required for multi-day events",
      path: ["endDate"],
    }
  );

type EventFormValues = z.infer<typeof eventFormSchema>;

function formatDateForInput(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toISOString().split("T")[0];
}

export function EventForm({
  open,
  onOpenChange,
  event,
  defaultDate,
  academicYears,
  selectedAcademicYearId,
  onSuccess,
}: EventFormProps) {
  const isEditing = !!event;
  const [isDeleting, setIsDeleting] = useState(false);

  const form = useForm<EventFormValues>({
    resolver: zodResolver(eventFormSchema),
    defaultValues: {
      name: "",
      date: "",
      endDate: "",
      holiday_type: "event",
      description: "",
      academic_year_id: "",
      is_recurring: false,
      isMultiDay: false,
    },
  });

  // Reset form when dialog opens/closes or event changes
  useEffect(() => {
    if (open) {
      if (event) {
        form.reset({
          name: event.name,
          date: event.date,
          endDate: "",
          holiday_type: event.holiday_type,
          description: event.description || "",
          academic_year_id: event.academic_year_id || "",
          is_recurring: event.is_recurring,
          isMultiDay: false,
        });
      } else {
        form.reset({
          name: "",
          date: defaultDate ? formatDateForInput(defaultDate) : "",
          endDate: "",
          holiday_type: "event",
          description: "",
          academic_year_id: selectedAcademicYearId || "",
          is_recurring: false,
          isMultiDay: false,
        });
      }
    }
  }, [open, event, defaultDate, selectedAcademicYearId, form]);

  const isMultiDay = form.watch("isMultiDay");

  async function onSubmit(values: EventFormValues) {
    try {
      if (values.isMultiDay && values.endDate) {
        const startDate = new Date(values.date);
        const endDate = new Date(values.endDate);

        const current = new Date(startDate);
        let successCount = 0;
        let errorCount = 0;

        while (current <= endDate) {
          const result = await createSchoolHoliday({
            name: values.name,
            date: formatDateForInput(current),
            holiday_type: values.holiday_type,
            description: values.description || undefined,
            academic_year_id: values.academic_year_id || undefined,
            is_recurring: values.is_recurring,
          });

          if (result.success) {
            successCount++;
          } else {
            errorCount++;
          }

          current.setDate(current.getDate() + 1);
        }

        if (successCount > 0) {
          toast.success(`Created ${successCount} event(s)`);
          if (errorCount > 0) {
            toast.warning(`${errorCount} event(s) failed (may already exist)`);
          }
          onSuccess();
          onOpenChange(false);
        } else {
          toast.error("Failed to create events");
        }
      } else {
        if (isEditing && event) {
          const result = await updateSchoolHoliday(event.id, {
            name: values.name,
            date: values.date,
            holiday_type: values.holiday_type,
            description: values.description || undefined,
            academic_year_id: values.academic_year_id || undefined,
            is_recurring: values.is_recurring,
          });

          if (result.success) {
            toast.success("Event updated successfully");
            onSuccess();
            onOpenChange(false);
          } else {
            toast.error(result.error || "Failed to update event");
          }
        } else {
          const result = await createSchoolHoliday({
            name: values.name,
            date: values.date,
            holiday_type: values.holiday_type,
            description: values.description || undefined,
            academic_year_id: values.academic_year_id || undefined,
            is_recurring: values.is_recurring,
          });

          if (result.success) {
            toast.success("Event created successfully");
            onSuccess();
            onOpenChange(false);
          } else {
            toast.error(result.error || "Failed to create event");
          }
        }
      }
    } catch {
      toast.error("An unexpected error occurred");
    }
  }

  async function handleDelete() {
    if (!event) return;

    setIsDeleting(true);

    try {
      const result = await deleteSchoolHoliday(event.id);

      if (result.success) {
        toast.success("Event deleted successfully");
        onSuccess();
        onOpenChange(false);
      } else {
        toast.error(result.error || "Failed to delete event");
      }
    } catch {
      toast.error("An unexpected error occurred");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarPlus className="h-5 w-5" />
            {isEditing ? "Edit Event" : "Add Event"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the event details below."
              : "Create a new calendar event."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Event Name */}
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Name</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g., Independence Day"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Event Type */}
            <FormField
              control={form.control}
              name="holiday_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Event Type</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {HOLIDAY_TYPES.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Date */}
            <FormField
              control={form.control}
              name="date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {isMultiDay ? "Start Date" : "Date"}
                  </FormLabel>
                  <FormControl>
                    <Input type="date" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Multi-day toggle (only for new events) */}
            {!isEditing && (
              <FormField
                control={form.control}
                name="isMultiDay"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel className="cursor-pointer">
                        Multi-day event
                      </FormLabel>
                      <FormDescription>
                        Creates separate entries for each day in the range (e.g., vacation period)
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />
            )}

            {/* End Date (for multi-day events) */}
            {isMultiDay && (
              <FormField
                control={form.control}
                name="endDate"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>End Date</FormLabel>
                    <FormControl>
                      <Input
                        type="date"
                        min={form.getValues("date")}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            {/* Academic Year */}
            <FormField
              control={form.control}
              name="academic_year_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Academic Year</FormLabel>
                  <Select
                    onValueChange={(value) =>
                      field.onChange(value === "none" ? "" : value)
                    }
                    value={field.value || "none"}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select academic year" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="none">All Years</SelectItem>
                      {academicYears.map((year) => (
                        <SelectItem key={year.id} value={year.id}>
                          {year.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Leave as "All Years" for recurring national holidays
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Description */}
            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Optional description..."
                      rows={2}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Recurring */}
            <FormField
              control={form.control}
              name="is_recurring"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel className="cursor-pointer">
                      Recurring annually
                    </FormLabel>
                    <FormDescription>
                      This event occurs on the same date every year
                    </FormDescription>
                  </div>
                </FormItem>
              )}
            />

            <DialogFooter className="gap-2 sm:gap-0">
              {isEditing && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={form.formState.isSubmitting || isDeleting}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete event</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to delete &ldquo;{event?.name}&rdquo;? This
                        action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={isDeleting}>
                        Cancel
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        {isDeleting && (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        )}
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
              <div className="flex-1" />
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={form.formState.isSubmitting || isDeleting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={form.formState.isSubmitting || isDeleting}
              >
                {form.formState.isSubmitting && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                {isEditing ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
