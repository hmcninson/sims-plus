"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
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
import {
  verifyEmail,
  validateVerificationToken,
  resendVerificationEmail,
} from "@/actions/auth.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { toast } from "sonner";
import {
  Loader2,
  ArrowLeft,
  GraduationCap,
  CheckCircle,
  XCircle,
  Mail,
  RefreshCw,
} from "lucide-react";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [isValidating, setIsValidating] = useState(true);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [isTokenValid, setIsTokenValid] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [showResendForm, setShowResendForm] = useState(false);
  const [email, setEmail] = useState("");
  const [resendSuccess, setResendSuccess] = useState(false);

  const token = searchParams.get("token");

  // Validate and verify token on mount
  useEffect(() => {
    async function processToken() {
      if (!token) {
        setIsValidating(false);
        setIsTokenValid(false);
        return;
      }

      // First validate the token
      const validateResult = await validateVerificationToken(token);

      if (!validateResult.success || !validateResult.data?.valid) {
        setIsValidating(false);
        setIsTokenValid(false);
        return;
      }

      setIsTokenValid(true);
      setIsValidating(false);

      // Auto-verify the email
      setIsVerifying(true);
      const verifyResult = await verifyEmail(token);
      setIsVerifying(false);

      if (verifyResult.success) {
        setIsSuccess(true);
        toast.success("Email verified successfully!");
      } else {
        // Token was valid but verification failed
        setIsTokenValid(false);
        toast.error(verifyResult.error || "Failed to verify email");
      }
    }

    processToken();
  }, [token]);

  async function handleResendVerification(e: React.FormEvent) {
    e.preventDefault();

    if (!email) {
      toast.error("Please enter your email address");
      return;
    }

    setIsResending(true);
    const result = await resendVerificationEmail(email);
    setIsResending(false);

    if (result.success) {
      setResendSuccess(true);
      toast.success("Verification email sent!");
    } else {
      toast.error(result.error || "Failed to send verification email");
    }
  }

  // Loading state
  if (tenantLoading || isValidating || isVerifying) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-muted p-4">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-muted-foreground">
            {isValidating
              ? "Validating verification link..."
              : isVerifying
              ? "Verifying your email..."
              : "Loading..."}
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
                Email Verification
              </p>
            </>
          ) : (
            <>
              <Link href="/">
                <h1 className="text-3xl font-bold text-primary">SIMS Plus</h1>
              </Link>
              <p className="mt-2 text-muted-foreground">Email Verification</p>
            </>
          )}
        </div>

        {/* Success State */}
        {isSuccess && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">Email Verified!</h2>
                <p className="mb-6 text-muted-foreground">
                  Your email address has been verified successfully. You can now
                  sign in to your account.
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

        {/* Invalid/Expired Token State */}
        {!isTokenValid && !isSuccess && !showResendForm && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
                  <XCircle className="h-8 w-8 text-red-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">
                  {token ? "Invalid or Expired Link" : "Verification Required"}
                </h2>
                <p className="mb-6 text-muted-foreground">
                  {token
                    ? "This verification link is invalid or has expired. Please request a new one."
                    : "Please check your email for a verification link, or request a new one below."}
                </p>
                <div className="space-y-3">
                  <Button
                    className="w-full"
                    onClick={() => setShowResendForm(true)}
                    style={{
                      backgroundColor:
                        tenant?.branding?.primary_color || undefined,
                    }}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Resend Verification Email
                  </Button>
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

        {/* Resend Success State */}
        {resendSuccess && (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
                  <Mail className="h-8 w-8 text-blue-600" />
                </div>
                <h2 className="mb-2 text-xl font-semibold">Check Your Email</h2>
                <p className="mb-6 text-muted-foreground">
                  If an account exists with this email address and is not yet
                  verified, you will receive a verification link shortly.
                </p>
                <div className="space-y-3">
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      setResendSuccess(false);
                      setShowResendForm(true);
                      setEmail("");
                    }}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Send Again
                  </Button>
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

        {/* Resend Form */}
        {showResendForm && !resendSuccess && (
          <Card>
            <CardHeader>
              <CardTitle>Resend Verification Email</CardTitle>
              <CardDescription>
                Enter your email address and we&apos;ll send you a new
                verification link.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleResendVerification} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email Address</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="Enter your email"
                    required
                    autoComplete="email"
                    disabled={isResending}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isResending || !email}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isResending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Mail className="mr-2 h-4 w-4" />
                      Send Verification Email
                    </>
                  )}
                </Button>
              </form>

              <div className="mt-6 space-y-3">
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => setShowResendForm(false)}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Go Back
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </main>
  );
}
