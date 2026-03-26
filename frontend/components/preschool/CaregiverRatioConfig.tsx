"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Loader2, Save, Info, CheckCircle2, AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { listCaregiverRatios, setCaregiverRatio } from "@/actions/preschool.action";
import type { CaregiverRatio } from "@/types";

interface EditableRatio {
  class_id: string;
  max_children_per_caregiver: number;
  current_caregiver_count: number;
}

export function CaregiverRatioConfig() {
  const [ratios, setRatios] = useState<CaregiverRatio[]>([]);
  const [edits, setEdits] = useState<Record<string, EditableRatio>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadRatios();
  }, []);

  async function loadRatios() {
    setLoading(true);
    const result = await listCaregiverRatios();
    if (result.success && result.data) {
      setRatios(result.data);
      // Initialize edits from current data
      const initial: Record<string, EditableRatio> = {};
      for (const r of result.data) {
        initial[r.class_id] = {
          class_id: r.class_id,
          max_children_per_caregiver: r.max_children_per_caregiver,
          current_caregiver_count: r.current_caregiver_count,
        };
      }
      setEdits(initial);
    } else {
      toast.error(result.error || "Failed to load caregiver ratios");
    }
    setLoading(false);
  }

  function handleChange(classId: string, field: keyof EditableRatio, value: number) {
    setEdits((prev) => ({
      ...prev,
      [classId]: { ...prev[classId], [field]: value },
    }));
    setHasChanges(true);
  }

  async function handleSave() {
    setSaving(true);
    let successCount = 0;
    let errorCount = 0;

    for (const [classId, edit] of Object.entries(edits)) {
      const original = ratios.find((r) => r.class_id === classId);
      if (
        original &&
        (original.max_children_per_caregiver !== edit.max_children_per_caregiver ||
          original.current_caregiver_count !== edit.current_caregiver_count)
      ) {
        const result = await setCaregiverRatio(classId, {
          max_children_per_caregiver: edit.max_children_per_caregiver,
          current_caregiver_count: edit.current_caregiver_count,
        });
        if (result.success) {
          successCount++;
        } else {
          errorCount++;
        }
      }
    }

    if (errorCount > 0) {
      toast.error(`Failed to update ${errorCount} ratio(s)`);
    }
    if (successCount > 0) {
      toast.success(`Updated ${successCount} ratio(s) successfully`);
    }

    // Reload to get fresh computed values
    await loadRatios();
    setHasChanges(false);
    setSaving(false);
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72 mt-2" />
        </CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (ratios.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Info className="h-10 w-10 text-muted-foreground mb-3" />
          <h3 className="text-sm font-medium">No preschool classes found</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Add preschool classes first, then configure caregiver ratios here.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          <strong>Ghana ECCD recommended ratios:</strong> Creche 1:5, Nursery 1:10, KG 1:15.
          Set the maximum number of children per caregiver and the number of caregivers assigned to each class.
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Caregiver Ratios</CardTitle>
          <CardDescription>
            Configure child-to-caregiver ratios for each preschool class.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Class</TableHead>
                  <TableHead className="hidden sm:table-cell">Max per Caregiver</TableHead>
                  <TableHead className="hidden sm:table-cell">Caregivers</TableHead>
                  <TableHead className="hidden md:table-cell">Max Capacity</TableHead>
                  <TableHead className="hidden md:table-cell">Enrollment</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ratios.map((ratio) => {
                  const edit = edits[ratio.class_id];
                  if (!edit) return null;
                  const maxCapacity = edit.max_children_per_caregiver * edit.current_caregiver_count;
                  const isCompliant = ratio.current_enrollment <= maxCapacity;

                  return (
                    <TableRow key={ratio.class_id}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-sm">
                            {/* Use class_id as fallback since we may not have name */}
                            Class {ratio.class_id.slice(0, 8)}
                          </p>
                          {/* Mobile-only fields */}
                          <div className="sm:hidden mt-1 space-y-1 text-xs text-muted-foreground">
                            <div className="flex items-center gap-2">
                              <span>Max/Caregiver:</span>
                              <Input
                                type="number"
                                min={1}
                                max={30}
                                value={edit.max_children_per_caregiver}
                                onChange={(e) =>
                                  handleChange(
                                    ratio.class_id,
                                    "max_children_per_caregiver",
                                    Number(e.target.value)
                                  )
                                }
                                className="h-7 w-16 text-xs"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <span>Caregivers:</span>
                              <Input
                                type="number"
                                min={0}
                                max={50}
                                value={edit.current_caregiver_count}
                                onChange={(e) =>
                                  handleChange(
                                    ratio.class_id,
                                    "current_caregiver_count",
                                    Number(e.target.value)
                                  )
                                }
                                className="h-7 w-16 text-xs"
                              />
                            </div>
                            <p>Cap: {maxCapacity} | Enrolled: {ratio.current_enrollment}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Input
                          type="number"
                          min={1}
                          max={30}
                          value={edit.max_children_per_caregiver}
                          onChange={(e) =>
                            handleChange(
                              ratio.class_id,
                              "max_children_per_caregiver",
                              Number(e.target.value)
                            )
                          }
                          className="h-8 w-20"
                        />
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Input
                          type="number"
                          min={0}
                          max={50}
                          value={edit.current_caregiver_count}
                          onChange={(e) =>
                            handleChange(
                              ratio.class_id,
                              "current_caregiver_count",
                              Number(e.target.value)
                            )
                          }
                          className="h-8 w-20"
                        />
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {maxCapacity}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm">
                        {ratio.current_enrollment}
                      </TableCell>
                      <TableCell>
                        {isCompliant ? (
                          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Compliant
                          </Badge>
                        ) : (
                          <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300">
                            <AlertTriangle className="mr-1 h-3 w-3" />
                            Over Capacity
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={saving || !hasChanges}>
          {saving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Ratios
        </Button>
      </div>
    </div>
  );
}
