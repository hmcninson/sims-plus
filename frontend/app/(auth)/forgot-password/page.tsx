"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
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
import { requestPasswordReset } from "@/actions/auth.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { toast } from "sonner";
import { Loader2, ArrowLeft, GraduationCap, Mail, CheckCircle } from "lucide-react";

export default function ForgotPasswordPage() {
  const { tenant, isLoading: tenantLoading } = useTenant();
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [email, setEmail] = useState("");

  async function handleSubmit(formData: FormData) {
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

        {/* Success State */}
        {isSubmitted ? (
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
          /* Request Form */
          <Card>
            <CardHeader>
              <CardTitle>Forgot Password?</CardTitle>
              <CardDescription>
                Enter your email address and we&apos;ll send you instructions to
                reset your password.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form action={handleSubmit} className="space-y-4">
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
                    backgroundColor: tenant?.branding?.primary_color || undefined,
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
