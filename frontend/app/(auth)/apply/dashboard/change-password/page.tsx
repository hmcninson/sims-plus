"use client";

/**
 * SIMS Plus - Applicant Change Password Page
 *
 * Current password + new password with strength checklist + confirmation.
 * Redirects to dashboard on success.
 * Path: {school}.simsplus.io/apply/dashboard/change-password
 */

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { changeApplicantPassword } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";

import { Loader2, AlertCircle, Check, X, ArrowLeft } from "lucide-react";

// ---------------------------------------------------------------------------
// Password strength checks (matches register + reset pages)
// ---------------------------------------------------------------------------

const PASSWORD_CHECKS = [
  { label: "At least 8 characters", test: (pw: string) => pw.length >= 8 },
  { label: "One uppercase letter", test: (pw: string) => /[A-Z]/.test(pw) },
  { label: "One lowercase letter", test: (pw: string) => /[a-z]/.test(pw) },
  { label: "One number", test: (pw: string) => /[0-9]/.test(pw) },
  {
    label: "One special character",
    test: (pw: string) => /[^a-zA-Z0-9]/.test(pw),
  },
];

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_new_password: z.string().min(1, "Please confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_new_password, {
    message: "Passwords do not match",
    path: ["confirm_new_password"],
  });

type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantChangePasswordPage() {
  const router = useRouter();
  const { tenant } = useTenant();

  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_new_password: "",
    },
  });

  const { isSubmitting } = form.formState;
  const newPasswordValue = form.watch("new_password");

  async function onSubmit(values: ChangePasswordFormData) {
    setFormError(null);

    // Verify all password strength checks pass
    const allPassed = PASSWORD_CHECKS.every((c) => c.test(values.new_password));
    if (!allPassed) {
      setFormError("New password does not meet all requirements.");
      return;
    }

    const result = await changeApplicantPassword({
      current_password: values.current_password,
      new_password: values.new_password,
    });

    if (result.success) {
      toast.success("Password changed successfully");
      router.push("/apply/dashboard");
    } else {
      setFormError(result.error || "Failed to change password");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Change Password</CardTitle>
            <CardDescription>
              Enter your current password and choose a new one
            </CardDescription>
          </CardHeader>
          <CardContent>
            {formError && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="current_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Current Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Enter current password"
                          autoComplete="current-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Enter new password"
                          autoComplete="new-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Password strength checklist */}
                {newPasswordValue && (
                  <div className="space-y-1 rounded-md border p-3">
                    {PASSWORD_CHECKS.map((check) => {
                      const passed = check.test(newPasswordValue);
                      return (
                        <div
                          key={check.label}
                          className="flex items-center gap-2 text-xs"
                        >
                          {passed ? (
                            <Check className="h-3.5 w-3.5 text-green-600" />
                          ) : (
                            <X className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                          <span
                            className={
                              passed
                                ? "text-green-700 dark:text-green-400"
                                : "text-muted-foreground"
                            }
                          >
                            {check.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="confirm_new_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm New Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Confirm new password"
                          autoComplete="new-password"
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
                      Changing Password...
                    </>
                  ) : (
                    "Change Password"
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
