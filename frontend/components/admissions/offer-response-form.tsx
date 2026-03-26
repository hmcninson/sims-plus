"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Download,
  Loader2,
  GraduationCap,
  Calendar,
  FileText,
} from "lucide-react";
import {
  getApplicantOfferDetails,
  respondToApplicantOffer,
} from "@/actions/applicant.action";
import type { OfferDetail, OfferResponse } from "@/types/admissions.type";

interface OfferResponseFormProps {
  applicationId: string;
}

export function OfferResponseForm({ applicationId }: OfferResponseFormProps) {
  const [offer, setOffer] = useState<OfferDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Confirmation dialogs
  const [confirmAction, setConfirmAction] = useState<OfferResponse | null>(
    null
  );

  const loadOffer = useCallback(async () => {
    setLoading(true);
    const result = await getApplicantOfferDetails(applicationId);
    if (result.success && result.data) {
      setOffer(result.data);
    } else {
      setError(result.error || "Failed to load offer details");
    }
    setLoading(false);
  }, [applicationId]);

  useEffect(() => {
    loadOffer();
  }, [loadOffer]);

  async function handleRespond() {
    if (!confirmAction || !offer) return;

    setSubmitting(true);
    const result = await respondToApplicantOffer(
      applicationId,
      confirmAction,
      notes || undefined
    );

    if (result.success && result.data) {
      setOffer(result.data);
      toast.success(
        confirmAction === "accepted"
          ? "Congratulations! You have accepted the offer."
          : "The offer has been declined."
      );
      setNotes("");
    } else {
      toast.error(result.error);
    }
    setSubmitting(false);
    setConfirmAction(null);
  }

  // Calculate deadline info
  function getDeadlineInfo(): {
    text: string;
    daysLeft: number;
    isUrgent: boolean;
  } | null {
    if (!offer?.response_deadline) return null;
    const deadline = new Date(offer.response_deadline);
    const now = new Date();
    const diffMs = deadline.getTime() - now.getTime();
    const daysLeft = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

    if (daysLeft < 0) {
      return { text: "Expired", daysLeft, isUrgent: true };
    }
    if (daysLeft === 0) {
      return { text: "Due today", daysLeft, isUrgent: true };
    }
    if (daysLeft === 1) {
      return { text: "1 day remaining", daysLeft, isUrgent: true };
    }
    return {
      text: `${daysLeft} days remaining`,
      daysLeft,
      isUrgent: daysLeft <= 3,
    };
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  if (error || !offer) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FileText className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
          <p className="text-muted-foreground">{error || "Offer not found"}</p>
        </CardContent>
      </Card>
    );
  }

  const hasResponded = offer.offer_response !== null;
  const deadlineInfo = getDeadlineInfo();

  // Already responded -- show status
  if (hasResponded) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GraduationCap className="h-4 w-4" />
            Offer Response
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border p-4 space-y-3">
            <div className="flex items-center gap-3">
              {offer.offer_response === "accepted" ? (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                  <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-900">
                  <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
              )}
              <div>
                <p className="font-semibold">
                  {offer.offer_response === "accepted"
                    ? "Offer Accepted"
                    : "Offer Declined"}
                </p>
                {offer.offer_responded_at && (
                  <p className="text-sm text-muted-foreground">
                    Responded on{" "}
                    {new Date(offer.offer_responded_at).toLocaleDateString(
                      "en-GB",
                      {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      }
                    )}
                  </p>
                )}
              </div>
            </div>
            {offer.offer_response_notes && (
              <div className="rounded border bg-muted/50 p-3">
                <p className="text-xs text-muted-foreground mb-1">Your notes:</p>
                <p className="text-sm">{offer.offer_response_notes}</p>
              </div>
            )}
          </div>

          {offer.offer_response === "accepted" && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950">
              <p className="text-sm text-green-700 dark:text-green-300">
                The school will contact you with next steps for enrollment. Please
                ensure all required documents are ready.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  // Not yet responded -- show offer details and response form
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <GraduationCap className="h-4 w-4" />
            Admission Offer
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Offer status banner */}
          {offer.is_expired ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600 dark:text-red-400" />
                <p className="text-sm font-medium text-red-700 dark:text-red-300">
                  This offer has expired
                </p>
              </div>
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                The response deadline has passed. Please contact the school
                directly if you wish to discuss this offer.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
                  Response Required
                </p>
              </div>
              {deadlineInfo && (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                  {deadlineInfo.isUrgent && deadlineInfo.daysLeft >= 0
                    ? "Urgent: "
                    : ""}
                  {deadlineInfo.text}
                  {offer.response_deadline &&
                    ` (by ${new Date(offer.response_deadline).toLocaleDateString(
                      "en-GB",
                      {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      }
                    )})`}
                </p>
              )}
            </div>
          )}

          {/* Offer details */}
          <div className="rounded-lg border p-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">School</span>
              <span className="font-medium">{offer.school_name}</span>
            </div>
            {offer.offered_class_name && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Offered Class</span>
                <span className="font-medium">{offer.offered_class_name}</span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Decision Date</span>
              <span>
                {offer.decision_date
                  ? new Date(offer.decision_date).toLocaleDateString("en-GB")
                  : "-"}
              </span>
            </div>
            {offer.response_deadline && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  Response Deadline
                </span>
                <div className="flex items-center gap-2">
                  <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>
                    {new Date(offer.response_deadline).toLocaleDateString(
                      "en-GB"
                    )}
                  </span>
                  {deadlineInfo && (
                    <Badge
                      variant="outline"
                      className={
                        deadlineInfo.isUrgent
                          ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                          : "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                      }
                    >
                      {deadlineInfo.text}
                    </Badge>
                  )}
                </div>
              </div>
            )}
            {offer.conditions && (
              <div>
                <span className="text-muted-foreground">
                  Conditions of Admission
                </span>
                <p className="mt-1 rounded border bg-muted/50 p-2 text-sm">
                  {offer.conditions}
                </p>
              </div>
            )}
          </div>

          {/* Letter download */}
          {offer.decision_letter_url && (
            <a
              href={offer.decision_letter_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <Download className="h-3.5 w-3.5" />
              Download Admission Letter
            </a>
          )}

          {/* Response form */}
          {!offer.is_expired && (
            <div className="space-y-4 pt-2 border-t">
              <div className="space-y-2">
                <Label>Notes (Optional)</Label>
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any additional notes regarding your response..."
                  rows={3}
                />
              </div>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Button
                  className="flex-1 bg-green-600 hover:bg-green-700 text-white"
                  onClick={() => setConfirmAction("accepted")}
                >
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Accept Offer
                </Button>
                <Button
                  variant="outline"
                  className="flex-1 border-red-300 text-red-600 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
                  onClick={() => setConfirmAction("declined")}
                >
                  <XCircle className="mr-2 h-4 w-4" />
                  Decline Offer
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confirmation Dialog */}
      <AlertDialog
        open={confirmAction !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirmAction === "accepted"
                ? "Accept Admission Offer?"
                : "Decline Admission Offer?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmAction === "accepted"
                ? `You are about to accept the admission offer from ${offer.school_name}. This action cannot be undone. The school will proceed with your enrollment.`
                : `You are about to decline the admission offer from ${offer.school_name}. This action cannot be undone. Your application will be withdrawn.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleRespond();
              }}
              disabled={submitting}
              className={
                confirmAction === "declined"
                  ? "bg-red-600 hover:bg-red-700"
                  : ""
              }
            >
              {submitting && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {confirmAction === "accepted" ? "Yes, Accept" : "Yes, Decline"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
