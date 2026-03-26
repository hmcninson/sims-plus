"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Shield } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MFAEnforcementBannerProps {
  /** Whether the tenant requires MFA for admin roles */
  requireMfa: boolean;
  /** Current user's role */
  userRole: string;
  /** Whether the user has MFA enabled */
  mfaEnabled: boolean;
}

/** Roles that must enable MFA when enforcement is on */
const MFA_REQUIRED_ROLES = [
  "school_admin",
  "academic_head",
  "finance_officer",
  "hr_officer",
  "chain_admin",
  "platform_admin",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Non-dismissible banner shown when the tenant requires MFA for admin roles
 * and the current user has not yet enabled it.
 *
 * Also auto-redirects to account settings with the setup_mfa=required param
 * so the MFA setup dialog opens automatically.
 */
export function MFAEnforcementBanner({
  requireMfa,
  userRole,
  mfaEnabled,
}: MFAEnforcementBannerProps) {
  const router = useRouter();

  const shouldEnforce =
    requireMfa &&
    MFA_REQUIRED_ROLES.includes(userRole) &&
    !mfaEnabled;

  // Auto-redirect to settings after a brief delay on first render
  useEffect(() => {
    if (shouldEnforce) {
      // Only redirect if not already on the settings page
      if (!window.location.pathname.includes("/settings/account")) {
        const timeout = setTimeout(() => {
          router.push("/settings/account?setup_mfa=required");
        }, 3000);
        return () => clearTimeout(timeout);
      }
    }
  }, [shouldEnforce, router]);

  if (!shouldEnforce) return null;

  return (
    <Alert className="mx-4 mt-2 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
      <Shield className="h-4 w-4" />
      <AlertTitle>Two-factor authentication required</AlertTitle>
      <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span>
          Your administrator requires 2FA for your role. Please set up
          two-factor authentication to continue using the system.
        </span>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0 border-amber-600 text-amber-900 hover:bg-amber-100 dark:border-amber-500 dark:text-amber-200 dark:hover:bg-amber-900"
          onClick={() =>
            router.push("/settings/account?setup_mfa=required")
          }
        >
          Set up 2FA now
        </Button>
      </AlertDescription>
    </Alert>
  );
}
