/**
 * SIMS Plus - Application Status Check
 *
 * Path: {school}.simsplus.io/apply/status
 * Allows applicants to check their application status using tracking code.
 */

"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";

import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { checkApplicationStatus } from "@/actions/admissions.action";

import type { ApplicationStatusCheck } from "@/types/admissions.type";
import {
  Search,
  Loader2,
  ArrowLeft,
  Calendar,
  Clock,
  User,
} from "lucide-react";

export default function StatusCheckPage() {
  const [trackingCode, setTrackingCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ApplicationStatusCheck | null>(null);
  const [notFound, setNotFound] = useState(false);

  async function handleCheck() {
    const code = trackingCode.trim();
    if (!code) {
      toast.error("Please enter your tracking code");
      return;
    }

    setLoading(true);
    setNotFound(false);

    const response = await checkApplicationStatus(code);

    if (response.success) {
      setResult(response.data);
      setNotFound(false);
    } else {
      setResult(null);
      setNotFound(true);
      toast.error(response.error || "Application not found");
    }
    setLoading(false);
  }

  return (
    <div className="mx-auto max-w-md px-4 py-8 md:py-12">
      {/* Back link */}
      <Link
        href="/apply"
        className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Admissions
      </Link>

      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Search className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>Check Application Status</CardTitle>
          <CardDescription>
            Enter the tracking code you received when you submitted your
            application.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tracking-code">Tracking Code</Label>
            <Input
              id="tracking-code"
              placeholder="e.g. APP-2026-ABCDEF"
              value={trackingCode}
              onChange={(e) => {
                setTrackingCode(e.target.value.toUpperCase());
                if (notFound) setNotFound(false);
              }}
              onKeyDown={(e) => e.key === "Enter" && handleCheck()}
              disabled={loading}
              autoComplete="off"
              className="font-mono tracking-wider"
            />
          </div>

          <Button
            onClick={handleCheck}
            disabled={loading || !trackingCode.trim()}
            className="w-full gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Check Status
              </>
            )}
          </Button>

          {/* Not found message */}
          {notFound && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/5 p-3 text-center text-sm text-destructive">
              No application found with this tracking code. Please check the code
              and try again.
            </div>
          )}

          {/* Result display */}
          {result && (
            <>
              <Separator className="my-2" />

              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <User className="h-3.5 w-3.5" />
                    Applicant
                  </span>
                  <span className="font-medium">
                    {result.applicant_first_name}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <ApplicationStatusBadge status={result.status} />
                </div>

                {result.submitted_at && (
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Calendar className="h-3.5 w-3.5" />
                      Submitted
                    </span>
                    <span className="text-sm">
                      {new Date(result.submitted_at).toLocaleDateString(
                        "en-GB",
                        {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        }
                      )}
                    </span>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    Last Updated
                  </span>
                  <span className="text-sm">
                    {new Date(result.last_updated_at).toLocaleDateString(
                      "en-GB",
                      {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                      }
                    )}
                  </span>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Help text */}
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Lost your tracking code? Contact the school administration for
        assistance.
      </p>
    </div>
  );
}
