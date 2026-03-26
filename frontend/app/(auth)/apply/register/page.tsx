"use client";

/**
 * SIMS Plus - Applicant Registration Page
 *
 * Prospective parents register here to create an applicant account.
 * Includes Turnstile captcha, password strength validation, and school branding.
 * Path: {school}.simsplus.io/apply/register
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import Script from "next/script";
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
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { registerApplicant } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import {
  Loader2,
  AlertCircle,
  GraduationCap,
  Check,
  X,
  Eye,
  EyeOff,
  ArrowLeft,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const registerSchema = z
  .object({
    first_name: z
      .string()
      .min(1, "First name is required")
      .max(100, "First name is too long")
      .transform((v) => v.trim()),
    last_name: z
      .string()
      .min(1, "Last name is required")
      .max(100, "Last name is too long")
      .transform((v) => v.trim()),
    email: z.string().email("Please enter a valid email address"),
    phone: z
      .string()
      .min(10, "Please enter a valid phone number")
      .max(20, "Phone number is too long"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

// ---------------------------------------------------------------------------
// Password Strength
// ---------------------------------------------------------------------------

interface PasswordCheck {
  label: string;
  test: (pw: string) => boolean;
}

const PASSWORD_CHECKS: PasswordCheck[] = [
  { label: "At least 8 characters", test: (pw) => pw.length >= 8 },
  { label: "One uppercase letter", test: (pw) => /[A-Z]/.test(pw) },
  { label: "One lowercase letter", test: (pw) => /[a-z]/.test(pw) },
  { label: "One number", test: (pw) => /[0-9]/.test(pw) },
  {
    label: "One special character",
    test: (pw) => /[^a-zA-Z0-9]/.test(pw),
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantRegisterPage() {
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const turnstileRef = useRef<HTMLDivElement>(null);

  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      phone: "",
      password: "",
      confirm_password: "",
    },
  });

  const { isSubmitting } = form.formState;
  const passwordValue = form.watch("password");

  // Clear form error when user types
  useEffect(() => {
    const sub = form.watch(() => {
      if (formError) setFormError(null);
    });
    return () => sub.unsubscribe();
  }, [form, formError]);

  // Render Turnstile widget
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      (window as unknown as Record<string, unknown>).turnstile &&
      turnstileRef.current &&
      turnstileRef.current.childNodes.length === 0
    ) {
      const turnstile = (window as unknown as Record<string, unknown>).turnstile as {
        render: (el: HTMLElement, opts: Record<string, unknown>) => void;
        reset: () => void;
      };
      turnstile.render(turnstileRef.current, {
        sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "",
        callback: (token: string) => setTurnstileToken(token),
        "expired-callback": () => setTurnstileToken(null),
      });
    }
  }, [tenantLoading]);

  async function onSubmit(values: RegisterFormData) {
    if (!turnstileToken) {
      setFormError("Please complete the security check.");
      return;
    }

    // Verify all password checks pass
    const allPassed = PASSWORD_CHECKS.every((c) => c.test(values.password));
    if (!allPassed) {
      setFormError("Password does not meet all requirements.");
      return;
    }

    setFormError(null);

    const result = await registerApplicant({
      first_name: values.first_name,
      last_name: values.last_name,
      email: values.email,
      phone: values.phone,
      password: values.password,
      turnstile_token: turnstileToken,
    });

    if (result.success) {
      setSuccess(true);
    } else {
      setFormError(result.error || "Registration failed. Please try again.");
      // Reset Turnstile on failure
      if ((window as unknown as Record<string, unknown>).turnstile) {
        const turnstile = (window as unknown as Record<string, unknown>).turnstile as {
          reset: () => void;
        };
        turnstile.reset();
      }
      setTurnstileToken(null);
    }
  }

  // ---------- Loading ----------
  if (tenantLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // ---------- Success ----------
  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
              <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <CardTitle>Check Your Email</CardTitle>
            <CardDescription>
              We have sent a verification link to{" "}
              <span className="font-medium text-foreground">
                {form.getValues("email")}
              </span>
              . Please click the link to verify your email and activate your
              account.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button asChild variant="outline">
              <Link href="/apply/login">Go to Login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------- Render ----------
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />

      <div className="w-full max-w-lg">
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
            Create an Applicant Account
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Register</CardTitle>
            <CardDescription>
              Create an account to apply for admission, save drafts, and track
              your applications.
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
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="first_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>First Name</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="Kwame"
                            autoComplete="given-name"
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
                            placeholder="Mensah"
                            autoComplete="family-name"
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

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
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone Number</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="tel"
                          placeholder="+233 24 123 4567"
                          autoComplete="tel"
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
                      <FormLabel>Password</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Input
                            {...field}
                            type={showPassword ? "text" : "password"}
                            placeholder="Create a strong password"
                            autoComplete="new-password"
                            disabled={isSubmitting}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                            onClick={() => setShowPassword(!showPassword)}
                            tabIndex={-1}
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Password strength checklist */}
                {passwordValue && (
                  <div className="space-y-1 rounded-md border p-3">
                    {PASSWORD_CHECKS.map((check) => {
                      const passed = check.test(passwordValue);
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
                  name="confirm_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Confirm your password"
                          autoComplete="new-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Turnstile widget */}
                <div ref={turnstileRef} className="flex justify-center" />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting || !turnstileToken}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    "Create Account"
                  )}
                </Button>
              </form>
            </Form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link
                href="/apply/login"
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </Link>
            </p>
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
