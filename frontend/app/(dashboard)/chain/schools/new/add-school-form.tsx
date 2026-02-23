"use client";

/**
 * Add School Form
 *
 * Form for chain admins to add a new school to the chain.
 * Uses React Hook Form + Zod for validation.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { addSchoolToChain } from "@/actions/chain.action";

const addSchoolSchema = z.object({
  name: z
    .string()
    .min(2, "School name must be at least 2 characters")
    .max(255, "School name must be at most 255 characters")
    .trim(),
  code: z
    .string()
    .min(1, "School code is required")
    .max(20, "Code must be at most 20 characters")
    .trim(),
  address: z.string().max(500).trim().optional().or(z.literal("")),
  phone: z.string().max(20).trim().optional().or(z.literal("")),
  email: z
    .string()
    .email("Invalid email address")
    .optional()
    .or(z.literal("")),
  student_id_prefix: z
    .string()
    .max(10, "Prefix must be at most 10 characters")
    .trim()
    .optional()
    .or(z.literal("")),
});

type AddSchoolValues = z.infer<typeof addSchoolSchema>;

export function AddSchoolForm() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<AddSchoolValues>({
    resolver: zodResolver(addSchoolSchema),
    defaultValues: {
      name: "",
      code: "",
      address: "",
      phone: "",
      email: "",
      student_id_prefix: "",
    },
  });

  async function onSubmit(values: AddSchoolValues) {
    setIsSubmitting(true);
    try {
      const result = await addSchoolToChain({
        name: values.name,
        code: values.code,
        address: values.address || undefined,
        phone: values.phone || undefined,
        email: values.email || undefined,
        student_id_prefix: values.student_id_prefix || undefined,
      });

      if (result.success) {
        toast.success("School added successfully");
        router.push("/chain/schools");
        router.refresh();
      } else {
        toast.error(result.error);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>School Details</CardTitle>
        <CardDescription>
          Enter the basic details for the new school. You can update branding
          and additional settings later.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>School Name *</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Presec Primary Campus" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="code"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>School Code *</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., PPC" {...field} />
                    </FormControl>
                    <FormDescription>
                      A short code used to identify the school.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder="school@example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Phone</FormLabel>
                    <FormControl>
                      <Input placeholder="+233 XX XXX XXXX" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Address</FormLabel>
                    <FormControl>
                      <Input placeholder="Street address" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="student_id_prefix"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Student ID Prefix</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., PPC" {...field} />
                    </FormControl>
                    <FormDescription>
                      Prefix for auto-generated student IDs at this school.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/chain/schools")}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 size-4 animate-spin" />}
                Add School
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
