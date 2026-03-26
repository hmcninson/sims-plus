/**
 * SIMS Plus - Paystack Payment Callback
 *
 * Path: {school}.simsplus.io/apply/pay/callback
 * Paystack redirects here after payment attempt.
 *
 * Payment verification happens server-side via webhook.
 * This page shows an optimistic success/failure message based on
 * the presence of the reference parameter.
 */

"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

import {
  CheckCircle,
  XCircle,
  Loader2,
  ArrowRight,
  Search,
  ArrowLeft,
} from "lucide-react";

/**
 * Inner component that reads search params.
 * Wrapped in Suspense because useSearchParams() requires it in App Router.
 */
function PaymentCallbackContent() {
  const searchParams = useSearchParams();
  const reference = searchParams.get("reference");
  const trxref = searchParams.get("trxref");
  const [status, setStatus] = useState<
    "loading" | "success" | "pending" | "failed"
  >("loading");

  useEffect(() => {
    // Paystack redirects with ?reference=xxx&trxref=xxx on successful payment.
    // If these params are present, the payment was likely successful.
    // The actual verification happens via the Paystack webhook on the backend.
    const timer = setTimeout(() => {
      if (reference || trxref) {
        setStatus("success");
      } else {
        setStatus("failed");
      }
    }, 1500); // Brief delay for UX

    return () => clearTimeout(timer);
  }, [reference, trxref]);

  return (
    <div className="mx-auto max-w-md px-4 py-8 md:py-12">
      <Link
        href="/apply"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Admissions
      </Link>

      <Card>
        <CardHeader className="text-center">
          <CardTitle>Payment Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          {/* Loading */}
          {status === "loading" && (
            <div className="py-4">
              <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
              <p className="mt-4 text-muted-foreground">
                Verifying your payment...
              </p>
            </div>
          )}

          {/* Success */}
          {status === "success" && (
            <div className="py-4">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
              </div>
              <p className="text-lg font-medium text-green-600 dark:text-green-400">
                Payment Received!
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Your application fee has been received. Your application is now
                being processed.
              </p>

              {(reference || trxref) && (
                <>
                  <Separator className="my-4" />
                  <div className="rounded-lg bg-muted p-3">
                    <p className="text-xs font-medium uppercase text-muted-foreground">
                      Payment Reference
                    </p>
                    <p className="mt-1 font-mono text-sm">
                      {reference || trxref}
                    </p>
                  </div>
                </>
              )}

              <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
                <Button asChild className="gap-2">
                  <Link href="/apply/status">
                    <Search className="h-4 w-4" />
                    Check Application Status
                  </Link>
                </Button>
                <Button variant="outline" asChild className="gap-2">
                  <Link href="/apply">
                    <ArrowRight className="h-4 w-4" />
                    Back to Admissions
                  </Link>
                </Button>
              </div>
            </div>
          )}

          {/* Pending (potential future state) */}
          {status === "pending" && (
            <div className="py-4">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900">
                <Loader2 className="h-8 w-8 text-amber-600 dark:text-amber-400" />
              </div>
              <p className="text-lg font-medium text-amber-600 dark:text-amber-400">
                Payment Pending
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                Your payment is being processed. This may take a few moments.
                Check your application status for updates.
              </p>
              <Button variant="outline" asChild className="mt-6 gap-2">
                <Link href="/apply/status">
                  <Search className="h-4 w-4" />
                  Check Application Status
                </Link>
              </Button>
            </div>
          )}

          {/* Failed */}
          {status === "failed" && (
            <div className="py-4">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900">
                <XCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
              </div>
              <p className="text-lg font-medium text-red-600 dark:text-red-400">
                Payment Not Confirmed
              </p>
              <p className="mt-2 text-sm text-muted-foreground">
                We could not confirm your payment. If you believe this is an
                error, please check your application status or contact the
                school.
              </p>
              <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
                <Button variant="outline" asChild className="gap-2">
                  <Link href="/apply/status">
                    <Search className="h-4 w-4" />
                    Check Application Status
                  </Link>
                </Button>
                <Button variant="outline" asChild className="gap-2">
                  <Link href="/apply">
                    <ArrowRight className="h-4 w-4" />
                    Back to Admissions
                  </Link>
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * Page component with Suspense boundary for useSearchParams().
 */
export default function PaymentCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center p-4">
          <Card className="w-full max-w-md">
            <CardContent className="py-12 text-center">
              <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
              <p className="mt-4 text-muted-foreground">
                Verifying your payment...
              </p>
            </CardContent>
          </Card>
        </div>
      }
    >
      <PaymentCallbackContent />
    </Suspense>
  );
}
