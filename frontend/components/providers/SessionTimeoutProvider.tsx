"use client";

import type { ReactNode } from "react";
import { useSessionTimeout } from "@/hooks/use-session-timeout";
import { SessionTimeoutDialog } from "@/components/session-timeout-dialog";
import { logout } from "@/actions/auth.action";
import { clearOfflineData } from "@/lib/offline/db";

interface SessionTimeoutProviderProps {
  children: ReactNode;
}

/**
 * Client component wrapper that adds session timeout tracking to the
 * dashboard layout. Renders the warning dialog when inactivity is detected.
 *
 * Must be placed inside the dashboard layout (Server Component) so it only
 * runs for authenticated users.
 */
export function SessionTimeoutProvider({ children }: SessionTimeoutProviderProps) {
  const { showWarning, remainingSeconds, continueSession } = useSessionTimeout();

  const handleLogout = async () => {
    try {
      // Clear offline data before redirecting
      if (typeof indexedDB !== "undefined") {
        try {
          await clearOfflineData();
        } catch {
          // Best effort
        }
      }
      await logout();
    } catch {
      // Force redirect even if logout fails
      window.location.href = "/login?error=session_expired";
    }
  };

  return (
    <>
      {children}
      <SessionTimeoutDialog
        open={showWarning}
        remainingSeconds={remainingSeconds}
        onContinue={continueSession}
        onLogout={handleLogout}
      />
    </>
  );
}
