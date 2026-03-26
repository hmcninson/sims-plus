"use client";

import { useState, useEffect, useCallback, useTransition } from "react";
import { Check, Loader2, Save, Trash2, AlertCircle, ArrowRightLeft } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { getGradingScales } from "@/actions/academic.action";
import {
  getGradeEquivalencies,
  createGradeEquivalencies,
  deleteGradeEquivalency,
} from "@/actions/curriculum.action";
import type { GradingScale, Grade } from "@/types";
import type { GradeEquivalency, GradeMapping } from "@/types/curriculum.type";

interface GradeEquivalencyMatrixProps {
  initialScales?: GradingScale[];
}

export function GradeEquivalencyMatrix({ initialScales }: GradeEquivalencyMatrixProps) {
  const [scales, setScales] = useState<GradingScale[]>(initialScales || []);
  const [isLoadingScales, setIsLoadingScales] = useState(!initialScales);
  const [sourceScaleId, setSourceScaleId] = useState<string>("");
  const [targetScaleId, setTargetScaleId] = useState<string>("");
  const [existingMappings, setExistingMappings] = useState<GradeEquivalency[]>([]);
  const [pendingMappings, setPendingMappings] = useState<Map<string, string>>(new Map());
  const [isPending, startTransition] = useTransition();
  const [isSaving, setIsSaving] = useState(false);

  // Load grading scales
  useEffect(() => {
    if (initialScales) return;
    let mounted = true;
    async function load() {
      const result = await getGradingScales();
      if (mounted && result.success) {
        setScales(result.data);
      }
      if (mounted) setIsLoadingScales(false);
    }
    load();
    return () => { mounted = false; };
  }, [initialScales]);

  // Load existing equivalencies when both scales are selected
  const loadEquivalencies = useCallback(() => {
    if (!sourceScaleId || !targetScaleId) return;
    startTransition(async () => {
      const result = await getGradeEquivalencies({
        source_scale_id: sourceScaleId,
        target_scale_id: targetScaleId,
        page_size: 200,
      });
      if (result.success) {
        setExistingMappings(result.data.items);
        // Pre-populate pending mappings from existing
        const map = new Map<string, string>();
        for (const eq of result.data.items) {
          map.set(eq.source_grade_id, eq.target_grade_id);
        }
        setPendingMappings(map);
      }
    });
  }, [sourceScaleId, targetScaleId]);

  useEffect(() => {
    loadEquivalencies();
  }, [loadEquivalencies]);

  const sourceScale = scales.find((s) => s.id === sourceScaleId);
  const targetScale = scales.find((s) => s.id === targetScaleId);
  const sourceGrades = sourceScale?.grades || [];
  const targetGrades = targetScale?.grades || [];

  const toggleMapping = (sourceGradeId: string, targetGradeId: string) => {
    setPendingMappings((prev) => {
      const next = new Map(prev);
      if (next.get(sourceGradeId) === targetGradeId) {
        next.delete(sourceGradeId);
      } else {
        next.set(sourceGradeId, targetGradeId);
      }
      return next;
    });
  };

  const handleSave = async () => {
    if (!sourceScaleId || !targetScaleId) return;

    setIsSaving(true);
    try {
      // Delete existing mappings first
      for (const existing of existingMappings) {
        await deleteGradeEquivalency(existing.id);
      }

      // Create new mappings if any
      const mappings: GradeMapping[] = [];
      pendingMappings.forEach((targetGradeId, sourceGradeId) => {
        mappings.push({ source_grade_id: sourceGradeId, target_grade_id: targetGradeId });
      });

      if (mappings.length > 0) {
        const result = await createGradeEquivalencies({
          source_grading_scale_id: sourceScaleId,
          target_grading_scale_id: targetScaleId,
          mappings,
        });
        if (!result.success) {
          toast.error("Failed to save mappings", { description: result.error });
          return;
        }
      }

      toast.success("Grade equivalencies saved successfully");
      loadEquivalencies();
    } catch {
      toast.error("An error occurred while saving");
    } finally {
      setIsSaving(false);
    }
  };

  const handleClearAll = () => {
    setPendingMappings(new Map());
  };

  // Check if mappings have changed from saved state
  const hasChanges = (() => {
    const existingMap = new Map<string, string>();
    for (const eq of existingMappings) {
      existingMap.set(eq.source_grade_id, eq.target_grade_id);
    }
    if (existingMap.size !== pendingMappings.size) return true;
    for (const [key, val] of pendingMappings) {
      if (existingMap.get(key) !== val) return true;
    }
    return false;
  })();

  if (isLoadingScales) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-72" />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-4">
            <Skeleton className="h-9 flex-1" />
            <Skeleton className="h-9 flex-1" />
          </div>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (scales.length < 2) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
          <AlertCircle className="h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground text-center">
            You need at least two grading scales to create equivalency mappings.
            <br />
            Go to Academic Settings to create grading scales first.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Scale selectors */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Select Grading Scales</CardTitle>
          <CardDescription>
            Choose the source and target grading scales to map grades between them.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1 w-full">
              <label className="text-sm font-medium mb-1.5 block">Source Scale</label>
              <Select value={sourceScaleId} onValueChange={setSourceScaleId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select source scale" />
                </SelectTrigger>
                <SelectContent>
                  {scales.map((scale) => (
                    <SelectItem
                      key={scale.id}
                      value={scale.id}
                      disabled={scale.id === targetScaleId}
                    >
                      {scale.name}
                      {scale.grades && (
                        <span className="text-muted-foreground ml-2">
                          ({scale.grades.length} grades)
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ArrowRightLeft className="h-5 w-5 text-muted-foreground shrink-0 mt-6 sm:mt-0 hidden sm:block" />

            <div className="flex-1 w-full">
              <label className="text-sm font-medium mb-1.5 block">Target Scale</label>
              <Select value={targetScaleId} onValueChange={setTargetScaleId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select target scale" />
                </SelectTrigger>
                <SelectContent>
                  {scales.map((scale) => (
                    <SelectItem
                      key={scale.id}
                      value={scale.id}
                      disabled={scale.id === sourceScaleId}
                    >
                      {scale.name}
                      {scale.grades && (
                        <span className="text-muted-foreground ml-2">
                          ({scale.grades.length} grades)
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Matrix grid */}
      {sourceScaleId && targetScaleId && (
        <Card>
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base">Equivalency Matrix</CardTitle>
                <CardDescription>
                  Click a cell to map a source grade to a target grade. Each source grade can map to one target grade.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearAll}
                  disabled={pendingMappings.size === 0 || isSaving}
                >
                  <Trash2 className="mr-2 h-3.5 w-3.5" />
                  Clear All
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={!hasChanges || isSaving}
                >
                  {isSaving ? (
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="mr-2 h-3.5 w-3.5" />
                  )}
                  Save Mappings
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {isPending ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : sourceGrades.length === 0 || targetGrades.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3">
                <AlertCircle className="h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  One or both scales have no grades defined. Add grades to the scales first.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <TooltipProvider>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="sticky left-0 bg-background z-10 min-w-[100px]">
                          Source / Target
                        </TableHead>
                        {targetGrades.map((tg) => (
                          <TableHead key={tg.id} className="text-center min-w-[80px]">
                            <div className="flex flex-col items-center gap-0.5">
                              <span className="font-semibold">{tg.grade}</span>
                              <span className="text-[10px] text-muted-foreground font-normal">
                                {tg.min_score}-{tg.max_score}
                              </span>
                            </div>
                          </TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sourceGrades.map((sg) => (
                        <TableRow key={sg.id}>
                          <TableCell className="sticky left-0 bg-background z-10 font-medium">
                            <div className="flex flex-col">
                              <span>{sg.grade}</span>
                              <span className="text-[10px] text-muted-foreground">
                                {sg.min_score}-{sg.max_score}
                              </span>
                            </div>
                          </TableCell>
                          {targetGrades.map((tg) => {
                            const isSelected = pendingMappings.get(sg.id) === tg.id;
                            return (
                              <TableCell key={tg.id} className="text-center p-1">
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <button
                                      type="button"
                                      onClick={() => toggleMapping(sg.id, tg.id)}
                                      className={`
                                        inline-flex items-center justify-center
                                        h-8 w-8 rounded-md border transition-colors
                                        ${isSelected
                                          ? "bg-primary text-primary-foreground border-primary"
                                          : "border-transparent hover:border-muted-foreground/30 hover:bg-muted/50"
                                        }
                                      `}
                                      aria-label={`Map ${sg.grade} to ${tg.grade}`}
                                    >
                                      {isSelected && <Check className="h-4 w-4" />}
                                    </button>
                                  </TooltipTrigger>
                                  <TooltipContent>
                                    {sg.grade} ({sg.remark || `${sg.min_score}-${sg.max_score}`})
                                    {" -> "}
                                    {tg.grade} ({tg.remark || `${tg.min_score}-${tg.max_score}`})
                                  </TooltipContent>
                                </Tooltip>
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TooltipProvider>
              </div>
            )}

            {/* Summary */}
            {pendingMappings.size > 0 && (
              <div className="mt-4 rounded-lg border p-3 bg-muted/30">
                <p className="text-sm font-medium mb-2">
                  Mappings ({pendingMappings.size})
                </p>
                <div className="flex flex-wrap gap-2">
                  {Array.from(pendingMappings.entries()).map(([srcId, tgtId]) => {
                    const src = sourceGrades.find((g) => g.id === srcId);
                    const tgt = targetGrades.find((g) => g.id === tgtId);
                    if (!src || !tgt) return null;
                    return (
                      <Badge key={srcId} variant="secondary" className="text-xs">
                        {src.grade} &rarr; {tgt.grade}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            )}

            {hasChanges && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                You have unsaved changes.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
