"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, Clock, Lock, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { approvePayrollRun, rejectPayrollRun } from "@/actions/payroll.action";
import { formatGhanaDate } from "@/lib/format";
import type { PayrollRun } from "@/types/payroll.type";

interface PayrollApprovalFlowProps {
  run: PayrollRun;
  currentUserId: string;
  onActionComplete: () => void;
}

export function PayrollApprovalFlow({
  run,
  currentUserId,
  onActionComplete,
}: PayrollApprovalFlowProps) {
  const [showApproveDialog, setShowApproveDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [comments, setComments] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isProcessor = run.processed_by === currentUserId;
  const canApprove = run.status === "pending_approval" && !isProcessor;

  async function handleApprove() {
    setIsSubmitting(true);
    const result = await approvePayrollRun(run.id, comments || undefined);
    setIsSubmitting(false);
    if (result.success) {
      toast.success("Payroll run approved successfully");
      setShowApproveDialog(false);
      setComments("");
      onActionComplete();
    } else {
      toast.error(result.error);
    }
  }

  async function handleReject() {
    if (!comments.trim()) {
      toast.error("Please provide a reason for rejection");
      return;
    }
    setIsSubmitting(true);
    const result = await rejectPayrollRun(run.id, comments);
    setIsSubmitting(false);
    if (result.success) {
      toast.success("Payroll run rejected");
      setShowRejectDialog(false);
      setComments("");
      onActionComplete();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <>
      <Card>
        <CardContent className="p-4 space-y-4">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">Approval Workflow</span>
          </div>

          {/* Processor info */}
          {run.processed_by_name && (
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="outline" className="gap-1">
                <CheckCircle2 className="h-3 w-3" />
                Processed
              </Badge>
              <span>{run.processed_by_name}</span>
              {run.processed_at && (
                <span className="text-muted-foreground">
                  {formatGhanaDate(run.processed_at)}
                </span>
              )}
            </div>
          )}

          {/* Approver info */}
          {run.approved_by_name && (
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="outline" className="gap-1 border-green-300 text-green-700 dark:border-green-700 dark:text-green-400">
                <CheckCircle2 className="h-3 w-3" />
                Approved
              </Badge>
              <span>{run.approved_by_name}</span>
              {run.approved_at && (
                <span className="text-muted-foreground">
                  {formatGhanaDate(run.approved_at)}
                </span>
              )}
            </div>
          )}

          {/* Paid info */}
          {run.paid_at && (
            <div className="flex items-center gap-3 text-sm">
              <Badge variant="outline" className="gap-1 border-emerald-300 text-emerald-700 dark:border-emerald-700 dark:text-emerald-400">
                <Lock className="h-3 w-3" />
                Paid
              </Badge>
              <span className="text-muted-foreground">
                {formatGhanaDate(run.paid_at)}
              </span>
            </div>
          )}

          {/* Separation of duties warning */}
          {run.status === "pending_approval" && isProcessor && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
              <p className="text-sm text-amber-700 dark:text-amber-300">
                Separation of duties: You processed this payroll run and cannot approve it.
                A different administrator must approve.
              </p>
            </div>
          )}

          {/* Action buttons */}
          {run.status === "pending_approval" && (
            <div className="flex gap-2">
              <Button
                onClick={() => setShowApproveDialog(true)}
                disabled={!canApprove}
                className="gap-1"
              >
                <CheckCircle2 className="h-4 w-4" />
                Approve
              </Button>
              <Button
                variant="destructive"
                onClick={() => setShowRejectDialog(true)}
                disabled={!canApprove}
                className="gap-1"
              >
                <XCircle className="h-4 w-4" />
                Reject
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Approve Dialog */}
      <Dialog open={showApproveDialog} onOpenChange={setShowApproveDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Payroll Run</DialogTitle>
            <DialogDescription>
              Confirm approval of this payroll run. Once approved, it can be marked as paid.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="approve-comments">Comments (optional)</Label>
            <Textarea
              id="approve-comments"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Add any comments..."
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowApproveDialog(false);
                setComments("");
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleApprove} disabled={isSubmitting}>
              {isSubmitting ? "Approving..." : "Approve"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Payroll Run</DialogTitle>
            <DialogDescription>
              Rejecting will return the payroll run to draft status for corrections.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="reject-comments">Reason for rejection (required)</Label>
            <Textarea
              id="reject-comments"
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Explain why the payroll run is being rejected..."
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowRejectDialog(false);
                setComments("");
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={isSubmitting || !comments.trim()}
            >
              {isSubmitting ? "Rejecting..." : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
