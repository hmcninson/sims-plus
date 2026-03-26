"use client";

import { useState, useCallback, useRef } from "react";
import {
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  ArrowUp,
  ArrowDown,
} from "lucide-react";

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
import { cn } from "@/lib/utils";
import type {
  AssessmentComponentType,
  AssessmentComponentCreate,
} from "@/types/curriculum.type";

const COMPONENT_TYPE_OPTIONS: { value: AssessmentComponentType; label: string }[] = [
  { value: "continuous_assessment", label: "Continuous Assessment" },
  { value: "exam", label: "Exam" },
  { value: "class_work", label: "Class Work" },
  { value: "homework", label: "Homework" },
  { value: "midterm", label: "Midterm" },
  { value: "end_term", label: "End of Term" },
  { value: "coursework", label: "Coursework" },
  { value: "controlled_assessment", label: "Controlled Assessment" },
  { value: "external_exam", label: "External Exam" },
  { value: "practical", label: "Practical" },
  { value: "oral", label: "Oral" },
  { value: "internal_assessment", label: "Internal Assessment" },
  { value: "external_assessment", label: "External Assessment" },
  { value: "extended_essay", label: "Extended Essay" },
  { value: "tok", label: "Theory of Knowledge" },
  { value: "cas", label: "CAS" },
  { value: "quiz", label: "Quiz" },
  { value: "test", label: "Test" },
  { value: "project", label: "Project" },
  { value: "participation", label: "Participation" },
  { value: "final", label: "Final" },
  { value: "controle_continu", label: "Controle Continu" },
  { value: "epreuve", label: "Epreuve" },
  { value: "observation", label: "Observation" },
  { value: "narrative", label: "Narrative" },
  { value: "portfolio", label: "Portfolio" },
];

interface EditableComponent extends AssessmentComponentCreate {
  _key: string; // local key for React rendering
}

function createDefaultComponent(sequence: number): EditableComponent {
  return {
    _key: crypto.randomUUID(),
    component_type: "continuous_assessment",
    name: "",
    weight: 0,
    max_score: 100,
    is_external: false,
    sequence,
    maps_to_ca: false,
    maps_to_exam: false,
  };
}

interface AssessmentStructureEditorProps {
  /** Initial components to edit. */
  initialComponents?: AssessmentComponentCreate[];
  /** Callback when components change. */
  onChange: (components: AssessmentComponentCreate[]) => void;
  /** Callback when a component is deleted — lets the parent persist immediately. */
  onDelete?: (deleted: AssessmentComponentCreate) => void;
  /** Whether the editor is in read-only mode. */
  readOnly?: boolean;
}

export function AssessmentStructureEditor({
  initialComponents,
  onChange,
  onDelete,
  readOnly = false,
}: AssessmentStructureEditorProps) {
  const [components, setComponents] = useState<EditableComponent[]>(() => {
    if (initialComponents && initialComponents.length > 0) {
      return initialComponents.map((c, i) => ({
        ...c,
        _key: crypto.randomUUID(),
        sequence: c.sequence ?? i + 1,
      }));
    }
    return [];
  });

  const [deleteIndex, setDeleteIndex] = useState<number | null>(null);
  // Ref mirrors deleteIndex so the AlertDialogAction onClick can read the
  // value even if Radix's onOpenChange fires first and clears the state.
  const deleteIndexRef = useRef<number | null>(null);

  const setDeleteTarget = useCallback((index: number | null) => {
    deleteIndexRef.current = index;
    setDeleteIndex(index);
  }, []);

  // Coerce to number — API returns Decimal-serialized strings (e.g. "20.00")
  const totalWeight = components.reduce((sum, c) => sum + (Number(c.weight) || 0), 0);
  const isValid = Math.abs(totalWeight - 100) < 0.01;

  const emitChange = (updated: EditableComponent[]) => {
    setComponents(updated);
    // Strip _key before emitting
    onChange(
      updated.map(({ _key, ...rest }) => rest),
    );
  };

  const handleAdd = () => {
    const next = [...components, createDefaultComponent(components.length + 1)];
    emitChange(next);
  };

  const handleRemove = (index: number) => {
    const removed = components[index];
    const next = components.filter((_, i) => i !== index).map((c, i) => ({
      ...c,
      sequence: i + 1,
    }));
    emitChange(next);
    setDeleteTarget(null);
    // Notify parent so it can persist the deletion immediately
    if (onDelete) {
      const { _key, ...rest } = removed;
      onDelete(rest);
    }
  };

  const handleUpdate = (
    index: number,
    field: keyof EditableComponent,
    value: string | number | boolean,
  ) => {
    const next = [...components];
    next[index] = { ...next[index], [field]: value };
    emitChange(next);
  };

  const handleMove = (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= components.length) return;
    const next = [...components];
    [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
    const resequenced = next.map((c, i) => ({ ...c, sequence: i + 1 }));
    emitChange(resequenced);
  };

  return (
    <div className="space-y-4">
      {/* Weight indicator */}
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border px-4 py-2 text-sm",
          isValid
            ? "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
            : "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
        )}
      >
        {isValid ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : (
          <AlertCircle className="h-4 w-4" />
        )}
        <span>
          Total weight: <strong>{totalWeight}%</strong>
          {!isValid && " (must equal 100%)"}
        </span>
      </div>

      {/* Desktop table view */}
      <div className="hidden md:block overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[40px]">#</TableHead>
              <TableHead className="w-[180px]">Type</TableHead>
              <TableHead>Name</TableHead>
              <TableHead className="w-[80px]">Weight %</TableHead>
              <TableHead className="w-[90px]">Max Score</TableHead>
              <TableHead className="w-[70px] text-center">External</TableHead>
              <TableHead className="w-[50px] text-center">CA</TableHead>
              <TableHead className="w-[55px] text-center">Exam</TableHead>
              {!readOnly && <TableHead className="w-[100px]">Actions</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {components.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={readOnly ? 8 : 9}
                  className="h-24 text-center text-muted-foreground"
                >
                  No assessment components yet. Click "Add Component" to begin.
                </TableCell>
              </TableRow>
            ) : (
              components.map((comp, index) => (
                <TableRow key={comp._key}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {comp.sequence}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={comp.component_type}
                      onValueChange={(v) =>
                        handleUpdate(index, "component_type", v)
                      }
                      disabled={readOnly}
                    >
                      <SelectTrigger className="h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {COMPONENT_TYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Input
                      value={comp.name}
                      onChange={(e) =>
                        handleUpdate(index, "name", e.target.value)
                      }
                      placeholder="Component name"
                      className="h-8 text-xs"
                      disabled={readOnly}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={comp.weight}
                      onChange={(e) =>
                        handleUpdate(
                          index,
                          "weight",
                          parseFloat(e.target.value) || 0,
                        )
                      }
                      min={0}
                      max={100}
                      className="h-8 text-xs"
                      disabled={readOnly}
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      value={comp.max_score ?? ""}
                      onChange={(e) =>
                        handleUpdate(
                          index,
                          "max_score",
                          parseInt(e.target.value) || 0,
                        )
                      }
                      min={0}
                      className="h-8 text-xs"
                      disabled={readOnly}
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <Checkbox
                      checked={comp.is_external}
                      onCheckedChange={(checked) =>
                        handleUpdate(index, "is_external", !!checked)
                      }
                      disabled={readOnly}
                      aria-label="External component"
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <Checkbox
                      checked={comp.maps_to_ca}
                      onCheckedChange={(checked) =>
                        handleUpdate(index, "maps_to_ca", !!checked)
                      }
                      disabled={readOnly}
                      aria-label="Maps to CA"
                    />
                  </TableCell>
                  <TableCell className="text-center">
                    <Checkbox
                      checked={comp.maps_to_exam}
                      onCheckedChange={(checked) =>
                        handleUpdate(index, "maps_to_exam", !!checked)
                      }
                      disabled={readOnly}
                      aria-label="Maps to exam"
                    />
                  </TableCell>
                  {!readOnly && (
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleMove(index, "up")}
                          disabled={index === 0}
                          aria-label="Move up"
                        >
                          <ArrowUp className="h-3 w-3" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => handleMove(index, "down")}
                          disabled={index === components.length - 1}
                          aria-label="Move down"
                        >
                          <ArrowDown className="h-3 w-3" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => setDeleteTarget(index)}
                          aria-label="Delete component"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Mobile card view */}
      <div className="md:hidden space-y-3">
        {components.length === 0 ? (
          <div className="flex h-24 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            No assessment components yet.
          </div>
        ) : (
          components.map((comp, index) => (
            <div
              key={comp._key}
              className="rounded-lg border p-3 space-y-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  #{comp.sequence}
                </span>
                {!readOnly && (
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleMove(index, "up")}
                      disabled={index === 0}
                    >
                      <ArrowUp className="h-3 w-3" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleMove(index, "down")}
                      disabled={index === components.length - 1}
                    >
                      <ArrowDown className="h-3 w-3" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => setDeleteTarget(index)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <Select
                  value={comp.component_type}
                  onValueChange={(v) =>
                    handleUpdate(index, "component_type", v)
                  }
                  disabled={readOnly}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    {COMPONENT_TYPE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  value={comp.name}
                  onChange={(e) =>
                    handleUpdate(index, "name", e.target.value)
                  }
                  placeholder="Component name"
                  className="h-8 text-xs"
                  disabled={readOnly}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground">Weight %</label>
                  <Input
                    type="number"
                    value={comp.weight}
                    onChange={(e) =>
                      handleUpdate(index, "weight", parseFloat(e.target.value) || 0)
                    }
                    min={0}
                    max={100}
                    className="h-8 text-xs"
                    disabled={readOnly}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-muted-foreground">Max Score</label>
                  <Input
                    type="number"
                    value={comp.max_score ?? ""}
                    onChange={(e) =>
                      handleUpdate(index, "max_score", parseInt(e.target.value) || 0)
                    }
                    min={0}
                    className="h-8 text-xs"
                    disabled={readOnly}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-4 text-xs">
                <label className="flex items-center gap-1.5">
                  <Checkbox
                    checked={comp.is_external}
                    onCheckedChange={(checked) =>
                      handleUpdate(index, "is_external", !!checked)
                    }
                    disabled={readOnly}
                  />
                  External
                </label>
                <label className="flex items-center gap-1.5">
                  <Checkbox
                    checked={comp.maps_to_ca}
                    onCheckedChange={(checked) =>
                      handleUpdate(index, "maps_to_ca", !!checked)
                    }
                    disabled={readOnly}
                  />
                  CA
                </label>
                <label className="flex items-center gap-1.5">
                  <Checkbox
                    checked={comp.maps_to_exam}
                    onCheckedChange={(checked) =>
                      handleUpdate(index, "maps_to_exam", !!checked)
                    }
                    disabled={readOnly}
                  />
                  Exam
                </label>
              </div>
            </div>
          ))
        )}
      </div>

      {!readOnly && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleAdd}
          className="w-full sm:w-auto"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Component
        </Button>
      )}

      {/* Delete confirmation */}
      <AlertDialog
        open={deleteIndex !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Component</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{" "}
              {deleteIndex !== null && components[deleteIndex]
                ? `"${components[deleteIndex].name || "this component"}"`
                : "this component"}
              ? This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                // Read from ref instead of state — Radix AlertDialog in controlled
                // mode may fire onOpenChange(false) before onClick, clearing the
                // state value. The ref retains the index until we explicitly reset it.
                const idx = deleteIndexRef.current;
                if (idx !== null) handleRemove(idx);
              }}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
