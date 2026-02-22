"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
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
import { validateResetToken, resetPassword } from "@/actions/auth.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { toast } from "sonner";
import {
  Loader2,
  ArrowLeft,
  GraduationCap,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Check,
  X,
} from "lucide-react";

// Password requirements
const passwordRequirements = [
  { regex: /.{8,}/, label: "At least 8 characters" },
  { regex: /[A-Z]/, label: "One uppercase letter" },
  { regex: /[a-z]/, label: "One lowercase letter" },
  { regex: /\d/, label: "One number" },
  { regex: /[!@#$%^&*(),.?":{}|<>]/, label: "One special character" },
];

export default function ResetPasswordPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [isLoading, setIsLoading] = useState(false);
  const [isValidating, setIsValidating] = useState(true);
  const [isTokenValid, setIsTokenValid] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const token = searchParams.get("token");

  // Validate token on mount
  useEffect(() => {
    async function checkToken() {
      if (!token) {
        setIsValidating(false);
        setIsTokenValid(false);
        return;
      }

      const result = await validateResetToken(token);
      setIsValidating(false);
      setIsTokenValid(result.success && result.data?.valid === true);
    }

    checkToken();
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    // Check password requirements
    const meetsAllRequirements = passwordRequirements.every((req) =>
      req.regex.test(password)
    );
    if (!meetsAllRequirements) {
      toast.error("Password does not meet all requirements");
      return;
    }

    if (!token) {
      toast.error("Invalid reset token");
      return;
    }

    setIsLoading(true);

    const result = await resetPassword(token, password);

    setIsLoading(false);

    if (result.success) {
      setIsSuccess(true);
      toast.success("Password reset successfully!");
    } else {
      toast.error(result.error || "Failed to reset password");
    }
  }

  // Loading state
  if (tenantLoading || isValidating) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted p-4">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">
            {isValidating ? "Validating reset link..." : "Loading..."}
          </p>
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
                Reset Your Password
              </p>
            </>
          ) : (
            <>
              <Link href="/">
                <h1 className="text-3xl font-bold text-primary">SIMS Plus</h1>
              </Link>
              <p className="mt-2 text-muted-foreground">Reset Your Password</p>
            </>
          )}
        </div>

        {/* Invalid Token State */}
        {!isTokenValid && !isSuccess && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
                  <XCircle className="h-8 w-8 text-red-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">Invalid or Expired Link</h2>
                <p className="mb-6 text-muted-foreground">
                  This password reset link is invalid or has expired. Please
                  request a new one.
                </p>
                <div className="space-y-3">
                  <Link href="/forgot-password" className="block">
                    <Button
                      className="w-full"
                      style={{
                        backgroundColor:
                          tenant?.branding?.primary_color || undefined,
                      }}
                    >
                      Request New Link
                    </Button>
                  </Link>
                  <Link href="/login" className="block">
                    <Button variant="ghost" className="w-full">
                      <ArrowLeft className="mr-2 h-4 w-4" />
                      Back to Sign In
                    </Button>
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Success State */}
        {isSuccess && (
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
        )}

        {/* Reset Form */}
        {isTokenValid && !isSuccess && (
          <Card>
            <CardHeader>
              <CardTitle>Create New Password</CardTitle>
              <CardDescription>
                Enter your new password below. Make sure it meets all the
                requirements.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">New Password</Label>
                  <div className="relative">
                    <Input
                      id="password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="Enter new password"
                      required
                      autoComplete="new-password"
                      disabled={isLoading}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Password Requirements */}
                <div className="rounded-lg border bg-muted/50 p-3">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    Password Requirements:
                  </p>
                  <ul className="space-y-1">
                    {passwordRequirements.map((req) => {
                      const isMet = req.regex.test(password);
                      return (
                        <li
                          key={req.label}
                          className={`flex items-center gap-2 text-xs ${
                            isMet ? "text-green-600" : "text-muted-foreground"
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

                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm New Password</Label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      name="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      placeholder="Confirm new password"
                      required
                      autoComplete="new-password"
                      disabled={isLoading}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                    >
                      {showConfirmPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {confirmPassword && password !== confirmPassword && (
                    <p className="text-xs text-red-500">Passwords do not match</p>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={
                    isLoading ||
                    !password ||
                    !confirmPassword ||
                    password !== confirmPassword
                  }
                  style={{
                    backgroundColor: tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Resetting...
                    </>
                  ) : (
                    "Reset Password"
                  )}
                </Button>
              </form>

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
      </div>
    </main>
  );
}
