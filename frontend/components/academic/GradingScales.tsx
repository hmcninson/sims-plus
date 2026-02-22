"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GraduationCap, Plus, Settings2, Trash2, Loader2 } from "lucide-react";
import {
  getGradingScales,
  createGradingScale,
  updateGradingScale,
  deleteGradingScale,
} from "@/actions/academic.action";
import type { GradingScale, GradingScaleCreate, GradingScaleUpdate, GradeCreate } from "@/types";

interface GradingScalesProps {
  initialData?: GradingScale[];
}

// WAEC default grades
const waecGrades: GradeCreate[] = [
  { grade: "A1", min_score: 80, max_score: 100, grade_point: 1, remark: "Excellent" },
  { grade: "B2", min_score: 70, max_score: 79, grade_point: 2, remark: "Very Good" },
  { grade: "B3", min_score: 65, max_score: 69, grade_point: 3, remark: "Good" },
  { grade: "C4", min_score: 60, max_score: 64, grade_point: 4, remark: "Credit" },
  { grade: "C5", min_score: 55, max_score: 59, grade_point: 5, remark: "Credit" },
  { grade: "C6", min_score: 50, max_score: 54, grade_point: 6, remark: "Credit" },
  { grade: "D7", min_score: 45, max_score: 49, grade_point: 7, remark: "Pass" },
  { grade: "E8", min_score: 40, max_score: 44, grade_point: 8, remark: "Pass" },
  { grade: "F9", min_score: 0, max_score: 39, grade_point: 9, remark: "Fail" },
];

export function GradingScales({ initialData }: GradingScalesProps) {
  const [scales, setScales] = useState<GradingScale[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingScale, setEditingScale] = useState<GradingScale | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedScale, setSelectedScale] = useState<GradingScale | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [scaleToDelete, setScaleToDelete] = useState<GradingScale | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    scale_type: "waec" as "waec" | "gpa" | "percentage" | "custom",
    is_default: false,
    grades: [] as GradeCreate[],
  });

  useEffect(() => {
    if (!initialData) {
      loadScales();
    }
  }, [initialData]);

  useEffect(() => {
    // Set default scale for display
    if (scales.length > 0 && !selectedScale) {
      const defaultScale = scales.find((s) => s.is_default) || scales[0];
      setSelectedScale(defaultScale);
    }
  }, [scales, selectedScale]);

  const loadScales = async () => {
    setLoading(true);
    const result = await getGradingScales();
    if (result.success && result.data) {
      setScales(result.data);
    }
    setLoading(false);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      scale_type: "waec",
      is_default: false,
      grades: [],
    });
    setEditingScale(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setFormData((prev) => ({ ...prev, grades: waecGrades }));
    setIsDialogOpen(true);
  };

  const openEditDialog = (scale: GradingScale) => {
    setEditingScale(scale);
    setFormData({
      name: scale.name,
      description: scale.description || "",
      scale_type: scale.scale_type as "waec" | "gpa" | "percentage" | "custom",
      is_default: scale.is_default,
      grades: scale.grades || [],
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingScale) {
        const updateData: GradingScaleUpdate = {
          name: formData.name,
          description: formData.description || undefined,
          scale_type: formData.scale_type,
          is_default: formData.is_default,
        };
        const result = await updateGradingScale(editingScale.id, updateData);
        if (result.success && result.data) {
          setScales(scales.map((s) => (s.id === editingScale.id ? result.data! : s)));
          setSelectedScale(result.data);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update grading scale");
        }
      } else {
        const createData: GradingScaleCreate = {
          name: formData.name,
          description: formData.description || undefined,
          scale_type: formData.scale_type,
          is_default: formData.is_default,
          grades: formData.grades,
        };
        const result = await createGradingScale(createData);
        if (result.success && result.data) {
          setScales([...scales, result.data]);
          setSelectedScale(result.data);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create grading scale");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (scale: GradingScale) => {
    setScaleToDelete(scale);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!scaleToDelete) return;

    setIsDeleting(true);
    const result = await deleteGradingScale(scaleToDelete.id);
    if (result.success) {
      setScales(scales.filter((s) => s.id !== scaleToDelete.id));
      if (selectedScale?.id === scaleToDelete.id) {
        setSelectedScale(scales.find((s) => s.id !== scaleToDelete.id) || null);
      }
      setDeleteDialogOpen(false);
      setScaleToDelete(null);
    } else {
      setError(result.error || "Failed to delete grading scale");
    }
    setIsDeleting(false);
  };

  const getScaleTypeLabel = (type: string) => {
    switch (type) {
      case "waec":
        return "WAEC Standard (A1-F9)";
      case "gpa":
        return "GPA Scale (4.0)";
      case "percentage":
        return "Percentage Based";
      default:
        return "Custom Scale";
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <GraduationCap className="h-5 w-5" />
              Grading System
            </CardTitle>
            <CardDescription>
              Configure your school&apos;s grading scale.
            </CardDescription>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline" onClick={openCreateDialog}>
                <Plus className="mr-2 h-4 w-4" />
                New Scale
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingScale ? "Edit Grading Scale" : "Create Grading Scale"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingScale
                      ? "Update the grading scale details."
                      : "Add a new grading scale for your school."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        placeholder="e.g., WAEC Grading"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="scale_type">Scale Type</Label>
                      <Select
                        value={formData.scale_type}
                        onValueChange={(value) =>
                          setFormData({
                            ...formData,
                            scale_type: value as "waec" | "gpa" | "percentage" | "custom",
                          })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="waec">WAEC Standard</SelectItem>
                          <SelectItem value="gpa">GPA Scale</SelectItem>
                          <SelectItem value="percentage">Percentage</SelectItem>
                          <SelectItem value="custom">Custom</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="description">Description (Optional)</Label>
                    <Input
                      id="description"
                      placeholder="Brief description"
                      value={formData.description}
                      onChange={(e) =>
                        setFormData({ ...formData, description: e.target.value })
                      }
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_default"
                      checked={formData.is_default}
                      onChange={(e) =>
                        setFormData({ ...formData, is_default: e.target.checked })
                      }
                      className="h-4 w-4"
                    />
                    <Label htmlFor="is_default" className="text-sm font-normal">
                      Set as default grading scale
                    </Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {editingScale ? "Update" : "Create"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {scales.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            No grading scales found. Create your first grading scale to get started.
          </div>
        ) : (
          <>
            {/* Scale Selector */}
            <div className="flex items-center gap-4">
              <Label>Active Scale:</Label>
              <Select
                value={selectedScale?.id || ""}
                onValueChange={(value) =>
                  setSelectedScale(scales.find((s) => s.id === value) || null)
                }
              >
                <SelectTrigger className="w-64">
                  <SelectValue placeholder="Select grading scale" />
                </SelectTrigger>
                <SelectContent>
                  {scales.map((scale) => (
                    <SelectItem key={scale.id} value={scale.id}>
                      {scale.name}
                      {scale.is_default && " (Default)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedScale && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditDialog(selectedScale)}
                  >
                    <Settings2 className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => openDeleteDialog(selectedScale)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>

            {/* Grade Table */}
            {selectedScale && selectedScale.grades && selectedScale.grades.length > 0 && (
              <div className="rounded-lg border">
                <div className="grid grid-cols-5 gap-4 border-b bg-muted/50 p-3 text-sm font-medium">
                  <div>Grade</div>
                  <div>Min Score</div>
                  <div>Max Score</div>
                  <div>Points</div>
                  <div>Remark</div>
                </div>
                <div className="divide-y">
                  {selectedScale.grades
                    .sort((a, b) => b.max_score - a.max_score)
                    .map((grade) => (
                      <div
                        key={grade.id}
                        className="grid grid-cols-5 gap-4 p-3 text-sm"
                      >
                        <div className="font-medium">{grade.grade}</div>
                        <div>{grade.min_score}%</div>
                        <div>{grade.max_score}%</div>
                        <div>{grade.grade_point}</div>
                        <div className="text-muted-foreground">{grade.remark}</div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {selectedScale && (!selectedScale.grades || selectedScale.grades.length === 0) && (
              <div className="py-4 text-center text-muted-foreground">
                No grades defined for this scale.
              </div>
            )}
          </>
        )}
      </CardContent>

      {/* Delete Grading Scale Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Grading Scale</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{scaleToDelete?.name}&quot;?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
