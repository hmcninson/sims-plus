"use client";

import { useState } from "react";
import { Banknote, Loader2 } from "lucide-react";

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
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { disburseLoan } from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";

interface LoanDisbursementDialogProps {
  loanId: string;
  loanNumber: string;
  principalAmount: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LoanDisbursementDialog({
  loanId,
  loanNumber,
  principalAmount,
  open,
  onOpenChange,
  onSuccess,
}: LoanDisbursementDialogProps) {
  const today = new Date().toISOString().split("T")[0];
  const [disbursementDate, setDisbursementDate] = useState(today);
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit() {
    if (!disbursementDate) {
      toast.error("Please select a disbursement date");
      return;
    }

    setIsSubmitting(true);
    const result = await disburseLoan(loanId, {
      disbursement_date: disbursementDate,
      notes: notes.trim() || undefined,
    });

    if (result.success) {
      toast.success("Loan disbursed successfully");
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
            <Banknote className="h-5 w-5 text-green-600" />
            Confirm Disbursement
          </AlertDialogTitle>
          <AlertDialogDescription>
            Disburse {formatGHS(principalAmount)} for loan {loanNumber}. This
            will activate the loan and generate the installment schedule.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="disbursement-date">Disbursement Date</Label>
            <Input
              id="disbursement-date"
              type="date"
              value={disbursementDate}
              onChange={(e) => setDisbursementDate(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="disbursement-notes">Notes (optional)</Label>
            <Textarea
              id="disbursement-notes"
              placeholder="Optional notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
            />
          </div>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Confirm Disbursement
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
