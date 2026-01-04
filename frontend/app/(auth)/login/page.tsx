"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/actions/auth.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { toast } from "sonner";
import { Loader2, AlertCircle, GraduationCap } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading, error: tenantError } = useTenant();
  const [isLoading, setIsLoading] = useState(false);

  // Check for error params
  const errorParam = searchParams.get("error");
  const messageParam = searchParams.get("message");

  async function handleSubmit(formData: FormData) {
    setIsLoading(true);

    const result = await login({
      email: formData.get("email") as string,
      password: formData.get("password") as string,
    });

    setIsLoading(false);

    if (result.success) {
      toast.success("Welcome back!");
      router.push("/dashboard");
    } else {
      toast.error(result.error || "Login failed");
    }
  }

  // Apply tenant branding color
  useEffect(() => {
    if (tenant?.branding?.primary_color) {
      document.documentElement.style.setProperty(
        "--tenant-primary",
        tenant.branding.primary_color
      );
    }
  }, [tenant]);

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
        {/* Error Alert */}
        {(errorParam || tenantError) && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <p>{messageParam || tenantError || "An error occurred. Please try again."}</p>
          </div>
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

        {/* Login Form */}
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

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  disabled={isLoading}
                />
              </div>

              <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    name="remember"
                    className="h-4 w-4 rounded border-input"
                    disabled={isLoading}
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
                disabled={isLoading}
                style={{
                  backgroundColor: tenant?.branding?.primary_color || undefined,
                }}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  "Sign In"
                )}
              </Button>
            </form>

            {/* Registration link - only show on main site */}
            {!tenant && (
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{" "}
                <Link href="/register" className="font-medium text-primary hover:underline">
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
