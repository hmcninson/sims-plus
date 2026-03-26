"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Label } from "@/components/ui/label";
import { login } from "@/actions/auth.action";
import { verifyMFALogin } from "@/actions/mfa.action";
import { validateTenant } from "@/actions/tenant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { SuspensionBanner } from "@/components/banners/SuspensionBanner";
import {
  Loader2,
  AlertCircle,
  GraduationCap,
  Lock,
  Clock,
  Shield,
  ArrowLeft,
  Search,
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

// Whitelisted URL error codes -- prevents social engineering via crafted URLs
const URL_ERROR_MESSAGES: Record<
  string,
  { title: string; message: string; variant: "warning" | "error" }
> = {
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
// School code validation (matches proxy.ts rules)
// ---------------------------------------------------------------------------

const schoolCodeSchema = z.object({
  schoolCode: z
    .string()
    .min(4, "School code must be at least 4 characters")
    .max(63, "School code must be at most 63 characters")
    .regex(
      /^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]+$/,
      "Only lowercase letters, numbers, and hyphens allowed"
    )
    .refine((val) => !val.includes("--"), {
      message: "School code cannot contain consecutive hyphens",
    }),
});

type SchoolCodeFormData = z.infer<typeof schoolCodeSchema>;

/**
 * Build the login URL for a given school code, respecting the current
 * environment (localhost vs production).
 */
function buildSchoolLoginUrl(schoolCode: string): string {
  if (typeof window === "undefined") return "#";

  const hostname = window.location.hostname;
  const isLocalhost =
    hostname === "localhost" || hostname === "127.0.0.1";

  if (isLocalhost) {
    const port = window.location.port ? `:${window.location.port}` : "";
    return `http://${schoolCode}.localhost${port}/login`;
  }

  // Production: use the same base domain (e.g., simsplus.io)
  const parts = hostname.split(".");
  // Handle app.simsplus.io -> presec.simsplus.io
  // or simsplus.io -> presec.simsplus.io
  const baseDomain =
    parts.length >= 2 ? parts.slice(-2).join(".") : hostname;
  const protocol = window.location.protocol;

  return `${protocol}//${schoolCode}.${baseDomain}/login`;
}

// ---------------------------------------------------------------------------
// School Finder (shown when no tenant context)
// ---------------------------------------------------------------------------

function SchoolFinder() {
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<SchoolCodeFormData>({
    resolver: zodResolver(schoolCodeSchema),
    defaultValues: { schoolCode: "" },
  });

  async function onSubmit(values: SchoolCodeFormData) {
    setError(null);
    setIsChecking(true);

    try {
      const result = await validateTenant(values.schoolCode);

      if (result.success && result.data.valid && result.data.tenant) {
        // School exists and is active -- redirect
        window.location.href = buildSchoolLoginUrl(values.schoolCode);
        return;
      }

      // Tenant not found or inactive
      setError(
        "No school found with that code. Please check and try again."
      );
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setIsChecking(false);
    }
  }

  // Clear error when user edits the input
  useEffect(() => {
    const subscription = form.watch(() => {
      if (error) setError(null);
    });
    return () => subscription.unsubscribe();
  }, [form, error]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="mb-8 text-center">
          <div className="mb-4 flex justify-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-[#1B4F72]">
              <GraduationCap className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-foreground">
            Welcome to SIMS Plus
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Enter your school code to continue
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Find Your School
            </CardTitle>
            <CardDescription>
              Your school code is the subdomain used to access your portal
              (e.g., <span className="font-mono text-foreground">presec</span>
              .simsplus.io)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form
              onSubmit={form.handleSubmit(onSubmit)}
              noValidate
              className="space-y-4"
            >
              <div className="space-y-2">
                <Label htmlFor="schoolCode">School Code</Label>
                <Input
                  id="schoolCode"
                  placeholder="e.g., presec"
                  autoComplete="off"
                  autoFocus
                  disabled={isChecking}
                  {...form.register("schoolCode", {
                    // Normalize to lowercase on change
                    onChange: (e) => {
                      e.target.value = e.target.value
                        .toLowerCase()
                        .replace(/[^a-z0-9-]/g, "");
                    },
                  })}
                />
                {form.formState.errors.schoolCode && (
                  <p className="text-sm text-destructive">
                    {form.formState.errors.schoolCode.message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isChecking}
              >
                {isChecking ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Checking...
                  </>
                ) : (
                  "Continue"
                )}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Don&apos;t know your school code? Contact your school
              administrator.
            </p>
          </CardContent>
        </Card>

        {/* Registration link */}
        <p className="mt-4 text-center text-sm text-muted-foreground">
          Want to register your school?{" "}
          <Link
            href="/register"
            className="font-medium text-primary hover:underline"
          >
            Start free trial
          </Link>
        </p>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    tenant,
    isLoading: tenantLoading,
    error: tenantError,
    isSuspended,
    suspensionMessage,
  } = useTenant();

  const [formError, setFormError] = useState<FormError | null>(null);

  // MFA state
  const [showMfaStep, setShowMfaStep] = useState(false);
  const [mfaPendingToken, setMfaPendingToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [useBackupCode, setUseBackupCode] = useState(false);
  const [backupCode, setBackupCode] = useState("");
  const [mfaError, setMfaError] = useState<string | null>(null);
  const [isMfaSubmitting, setIsMfaSubmitting] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);

  // URL-based messaging (e.g. after password reset or session timeout)
  // Only whitelisted error codes are rendered -- arbitrary message params are ignored
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

    const result = await login({ ...values, remember_me: rememberMe });

    if (result.success) {
      // Check if MFA verification is required
      if (result.data.mfa_required && result.data.mfa_pending_token) {
        setMfaPendingToken(result.data.mfa_pending_token);
        setShowMfaStep(true);
        return;
      }

      // Normal login -- route to appropriate portal
      if (result.data.user) {
        let redirectUrl = "/dashboard";
        if (result.data.user.role === "parent") {
          redirectUrl = "/parent/dashboard";
        } else if (
          result.data.user.role === "teacher" ||
          result.data.user.role === "academic_head"
        ) {
          redirectUrl = "/teacher/dashboard";
        } else if (result.data.user.role === "applicant") {
          redirectUrl = "/apply/dashboard";
        }
        router.push(redirectUrl);
      }
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

  // MFA verification handler
  const handleMfaVerify = useCallback(async () => {
    const code = useBackupCode ? backupCode.trim() : mfaCode;

    if (!code) {
      setMfaError(
        useBackupCode
          ? "Please enter your backup code"
          : "Please enter the 6-digit code"
      );
      return;
    }

    if (!useBackupCode && code.length !== 6) {
      setMfaError("Please enter the full 6-digit code");
      return;
    }

    setIsMfaSubmitting(true);
    setMfaError(null);

    const result = await verifyMFALogin({
      mfa_pending_token: mfaPendingToken,
      code,
    });

    setIsMfaSubmitting(false);

    if (result.success) {
      // Route to appropriate portal
      let redirectUrl = "/dashboard";
      if (result.data.role === "parent") {
        redirectUrl = "/parent/dashboard";
      } else if (
        result.data.role === "teacher" ||
        result.data.role === "academic_head"
      ) {
        redirectUrl = "/teacher/dashboard";
      } else if (result.data.role === "applicant") {
        redirectUrl = "/apply/dashboard";
      }
      router.push(redirectUrl);
      return;
    }

    // Handle specific MFA errors
    if (result.code === 429) {
      setMfaError(
        "Too many failed attempts. Please log in again."
      );
    } else if (result.code === 401) {
      setMfaError(
        result.error || "Invalid or expired code. Please try again."
      );
    } else {
      setMfaError(result.error || "Verification failed");
    }
  }, [useBackupCode, backupCode, mfaCode, mfaPendingToken, router]);

  const handleBackToLogin = useCallback(() => {
    setShowMfaStep(false);
    setMfaPendingToken("");
    setMfaCode("");
    setBackupCode("");
    setUseBackupCode(false);
    setMfaError(null);
  }, []);

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

  // ---------- Suspended tenant ----------
  if (isSuspended) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted p-4">
        <SuspensionBanner message={suspensionMessage ?? undefined} />
      </main>
    );
  }

  // ---------- No tenant context: show school finder ----------
  if (!tenant) {
    return <SchoolFinder />;
  }

  // ---------- Render ----------
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md">
        {/* URL-based error/message alert (e.g. session expired) -- whitelisted codes only */}
        {!showMfaStep && urlError && urlError.variant === "warning" && (
          <Alert className="mb-6 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
            <Clock className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {!showMfaStep && urlError && urlError.variant === "error" && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {!showMfaStep && !urlError && tenantError && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{tenantError}</AlertDescription>
          </Alert>
        )}

        {/* Logo and School Name -- tenant is guaranteed non-null here */}
        <div className="mb-8 text-center">
          {tenant.branding?.logo_url ? (
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
                  backgroundColor:
                    tenant.branding?.primary_color || "#1B4F72",
                }}
              >
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            </div>
          )}

          <h1
            className="text-2xl font-bold"
            style={{
              color: tenant.branding?.primary_color || "#1B4F72",
            }}
          >
            {tenant.name}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            School Management Portal
          </p>
        </div>

        {/* ========== MFA VERIFICATION STEP ========== */}
        {showMfaStep ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5" />
                Two-Factor Authentication
              </CardTitle>
              <CardDescription>
                {useBackupCode
                  ? "Enter one of your backup codes"
                  : "Enter the 6-digit code from your authenticator app"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* MFA error alert */}
              {mfaError && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{mfaError}</AlertDescription>
                </Alert>
              )}

              {useBackupCode ? (
                /* Backup code input */
                <div className="space-y-2">
                  <label
                    htmlFor="backup-code"
                    className="text-sm font-medium"
                  >
                    Backup Code
                  </label>
                  <Input
                    id="backup-code"
                    type="text"
                    placeholder="XXXX-XXXX"
                    maxLength={9}
                    value={backupCode}
                    onChange={(e) => {
                      setBackupCode(e.target.value.toUpperCase());
                      if (mfaError) setMfaError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && backupCode) {
                        handleMfaVerify();
                      }
                    }}
                    className="text-center text-lg tracking-widest font-mono"
                    autoFocus
                    autoComplete="one-time-code"
                    aria-label="Backup code"
                  />
                </div>
              ) : (
                /* TOTP code input */
                <div className="space-y-2">
                  <label
                    htmlFor="mfa-code"
                    className="text-sm font-medium"
                  >
                    Verification Code
                  </label>
                  <Input
                    id="mfa-code"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="000000"
                    value={mfaCode}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, "");
                      setMfaCode(value);
                      if (mfaError) setMfaError(null);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && mfaCode.length === 6) {
                        handleMfaVerify();
                      }
                    }}
                    className="text-center text-lg tracking-widest"
                    autoFocus
                    autoComplete="one-time-code"
                    aria-label="6-digit verification code"
                  />
                </div>
              )}

              <Button
                onClick={handleMfaVerify}
                className="w-full"
                disabled={isMfaSubmitting}
                style={{
                  backgroundColor:
                    tenant.branding?.primary_color || undefined,
                }}
              >
                {isMfaSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  "Verify"
                )}
              </Button>

              {/* Toggle between TOTP and backup code */}
              <div className="text-center">
                <button
                  type="button"
                  className="text-sm text-muted-foreground underline hover:text-foreground"
                  onClick={() => {
                    setUseBackupCode(!useBackupCode);
                    setMfaError(null);
                  }}
                >
                  {useBackupCode
                    ? "Use authenticator code instead"
                    : "Use a backup code instead"}
                </button>
              </div>

              <p className="text-center text-xs text-muted-foreground">
                <Clock className="mr-1 inline h-3 w-3" />
                Token expires in 5 minutes
              </p>

              {/* Back to login */}
              <Button
                variant="ghost"
                className="w-full"
                onClick={handleBackToLogin}
              >
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to login
              </Button>
            </CardContent>
          </Card>
        ) : (
          /* ========== LOGIN FORM ========== */
          <>
            <Card>
              <CardHeader>
                <CardTitle>Sign In</CardTitle>
                <CardDescription>
                  Enter your credentials to access {tenant.name}
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
                        <Checkbox
                          disabled={isSubmitting}
                          checked={rememberMe}
                          onCheckedChange={(checked) => setRememberMe(checked === true)}
                        />
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
                        backgroundColor:
                          tenant.branding?.primary_color || undefined,
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

                <p className="mt-6 text-center text-sm text-muted-foreground">
                  Need help? Contact your school administrator
                </p>
              </CardContent>
            </Card>

          </>
        )}
      </div>
    </main>
  );
}
