"use client";

import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { exitImpersonation } from "@/actions/platform.action";
import { ShieldAlert, LogOut } from "lucide-react";

interface ImpersonationBannerProps {
  tenantSubdomain: string;
}

/**
 * Non-dismissible banner shown at the very top of the school dashboard
 * when a platform admin is impersonating a tenant.
 *
 * The isImpersonation state is determined server-side in the dashboard layout
 * by decoding the JWT payload.
 */
export function ImpersonationBanner({
  tenantSubdomain,
}: ImpersonationBannerProps) {
  const handleExit = useCallback(async () => {
    await exitImpersonation();

    // Redirect to admin portal
    const isDev =
      typeof window !== "undefined" &&
      (window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1");

    if (isDev) {
      window.location.href = `${window.location.protocol}//${window.location.host}/platform/tenants?subdomain=admin`;
    } else {
      window.location.href = "https://admin.simsplus.io/platform/tenants";
    }
  }, []);

  return (
    <div className="sticky top-0 z-50 flex items-center justify-between gap-3 border-b border-amber-600/30 bg-amber-500 px-4 py-2 text-amber-950">
      <div className="flex items-center gap-2 text-sm font-medium">
        <ShieldAlert className="h-4 w-4 shrink-0" />
        <span>
          You are viewing{" "}
          <strong>{tenantSubdomain}.simsplus.io</strong> as Platform Admin
        </span>
      </div>
      <Button
        size="sm"
        variant="outline"
        className="shrink-0 border-amber-700 bg-amber-600 text-amber-950 hover:bg-amber-700"
        onClick={handleExit}
      >
        <LogOut className="mr-1 h-3 w-3" />
        Exit Impersonation
      </Button>
    </div>
  );
}
