"use client";

/**
 * SIMS Plus - Applicant Email Verification Page
 *
 * Auto-calls verifyApplicantEmail(token) on mount.
 * Reads `token` from URL search params.
 * Path: {school}.simsplus.io/apply/verify-email?token=...
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { verifyApplicantEmail } from "@/actions/applicant.action";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

type VerifyState = "loading" | "success" | "error";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<VerifyState>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setErrorMsg("No verification token provided.");
      return;
    }

    let cancelled = false;

    verifyApplicantEmail(token).then((result) => {
      if (cancelled) return;
      if (result.success) {
        setState("success");
      } else {
        setState("error");
        setErrorMsg(result.error || "Verification failed.");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {state === "loading" && (
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
          )}
          {state === "success" && (
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
          )}
          {state === "error" && (
            <XCircle className="mx-auto h-12 w-12 text-red-600" />
          )}
          <CardTitle className="mt-4">
            {state === "loading" && "Verifying your email..."}
            {state === "success" && "Email Verified"}
            {state === "error" && "Verification Failed"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center">
          {state === "success" && (
            <>
              <p className="mb-4 text-sm text-muted-foreground">
                Your email has been verified. You can now sign in to your
                account.
              </p>
              <Button asChild>
                <Link href="/apply/login?msg=email_verified">
                  Sign In
                </Link>
              </Button>
            </>
          )}
          {state === "error" && (
            <>
              <p className="mb-4 text-sm text-muted-foreground">{errorMsg}</p>
              <Button asChild variant="outline">
                <Link href="/apply/login">Go to Login</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
