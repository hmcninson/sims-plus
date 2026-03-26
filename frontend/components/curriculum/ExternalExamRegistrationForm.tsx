"use client";

import { useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus, Trash2, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";

import {
  createExternalExamRegistration,
  updateExternalExamRegistration,
} from "@/actions/curriculum.action";
import type {
  ExternalExamBoard,
  ExternalExamRegistration,
  ExternalExamRegistrationCreate,
} from "@/types/curriculum.type";

const EXAM_BOARDS: { value: ExternalExamBoard; label: string }[] = [
  { value: "waec", label: "WAEC" },
  { value: "cambridge_international", label: "Cambridge International" },
  { value: "edexcel", label: "Edexcel" },
  { value: "college_board", label: "College Board" },
  { value: "ibo", label: "IBO" },
];

const LEVEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  cambridge_international: [
    { value: "Core", label: "Core" },
    { value: "Extended", label: "Extended" },
  ],
  ibo: [
    { value: "SL", label: "Standard Level (SL)" },
    { value: "HL", label: "Higher Level (HL)" },
  ],
  edexcel: [
    { value: "Foundation", label: "Foundation" },
    { value: "Higher", label: "Higher" },
  ],
};

const subjectSchema = z.object({
  subject_code: z.string().min(1, "Subject code is required"),
  subject_name: z.string().min(1, "Subject name is required"),
  level: z.string().optional(),
  paper_numbers: z.array(z.string()).optional(),
});

const formSchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  exam_board: z.enum(
    ["waec", "cambridge_international", "edexcel", "college_board", "ibo"],
    { message: "Exam board is required" },
  ),
  exam_session: z
    .string()
    .min(1, "Exam session is required")
    .max(20, "Maximum 20 characters"),
  candidate_number: z.string().optional(),
  center_number: z.string().optional(),
  registration_date: z.string().optional(),
  subjects: z.array(subjectSchema).min(1, "At least one subject is required"),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

interface ExternalExamRegistrationFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingRegistration?: ExternalExamRegistration;
  students: { id: string; name: string; student_number?: string }[];
  onSuccess: () => void;
}

export function ExternalExamRegistrationForm({
  open,
  onOpenChange,
  editingRegistration,
  students,
  onSuccess,
}: ExternalExamRegistrationFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isEditing = !!editingRegistration;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: editingRegistration
      ? {
          student_id: editingRegistration.student_id,
          exam_board: editingRegistration.exam_board as FormValues["exam_board"],
          exam_session: editingRegistration.exam_session,
          candidate_number: editingRegistration.candidate_number ?? "",
          center_number: editingRegistration.center_number ?? "",
          registration_date: editingRegistration.registration_date ?? "",
          subjects: editingRegistration.subjects,
          notes: editingRegistration.notes ?? "",
        }
      : {
          student_id: "",
          exam_board: undefined,
          exam_session: "",
          candidate_number: "",
          center_number: "",
          registration_date: "",
          subjects: [{ subject_code: "", subject_name: "", level: "", paper_numbers: [] }],
          notes: "",
        },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "subjects",
  });

  const selectedBoard = form.watch("exam_board");
  const levelOptions = selectedBoard ? LEVEL_OPTIONS[selectedBoard] : undefined;

  async function onSubmit(values: FormValues) {
    setIsSubmitting(true);
    try {
      if (isEditing && editingRegistration) {
        const result = await updateExternalExamRegistration(editingRegistration.id, {
          candidate_number: values.candidate_number,
          center_number: values.center_number,
          subjects: values.subjects,
          registration_date: values.registration_date,
          notes: values.notes,
        });
        if (result.success) {
          toast.success("Registration updated successfully");
          onOpenChange(false);
          onSuccess();
        } else {
          toast.error(result.error);
        }
      } else {
        const createData: ExternalExamRegistrationCreate = {
          student_id: values.student_id,
          exam_board: values.exam_board,
          exam_session: values.exam_session,
          candidate_number: values.candidate_number || undefined,
          center_number: values.center_number || undefined,
          subjects: values.subjects,
          registration_date: values.registration_date || undefined,
          notes: values.notes || undefined,
        };
        const result = await createExternalExamRegistration(createData);
        if (result.success) {
          toast.success("Student registered for external exam");
          form.reset();
          onOpenChange(false);
          onSuccess();
        } else {
          toast.error(result.error);
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Edit Registration" : "Register for External Exam"}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the external exam registration details."
              : "Register a student for an external examination."}
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="student_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Student</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      disabled={isEditing}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select student" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {students.map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.name}
                            {s.student_number ? ` (${s.student_number})` : ""}
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
                name="exam_board"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exam Board</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      disabled={isEditing}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select exam board" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {EXAM_BOARDS.map((b) => (
                          <SelectItem key={b.value} value={b.value}>
                            {b.label}
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
                name="exam_session"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Exam Session</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., May 2026" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="registration_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Registration Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="candidate_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Candidate Number</FormLabel>
                    <FormControl>
                      <Input placeholder="Assigned by exam board" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="center_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Center Number</FormLabel>
                    <FormControl>
                      <Input placeholder="School's exam center number" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Subjects Array */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <FormLabel className="text-sm font-medium">Subjects</FormLabel>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    append({ subject_code: "", subject_name: "", level: "", paper_numbers: [] })
                  }
                >
                  <Plus className="mr-1 size-4" />
                  Add Subject
                </Button>
              </div>

              {fields.map((field, index) => (
                <Card key={field.id}>
                  <CardContent className="pt-4 pb-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 items-end">
                      <FormField
                        control={form.control}
                        name={`subjects.${index}.subject_code`}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Code</FormLabel>
                            <FormControl>
                              <Input placeholder="e.g., 0580" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`subjects.${index}.subject_name`}
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel className="text-xs">Name</FormLabel>
                            <FormControl>
                              <Input placeholder="e.g., Mathematics" {...field} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      {levelOptions && (
                        <FormField
                          control={form.control}
                          name={`subjects.${index}.level`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-xs">Level</FormLabel>
                              <Select
                                onValueChange={field.onChange}
                                defaultValue={field.value}
                              >
                                <FormControl>
                                  <SelectTrigger className="w-full">
                                    <SelectValue placeholder="Level" />
                                  </SelectTrigger>
                                </FormControl>
                                <SelectContent>
                                  {levelOptions.map((l) => (
                                    <SelectItem key={l.value} value={l.value}>
                                      {l.label}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      )}
                      <div className="flex justify-end">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => remove(index)}
                          disabled={fields.length <= 1}
                        >
                          <Trash2 className="size-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {form.formState.errors.subjects?.message && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.subjects.message}
                </p>
              )}
            </div>

            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Any additional notes..."
                      className="resize-none"
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
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                {isEditing ? "Update Registration" : "Register Student"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
