"use client";

import { useCallback, useState, useTransition } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CheckCircle2,
  Circle,
  FileText,
  CreditCard,
  ClipboardList,
  Home,
  Stethoscope,
  Loader2,
  Plus,
  PartyPopper,
} from "lucide-react";
import {
  createEnrollmentChecklist,
  completeChecklistItem,
  getEnrollmentChecklist,
} from "@/actions/admissions.action";
import type {
  EnrollmentChecklist,
  EnrollmentChecklistItem,
  ChecklistItemType,
} from "@/types/admissions.type";

interface EnrollmentChecklistUIProps {
  applicationId: string;
  initialChecklist: EnrollmentChecklist | null;
}

const ITEM_TYPE_CONFIG: Record<
  ChecklistItemType,
  { label: string; icon: typeof FileText; color: string }
> = {
  document: {
    label: "Documents",
    icon: FileText,
    color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  payment: {
    label: "Payments",
    icon: CreditCard,
    color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  form: {
    label: "Forms",
    icon: ClipboardList,
    color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  },
  boarding: {
    label: "Boarding",
    icon: Home,
    color: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  },
  medical: {
    label: "Medical",
    icon: Stethoscope,
    color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
};

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function groupItemsByType(
  items: EnrollmentChecklistItem[]
): Record<string, EnrollmentChecklistItem[]> {
  const groups: Record<string, EnrollmentChecklistItem[]> = {};
  for (const item of items) {
    const key = item.item_type;
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  return groups;
}

export function EnrollmentChecklistUI({
  applicationId,
  initialChecklist,
}: EnrollmentChecklistUIProps) {
  const [checklist, setChecklist] = useState<EnrollmentChecklist | null>(
    initialChecklist
  );
  const [isPending, startTransition] = useTransition();
  const [completingItemId, setCompletingItemId] = useState<string | null>(null);
  const [showNotesDialog, setShowNotesDialog] = useState(false);
  const [pendingItemId, setPendingItemId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");

  const refreshChecklist = useCallback(async () => {
    const result = await getEnrollmentChecklist(applicationId);
    if (result.success) {
      setChecklist(result.data);
    }
  }, [applicationId]);

  function handleCreateChecklist() {
    startTransition(async () => {
      const result = await createEnrollmentChecklist(applicationId);
      if (result.success) {
        setChecklist(result.data);
        toast.success("Enrollment checklist created");
      } else {
        toast.error(result.error);
      }
    });
  }

  function handleCompleteItem(itemId: string) {
    setPendingItemId(itemId);
    setNotes("");
    setShowNotesDialog(true);
  }

  function handleConfirmComplete() {
    if (!pendingItemId) return;
    const itemId = pendingItemId;
    setShowNotesDialog(false);
    setCompletingItemId(itemId);

    startTransition(async () => {
      const result = await completeChecklistItem(
        itemId,
        notes || undefined
      );
      if (result.success) {
        toast.success("Item marked as completed");
        await refreshChecklist();
      } else {
        toast.error(result.error);
      }
      setCompletingItemId(null);
      setPendingItemId(null);
      setNotes("");
    });
  }

  // No checklist yet - show create button
  if (!checklist) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-4">
          <ClipboardList className="h-12 w-12 text-muted-foreground" />
          <div className="text-center">
            <h3 className="font-semibold">No Enrollment Checklist</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Create a checklist to track enrollment requirements for this applicant.
            </p>
          </div>
          <Button onClick={handleCreateChecklist} disabled={isPending}>
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Plus className="mr-2 h-4 w-4" />
            )}
            Create Checklist
          </Button>
        </CardContent>
      </Card>
    );
  }

  const isComplete = checklist.completed_at !== null;
  const grouped = groupItemsByType(checklist.items);
  const typeOrder: ChecklistItemType[] = [
    "document",
    "payment",
    "form",
    "medical",
    "boarding",
  ];

  return (
    <div className="space-y-4">
      {/* Progress overview */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle className="text-base">
              Enrollment Checklist
              {checklist.checklist_type === "boarding" && (
                <Badge variant="outline" className="ml-2">
                  Boarding
                </Badge>
              )}
            </CardTitle>
            {isComplete ? (
              <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                <CheckCircle2 className="mr-1 h-3 w-3" />
                All required items complete
              </Badge>
            ) : (
              <span className="text-sm text-muted-foreground">
                {checklist.required_completed} / {checklist.required_items} required items
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent>
          <Progress
            value={checklist.progress_pct}
            className="h-2"
          />
          <div className="flex justify-between mt-2 text-xs text-muted-foreground">
            <span>{checklist.completed_items} of {checklist.total_items} total items completed</span>
            <span>{Math.round(checklist.progress_pct)}%</span>
          </div>
        </CardContent>
      </Card>

      {/* Completion celebration */}
      {isComplete && (
        <Card className="border-green-200 dark:border-green-800">
          <CardContent className="flex items-center gap-3 py-4">
            <PartyPopper className="h-8 w-8 text-green-600 dark:text-green-400 shrink-0" />
            <div>
              <p className="font-semibold text-green-700 dark:text-green-300">
                Enrollment checklist is complete
              </p>
              <p className="text-sm text-muted-foreground">
                All required items have been verified. This applicant is ready for enrollment.
                {checklist.completed_at && (
                  <> Completed on {formatDateTime(checklist.completed_at)}.</>
                )}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Grouped items */}
      {typeOrder.map((type) => {
        const items = grouped[type];
        if (!items || items.length === 0) return null;
        const config = ITEM_TYPE_CONFIG[type];
        const Icon = config.icon;

        return (
          <Card key={type}>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Icon className="h-4 w-4" />
                {config.label}
                <Badge variant="secondary" className="text-xs">
                  {items.filter((i) => i.is_completed).length}/{items.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {items.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-start gap-3 rounded-lg border p-3 ${
                    item.is_completed
                      ? "bg-muted/50 border-green-200 dark:border-green-800"
                      : ""
                  }`}
                >
                  {/* Status icon */}
                  <div className="mt-0.5 shrink-0">
                    {item.is_completed ? (
                      <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                    ) : (
                      <Circle className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`text-sm font-medium ${
                          item.is_completed
                            ? "line-through text-muted-foreground"
                            : ""
                        }`}
                      >
                        {item.item_name}
                      </span>
                      {item.is_required && (
                        <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                          Required
                        </Badge>
                      )}
                      <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${config.color}`}>
                        {config.label}
                      </Badge>
                    </div>
                    {item.description && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {item.description}
                      </p>
                    )}
                    {item.is_completed && (
                      <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                        {item.completed_at && (
                          <p>Completed: {formatDateTime(item.completed_at)}</p>
                        )}
                        {item.completed_by_name && (
                          <p>By: {item.completed_by_name}</p>
                        )}
                        {item.notes && (
                          <p className="italic">Note: {item.notes}</p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Action button */}
                  {!item.is_completed && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleCompleteItem(item.id)}
                      disabled={completingItemId === item.id || isPending}
                      className="shrink-0"
                    >
                      {completingItemId === item.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        "Complete"
                      )}
                    </Button>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        );
      })}

      {/* Complete item dialog */}
      <Dialog open={showNotesDialog} onOpenChange={setShowNotesDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete Checklist Item</DialogTitle>
            <DialogDescription>
              Add optional verification notes before marking this item as complete.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label htmlFor="notes">Notes (optional)</Label>
              <Input
                id="notes"
                placeholder="e.g., Verified original document"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowNotesDialog(false)}
            >
              Cancel
            </Button>
            <Button onClick={handleConfirmComplete} disabled={isPending}>
              {isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="mr-2 h-4 w-4" />
              )}
              Mark Complete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
