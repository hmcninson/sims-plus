"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { Loader2 } from "lucide-react";

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
import { StudentCombobox } from "@/components/preschool/StudentCombobox";
import type {
  Student,
  AuthorizedPickup,
  PickupLogCreate,
  StudentGuardianLink,
} from "@/types";

interface PickupLogFormProps {
  students: Student[];
  guardians: Map<string, StudentGuardianLink[]>;
  authorizedPickups: Map<string, AuthorizedPickup[]>;
  onSubmit: (data: PickupLogCreate) => Promise<void>;
  isSaving?: boolean;
}

const formSchema = z
  .object({
    student_id: z.string().min(1, "Student is required"),
    picked_up_by_type: z.enum(["guardian", "authorized_person"], {
      message: "Select person type",
    }),
    picked_up_by_guardian_id: z.string().optional(),
    picked_up_by_authorized_id: z.string().optional(),
    pickup_time: z.string().min(1, "Pickup time is required"),
    notes: z.string().optional(),
  })
  .refine(
    (data) => {
      if (data.picked_up_by_type === "guardian") {
        return !!data.picked_up_by_guardian_id;
      }
      return !!data.picked_up_by_authorized_id;
    },
    {
      message: "Select who is picking up the student",
      path: ["picked_up_by_guardian_id"],
    }
  );

type FormValues = z.infer<typeof formSchema>;

export function PickupLogForm({
  students,
  guardians,
  authorizedPickups,
  onSubmit,
  isSaving,
}: PickupLogFormProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      student_id: "",
      picked_up_by_type: undefined,
      picked_up_by_guardian_id: "",
      picked_up_by_authorized_id: "",
      pickup_time: format(new Date(), "HH:mm"),
      notes: "",
    },
  });

  const selectedStudentId = form.watch("student_id");
  const personType = form.watch("picked_up_by_type");

  // Get guardians with can_pickup=true for the selected student
  const studentGuardians = (guardians.get(selectedStudentId) ?? []).filter(
    (sg) => sg.can_pickup
  );

  // Get active authorized pickups for the selected student
  const studentAuthorized = (authorizedPickups.get(selectedStudentId) ?? []).filter(
    (ap) => ap.is_active
  );

  async function handleSubmit(values: FormValues) {
    const data: PickupLogCreate = {
      student_id: values.student_id,
      pickup_time: values.pickup_time,
      picked_up_by_type: values.picked_up_by_type,
      picked_up_by_guardian_id:
        values.picked_up_by_type === "guardian"
          ? values.picked_up_by_guardian_id || undefined
          : undefined,
      picked_up_by_authorized_id:
        values.picked_up_by_type === "authorized_person"
          ? values.picked_up_by_authorized_id || undefined
          : undefined,
      notes: values.notes || undefined,
    };
    await onSubmit(data);
    form.reset({
      student_id: "",
      picked_up_by_type: undefined,
      picked_up_by_guardian_id: "",
      picked_up_by_authorized_id: "",
      pickup_time: format(new Date(), "HH:mm"),
      notes: "",
    });
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
              <FormItem>
                <FormLabel>Student</FormLabel>
                <FormControl>
                  <StudentCombobox
                    students={students}
                    value={field.value}
                    onValueChange={(val) => {
                      field.onChange(val);
                      // Reset person selections when student changes
                      form.setValue("picked_up_by_guardian_id", "");
                      form.setValue("picked_up_by_authorized_id", "");
                    }}
                    placeholder="Select student..."
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Pickup Time */}
          <FormField
            control={form.control}
            name="pickup_time"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Pickup Time</FormLabel>
                <FormControl>
                  <Input type="time" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Person Type */}
          <FormField
            control={form.control}
            name="picked_up_by_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Picked Up By</FormLabel>
                <Select
                  onValueChange={(val) => {
                    field.onChange(val);
                    form.setValue("picked_up_by_guardian_id", "");
                    form.setValue("picked_up_by_authorized_id", "");
                  }}
                  value={field.value}
                >
                  <FormControl>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Select type..." />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="guardian">Guardian</SelectItem>
                    <SelectItem value="authorized_person">
                      Authorized Person
                    </SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Guardian Select */}
          {personType === "guardian" && (
            <FormField
              control={form.control}
              name="picked_up_by_guardian_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Select Guardian</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select guardian..." />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {studentGuardians.length === 0 ? (
                        <SelectItem value="_none" disabled>
                          No guardians with pickup permission
                        </SelectItem>
                      ) : (
                        studentGuardians.map((sg) => (
                          <SelectItem key={sg.guardian_id} value={sg.guardian_id}>
                            {sg.guardian.first_name} {sg.guardian.last_name} (
                            {sg.relationship})
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          {/* Authorized Person Select */}
          {personType === "authorized_person" && (
            <FormField
              control={form.control}
              name="picked_up_by_authorized_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Select Authorized Person</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select person..." />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {studentAuthorized.length === 0 ? (
                        <SelectItem value="_none" disabled>
                          No authorized persons
                        </SelectItem>
                      ) : (
                        studentAuthorized.map((ap) => (
                          <SelectItem key={ap.id} value={ap.id}>
                            {ap.full_name}
                            {ap.relationship_to_student &&
                              ` (${ap.relationship_to_student})`}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}
        </div>

        {/* Notes */}
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Notes (optional)</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Any notes about the pickup..."
                  rows={2}
                  {...field}
                  value={field.value ?? ""}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button
          type="submit"
          disabled={isSaving || !selectedStudentId}
        >
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Record Pickup
        </Button>
      </form>
    </Form>
  );
}
