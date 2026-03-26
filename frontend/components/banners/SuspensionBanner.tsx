"use client";

import { ShieldAlert, Mail } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface SuspensionBannerProps {
  /** Override the default suspension message */
  message?: string;
}

/**
 * Full-page suspension notice displayed when a tenant account has been
 * suspended. Replaces the login form entirely so users understand why
 * they cannot sign in.
 */
export function SuspensionBanner({
  message = "This school account has been suspended. Contact your administrator for more information.",
}: SuspensionBannerProps) {
  return (
    <Card className="w-full max-w-md border-destructive/50">
      <CardHeader className="text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
          <ShieldAlert className="h-8 w-8 text-destructive" />
        </div>
        <CardTitle className="text-xl text-destructive">
          Account Suspended
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6 text-center">
        <p className="text-sm text-muted-foreground">{message}</p>
        <Button variant="outline" className="w-full" asChild>
          <a href="mailto:support@simsplus.io">
            <Mail className="mr-2 h-4 w-4" />
            Contact Support
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}
