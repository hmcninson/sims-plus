"use client";

/**
 * SIMS Plus - Applicant Forgot Password Page
 *
 * Email input + Turnstile captcha. Calls applicantForgotPassword().
 * Always shows a success message to prevent email enumeration.
 * Path: {school}.simsplus.io/apply/forgot-password
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { applicantForgotPassword } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { Loader2, ArrowLeft, Mail } from "lucide-react";

const forgotSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
});

type ForgotFormData = z.infer<typeof forgotSchema>;

export default function ApplicantForgotPasswordPage() {
  const { tenant } = useTenant();
  const [success, setSuccess] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const turnstileRef = useRef<HTMLDivElement>(null);

  const form = useForm<ForgotFormData>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: "" },
  });

  const { isSubmitting } = form.formState;

  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      (window as unknown as Record<string, unknown>).turnstile &&
      turnstileRef.current &&
      turnstileRef.current.childNodes.length === 0
    ) {
      const turnstile = (window as unknown as Record<string, unknown>).turnstile as {
        render: (el: HTMLElement, opts: Record<string, unknown>) => void;
      };
      turnstile.render(turnstileRef.current, {
        sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "",
        callback: (token: string) => setTurnstileToken(token),
        "expired-callback": () => setTurnstileToken(null),
      });
    }
  }, []);

  async function onSubmit(values: ForgotFormData) {
    if (!turnstileToken) return;
    await applicantForgotPassword(values.email, turnstileToken);
    // Always show success to prevent enumeration
    setSuccess(true);
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <Mail className="mx-auto h-12 w-12 text-primary" />
            <CardTitle className="mt-4">Check Your Email</CardTitle>
            <CardDescription>
              If an account with that email exists, we have sent a password
              reset link. Please check your inbox and spam folder.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button asChild variant="outline">
              <Link href="/apply/login">Back to Login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Forgot Password</CardTitle>
            <CardDescription>
              Enter your email address and we will send you a link to reset
              your password.
            </CardDescription>
          </CardHeader>
          <CardContent>
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
                      Sending...
                    </>
                  ) : (
                    "Send Reset Link"
                  )}
                </Button>
              </form>
            </Form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              <Link
                href="/apply/login"
                className="inline-flex items-center gap-1 hover:underline"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Login
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
