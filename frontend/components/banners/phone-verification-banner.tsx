"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Phone, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

const DISMISS_KEY = "phone-verification-banner-dismissed";

interface PhoneVerificationBannerProps {
  /** The settings page path where user can verify phone */
  settingsPath?: string;
}

/**
 * Dismissible banner prompting users with unverified phone numbers
 * to verify their phone. Uses sessionStorage so it only shows once
 * per browser session after dismissal.
 *
 * This is a client component that should receive user data from a parent.
 * The parent (server component or layout) should conditionally render
 * this only when the user has an unverified phone.
 */
export function PhoneVerificationBanner({
  settingsPath = "/settings/account",
}: PhoneVerificationBannerProps) {
  const [isDismissed, setIsDismissed] = useState(true); // Start hidden to avoid flash

  useEffect(() => {
    // Check sessionStorage on mount
    const dismissed = sessionStorage.getItem(DISMISS_KEY);
    setIsDismissed(dismissed === "true");
  }, []);

  function handleDismiss() {
    sessionStorage.setItem(DISMISS_KEY, "true");
    setIsDismissed(true);
  }

  if (isDismissed) {
    return null;
  }

  return (
    <Alert className="mb-4 border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
      <Phone className="h-4 w-4 text-amber-600 dark:text-amber-400" />
      <AlertTitle className="text-amber-800 dark:text-amber-200">
        Verify your phone number
      </AlertTitle>
      <AlertDescription className="flex items-center justify-between gap-2">
        <span className="text-amber-700 dark:text-amber-300">
          Verify your phone to receive SMS notifications and updates.{" "}
          <Link
            href={settingsPath}
            className="font-medium underline hover:no-underline"
          >
            Verify now
          </Link>
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 shrink-0 text-amber-600 hover:text-amber-800 hover:bg-amber-100 dark:text-amber-400 dark:hover:text-amber-200 dark:hover:bg-amber-900"
          onClick={handleDismiss}
          aria-label="Dismiss phone verification banner"
        >
          <X className="h-4 w-4" />
        </Button>
      </AlertDescription>
    </Alert>
  );
}
