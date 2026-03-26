"use client";

/**
 * SIMS Plus - Applicant Login Page
 *
 * Applicants log in here (separate from staff /auth/login).
 * The login endpoint rejects non-applicant roles.
 * Path: {school}.simsplus.io/apply/login
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { loginApplicant } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import {
  Loader2,
  AlertCircle,
  GraduationCap,
  Lock,
  Clock,
  ArrowLeft,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

interface FormError {
  message: string;
  type: "error" | "locked" | "rate_limited";
}

const URL_ERROR_MESSAGES: Record<
  string,
  { title: string; message: string; variant: "warning" | "error" }
> = {
  session_expired: {
    title: "Session expired",
    message: "Your session has expired. Please sign in again.",
    variant: "warning",
  },
  email_verified: {
    title: "Email verified",
    message: "Your email has been verified. You can now sign in.",
    variant: "warning",
  },
  password_reset: {
    title: "Password reset",
    message: "Your password has been reset. Please sign in with your new password.",
    variant: "warning",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantLoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [formError, setFormError] = useState<FormError | null>(null);

  const errorParam = searchParams.get("error");
  const msgParam = searchParams.get("msg");
  const urlError = errorParam
    ? URL_ERROR_MESSAGES[errorParam]
    : msgParam
      ? URL_ERROR_MESSAGES[msgParam]
      : undefined;

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const { isSubmitting } = form.formState;

  // Clear form error on input change
  useEffect(() => {
    const sub = form.watch(() => {
      if (formError) setFormError(null);
    });
    return () => sub.unsubscribe();
  }, [form, formError]);

  async function onSubmit(values: LoginFormData) {
    setFormError(null);

    const result = await loginApplicant(values);

    if (result.success) {
      const redirectTo = searchParams.get("redirect");
      if (redirectTo && redirectTo.startsWith("/apply/")) {
        router.push(redirectTo);
      } else {
        router.push("/apply/dashboard");
      }
      return;
    }

    const code = result.code;

    if (code === 401) {
      setFormError({ message: "Invalid email or password", type: "error" });
    } else if (code === 403) {
      setFormError({
        message: result.error || "Account is locked",
        type: "locked",
      });
    } else if (code === 429) {
      setFormError({
        message: result.error || "Too many attempts. Please wait.",
        type: "rate_limited",
      });
    } else {
      setFormError({
        message: result.error || "Login failed. Please try again.",
        type: "error",
      });
    }
  }

  if (tenantLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* URL-based messages */}
        {urlError && (
          <Alert
            className={`mb-6 ${
              urlError.variant === "warning"
                ? "border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200"
                : ""
            }`}
            variant={urlError.variant === "error" ? "destructive" : undefined}
          >
            <Clock className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {/* School Branding */}
        <div className="mb-8 text-center">
          {tenant?.branding?.logo_url ? (
            <div className="mb-4 flex justify-center">
              <Image
                src={tenant.branding.logo_url}
                alt={`${tenant.name} logo`}
                width={72}
                height={72}
                className="rounded-lg"
              />
            </div>
          ) : (
            <div className="mb-4 flex justify-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-xl"
                style={{
                  backgroundColor:
                    tenant?.branding?.primary_color || "#1B4F72",
                }}
              >
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            </div>
          )}
          <h1
            className="text-2xl font-bold"
            style={{ color: tenant?.branding?.primary_color || undefined }}
          >
            {tenant?.name || "SIMS Plus"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Applicant Portal
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Sign In</CardTitle>
            <CardDescription>
              Sign in to manage your admission applications
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Error alerts -- same pattern as staff login */}
            {formError?.type === "error" && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Login failed</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}
            {formError?.type === "locked" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Lock className="h-4 w-4" />
                <AlertTitle>Account locked</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}
            {formError?.type === "rate_limited" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Clock className="h-4 w-4" />
                <AlertTitle>Too many attempts</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
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
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="email"
                          placeholder="parent@example.com"
                          autoComplete="email"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center justify-between">
                        <FormLabel>Password</FormLabel>
                        <Link
                          href="/apply/forgot-password"
                          className="text-xs text-primary hover:underline"
                        >
                          Forgot password?
                        </Link>
                      </div>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Enter your password"
                          autoComplete="current-password"
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
                      Signing in...
                    </>
                  ) : (
                    "Sign In"
                  )}
                </Button>
              </form>
            </Form>

            <div className="mt-6 space-y-2 text-center text-sm text-muted-foreground">
              <p>
                Don&apos;t have an account?{" "}
                <Link
                  href="/apply/register"
                  className="font-medium text-primary hover:underline"
                >
                  Create Account
                </Link>
              </p>
              <p>
                <Link
                  href="/apply/status"
                  className="text-primary hover:underline"
                >
                  Check Application Status
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link
            href="/apply"
            className="inline-flex items-center gap-1 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Admissions
          </Link>
        </p>
      </div>
    </div>
  );
}
