"use client";

import { useState, useEffect } from "react";
import { CalendarPlus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

  const [formData, setFormData] = useState({
    name: "",
    date: "",
    endDate: "",
    holiday_type: "event" as HolidayType,
    description: "",
    academic_year_id: "",
    is_recurring: false,
    isMultiDay: false,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Reset form when dialog opens/closes or event changes
  useEffect(() => {
    if (open) {
      if (event) {
        setFormData({
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
        setFormData({
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
  }, [open, event, defaultDate, selectedAcademicYearId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error("Please enter an event name");
      return;
    }

    if (!formData.date) {
      toast.error("Please select a date");
      return;
    }

    setIsSubmitting(true);

    try {
      // If multi-day, create events for each day in the range
      if (formData.isMultiDay && formData.endDate) {
        const startDate = new Date(formData.date);
        const endDate = new Date(formData.endDate);

        if (endDate < startDate) {
          toast.error("End date must be after start date");
          setIsSubmitting(false);
          return;
        }

        // Create events for each day in the range
        const current = new Date(startDate);
        let successCount = 0;
        let errorCount = 0;

        while (current <= endDate) {
          const result = await createSchoolHoliday({
            name: formData.name,
            date: formatDateForInput(current),
            holiday_type: formData.holiday_type,
            description: formData.description || undefined,
            academic_year_id: formData.academic_year_id || undefined,
            is_recurring: formData.is_recurring,
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
        // Single day event
        if (isEditing && event) {
          const result = await updateSchoolHoliday(event.id, {
            name: formData.name,
            date: formData.date,
            holiday_type: formData.holiday_type,
            description: formData.description || undefined,
            academic_year_id: formData.academic_year_id || undefined,
            is_recurring: formData.is_recurring,
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
            name: formData.name,
            date: formData.date,
            holiday_type: formData.holiday_type,
            description: formData.description || undefined,
            academic_year_id: formData.academic_year_id || undefined,
            is_recurring: formData.is_recurring,
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
      toast.error("An error occurred");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!event) return;

    if (!confirm("Are you sure you want to delete this event?")) {
      return;
    }

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
      toast.error("An error occurred");
    } finally {
      setIsDeleting(false);
    }
  };

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

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Event Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Event Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              placeholder="e.g., Independence Day"
              required
            />
          </div>

          {/* Event Type */}
          <div className="space-y-2">
            <Label htmlFor="type">Event Type</Label>
            <Select
              value={formData.holiday_type}
              onValueChange={(value: HolidayType) =>
                setFormData({ ...formData, holiday_type: value })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HOLIDAY_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date */}
          <div className="space-y-2">
            <Label htmlFor="date">
              {formData.isMultiDay ? "Start Date *" : "Date *"}
            </Label>
            <Input
              id="date"
              type="date"
              value={formData.date}
              onChange={(e) =>
                setFormData({ ...formData, date: e.target.value })
              }
              required
            />
          </div>

          {/* Multi-day toggle (only for new events) */}
          {!isEditing && (
            <div className="flex items-center space-x-2">
              <Checkbox
                id="multiDay"
                checked={formData.isMultiDay}
                onCheckedChange={(checked) =>
                  setFormData({ ...formData, isMultiDay: checked === true })
                }
              />
              <Label htmlFor="multiDay" className="text-sm cursor-pointer">
                Multi-day event (e.g., vacation period)
              </Label>
            </div>
          )}

          {/* End Date (for multi-day events) */}
          {formData.isMultiDay && (
            <div className="space-y-2">
              <Label htmlFor="endDate">End Date *</Label>
              <Input
                id="endDate"
                type="date"
                value={formData.endDate}
                onChange={(e) =>
                  setFormData({ ...formData, endDate: e.target.value })
                }
                min={formData.date}
                required={formData.isMultiDay}
              />
            </div>
          )}

          {/* Academic Year */}
          <div className="space-y-2">
            <Label htmlFor="academicYear">Academic Year</Label>
            <Select
              value={formData.academic_year_id || "none"}
              onValueChange={(value) =>
                setFormData({
                  ...formData,
                  academic_year_id: value === "none" ? "" : value,
                })
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Select academic year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description */}
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Optional description..."
              rows={2}
            />
          </div>

          {/* Recurring */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="recurring"
              checked={formData.is_recurring}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, is_recurring: checked === true })
              }
            />
            <Label htmlFor="recurring" className="text-sm cursor-pointer">
              Recurring annually (same date each year)
            </Label>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            {isEditing && (
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                disabled={isSubmitting || isDeleting}
              >
                {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Delete
              </Button>
            )}
            <div className="flex-1" />
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting || isDeleting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || isDeleting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
