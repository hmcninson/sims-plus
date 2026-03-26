"use client";

import { useState, useCallback } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { updatePromotionEntry } from "@/actions/admissions.action";
import type {
  ClassPromotionEntry,
  PromotionAction,
} from "@/types/admissions.type";
import type { Class } from "@/types";

interface PromotionEntryTableProps {
  entries: ClassPromotionEntry[];
  classes: Class[];
  editable: boolean;
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  onEntryUpdated: () => void;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const ACTION_LABELS: Record<PromotionAction, string> = {
  promote: "Promote",
  repeat: "Repeat",
  graduate: "Graduate",
  withdraw: "Withdraw",
};

export function PromotionEntryTable({
  entries,
  classes,
  editable,
  selectedIds,
  onSelectionChange,
  onEntryUpdated,
  page,
  totalPages,
  onPageChange,
}: PromotionEntryTableProps) {
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const isAllSelected =
    entries.length > 0 && entries.every((e) => selectedIds.includes(e.id));

  function toggleAll() {
    if (isAllSelected) {
      onSelectionChange(
        selectedIds.filter((id) => !entries.some((e) => e.id === id))
      );
    } else {
      const newIds = entries
        .map((e) => e.id)
        .filter((id) => !selectedIds.includes(id));
      onSelectionChange([...selectedIds, ...newIds]);
    }
  }

  function toggleOne(entryId: string) {
    if (selectedIds.includes(entryId)) {
      onSelectionChange(selectedIds.filter((id) => id !== entryId));
    } else {
      onSelectionChange([...selectedIds, entryId]);
    }
  }

  const handleUpdate = useCallback(
    async (
      entryId: string,
      action: PromotionAction,
      targetClassId?: string,
      reason?: string
    ) => {
      setUpdatingId(entryId);
      try {
        const result = await updatePromotionEntry(entryId, {
          action,
          target_class_id: targetClassId || undefined,
          reason: reason || undefined,
        });
        if (result.success) {
          onEntryUpdated();
        } else {
          toast.error(result.error);
        }
      } finally {
        setUpdatingId(null);
      }
    },
    [onEntryUpdated]
  );

  if (entries.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        No promotion entries. Click &quot;Generate Preview&quot; to populate
        entries.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {editable && (
                <TableHead className="w-[40px]">
                  <Checkbox checked={isAllSelected} onCheckedChange={toggleAll} />
                </TableHead>
              )}
              <TableHead>Student</TableHead>
              <TableHead className="hidden sm:table-cell">Student #</TableHead>
              <TableHead>Current Class</TableHead>
              <TableHead className="w-[130px]">Action</TableHead>
              <TableHead className="w-[160px]">Target Class</TableHead>
              <TableHead className="hidden md:table-cell">Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map((entry) => {
              const isUpdating = updatingId === entry.id;
              const needsTarget =
                entry.action === "promote" || entry.action === "repeat";

              return (
                <TableRow key={entry.id}>
                  {editable && (
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.includes(entry.id)}
                        onCheckedChange={() => toggleOne(entry.id)}
                      />
                    </TableCell>
                  )}
                  <TableCell className="font-medium">
                    {entry.student_name || "Unknown"}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell text-muted-foreground text-sm">
                    {entry.student_number || "-"}
                  </TableCell>
                  <TableCell className="text-sm">
                    {entry.source_class_name || "N/A"}
                  </TableCell>
                  <TableCell>
                    {editable ? (
                      <Select
                        value={entry.action}
                        onValueChange={(val) =>
                          handleUpdate(
                            entry.id,
                            val as PromotionAction,
                            entry.target_class_id || undefined,
                            entry.reason || undefined
                          )
                        }
                        disabled={isUpdating}
                      >
                        <SelectTrigger className="h-8 w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(
                            Object.keys(ACTION_LABELS) as PromotionAction[]
                          ).map((action) => (
                            <SelectItem key={action} value={action}>
                              {ACTION_LABELS[action]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <span className="capitalize">{entry.action}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {editable && needsTarget ? (
                      <Select
                        value={entry.target_class_id || ""}
                        onValueChange={(val) =>
                          handleUpdate(
                            entry.id,
                            entry.action,
                            val,
                            entry.reason || undefined
                          )
                        }
                        disabled={isUpdating}
                      >
                        <SelectTrigger className="h-8 w-full">
                          <SelectValue placeholder="Select" />
                        </SelectTrigger>
                        <SelectContent>
                          {classes.map((cls) => (
                            <SelectItem key={cls.id} value={cls.id}>
                              {cls.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <span className="text-sm">
                        {entry.target_class_name || "-"}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {editable ? (
                      <Input
                        value={entry.reason || ""}
                        onChange={(e) =>
                          handleUpdate(
                            entry.id,
                            entry.action,
                            entry.target_class_id || undefined,
                            e.target.value
                          )
                        }
                        className="h-8"
                        placeholder="Reason..."
                        disabled={isUpdating}
                      />
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        {entry.reason || "-"}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
