"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, X, ArrowRight, Clock } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface TrialBannerProps {
  initialStatus: {
    plan: string;
    status: string;
    days_remaining: number | null;
  };
}

export function TrialBanner({ initialStatus }: TrialBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("trial-banner-dismissed") === "true") {
      setDismissed(true);
    }
  }, []);

  // Only show for trial tenants with a defined days_remaining
  if (initialStatus.plan !== "trial") return null;
  if (initialStatus.days_remaining === null) return null;
  if (dismissed) return null;

  const days = initialStatus.days_remaining;
  const canDismiss = days > 3;

  // Color coding: blue >7 days, amber 3-7 days, red <=3 days
  let bannerClasses: string;
  let iconClasses: string;
  let ButtonIcon = Clock;

  if (days <= 3) {
    bannerClasses = "bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200";
    iconClasses = "text-red-600 dark:text-red-400";
    ButtonIcon = AlertTriangle;
  } else if (days <= 7) {
    bannerClasses = "bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-950 dark:border-amber-800 dark:text-amber-200";
    iconClasses = "text-amber-600 dark:text-amber-400";
    ButtonIcon = AlertTriangle;
  } else {
    bannerClasses = "bg-blue-50 border-blue-200 text-blue-800 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-200";
    iconClasses = "text-blue-600 dark:text-blue-400";
  }

  const handleDismiss = () => {
    sessionStorage.setItem("trial-banner-dismissed", "true");
    setDismissed(true);
  };

  const message =
    days > 0
      ? `Your free trial expires in ${days} day${days !== 1 ? "s" : ""}. Upgrade to keep using SIMS Plus.`
      : "Your free trial has expired. Upgrade to continue using SIMS Plus.";

  return (
    <div
      className={`${bannerClasses} border-b px-4 py-2 flex items-center justify-between text-sm`}
      role="alert"
    >
      <div className="flex items-center gap-2 min-w-0">
        <ButtonIcon className={`h-4 w-4 shrink-0 ${iconClasses}`} />
        <span className="truncate">{message}</span>
      </div>
      <div className="flex items-center gap-2 shrink-0 ml-2">
        <Button size="sm" variant="outline" className="h-7 text-xs" asChild>
          <Link href="/settings/subscription">
            Upgrade Now
            <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
        {canDismiss && (
          <button
            onClick={handleDismiss}
            className="p-1 hover:opacity-70 rounded"
            aria-label="Dismiss trial banner"
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  );
}
