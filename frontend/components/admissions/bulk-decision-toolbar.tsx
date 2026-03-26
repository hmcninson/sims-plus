"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, CheckCircle, XCircle, Clock } from "lucide-react";
import { bulkDecision } from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type { DecisionType, BulkDecisionResponse } from "@/types/admissions.type";
import type { Class } from "@/types";

interface BulkDecisionToolbarProps {
  selectedIds: string[];
  onComplete: () => void;
}

export function BulkDecisionToolbar({
  selectedIds,
  onComplete,
}: BulkDecisionToolbarProps) {
  const [showAcceptDialog, setShowAcceptDialog] = useState(false);
  const [showRejectDialog, setShowRejectDialog] = useState(false);
  const [showWaitlistDialog, setShowWaitlistDialog] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [offeredClassId, setOfferedClassId] = useState("");
  const [responseDeadline, setResponseDeadline] = useState("");
  const [conditions, setConditions] = useState("");
  const [classes, setClasses] = useState<Class[]>([]);
  const [result, setResult] = useState<BulkDecisionResponse | null>(null);

  if (selectedIds.length === 0) return null;

  async function loadClasses() {
    if (classes.length === 0) {
      const res = await getClasses();
      if (res.success && res.data) setClasses(res.data);
    }
  }

  async function handleBulkDecision(decisionType: DecisionType) {
    setProcessing(true);
    try {
      const res = await bulkDecision({
        application_ids: selectedIds,
        decision_type: decisionType,
        offered_class_id:
          decisionType === "accepted" && offeredClassId
            ? offeredClassId
            : undefined,
        conditions: conditions || undefined,
        response_deadline: responseDeadline || undefined,
      });

      if (res.success && res.data) {
        setResult(res.data);
        const { total_succeeded, total_failed } = res.data;
        if (total_failed === 0) {
          toast.success(
            `${total_succeeded} application${total_succeeded !== 1 ? "s" : ""} ${decisionType} successfully`
          );
        } else {
          toast.warning(
            `${total_succeeded} succeeded, ${total_failed} failed`
          );
        }
        onComplete();
      } else {
        toast.error(res.error);
      }
    } finally {
      setProcessing(false);
      setShowAcceptDialog(false);
      setShowRejectDialog(false);
      setShowWaitlistDialog(false);
      setOfferedClassId("");
      setResponseDeadline("");
      setConditions("");
    }
  }

  return (
    <>
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 rounded-lg border bg-muted/80 px-4 py-3 backdrop-blur-sm">
        <span className="text-sm font-medium">
          {selectedIds.length} selected
        </span>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="default"
            onClick={() => {
              loadClasses();
              setShowAcceptDialog(true);
            }}
            disabled={processing}
          >
            <CheckCircle className="mr-1.5 h-4 w-4" />
            Accept
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => setShowRejectDialog(true)}
            disabled={processing}
          >
            <XCircle className="mr-1.5 h-4 w-4" />
            Reject
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowWaitlistDialog(true)}
            disabled={processing}
          >
            <Clock className="mr-1.5 h-4 w-4" />
            Waitlist
          </Button>
        </div>

        {result && (
          <div className="ml-auto text-sm text-muted-foreground">
            {result.total_succeeded} succeeded
            {result.total_failed > 0 && (
              <span className="text-destructive">
                , {result.total_failed} failed
              </span>
            )}
          </div>
        )}
      </div>

      {/* Accept Dialog */}
      <AlertDialog open={showAcceptDialog} onOpenChange={setShowAcceptDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Accept {selectedIds.length} Application
              {selectedIds.length !== 1 ? "s" : ""}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Accept the selected applications. You can optionally assign a class
              and set a response deadline.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Offered Class (Optional)</Label>
              <Select value={offeredClassId} onValueChange={setOfferedClassId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select class" />
                </SelectTrigger>
                <SelectContent>
                  {classes.map((cls) => (
                    <SelectItem key={cls.id} value={cls.id}>
                      {cls.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Response Deadline (Optional)</Label>
              <Input
                type="date"
                value={responseDeadline}
                onChange={(e) => setResponseDeadline(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Conditions (Optional)</Label>
              <Input
                value={conditions}
                onChange={(e) => setConditions(e.target.value)}
                placeholder="Any conditions..."
              />
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={processing}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleBulkDecision("accepted")}
              disabled={processing}
            >
              {processing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Accept All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reject Dialog */}
      <AlertDialog open={showRejectDialog} onOpenChange={setShowRejectDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Reject {selectedIds.length} Application
              {selectedIds.length !== 1 ? "s" : ""}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will reject all selected applications. This action cannot be
              easily undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={processing}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleBulkDecision("rejected")}
              disabled={processing}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {processing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Reject All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Waitlist Dialog */}
      <AlertDialog
        open={showWaitlistDialog}
        onOpenChange={setShowWaitlistDialog}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Waitlist {selectedIds.length} Application
              {selectedIds.length !== 1 ? "s" : ""}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will place all selected applications on the waitlist.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={processing}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleBulkDecision("waitlisted")}
              disabled={processing}
            >
              {processing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Waitlist All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
