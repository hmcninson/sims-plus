"use client";

import { usePathname } from "next/navigation";
import { ShieldAlert, Mail } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

type ExpiredCode =
  | "TRIAL_EXPIRED"
  | "SUBSCRIPTION_EXPIRED"
  | "TRIAL_GRACE_PERIOD"
  | "SUBSCRIPTION_GRACE_PERIOD"
  | "TENANT_SUSPENDED";

interface ExpiredGateProps {
  code: ExpiredCode;
  graceDaysRemaining?: number;
}

export function ExpiredGate({ code, graceDaysRemaining }: ExpiredGateProps) {
  const pathname = usePathname();

  // H3: Never block access to the subscription page itself
  if (pathname.startsWith("/settings/subscription")) {
    return null;
  }

  const isGracePeriod = code.includes("GRACE_PERIOD");
  const isTrial = code.includes("TRIAL");
  const isSuspended = code === "TENANT_SUSPENDED";

  let title: string;
  let description: string;

  if (isSuspended) {
    title = "Account Suspended";
    description =
      "Your school account has been suspended. Please contact support to resolve this issue.";
  } else if (isGracePeriod) {
    const daysLabel = graceDaysRemaining === 1 ? "day" : "days";
    title = isTrial ? "Trial Expired" : "Subscription Expired";
    description = `You have ${graceDaysRemaining} ${daysLabel} of read-only access remaining. Upgrade now to regain full access to all features.`;
  } else {
    title = isTrial ? "Trial Expired" : "Subscription Expired";
    description = `Your ${isTrial ? "free trial" : "subscription"} has expired. Choose a plan to continue using SIMS Plus.`;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-md rounded-lg border bg-card p-8 text-center shadow-lg">
        <ShieldAlert className="mx-auto h-12 w-12 text-destructive" />
        <h2 className="mt-4 text-xl font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        <div className="mt-6 flex flex-col gap-2">
          {!isSuspended && (
            <Button asChild className="w-full">
              <Link href="/settings/subscription">Choose a Plan</Link>
            </Button>
          )}
          <Button variant="ghost" className="w-full" asChild>
            <a href="mailto:support@simsplus.io">
              <Mail className="mr-2 h-4 w-4" />
              Contact Support
            </a>
          </Button>
        </div>
      </div>
    </div>
  );
}
