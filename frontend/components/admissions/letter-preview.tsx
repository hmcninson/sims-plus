"use client";

import { useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  Download,
  Loader2,
  CheckCircle,
  XCircle,
} from "lucide-react";
import {
  generateAdmissionLetter,
  generateRejectionLetter,
} from "@/actions/admissions.action";
import type { AdmissionDecision } from "@/types/admissions.type";

interface LetterPreviewProps {
  decision: AdmissionDecision;
  onLetterGenerated?: () => void;
  trigger?: React.ReactNode;
}

export function LetterPreview({
  decision,
  onLetterGenerated,
  trigger,
}: LetterPreviewProps) {
  const [open, setOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [letterUrl, setLetterUrl] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const isAccepted = decision.decision_type === "accepted";
  const isRejected = decision.decision_type === "rejected";
  const canGenerateLetter = isAccepted || isRejected;

  const hasExistingLetter =
    (isAccepted && decision.decision_letter_url) ||
    (isRejected && decision.rejection_letter_url);

  async function handleGenerate() {
    setGenerating(true);
    setLetterUrl(null);

    let result;
    if (isAccepted) {
      result = await generateAdmissionLetter(decision.id);
    } else {
      result = await generateRejectionLetter(
        decision.id,
        rejectionReason || undefined
      );
    }

    if (result.success && result.data) {
      setLetterUrl(result.data.letter_url);
      toast.success(
        `${isAccepted ? "Admission" : "Rejection"} letter generated successfully`
      );
      onLetterGenerated?.();
    } else {
      toast.error(result.error);
    }
    setGenerating(false);
  }

  if (!canGenerateLetter) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) {
          setLetterUrl(null);
          setRejectionReason("");
        }
      }}
    >
      <DialogTrigger asChild>
        {trigger || (
          <Button variant="outline" size="sm">
            <FileText className="mr-1.5 h-3.5 w-3.5" />
            {hasExistingLetter ? "Regenerate Letter" : "Generate Letter"}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isAccepted ? "Admission Letter" : "Rejection Letter"}
          </DialogTitle>
          <DialogDescription>
            Generate a PDF{" "}
            {isAccepted ? "admission" : "rejection"} letter for this
            applicant. The letter will be uploaded and available for download.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Decision info summary */}
          <div className="rounded-lg border p-3 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Decision</span>
              <Badge
                variant="outline"
                className={
                  isAccepted
                    ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                    : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                }
              >
                {isAccepted ? (
                  <CheckCircle className="mr-1 h-3 w-3" />
                ) : (
                  <XCircle className="mr-1 h-3 w-3" />
                )}
                {decision.decision_type}
              </Badge>
            </div>
            {decision.offered_class_name && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Offered Class</span>
                <span className="font-medium">
                  {decision.offered_class_name}
                </span>
              </div>
            )}
            {decision.conditions && (
              <div>
                <span className="text-muted-foreground">Conditions</span>
                <p className="mt-1 text-xs">{decision.conditions}</p>
              </div>
            )}
            {decision.response_deadline && (
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">
                  Response Deadline
                </span>
                <span>
                  {new Date(decision.response_deadline).toLocaleDateString(
                    "en-GB"
                  )}
                </span>
              </div>
            )}
          </div>

          {/* Rejection reason (only for rejection letters) */}
          {isRejected && (
            <div className="space-y-2">
              <Label>Rejection Reason (Optional)</Label>
              <p className="text-xs text-muted-foreground">
                Provide an optional reason to include in the letter. This will
                appear under &quot;Additional Information&quot;.
              </p>
              <Textarea
                value={rejectionReason}
                onChange={(e) => setRejectionReason(e.target.value)}
                placeholder="e.g. Capacity has been reached for the requested class..."
                rows={3}
              />
            </div>
          )}

          {/* Existing letter link */}
          {hasExistingLetter && !letterUrl && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 dark:border-blue-900 dark:bg-blue-950">
              <p className="text-sm text-blue-700 dark:text-blue-300">
                A letter has already been generated. You can download the
                existing letter or regenerate a new one.
              </p>
              <a
                href={
                  isAccepted
                    ? decision.decision_letter_url || "#"
                    : decision.rejection_letter_url || "#"
                }
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline dark:text-blue-300"
              >
                <Download className="h-3.5 w-3.5" />
                Download Existing Letter
              </a>
            </div>
          )}

          {/* Generated letter link */}
          {letterUrl && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-green-950">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
                <p className="text-sm font-medium text-green-700 dark:text-green-300">
                  Letter generated successfully
                </p>
              </div>
              <a
                href={letterUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-green-700 hover:underline dark:text-green-300"
              >
                <Download className="h-3.5 w-3.5" />
                Download PDF Letter
              </a>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <FileText className="mr-2 h-4 w-4" />
            )}
            {letterUrl ? "Regenerate" : "Generate"} Letter
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
