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
import {
  Star,
  Plus,
  Settings2,
  Trash2,
  Loader2,
  Sparkles,
  Check,
  Pencil,
} from "lucide-react";
import {
  getRatingScales,
  createRatingScale,
  updateRatingScale,
  deleteRatingScale,
  seedRatingScale,
} from "@/actions/preschool.action";
import type {
  PreschoolRatingScale,
  PreschoolRatingScaleCreate,
  PreschoolRatingScaleUpdate,
  PreschoolRatingCreate,
} from "@/types";

interface RatingScalesProps {
  initialData?: PreschoolRatingScale[];
}

export function RatingScales({ initialData }: RatingScalesProps) {
  const [scales, setScales] = useState<PreschoolRatingScale[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingScale, setEditingScale] = useState<PreschoolRatingScale | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedScale, setSelectedScale] = useState<PreschoolRatingScale | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [scaleToDelete, setScaleToDelete] = useState<PreschoolRatingScale | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [seeding, setSeeding] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    is_default: false,
    ratings: [] as PreschoolRatingCreate[],
  });

  // Rating level editing state
  const [isRatingDialogOpen, setIsRatingDialogOpen] = useState(false);
  const [editingRatingIndex, setEditingRatingIndex] = useState<number | null>(null);
  const [ratingFormData, setRatingFormData] = useState<PreschoolRatingCreate>({
    name: "",
    short_code: "",
    description: "",
    numeric_value: 0,
    color: "#9ca3af",
    icon: "circle",
    display_order: 0,
  });

  // Default developmental rating scale
  const defaultRatings: PreschoolRatingCreate[] = [
    {
      name: "Not Yet Observed",
      short_code: "NYO",
      description: "Skill not yet observed or too early for developmental stage",
      numeric_value: 0,
      color: "#9ca3af",
      icon: "circle-dashed",
      display_order: 0,
    },
    {
      name: "Emerging",
      short_code: "E",
      description: "Beginning to show awareness or initial attempts",
      numeric_value: 1,
      color: "#ef4444",
      icon: "circle",
      display_order: 1,
    },
    {
      name: "Developing",
      short_code: "D",
      description: "Progressing, needs support or reminders",
      numeric_value: 2,
      color: "#eab308",
      icon: "circle-half",
      display_order: 2,
    },
    {
      name: "Proficient",
      short_code: "P",
      description: "Consistently demonstrates skill independently",
      numeric_value: 3,
      color: "#22c55e",
      icon: "check-circle",
      display_order: 3,
    },
    {
      name: "Advanced",
      short_code: "A",
      description: "Exceeds age-appropriate expectations",
      numeric_value: 4,
      color: "#3b82f6",
      icon: "star",
      display_order: 4,
    },
  ];

  useEffect(() => {
    if (!initialData) {
      loadScales();
    }
  }, [initialData]);

  useEffect(() => {
    if (scales.length > 0 && !selectedScale) {
      const defaultScale = scales.find((s) => s.is_default) || scales[0];
      setSelectedScale(defaultScale);
    }
  }, [scales, selectedScale]);

  const loadScales = async () => {
    setLoading(true);
    const result = await getRatingScales();
    if (result.success && result.data) {
      setScales(result.data);
    }
    setLoading(false);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      is_default: false,
      ratings: [],
    });
    setEditingScale(null);
    setError(null);
  };

  const resetRatingForm = () => {
    setRatingFormData({
      name: "",
      short_code: "",
      description: "",
      numeric_value: 0,
      color: "#9ca3af",
      icon: "circle",
      display_order: 0,
    });
    setEditingRatingIndex(null);
  };

  const openAddRatingDialog = () => {
    resetRatingForm();
    // Set display_order to next available
    const maxOrder = formData.ratings.reduce(
      (max, r) => Math.max(max, r.display_order ?? 0),
      -1
    );
    setRatingFormData((prev) => ({
      ...prev,
      display_order: maxOrder + 1,
      numeric_value: maxOrder + 1,
    }));
    setIsRatingDialogOpen(true);
  };

  const openEditRatingDialog = (index: number) => {
    const rating = formData.ratings[index];
    setRatingFormData({ ...rating });
    setEditingRatingIndex(index);
    setIsRatingDialogOpen(true);
  };

  const handleSaveRating = () => {
    if (!ratingFormData.name || !ratingFormData.short_code) {
      return;
    }

    if (editingRatingIndex !== null) {
      // Update existing rating
      const updatedRatings = [...formData.ratings];
      updatedRatings[editingRatingIndex] = ratingFormData;
      setFormData({ ...formData, ratings: updatedRatings });
    } else {
      // Add new rating
      setFormData({
        ...formData,
        ratings: [...formData.ratings, ratingFormData],
      });
    }
    setIsRatingDialogOpen(false);
    resetRatingForm();
  };

  const handleRemoveRating = (index: number) => {
    const updatedRatings = formData.ratings.filter((_, i) => i !== index);
    // Re-assign display_order values
    const reorderedRatings = updatedRatings.map((r, i) => ({
      ...r,
      display_order: i,
    }));
    setFormData({ ...formData, ratings: reorderedRatings });
  };

  const openCreateDialog = () => {
    resetForm();
    // Start with empty form - user can load template if needed
    setIsDialogOpen(true);
  };

  const loadDefaultTemplate = () => {
    setFormData({
      name: "5-Point Developmental Scale",
      description: "Standard developmental assessment scale for preschool",
      is_default: scales.length === 0, // Set as default if no other scales exist
      ratings: defaultRatings,
    });
  };

  const openEditDialog = (scale: PreschoolRatingScale) => {
    setEditingScale(scale);
    setFormData({
      name: scale.name,
      description: scale.description || "",
      is_default: scale.is_default,
      ratings: scale.ratings || [],
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingScale) {
        const updateData: PreschoolRatingScaleUpdate = {
          name: formData.name,
          description: formData.description || undefined,
          is_default: formData.is_default,
        };
        const result = await updateRatingScale(editingScale.id, updateData);
        if (result.success && result.data) {
          // Reload to get the full scale with ratings
          await loadScales();
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update rating scale");
        }
      } else {
        const createData: PreschoolRatingScaleCreate = {
          name: formData.name,
          description: formData.description || undefined,
          is_default: formData.is_default,
          ratings: formData.ratings,
        };
        const result = await createRatingScale(createData);
        if (result.success && result.data) {
          await loadScales();
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create rating scale");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (scale: PreschoolRatingScale) => {
    setScaleToDelete(scale);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!scaleToDelete) return;

    setIsDeleting(true);
    const result = await deleteRatingScale(scaleToDelete.id);
    if (result.success) {
      setScales(scales.filter((s) => s.id !== scaleToDelete.id));
      if (selectedScale?.id === scaleToDelete.id) {
        setSelectedScale(scales.find((s) => s.id !== scaleToDelete.id) || null);
      }
      setDeleteDialogOpen(false);
      setScaleToDelete(null);
    } else {
      setError(result.error || "Failed to delete rating scale");
    }
    setIsDeleting(false);
  };

  const handleSeedData = async () => {
    setSeeding(true);
    setError(null);
    const result = await seedRatingScale(true);
    if (result.success && result.data) {
      // Reload to get the full scale with ratings
      await loadScales();
    } else {
      setError(result.error || "Failed to seed rating scale");
    }
    setSeeding(false);
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
              <Star className="h-5 w-5" />
              Rating Scale
            </CardTitle>
            <CardDescription>
              Configure developmental assessment rating scales for preschool.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {scales.length === 0 && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleSeedData}
                disabled={seeding}
              >
                {seeding ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                Load Default
              </Button>
            )}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={openCreateDialog}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Scale
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-3xl">
                <form onSubmit={handleSubmit}>
                  <DialogHeader>
                    <DialogTitle>
                      {editingScale ? "Edit Rating Scale" : "Create Rating Scale"}
                    </DialogTitle>
                    <DialogDescription>
                      {editingScale
                        ? "Update the rating scale details."
                        : "Add a new rating scale for preschool assessment."}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    {error && (
                      <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                        {error}
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="grid gap-2">
                        <Label htmlFor="name">Scale Name</Label>
                        <Input
                          id="name"
                          placeholder="e.g., 5-Point Developmental Scale"
                          value={formData.name}
                          onChange={(e) =>
                            setFormData({ ...formData, name: e.target.value })
                          }
                          required
                        />
                      </div>
                      <div className="flex items-end gap-4">
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
                            Set as default scale
                          </Label>
                        </div>
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

                    {/* Rating levels */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Rating Levels</Label>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={openAddRatingDialog}
                        >
                          <Plus className="mr-1 h-3 w-3" />
                          Add Level
                        </Button>
                      </div>
                      {formData.ratings.length > 0 ? (
                        <div className="rounded-lg border">
                          <div className="grid grid-cols-[70px_120px_50px_1fr_80px] gap-4 border-b bg-muted/50 p-3 text-sm font-medium">
                            <div>Code</div>
                            <div>Name</div>
                            <div>Value</div>
                            <div>Description</div>
                            <div>Actions</div>
                          </div>
                          <div className="divide-y">
                            {formData.ratings
                              .sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0))
                              .map((rating, idx) => (
                                <div
                                  key={idx}
                                  className="grid grid-cols-[70px_120px_50px_1fr_80px] gap-4 p-3 text-sm items-center"
                                >
                                  <div className="flex items-center gap-2">
                                    <div
                                      className="h-3 w-3 rounded-full"
                                      style={{ backgroundColor: rating.color || "#9ca3af" }}
                                    />
                                    <span className="font-medium">{rating.short_code}</span>
                                  </div>
                                  <div>{rating.name}</div>
                                  <div>{rating.numeric_value}</div>
                                  <div className="text-muted-foreground truncate">
                                    {rating.description}
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 w-7 p-0"
                                      onClick={() => openEditRatingDialog(idx)}
                                    >
                                      <Pencil className="h-3 w-3" />
                                    </Button>
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="sm"
                                      className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                                      onClick={() => handleRemoveRating(idx)}
                                    >
                                      <Trash2 className="h-3 w-3" />
                                    </Button>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      ) : (
                        <div className="rounded-lg border border-dashed p-6 text-center">
                          <p className="text-sm text-muted-foreground mb-3">
                            No rating levels added yet.
                          </p>
                          <div className="flex items-center justify-center gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={openAddRatingDialog}
                            >
                              <Plus className="mr-1 h-3 w-3" />
                              Add Level
                            </Button>
                            {!editingScale && (
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                onClick={loadDefaultTemplate}
                              >
                                <Sparkles className="mr-1 h-3 w-3" />
                                Use Template
                              </Button>
                            )}
                          </div>
                        </div>
                      )}
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
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {scales.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            <Star className="mx-auto mb-2 h-12 w-12 opacity-20" />
            <p>No rating scales configured yet.</p>
            <p className="text-sm">Click &quot;Load Default&quot; to add the standard scale.</p>
          </div>
        ) : (
          <>
            {/* Scale Selector */}
            <div className="flex items-center gap-4">
              <Label className="shrink-0">Active Scale:</Label>
              <Select
                value={selectedScale?.id || ""}
                onValueChange={(value) =>
                  setSelectedScale(scales.find((s) => s.id === value) || null)
                }
              >
                <SelectTrigger className="w-80">
                  <SelectValue placeholder="Select rating scale" />
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
                <div className="ml-auto flex items-center gap-2">
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

            {/* Rating Table */}
            {selectedScale && selectedScale.ratings && selectedScale.ratings.length > 0 && (
              <div className="rounded-lg border">
                <div className="grid grid-cols-5 gap-4 border-b bg-muted/50 p-3 text-sm font-medium">
                  <div>Code</div>
                  <div>Name</div>
                  <div>Value</div>
                  <div>Color</div>
                  <div>Description</div>
                </div>
                <div className="divide-y">
                  {selectedScale.ratings
                    .sort((a, b) => a.display_order - b.display_order)
                    .map((rating) => (
                      <div
                        key={rating.id}
                        className="grid grid-cols-5 gap-4 p-3 text-sm"
                      >
                        <div className="font-medium">{rating.short_code}</div>
                        <div>{rating.name}</div>
                        <div>{rating.numeric_value}</div>
                        <div className="flex items-center gap-2">
                          <div
                            className="h-4 w-4 rounded-full"
                            style={{ backgroundColor: rating.color || "#9ca3af" }}
                          />
                          <span className="text-xs text-muted-foreground">
                            {rating.color}
                          </span>
                        </div>
                        <div className="text-muted-foreground">{rating.description}</div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {selectedScale && (!selectedScale.ratings || selectedScale.ratings.length === 0) && (
              <div className="py-4 text-center text-muted-foreground">
                No ratings defined for this scale.
              </div>
            )}
          </>
        )}
      </CardContent>

      {/* Delete Rating Scale Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Rating Scale</AlertDialogTitle>
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

      {/* Add/Edit Rating Level Dialog */}
      <Dialog open={isRatingDialogOpen} onOpenChange={setIsRatingDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingRatingIndex !== null ? "Edit Rating Level" : "Add Rating Level"}
            </DialogTitle>
            <DialogDescription>
              {editingRatingIndex !== null
                ? "Update the rating level details."
                : "Add a new rating level to the scale."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="rating_short_code">Code *</Label>
                <Input
                  id="rating_short_code"
                  placeholder="e.g., E, D, P"
                  maxLength={5}
                  value={ratingFormData.short_code}
                  onChange={(e) =>
                    setRatingFormData({ ...ratingFormData, short_code: e.target.value.toUpperCase() })
                  }
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="rating_numeric_value">Numeric Value *</Label>
                <Input
                  id="rating_numeric_value"
                  type="number"
                  min={0}
                  value={ratingFormData.numeric_value}
                  onChange={(e) =>
                    setRatingFormData({ ...ratingFormData, numeric_value: parseInt(e.target.value) || 0 })
                  }
                  required
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rating_name">Name *</Label>
              <Input
                id="rating_name"
                placeholder="e.g., Emerging, Developing, Proficient"
                value={ratingFormData.name}
                onChange={(e) =>
                  setRatingFormData({ ...ratingFormData, name: e.target.value })
                }
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rating_description">Description</Label>
              <Input
                id="rating_description"
                placeholder="Brief description of this rating level"
                value={ratingFormData.description || ""}
                onChange={(e) =>
                  setRatingFormData({ ...ratingFormData, description: e.target.value })
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="rating_color">Color</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="rating_color"
                    type="color"
                    className="h-10 w-14 p-1"
                    value={ratingFormData.color || "#9ca3af"}
                    onChange={(e) =>
                      setRatingFormData({ ...ratingFormData, color: e.target.value })
                    }
                  />
                  <Input
                    value={ratingFormData.color || "#9ca3af"}
                    onChange={(e) =>
                      setRatingFormData({ ...ratingFormData, color: e.target.value })
                    }
                    placeholder="#9ca3af"
                    className="flex-1"
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="rating_display_order">Display Order</Label>
                <Input
                  id="rating_display_order"
                  type="number"
                  min={0}
                  value={ratingFormData.display_order}
                  onChange={(e) =>
                    setRatingFormData({ ...ratingFormData, display_order: parseInt(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setIsRatingDialogOpen(false);
                resetRatingForm();
              }}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSaveRating}
              disabled={!ratingFormData.name || !ratingFormData.short_code}
            >
              {editingRatingIndex !== null ? "Update" : "Add"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
