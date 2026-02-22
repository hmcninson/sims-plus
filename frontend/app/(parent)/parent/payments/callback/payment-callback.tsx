"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Receipt,
  Home,
  AlertCircle,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatGHS } from "@/lib/format";
import { verifyPayment } from "@/actions/parent.action";
import type { PaymentVerifyResponse } from "@/types/parent.type";

// =========================
// Main Component
// =========================

interface PaymentCallbackViewProps {
  reference: string | null;
}

export function PaymentCallbackView({ reference }: PaymentCallbackViewProps) {
  const [verifying, setVerifying] = useState(true);
  const [result, setResult] = useState<PaymentVerifyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function verify() {
      if (!reference) {
        setError("No payment reference was provided.");
        setVerifying(false);
        return;
      }

      setVerifying(true);
      const res = await verifyPayment(reference);

      if (res.success) {
        setResult(res.data);
      } else {
        setError(res.error);
      }
      setVerifying(false);
    }

    verify();
  }, [reference]);

  // Loading state
  if (verifying) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <h2 className="text-lg font-semibold">Verifying your payment...</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Please wait while we confirm your payment with the provider. This may
          take a few seconds.
        </p>
      </div>
    );
  }

  // Error state
  if (error && !result) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <h2 className="text-lg font-semibold">Verification Failed</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          {error}
        </p>
        <div className="flex gap-3">
          <Button variant="outline" asChild>
            <Link href="/parent/dashboard">
              <Home className="h-4 w-4 mr-2" />
              Dashboard
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/parent/payments">
              <Receipt className="h-4 w-4 mr-2" />
              Payments
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  // Result state
  if (!result) return null;

  const statusConfig = {
    success: {
      icon: CheckCircle2,
      iconColor: "text-green-600",
      bgColor: "bg-green-50 dark:bg-green-950/30",
      borderColor: "border-green-500/30",
      title: "Payment Successful",
      description:
        "Your payment has been processed and recorded. A receipt has been sent to your email.",
    },
    failed: {
      icon: XCircle,
      iconColor: "text-red-600",
      bgColor: "bg-red-50 dark:bg-red-950/30",
      borderColor: "border-red-500/30",
      title: "Payment Failed",
      description:
        "Your payment could not be processed. No amount was charged. Please try again or use a different payment method.",
    },
    pending: {
      icon: Clock,
      iconColor: "text-amber-600",
      bgColor: "bg-amber-50 dark:bg-amber-950/30",
      borderColor: "border-amber-500/30",
      title: "Payment Pending",
      description:
        "Your payment is being processed. This may take a few minutes. You will receive a confirmation once it is complete.",
    },
  };

  const config = statusConfig[result.status];
  const StatusIcon = config.icon;

  return (
    <div className="max-w-lg mx-auto space-y-6 py-8">
      {/* Status Card */}
      <Card className={cn(config.borderColor, config.bgColor)}>
        <CardContent className="flex flex-col items-center text-center py-8 gap-4">
          <StatusIcon className={cn("h-16 w-16", config.iconColor)} />
          <div>
            <h1 className="text-xl font-bold">{config.title}</h1>
            <p className="text-sm text-muted-foreground mt-2 max-w-sm">
              {config.description}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Payment Details */}
      <Card>
        <CardContent className="py-4">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Invoice</dt>
              <dd className="font-medium">{result.invoice_number}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Amount</dt>
              <dd className="font-bold text-base">
                {formatGHS(result.amount)}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Method</dt>
              <dd>
                <Badge variant="outline" className="capitalize text-xs">
                  {result.method.replace("_", " ")}
                </Badge>
              </dd>
            </div>
            {result.receipt_number && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Receipt</dt>
                <dd className="font-medium">{result.receipt_number}</dd>
              </div>
            )}
            {reference && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Reference</dt>
                <dd className="font-mono text-xs">{reference}</dd>
              </div>
            )}
            {result.status === "success" && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Remaining Balance</dt>
                <dd
                  className={cn(
                    "font-semibold",
                    result.balance_remaining > 0
                      ? "text-amber-600"
                      : "text-green-600"
                  )}
                >
                  {formatGHS(result.balance_remaining)}
                </dd>
              </div>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-3">
        <Button asChild className="flex-1">
          <Link href="/parent/dashboard">
            <Home className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Link>
        </Button>
        <Button variant="outline" asChild className="flex-1">
          <Link href="/parent/payments">
            <Receipt className="h-4 w-4 mr-2" />
            View All Payments
          </Link>
        </Button>
      </div>

      {/* Retry button for failed payments */}
      {result.status === "failed" && (
        <p className="text-xs text-muted-foreground text-center">
          If you continue to experience issues, please contact the school
          finance office for assistance.
        </p>
      )}

      {/* Pending notice */}
      {result.status === "pending" && (
        <Card className="border-blue-500/30 bg-blue-50/50 dark:bg-blue-950/20">
          <CardContent className="py-3 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
            <p className="text-sm text-muted-foreground">
              For Mobile Money payments, please check your phone for a payment
              prompt and approve the transaction. The payment status will update
              automatically once confirmed.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
