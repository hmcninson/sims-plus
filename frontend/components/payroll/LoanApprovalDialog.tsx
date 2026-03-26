"use client";

import { useState } from "react";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { approveLoan, rejectLoan } from "@/actions/loans.action";

interface LoanApprovalDialogProps {
  loanId: string;
  loanNumber: string;
  action: "approve" | "reject";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LoanApprovalDialog({
  loanId,
  loanNumber,
  action,
  open,
  onOpenChange,
  onSuccess,
}: LoanApprovalDialogProps) {
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isReject = action === "reject";
  const title = isReject ? "Reject Loan" : "Approve Loan";
  const description = isReject
    ? `Are you sure you want to reject loan ${loanNumber}? Please provide a reason.`
    : `Are you sure you want to approve loan ${loanNumber}?`;

  async function handleSubmit() {
    if (isReject && !notes.trim()) {
      toast.error("Please provide a reason for rejection");
      return;
    }

    setIsSubmitting(true);
    // Backend has separate approve and reject endpoints
    const result = isReject
      ? await rejectLoan(loanId, { reason: notes.trim() })
      : await approveLoan(loanId);

    if (result.success) {
      toast.success(
        isReject ? "Loan rejected successfully" : "Loan approved successfully"
      );
      setNotes("");
      onOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error);
    }
    setIsSubmitting(false);
  }

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            {isReject ? (
              <XCircle className="h-5 w-5 text-destructive" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-600" />
            )}
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="approval-notes">
            Notes {isReject && <span className="text-destructive">*</span>}
          </Label>
          <Textarea
            id="approval-notes"
            placeholder={
              isReject
                ? "Reason for rejection (required)..."
                : "Optional notes..."
            }
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
            variant={isReject ? "destructive" : "default"}
          >
            {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {isReject ? "Reject" : "Approve"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
