"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

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
import { DuplicateWarning } from "./duplicate-warning";
import { createInquiry, updateInquiry, checkDuplicate } from "@/actions/inquiries.action";
import { getClasses } from "@/actions/academic.action";
import type { Inquiry, InquirySource } from "@/types/inquiry.type";
import type { Class } from "@/types";

const SOURCES: { value: InquirySource; label: string }[] = [
  { value: "website", label: "Website" },
  { value: "walk_in", label: "Walk-in" },
  { value: "phone", label: "Phone" },
  { value: "referral", label: "Referral" },
  { value: "event", label: "Event" },
  { value: "social_media", label: "Social Media" },
  { value: "other", label: "Other" },
];

const GENDERS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
];

const inquirySchema = z.object({
  source: z.enum(
    ["website", "walk_in", "phone", "referral", "event", "social_media", "other"],
    { message: "Please select a source" }
  ),
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  date_of_birth: z.string().optional(),
  gender: z.string().optional(),
  target_class_id: z.string().optional(),
  guardian_name: z.string().min(1, "Guardian name is required").max(200),
  guardian_phone: z.string().min(1, "Guardian phone is required").max(20),
  guardian_email: z.string().email("Invalid email address").optional().or(z.literal("")),
  referred_by: z.string().max(200).optional(),
  notes: z.string().optional(),
});

type InquiryFormValues = z.infer<typeof inquirySchema>;

interface InquiryFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editingInquiry?: Inquiry | null;
  onSuccess: () => void;
}

export function InquiryForm({
  open,
  onOpenChange,
  editingInquiry,
  onSuccess,
}: InquiryFormProps) {
  const [classes, setClasses] = useState<Class[]>([]);
  const [duplicates, setDuplicates] = useState<Inquiry[]>([]);
  const isEditing = !!editingInquiry;

  const form = useForm<InquiryFormValues>({
    resolver: zodResolver(inquirySchema),
    defaultValues: {
      source: "walk_in",
      first_name: "",
      last_name: "",
      date_of_birth: "",
      gender: "",
      target_class_id: "",
      guardian_name: "",
      guardian_phone: "",
      guardian_email: "",
      referred_by: "",
      notes: "",
    },
  });

  useEffect(() => {
    if (open) {
      loadClasses();
      setDuplicates([]);
      if (editingInquiry) {
        form.reset({
          source: editingInquiry.source,
          first_name: editingInquiry.first_name,
          last_name: editingInquiry.last_name,
          date_of_birth: editingInquiry.date_of_birth || "",
          gender: editingInquiry.gender || "",
          target_class_id: editingInquiry.target_class_id || "",
          guardian_name: editingInquiry.guardian_name,
          guardian_phone: editingInquiry.guardian_phone,
          guardian_email: editingInquiry.guardian_email || "",
          referred_by: editingInquiry.referred_by || "",
          notes: editingInquiry.notes || "",
        });
      } else {
        form.reset({
          source: "walk_in",
          first_name: "",
          last_name: "",
          date_of_birth: "",
          gender: "",
          target_class_id: "",
          guardian_name: "",
          guardian_phone: "",
          guardian_email: "",
          referred_by: "",
          notes: "",
        });
      }
    }
  }, [open, editingInquiry, form]);

  async function loadClasses() {
    const result = await getClasses();
    if (result.success && result.data) {
      setClasses(result.data);
    }
  }

  async function handleDuplicateCheck() {
    const phone = form.getValues("guardian_phone");
    const email = form.getValues("guardian_email");
    if (!phone && !email) return;

    const result = await checkDuplicate({
      guardian_phone: phone || undefined,
      guardian_email: email || undefined,
    });

    if (result.success && result.data?.has_duplicates) {
      setDuplicates(result.data.matches);
    } else {
      setDuplicates([]);
    }
  }

  async function onSubmit(values: InquiryFormValues) {
    const payload = {
      ...values,
      date_of_birth: values.date_of_birth || undefined,
      gender: values.gender || undefined,
      target_class_id: values.target_class_id || undefined,
      guardian_email: values.guardian_email || undefined,
      referred_by: values.referred_by || undefined,
      notes: values.notes || undefined,
    };

    if (isEditing && editingInquiry) {
      const result = await updateInquiry(editingInquiry.id, payload);
      if (result.success) {
        toast.success("Inquiry updated successfully");
        onOpenChange(false);
        onSuccess();
      } else {
        toast.error(result.error);
      }
    } else {
      const result = await createInquiry(payload);
      if (result.success) {
        toast.success("Inquiry created successfully");
        onOpenChange(false);
        onSuccess();
      } else {
        toast.error(result.error);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Inquiry" : "New Inquiry"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update the inquiry details below."
              : "Record a new inquiry from a prospective family."}
          </DialogDescription>
        </DialogHeader>

        {duplicates.length > 0 && <DuplicateWarning matches={duplicates} />}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Source */}
            <FormField
              control={form.control}
              name="source"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Source</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select source" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {SOURCES.map((s) => (
                        <SelectItem key={s.value} value={s.value}>
                          {s.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Student Name */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="first_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>First Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Student first name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="last_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Last Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Student last name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* DOB, Gender, Target Class */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField
                control={form.control}
                name="date_of_birth"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Date of Birth</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="gender"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Gender</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select gender" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {GENDERS.map((g) => (
                          <SelectItem key={g.value} value={g.value}>
                            {g.label}
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
                name="target_class_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Target Class</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select class" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {classes.map((c) => (
                          <SelectItem key={c.id} value={c.id}>
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Guardian Info */}
            <div className="space-y-2">
              <h4 className="text-sm font-medium text-muted-foreground">Guardian Information</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="guardian_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Guardian Name</FormLabel>
                      <FormControl>
                        <Input placeholder="Full name" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="guardian_phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Guardian Phone</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="+233 XX XXX XXXX"
                          {...field}
                          onBlur={() => {
                            field.onBlur();
                            if (!isEditing) handleDuplicateCheck();
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="guardian_email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Guardian Email (Optional)</FormLabel>
                    <FormControl>
                      <Input
                        type="email"
                        placeholder="email@example.com"
                        {...field}
                        onBlur={() => {
                          field.onBlur();
                          if (!isEditing) handleDuplicateCheck();
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Referred by */}
            <FormField
              control={form.control}
              name="referred_by"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Referred By (Optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Referral source or person" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Notes */}
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes (Optional)</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Any additional information..."
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
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {isEditing ? "Updating..." : "Creating..."}
                  </>
                ) : isEditing ? (
                  "Update Inquiry"
                ) : (
                  "Create Inquiry"
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
