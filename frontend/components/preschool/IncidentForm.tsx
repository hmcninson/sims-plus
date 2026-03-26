"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { Plus, X, Loader2, CalendarIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
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
import { StudentCombobox } from "@/components/preschool/StudentCombobox";
import { cn } from "@/lib/utils";
import type {
  PreschoolIncident,
  PreschoolIncidentCreate,
  PreschoolIncidentUpdate,
  Student,
} from "@/types";

interface IncidentFormProps {
  incident?: PreschoolIncident;
  students: Student[];
  onSubmit: (data: PreschoolIncidentCreate | PreschoolIncidentUpdate) => Promise<void>;
  onCancel: () => void;
  isSaving?: boolean;
}

const INCIDENT_TYPES = [
  { value: "accident", label: "Accident" },
  { value: "illness", label: "Illness" },
  { value: "behavioral", label: "Behavioral" },
  { value: "allergic_reaction", label: "Allergic Reaction" },
  { value: "other", label: "Other" },
] as const;

const SEVERITY_OPTIONS = [
  { value: "minor", label: "Minor", color: "text-green-600" },
  { value: "moderate", label: "Moderate", color: "text-amber-600" },
  { value: "serious", label: "Serious", color: "text-red-600" },
] as const;

const formSchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  incident_type: z.enum(["accident", "illness", "behavioral", "allergic_reaction", "other"], {
    message: "Select incident type",
  }),
  severity: z.enum(["minor", "moderate", "serious"], { message: "Select severity" }),
  incident_date: z.date({ message: "Date is required" }),
  incident_time: z.string().optional(),
  location: z.string().optional(),
  description: z.string().min(10, "Description must be at least 10 characters"),
  action_taken: z.string().optional(),
  first_aid_given: z.boolean(),
  medical_attention_required: z.boolean(),
  witnesses: z.array(z.object({ name: z.string() })),
  follow_up_notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

export function IncidentForm({
  incident,
  students,
  onSubmit,
  onCancel,
  isSaving,
}: IncidentFormProps) {
  const isEditMode = !!incident;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      student_id: incident?.student_id ?? "",
      incident_type: incident?.incident_type ?? undefined,
      severity: incident?.severity ?? undefined,
      incident_date: incident?.incident_date
        ? new Date(incident.incident_date)
        : new Date(),
      incident_time: incident?.incident_time ?? "",
      location: incident?.location ?? "",
      description: incident?.description ?? "",
      action_taken: incident?.action_taken ?? "",
      first_aid_given: incident?.first_aid_given ?? false,
      medical_attention_required: incident?.medical_attention_required ?? false,
      witnesses: incident?.witnesses?.map((w) => ({ name: w })) ?? [],
      follow_up_notes: incident?.follow_up_notes ?? "",
    },
  });

  const {
    fields: witnessFields,
    append: appendWitness,
    remove: removeWitness,
  } = useFieldArray({
    control: form.control,
    name: "witnesses",
  });

  async function handleSubmit(values: FormValues) {
    if (isEditMode) {
      const updateData: PreschoolIncidentUpdate = {
        incident_type: values.incident_type,
        severity: values.severity,
        location: values.location || undefined,
        description: values.description,
        action_taken: values.action_taken || undefined,
        first_aid_given: values.first_aid_given,
        medical_attention_required: values.medical_attention_required,
        witnesses: values.witnesses
          .map((w) => w.name)
          .filter((n) => n.trim() !== ""),
        follow_up_notes: values.follow_up_notes || undefined,
      };
      await onSubmit(updateData);
    } else {
      const createData: PreschoolIncidentCreate = {
        student_id: values.student_id,
        incident_type: values.incident_type,
        severity: values.severity,
        incident_date: format(values.incident_date, "yyyy-MM-dd"),
        incident_time: values.incident_time || undefined,
        location: values.location || undefined,
        description: values.description,
        action_taken: values.action_taken || undefined,
        first_aid_given: values.first_aid_given,
        medical_attention_required: values.medical_attention_required,
        witnesses: values.witnesses
          .map((w) => w.name)
          .filter((n) => n.trim() !== ""),
      };
      await onSubmit(createData);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Student Select */}
          <FormField
            control={form.control}
            name="student_id"
            render={({ field }) => (
              <FormItem className="md:col-span-2">
                <FormLabel>Student</FormLabel>
                <FormControl>
                  <StudentCombobox
                    students={students}
                    value={field.value}
                    onValueChange={field.onChange}
                    placeholder="Select student..."
                    disabled={isEditMode}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Incident Type */}
          <FormField
            control={form.control}
            name="incident_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Incident Type</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select type..." />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {INCIDENT_TYPES.map((type) => (
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

          {/* Severity */}
          <FormField
            control={form.control}
            name="severity"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Severity</FormLabel>
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select severity..." />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {SEVERITY_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        <span className={opt.color}>{opt.label}</span>
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
            name="incident_date"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Date</FormLabel>
                <Popover>
                  <PopoverTrigger asChild>
                    <FormControl>
                      <Button
                        variant="outline"
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !field.value && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {field.value
                          ? format(field.value, "dd/MM/yyyy")
                          : "Select date..."}
                      </Button>
                    </FormControl>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar
                      mode="single"
                      selected={field.value}
                      onSelect={field.onChange}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Time */}
          <FormField
            control={form.control}
            name="incident_time"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Time (optional)</FormLabel>
                <FormControl>
                  <Input type="time" {...field} value={field.value ?? ""} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Location */}
          <FormField
            control={form.control}
            name="location"
            render={({ field }) => (
              <FormItem className="md:col-span-2">
                <FormLabel>Location (optional)</FormLabel>
                <FormControl>
                  <Input
                    placeholder="e.g., Playground, Classroom 2"
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Description */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe what happened..."
                  rows={3}
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Action Taken */}
        <FormField
          control={form.control}
          name="action_taken"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Action Taken (optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="What actions were taken..."
                  rows={2}
                  {...field}
                  value={field.value ?? ""}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Checkboxes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="first_aid_given"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 space-y-0">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormLabel className="font-normal cursor-pointer">
                  First aid was given
                </FormLabel>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="medical_attention_required"
            render={({ field }) => (
              <FormItem className="flex items-center gap-2 space-y-0">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormLabel className="font-normal cursor-pointer">
                  Medical attention required
                </FormLabel>
              </FormItem>
            )}
          />
        </div>

        {/* Witnesses */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <FormLabel>Witnesses (optional)</FormLabel>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => appendWitness({ name: "" })}
            >
              <Plus className="mr-1 h-3 w-3" />
              Add
            </Button>
          </div>
          {witnessFields.map((field, index) => (
            <div key={field.id} className="flex items-center gap-2">
              <FormField
                control={form.control}
                name={`witnesses.${index}.name`}
                render={({ field }) => (
                  <FormItem className="flex-1">
                    <FormControl>
                      <Input placeholder="Witness name" {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => removeWitness(index)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>

        {/* Follow-up Notes (edit only) */}
        {isEditMode && (
          <FormField
            control={form.control}
            name="follow_up_notes"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Follow-up Notes</FormLabel>
                <FormControl>
                  <Textarea
                    placeholder="Add follow-up notes..."
                    rows={2}
                    {...field}
                    value={field.value ?? ""}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditMode ? "Update Incident" : "Report Incident"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
