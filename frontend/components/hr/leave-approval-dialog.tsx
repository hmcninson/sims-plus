"use client";

import { useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";

interface LeaveApprovalDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  action: "approve" | "reject";
  staffName?: string;
  onConfirm: (notes?: string) => Promise<void>;
  isSubmitting: boolean;
}

export function LeaveApprovalDialog({
  open,
  onOpenChange,
  action,
  staffName,
  onConfirm,
  isSubmitting,
}: LeaveApprovalDialogProps) {
  const [notes, setNotes] = useState("");

  const isApprove = action === "approve";

  const handleConfirm = async () => {
    await onConfirm(notes || undefined);
    setNotes("");
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {isApprove ? "Approve" : "Reject"} Leave Request
          </AlertDialogTitle>
          <AlertDialogDescription>
            {isApprove
              ? `Are you sure you want to approve ${staffName ? `${staffName}'s` : "this"} leave request?`
              : `Are you sure you want to reject ${staffName ? `${staffName}'s` : "this"} leave request? This action cannot be undone.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-2">
          <Label htmlFor="review-notes">
            Notes {!isApprove && "(recommended)"}
          </Label>
          <Textarea
            id="review-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={
              isApprove
                ? "Optional notes for the staff member..."
                : "Reason for rejection..."
            }
            rows={3}
            className="mt-1.5"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
          <Button
            onClick={handleConfirm}
            disabled={isSubmitting}
            variant={isApprove ? "default" : "destructive"}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isApprove ? "Approve" : "Reject"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
