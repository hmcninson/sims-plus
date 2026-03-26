"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { requestPasswordReset } from "@/actions/auth.action";
import { forgotPasswordSMS, resetPasswordSMS } from "@/actions/otp.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { toast } from "sonner";
import {
  Loader2,
  ArrowLeft,
  GraduationCap,
  Mail,
  CheckCircle,
  Phone,
  Eye,
  EyeOff,
  Check,
  X,
} from "lucide-react";

// Password requirements (same as reset-password page)
const passwordRequirements = [
  { regex: /.{8,}/, label: "At least 8 characters" },
  { regex: /[A-Z]/, label: "One uppercase letter" },
  { regex: /[a-z]/, label: "One lowercase letter" },
  { regex: /\d/, label: "One number" },
  { regex: /[!@#$%^&*(),.?":{}|<>]/, label: "One special character" },
];

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { tenant, isLoading: tenantLoading } = useTenant();

  // Email reset state
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [email, setEmail] = useState("");

  // SMS reset state
  const [smsStep, setSmsStep] = useState<"phone" | "reset">("phone");
  const [smsPhone, setSmsPhone] = useState("");
  const [smsCode, setSmsCode] = useState("");
  const [smsNewPassword, setSmsNewPassword] = useState("");
  const [smsConfirmPassword, setSmsConfirmPassword] = useState("");
  const [showSmsPassword, setShowSmsPassword] = useState(false);
  const [showSmsConfirmPassword, setShowSmsConfirmPassword] = useState(false);
  const [isSmsLoading, setIsSmsLoading] = useState(false);
  const [smsCooldown, setSmsCooldown] = useState(0);
  const [isSmsSuccess, setIsSmsSuccess] = useState(false);

  // Cooldown timer
  useEffect(() => {
    if (smsCooldown > 0) {
      const timer = setTimeout(() => setSmsCooldown(smsCooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [smsCooldown]);

  // Email reset handler
  async function handleEmailSubmit(formData: FormData) {
    setIsLoading(true);
    const emailValue = formData.get("email") as string;

    const result = await requestPasswordReset(emailValue);

    setIsLoading(false);

    if (result.success) {
      setEmail(emailValue);
      setIsSubmitted(true);
      toast.success("Check your email for reset instructions");
    } else {
      toast.error(result.error || "Failed to send reset email");
    }
  }

  // SMS step 1: send OTP
  async function handleSendSmsCode(e: React.FormEvent) {
    e.preventDefault();

    if (!smsPhone.trim()) {
      toast.error("Please enter your phone number");
      return;
    }

    setIsSmsLoading(true);
    const result = await forgotPasswordSMS(smsPhone);
    setIsSmsLoading(false);

    if (result.success) {
      setSmsStep("reset");
      setSmsCooldown(60);
      toast.success("If an account with this phone number exists, a verification code has been sent.");
    } else {
      toast.error(result.error || "Failed to send code");
    }
  }

  // SMS step 2: reset password
  async function handleSmsReset(e: React.FormEvent) {
    e.preventDefault();

    if (smsCode.length !== 6) {
      toast.error("Please enter the 6-digit code");
      return;
    }

    const meetsAllRequirements = passwordRequirements.every((req) =>
      req.regex.test(smsNewPassword)
    );
    if (!meetsAllRequirements) {
      toast.error("Password does not meet all requirements");
      return;
    }

    if (smsNewPassword !== smsConfirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    setIsSmsLoading(true);
    const result = await resetPasswordSMS({
      phone: smsPhone,
      code: smsCode,
      new_password: smsNewPassword,
    });
    setIsSmsLoading(false);

    if (result.success) {
      setIsSmsSuccess(true);
      toast.success("Password reset successfully!");
    } else {
      toast.error(result.error || "Password reset failed");
    }
  }

  // Resend SMS code
  async function handleResendSmsCode() {
    setIsSmsLoading(true);
    await forgotPasswordSMS(smsPhone);
    setIsSmsLoading(false);
    setSmsCooldown(60);
    toast.success("Verification code resent");
  }

  // Show loading state while checking tenant
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

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md">
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
                Password Recovery
              </p>
            </>
          ) : (
            <>
              <Link href="/">
                <h1 className="text-3xl font-bold text-primary">SIMS Plus</h1>
              </Link>
              <p className="mt-2 text-muted-foreground">Password Recovery</p>
            </>
          )}
        </div>

        {/* SMS Reset Success State */}
        {isSmsSuccess ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">Password Reset!</h2>
                <p className="mb-6 text-muted-foreground">
                  Your password has been successfully reset. You can now sign in
                  with your new password.
                </p>
                <Link href="/login" className="block">
                  <Button
                    className="w-full"
                    style={{
                      backgroundColor:
                        tenant?.branding?.primary_color || undefined,
                    }}
                  >
                    Sign In
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        ) : /* Email Success State */
        isSubmitted ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">Check Your Email</h2>
                <p className="mb-4 text-muted-foreground">
                  We&apos;ve sent password reset instructions to:
                </p>
                <p className="mb-6 font-medium text-foreground">{email}</p>
                <p className="mb-6 text-sm text-muted-foreground">
                  If you don&apos;t see the email, check your spam folder. The
                  link will expire in 1 hour.
                </p>
                <div className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => setIsSubmitted(false)}
                  >
                    <Mail className="mr-2 h-4 w-4" />
                    Try a different email
                  </Button>
                  <Link href="/login" className="block">
                    <Button
                      variant="ghost"
                      className="w-full"
                      style={{
                        color: tenant?.branding?.primary_color || undefined,
                      }}
                    >
                      <ArrowLeft className="mr-2 h-4 w-4" />
                      Back to Sign In
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          /* Main Form with Tabs */
          <Card>
            <CardHeader>
              <CardTitle>Forgot Password?</CardTitle>
              <CardDescription>
                Choose how you&apos;d like to reset your password.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="email" className="w-full">
                <TabsList className="grid w-full grid-cols-2 mb-4">
                  <TabsTrigger value="email" className="gap-1.5">
                    <Mail className="h-4 w-4" />
                    Email
                  </TabsTrigger>
                  <TabsTrigger value="sms" className="gap-1.5">
                    <Phone className="h-4 w-4" />
                    SMS
                  </TabsTrigger>
                </TabsList>

                {/* Email Tab */}
                <TabsContent value="email">
                  <form action={handleEmailSubmit} className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="email">Email Address</Label>
                      <Input
                        id="email"
                        name="email"
                        type="email"
                        placeholder="you@school.edu.gh"
                        required
                        autoComplete="email"
                        disabled={isLoading}
                      />
                    </div>

                    <Button
                      type="submit"
                      className="w-full"
                      disabled={isLoading}
                      style={{
                        backgroundColor:
                          tenant?.branding?.primary_color || undefined,
                      }}
                    >
                      {isLoading ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Sending...
                        </>
                      ) : (
                        <>
                          <Mail className="mr-2 h-4 w-4" />
                          Send Reset Link
                        </>
                      )}
                    </Button>
                  </form>
                </TabsContent>

                {/* SMS Tab */}
                <TabsContent value="sms">
                  {smsStep === "phone" ? (
                    /* Step 1: Enter phone number */
                    <form onSubmit={handleSendSmsCode} className="space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="sms-phone">Phone Number</Label>
                        <Input
                          id="sms-phone"
                          type="tel"
                          placeholder="+233 XX XXX XXXX"
                          value={smsPhone}
                          onChange={(e) => setSmsPhone(e.target.value)}
                          required
                          autoComplete="tel"
                          disabled={isSmsLoading}
                        />
                        <p className="text-xs text-muted-foreground">
                          Enter the phone number associated with your account.
                        </p>
                      </div>

                      <Button
                        type="submit"
                        className="w-full"
                        disabled={isSmsLoading || !smsPhone.trim()}
                        style={{
                          backgroundColor:
                            tenant?.branding?.primary_color || undefined,
                        }}
                      >
                        {isSmsLoading ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Sending...
                          </>
                        ) : (
                          <>
                            <Phone className="mr-2 h-4 w-4" />
                            Send Verification Code
                          </>
                        )}
                      </Button>
                    </form>
                  ) : (
                    /* Step 2: Enter OTP + new password */
                    <form onSubmit={handleSmsReset} className="space-y-4">
                      <p className="text-sm text-muted-foreground">
                        Enter the 6-digit code sent to{" "}
                        <span className="font-medium text-foreground">
                          {smsPhone}
                        </span>
                      </p>

                      {/* OTP Code */}
                      <div className="space-y-2">
                        <Label htmlFor="sms-code">Verification Code</Label>
                        <Input
                          id="sms-code"
                          type="text"
                          inputMode="numeric"
                          pattern="[0-9]*"
                          maxLength={6}
                          placeholder="000000"
                          value={smsCode}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, "");
                            setSmsCode(value);
                          }}
                          required
                          disabled={isSmsLoading}
                          className="text-center text-lg tracking-widest"
                          aria-label="6-digit verification code"
                        />
                        <div className="flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => {
                              setSmsStep("phone");
                              setSmsCode("");
                              setSmsNewPassword("");
                              setSmsConfirmPassword("");
                            }}
                            className="text-xs text-muted-foreground hover:text-foreground underline"
                          >
                            Change phone number
                          </button>
                          <button
                            type="button"
                            onClick={handleResendSmsCode}
                            disabled={smsCooldown > 0 || isSmsLoading}
                            className="text-xs text-primary hover:underline disabled:text-muted-foreground disabled:no-underline"
                          >
                            {smsCooldown > 0
                              ? `Resend in ${smsCooldown}s`
                              : "Resend Code"}
                          </button>
                        </div>
                      </div>

                      {/* New Password */}
                      <div className="space-y-2">
                        <Label htmlFor="sms-new-password">New Password</Label>
                        <div className="relative">
                          <Input
                            id="sms-new-password"
                            type={showSmsPassword ? "text" : "password"}
                            placeholder="Enter new password"
                            value={smsNewPassword}
                            onChange={(e) => setSmsNewPassword(e.target.value)}
                            required
                            autoComplete="new-password"
                            disabled={isSmsLoading}
                            className="pr-10"
                          />
                          <button
                            type="button"
                            onClick={() => setShowSmsPassword(!showSmsPassword)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showSmsPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Password Requirements */}
                      {smsNewPassword && (
                        <div className="rounded-lg border bg-muted/50 p-3">
                          <p className="mb-2 text-xs font-medium text-muted-foreground">
                            Password Requirements:
                          </p>
                          <ul className="space-y-1">
                            {passwordRequirements.map((req) => {
                              const isMet = req.regex.test(smsNewPassword);
                              return (
                                <li
                                  key={req.label}
                                  className={`flex items-center gap-2 text-xs ${
                                    isMet
                                      ? "text-green-600"
                                      : "text-muted-foreground"
                                  }`}
                                >
                                  {isMet ? (
                                    <Check className="h-3 w-3" />
                                  ) : (
                                    <X className="h-3 w-3" />
                                  )}
                                  {req.label}
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}

                      {/* Confirm Password */}
                      <div className="space-y-2">
                        <Label htmlFor="sms-confirm-password">
                          Confirm New Password
                        </Label>
                        <div className="relative">
                          <Input
                            id="sms-confirm-password"
                            type={showSmsConfirmPassword ? "text" : "password"}
                            placeholder="Confirm new password"
                            value={smsConfirmPassword}
                            onChange={(e) =>
                              setSmsConfirmPassword(e.target.value)
                            }
                            required
                            autoComplete="new-password"
                            disabled={isSmsLoading}
                            className="pr-10"
                          />
                          <button
                            type="button"
                            onClick={() =>
                              setShowSmsConfirmPassword(!showSmsConfirmPassword)
                            }
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showSmsConfirmPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                        {smsConfirmPassword &&
                          smsNewPassword !== smsConfirmPassword && (
                            <p className="text-xs text-destructive">
                              Passwords do not match
                            </p>
                          )}
                      </div>

                      <Button
                        type="submit"
                        className="w-full"
                        disabled={
                          isSmsLoading ||
                          smsCode.length !== 6 ||
                          !smsNewPassword ||
                          !smsConfirmPassword ||
                          smsNewPassword !== smsConfirmPassword
                        }
                        style={{
                          backgroundColor:
                            tenant?.branding?.primary_color || undefined,
                        }}
                      >
                        {isSmsLoading ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Resetting...
                          </>
                        ) : (
                          "Reset Password"
                        )}
                      </Button>
                    </form>
                  )}
                </TabsContent>
              </Tabs>

              <div className="mt-6">
                <Link href="/login">
                  <Button variant="ghost" className="w-full">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to Sign In
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Help text */}
        <p className="mt-4 text-center text-xs text-muted-foreground">
          Remember your password?{" "}
          <Link href="/login" className="text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
