"use client";

/**
 * SIMS Plus - Applicant Profile Settings Page
 *
 * Allows applicants to view/update their profile (first_name, last_name, phone).
 * Email is displayed read-only.
 * Path: {school}.simsplus.io/apply/dashboard/profile
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import {
  getApplicantProfile,
  updateApplicantProfile,
} from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";

import { Loader2, AlertCircle, ArrowLeft } from "lucide-react";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const profileSchema = z.object({
  first_name: z
    .string()
    .min(1, "First name is required")
    .max(100, "First name is too long"),
  last_name: z
    .string()
    .min(1, "Last name is required")
    .max(100, "Last name is too long"),
  phone: z
    .string()
    .max(20, "Phone number is too long")
    .optional()
    .or(z.literal("")),
});

type ProfileFormData = z.infer<typeof profileSchema>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantProfilePage() {
  const { tenant } = useTenant();

  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const form = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: { first_name: "", last_name: "", phone: "" },
  });

  const { isSubmitting } = form.formState;

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setFetchError(null);

    const result = await getApplicantProfile();

    if (result.success) {
      const { first_name, last_name, phone, email: userEmail } = result.data;
      form.reset({
        first_name,
        last_name,
        phone: phone || "",
      });
      setEmail(userEmail);
    } else {
      setFetchError(result.error || "Failed to load profile");
    }

    setLoading(false);
  }, [form]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  async function onSubmit(values: ProfileFormData) {
    setSubmitError(null);

    const result = await updateApplicantProfile({
      first_name: values.first_name,
      last_name: values.last_name,
      phone: values.phone || undefined,
    });

    if (result.success) {
      toast.success("Profile updated successfully");
      // Update form with returned data
      form.reset({
        first_name: result.data.first_name,
        last_name: result.data.last_name,
        phone: result.data.phone || "",
      });
    } else {
      setSubmitError(result.error || "Failed to update profile");
    }
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="w-full max-w-md space-y-4">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  // ---------- Fetch Error ----------
  if (fetchError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="py-12 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-destructive" />
            <p className="text-lg font-medium">Failed to load profile</p>
            <p className="mt-2 text-sm text-muted-foreground">{fetchError}</p>
            <div className="mt-4 flex justify-center gap-3">
              <Button onClick={fetchProfile} variant="outline">
                Try again
              </Button>
              <Button asChild variant="ghost">
                <Link href="/apply/dashboard">Back to Dashboard</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------- Form ----------
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Profile Settings</CardTitle>
            <CardDescription>
              Update your personal information
            </CardDescription>
          </CardHeader>
          <CardContent>
            {submitError && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{submitError}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                {/* Email (read-only) */}
                <div className="space-y-2">
                  <label className="text-sm font-medium leading-none">
                    Email Address
                  </label>
                  <Input
                    value={email}
                    disabled
                    className="bg-muted"
                  />
                  <p className="text-xs text-muted-foreground">
                    Email cannot be changed
                  </p>
                </div>

                <FormField
                  control={form.control}
                  name="first_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>First Name</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          placeholder="Enter first name"
                          disabled={isSubmitting}
                        />
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
                        <Input
                          {...field}
                          placeholder="Enter last name"
                          disabled={isSubmitting}
                        />
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
                      <FormLabel>Phone Number</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="tel"
                          placeholder="+233 XX XXX XXXX"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    "Save Changes"
                  )}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link
            href="/apply/dashboard"
            className="inline-flex items-center gap-1 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
        </p>
      </div>
    </div>
  );
}
