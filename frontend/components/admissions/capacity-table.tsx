"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Pencil, Loader2 } from "lucide-react";
import { createTarget } from "@/actions/capacity.action";
import type { ClassCapacityRow } from "@/types/admissions.type";

interface CapacityTableProps {
  classes: ClassCapacityRow[];
  academicYearId: string;
  onRefresh: () => void;
}

export function CapacityTable({
  classes,
  academicYearId,
  onRefresh,
}: CapacityTableProps) {
  const [editingClass, setEditingClass] = useState<ClassCapacityRow | null>(
    null
  );
  const [targetCount, setTargetCount] = useState("");
  const [boardingTarget, setBoardingTarget] = useState("");
  const [dayTarget, setDayTarget] = useState("");
  const [saving, setSaving] = useState(false);

  function openEditDialog(cls: ClassCapacityRow) {
    setEditingClass(cls);
    setTargetCount(String(cls.target ?? ""));
    setBoardingTarget(cls.boarding_target != null ? String(cls.boarding_target) : "");
    setDayTarget(cls.day_target != null ? String(cls.day_target) : "");
  }

  async function handleSaveTarget() {
    if (!editingClass) return;
    const count = parseInt(targetCount, 10);
    if (isNaN(count) || count < 0) {
      toast.error("Target count must be a non-negative number");
      return;
    }

    setSaving(true);
    const result = await createTarget({
      academic_year_id: academicYearId,
      class_id: editingClass.class_id,
      target_count: count,
      boarding_target: boardingTarget ? parseInt(boardingTarget, 10) : null,
      day_target: dayTarget ? parseInt(dayTarget, 10) : null,
    });
    setSaving(false);

    if (result.success) {
      toast.success(`Target set for ${editingClass.class_name}`);
      setEditingClass(null);
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  function getStatusBadge(cls: ClassCapacityRow) {
    if (cls.capacity != null && cls.current_enrolled >= cls.capacity) {
      return (
        <Badge variant="destructive" className="text-xs">
          Full
        </Badge>
      );
    }
    if (cls.target != null && cls.current_enrolled >= cls.target) {
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 text-xs">
          At Target
        </Badge>
      );
    }
    if (cls.utilization_pct >= 80) {
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 text-xs">
          Near Capacity
        </Badge>
      );
    }
    return (
      <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200 text-xs">
        Available
      </Badge>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Class</TableHead>
              <TableHead className="hidden sm:table-cell">Capacity</TableHead>
              <TableHead>Target</TableHead>
              <TableHead>Enrolled</TableHead>
              <TableHead className="hidden md:table-cell">Pipeline</TableHead>
              <TableHead className="hidden md:table-cell">Utilisation</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {classes.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="h-24 text-center text-muted-foreground"
                >
                  No classes found for the selected academic year.
                </TableCell>
              </TableRow>
            ) : (
              classes.map((cls) => (
                <TableRow key={cls.class_id}>
                  <TableCell className="font-medium">
                    {cls.class_name}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {cls.capacity ?? "--"}
                  </TableCell>
                  <TableCell>
                    {cls.target != null ? cls.target : (
                      <span className="text-muted-foreground">Not set</span>
                    )}
                  </TableCell>
                  <TableCell>{cls.current_enrolled}</TableCell>
                  <TableCell className="hidden md:table-cell">
                    {cls.applications_in_pipeline}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {cls.utilization_pct > 0 ? `${cls.utilization_pct}%` : "--"}
                  </TableCell>
                  <TableCell>{getStatusBadge(cls)}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEditDialog(cls)}
                      aria-label={`Set target for ${cls.class_name}`}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog
        open={!!editingClass}
        onOpenChange={() => setEditingClass(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Set Enrollment Target {editingClass ? `- ${editingClass.class_name}` : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="target-count">Total Target</Label>
              <Input
                id="target-count"
                type="number"
                min={0}
                value={targetCount}
                onChange={(e) => setTargetCount(e.target.value)}
                placeholder="e.g. 40"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="boarding-target">Boarding Target</Label>
                <Input
                  id="boarding-target"
                  type="number"
                  min={0}
                  value={boardingTarget}
                  onChange={(e) => setBoardingTarget(e.target.value)}
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="day-target">Day Target</Label>
                <Input
                  id="day-target"
                  type="number"
                  min={0}
                  value={dayTarget}
                  onChange={(e) => setDayTarget(e.target.value)}
                  placeholder="Optional"
                />
              </div>
            </div>
            {editingClass && (
              <p className="text-sm text-muted-foreground">
                Currently enrolled: {editingClass.current_enrolled}
                {editingClass.capacity != null && ` / ${editingClass.capacity} capacity`}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingClass(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveTarget} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Target
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
