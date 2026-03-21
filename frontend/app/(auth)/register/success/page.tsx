"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Mail,
  Globe,
  ArrowRight,
  Copy,
  ExternalLink,
  CheckCircle2,
  RefreshCw,
  Loader2,
} from "lucide-react";
import { resendOnboardingVerification } from "@/actions/auth.action";

const RESEND_COOLDOWN_SECONDS = 60;

export default function RegistrationSuccessPage() {
  const searchParams = useSearchParams();
  const subdomain = searchParams.get("school") || "yourschool";
  const portalUrl = `https://${subdomain}.simsplus.io`;

  // Read email from sessionStorage (avoids PII in URL params)
  const [email, setEmail] = useState("");

  useEffect(() => {
    const storedEmail = sessionStorage.getItem("registration_email");
    if (storedEmail) {
      setEmail(storedEmail);
      sessionStorage.removeItem("registration_email");
    }
  }, []);

  const [resendState, setResendState] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [resendMessage, setResendMessage] = useState("");
  const [copied, setCopied] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Countdown timer for resend cooldown
  useEffect(() => {
    if (cooldown <= 0) return;

    const intervalId = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(intervalId);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(intervalId);
  }, [cooldown]);

  async function handleResend() {
    if (!email || cooldown > 0) return;

    setResendState("loading");
    setResendMessage("");

    const result = await resendOnboardingVerification(email, subdomain);

    if (result.success) {
      setResendState("success");
      setResendMessage(
        result.data?.message || "Verification email sent! Check your inbox."
      );
      // Start cooldown after successful resend
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } else {
      setResendState("error");
      setResendMessage(result.error || "Failed to resend. Please try again.");
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(portalUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available
    }
  }

  const isResendDisabled = resendState === "loading" || cooldown > 0;

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-lg">
        {/* Success Icon */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <CheckCircle2 className="h-10 w-10 text-green-600" />
          </div>
          <h1 className="text-3xl font-bold text-foreground">
            Your School is Ready!
          </h1>
          <p className="mt-2 text-muted-foreground">
            Welcome to SIMS Plus. Your portal has been created.
          </p>
        </div>

        {/* Email Verification Notice — prominent, required step */}
        <Card className="mb-6 border-amber-300 bg-amber-50">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100">
                <Mail className="h-5 w-5 text-amber-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-amber-900">
                  Verify your email to get started
                </h3>
                <p className="mt-1 text-sm text-amber-800">
                  We&apos;ve sent a verification link to{" "}
                  {email ? (
                    <strong className="font-semibold">{email}</strong>
                  ) : (
                    "your email address"
                  )}
                  . You must verify your email before you can log in. Check your
                  spam folder if you don&apos;t see it.
                </p>

                {/* Resend button */}
                {email && (
                  <div className="mt-4">
                    {resendState === "success" && cooldown > 0 ? (
                      <div>
                        <p className="flex items-center gap-2 text-sm font-medium text-green-700">
                          <CheckCircle2 className="h-4 w-4" />
                          {resendMessage}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          You can resend in {cooldown}s
                        </p>
                      </div>
                    ) : resendState === "success" ? (
                      <div>
                        <p className="flex items-center gap-2 text-sm font-medium text-green-700">
                          <CheckCircle2 className="h-4 w-4" />
                          {resendMessage}
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleResend}
                          className="mt-2 border-amber-400 bg-white text-amber-900 hover:bg-amber-100"
                        >
                          <RefreshCw className="mr-2 h-3.5 w-3.5" />
                          Resend Verification Email
                        </Button>
                      </div>
                    ) : resendState === "error" ? (
                      <div>
                        <p className="mb-2 text-sm text-red-700">
                          {resendMessage}
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleResend}
                          disabled={isResendDisabled}
                          className="border-amber-400 bg-white text-amber-900 hover:bg-amber-100"
                        >
                          <RefreshCw className="mr-2 h-3.5 w-3.5" />
                          Try again
                        </Button>
                      </div>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResend}
                        disabled={isResendDisabled}
                        className="border-amber-400 bg-white text-amber-900 hover:bg-amber-100"
                      >
                        {resendState === "loading" ? (
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="mr-2 h-3.5 w-3.5" />
                        )}
                        {cooldown > 0
                          ? `Resend in ${cooldown}s`
                          : "Resend Verification Email"}
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Portal URL Card */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <Globe className="h-4 w-4" />
              Your school portal
            </div>
            <div className="flex items-center justify-between rounded-lg border bg-muted/50 p-4">
              <code className="text-lg font-semibold text-primary">
                {portalUrl}
              </code>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  title={copied ? "Copied!" : "Copy URL"}
                  onClick={handleCopy}
                >
                  {copied ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
                <Button variant="ghost" size="icon" asChild title="Open portal">
                  <a href={portalUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Next Steps */}
        <div className="mb-8 rounded-lg border bg-card p-6">
          <h3 className="mb-4 font-semibold text-foreground">
            What&apos;s next?
          </h3>
          <ol className="space-y-3 text-sm text-muted-foreground">
            <li className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                1
              </span>
              <span className="font-medium text-foreground">
                Check your email and click the verification link
              </span>
            </li>
            <li className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                2
              </span>
              <span>
                Login at{" "}
                <code className="rounded bg-muted px-1">
                  {subdomain}.simsplus.io
                </code>
              </span>
            </li>
            <li className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                3
              </span>
              <span>Complete your school setup (add logo, colors, details)</span>
            </li>
            <li className="flex items-start gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                4
              </span>
              <span>Start adding your students and staff</span>
            </li>
          </ol>
        </div>

        {/* Trial Info */}
        <div className="mb-6 rounded-lg bg-green-50 p-4 text-center text-sm text-green-800">
          Your <strong>90-day free trial</strong> has started. No credit card
          required.
        </div>

        {/* CTA Button */}
        <Button asChild className="w-full" size="lg">
          <a href={portalUrl} target="_blank" rel="noopener noreferrer">
            Go to Your Portal
            <ArrowRight className="ml-2 h-4 w-4" />
          </a>
        </Button>

        {/* Back to Home */}
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link href="/" className="text-primary hover:underline">
            Back to home
          </Link>
        </p>
      </div>
    </main>
  );
}
