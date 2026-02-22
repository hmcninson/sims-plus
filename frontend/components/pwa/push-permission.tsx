"use client";

import { useState, useEffect } from "react";
import { Bell, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { subscribeToPush } from "@/lib/push";

const PROMPT_KEY = "sims-push-prompt-dismissed";
const PROMPT_DAYS = 14;

/**
 * Non-intrusive push notification permission prompt.
 *
 * Only shown when:
 * - The browser supports Notification API
 * - Permission is still "default" (not yet granted or denied)
 * - The user hasn't dismissed the prompt in the last 14 days
 *
 * Appears after a 5-second delay to avoid overwhelming the user
 * on page load.
 */
export function PushPermissionPrompt() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Don't show if notifications are unsupported or already decided
    if (!("Notification" in window) || Notification.permission !== "default") {
      return;
    }

    // Respect the dismiss cooldown
    const dismissedAt = localStorage.getItem(PROMPT_KEY);
    if (dismissedAt) {
      const daysSince =
        (Date.now() - parseInt(dismissedAt, 10)) / (1000 * 60 * 60 * 24);
      if (daysSince < PROMPT_DAYS) return;
    }

    // Delay the prompt so it doesn't appear immediately on page load
    const timer = setTimeout(() => setShow(true), 5000);
    return () => clearTimeout(timer);
  }, []);

  const handleEnable = async () => {
    await subscribeToPush();
    setShow(false);
  };

  const handleDismiss = () => {
    localStorage.setItem(PROMPT_KEY, Date.now().toString());
    setShow(false);
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-md rounded-lg border bg-background p-4 shadow-lg sm:left-auto sm:right-4 sm:max-w-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300">
          <Bell className="h-5 w-5" />
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium">Enable notifications</p>
          <p className="text-xs text-muted-foreground">
            Get alerts for attendance, important updates, and announcements.
          </p>
          <div className="mt-2 flex gap-2">
            <Button size="sm" onClick={handleEnable} className="h-7 text-xs">
              Enable
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleDismiss}
              className="h-7 text-xs"
            >
              Not now
            </Button>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
