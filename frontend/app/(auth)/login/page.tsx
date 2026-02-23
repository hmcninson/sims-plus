"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { login } from "@/actions/auth.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { Loader2, AlertCircle, GraduationCap, Lock, Clock } from "lucide-react";

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

// Whitelisted URL error codes — prevents social engineering via crafted URLs
const URL_ERROR_MESSAGES: Record<string, { title: string; message: string; variant: "warning" | "error" }> = {
  session_expired: {
    title: "Session expired",
    message: "Your session has expired. Please sign in again.",
    variant: "warning",
  },
  unauthorized: {
    title: "Access denied",
    message: "Please sign in to continue.",
    variant: "error",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading, error: tenantError } = useTenant();

  const [formError, setFormError] = useState<FormError | null>(null);

  // URL-based messaging (e.g. after password reset or session timeout)
  // Only whitelisted error codes are rendered — arbitrary message params are ignored
  const errorParam = searchParams.get("error");
  const urlError = errorParam ? URL_ERROR_MESSAGES[errorParam] : undefined;

  // React Hook Form
  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  const { isSubmitting } = form.formState;

  // Apply tenant branding color
  useEffect(() => {
    if (tenant?.branding?.primary_color) {
      document.documentElement.style.setProperty(
        "--tenant-primary",
        tenant.branding.primary_color
      );
    }
  }, [tenant]);

  // Clear form-level error when user starts typing again
  useEffect(() => {
    const subscription = form.watch(() => {
      if (formError) setFormError(null);
    });
    return () => subscription.unsubscribe();
  }, [form, formError]);

  async function onSubmit(values: LoginFormData) {
    setFormError(null);

    const result = await login(values);

    if (result.success) {
      // Route each role to its dedicated portal
      let redirectUrl = "/dashboard";
      if (result.data.role === "parent") {
        redirectUrl = "/parent/dashboard";
      } else if (result.data.role === "teacher" || result.data.role === "academic_head") {
        redirectUrl = "/teacher/dashboard";
      }
      router.push(redirectUrl);
      return;
    }

    // Differentiated error handling based on HTTP status code
    const code = result.code;

    if (code === 401) {
      setFormError({
        message: "Invalid email or password",
        type: "error",
      });
    } else if (code === 403) {
      setFormError({
        message: result.error,
        type: "locked",
      });
    } else if (code === 429) {
      setFormError({
        message: result.error,
        type: "rate_limited",
      });
    } else {
      setFormError({
        message: result.error || "Login failed. Please try again.",
        type: "error",
      });
    }
  }

  // ---------- Tenant loading state ----------
  if (tenantLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted p-4">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </main>
    );
  }

  // ---------- Render ----------
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md">
        {/* URL-based error/message alert (e.g. session expired) — whitelisted codes only */}
        {urlError && urlError.variant === "warning" && (
          <Alert className="mb-6 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
            <Clock className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {urlError && urlError.variant === "error" && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {!urlError && tenantError && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{tenantError}</AlertDescription>
          </Alert>
        )}

        {/* Logo and School Name */}
        <div className="mb-8 text-center">
          {tenant?.branding?.logo_url ? (
            <div className="mb-4 flex justify-center">
              <Image
                src={tenant.branding.logo_url}
                alt={`${tenant.name} logo`}
                width={80}
                height={80}
                className="rounded-lg"
              />
            </div>
          ) : (
            <div className="mb-4 flex justify-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-xl"
                style={{
                  backgroundColor: tenant?.branding?.primary_color || "#1B4F72",
                }}
              >
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            </div>
          )}

          {tenant ? (
            <>
              <h1
                className="text-2xl font-bold"
                style={{ color: tenant.branding?.primary_color || "#1B4F72" }}
              >
                {tenant.name}
              </h1>
              <p className="mt-1 text-sm text-muted-foreground">
                School Management Portal
              </p>
            </>
          ) : (
            <>
              <Link href="/">
                <h1 className="text-3xl font-bold text-primary">SIMS Plus</h1>
              </Link>
              <p className="mt-2 text-muted-foreground">
                Sign in to your account
              </p>
            </>
          )}
        </div>

        {/* Login Card */}
        <Card>
          <CardHeader>
            <CardTitle>Sign In</CardTitle>
            <CardDescription>
              {tenant
                ? `Enter your credentials to access ${tenant.name}`
                : "Enter your email and password to access your account"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Form-level error alerts */}
            {formError && formError.type === "error" && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Login failed</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}

            {formError && formError.type === "locked" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Lock className="h-4 w-4" />
                <AlertTitle>Account locked</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}

            {formError && formError.type === "rate_limited" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Clock className="h-4 w-4" />
                <AlertTitle>Too many attempts</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="space-y-4">
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
                          placeholder="you@school.edu.gh"
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
                      <FormLabel>Password</FormLabel>
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

                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox disabled={isSubmitting} />
                    Remember me
                  </label>
                  <Link
                    href="/forgot-password"
                    className="text-sm text-primary hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                  style={{
                    backgroundColor: tenant?.branding?.primary_color || undefined,
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

            {/* Registration link -- only show on main site */}
            {!tenant && (
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{" "}
                <Link
                  href="/register"
                  className="font-medium text-primary hover:underline"
                >
                  Start free trial
                </Link>
              </p>
            )}

            {/* Help text for tenant context */}
            {tenant && (
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Need help? Contact your school administrator
              </p>
            )}
          </CardContent>
        </Card>

        {/* School-not-found message */}
        {!tenant && !tenantLoading && (
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Looking for your school?{" "}
            <Link href="/" className="text-primary hover:underline">
              Find your school portal
            </Link>
          </p>
        )}
      </div>
    </main>
  );
}
