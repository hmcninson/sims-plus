"use client";

import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

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
import { writeOffLoan } from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";

interface LoanWriteOffDialogProps {
  loanId: string;
  loanNumber: string;
  outstandingBalance: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LoanWriteOffDialog({
  loanId,
  loanNumber,
  outstandingBalance,
  open,
  onOpenChange,
  onSuccess,
}: LoanWriteOffDialogProps) {
  const [reason, setReason] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!reason.trim()) {
      toast.error("Please provide a reason for writing off this loan");
      return;
    }

    setIsSubmitting(true);
    const result = await writeOffLoan(loanId, { reason: reason.trim() });

    if (result.success) {
      toast.success("Loan written off successfully");
      setReason("");
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
            <AlertTriangle className="h-5 w-5 text-destructive" />
            Write Off Loan
          </AlertDialogTitle>
          <AlertDialogDescription>
            This will write off {formatGHS(outstandingBalance)} outstanding
            balance for loan {loanNumber}. This action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-2">
          <Label htmlFor="writeoff-reason">
            Reason <span className="text-destructive">*</span>
          </Label>
          <Textarea
            id="writeoff-reason"
            placeholder="Reason for write-off (required)..."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting}
            variant="destructive"
          >
            {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Write Off
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
