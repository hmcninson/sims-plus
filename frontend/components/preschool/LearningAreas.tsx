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
import { Textarea } from "@/components/ui/textarea";
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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Switch } from "@/components/ui/switch";
import {
  BookOpen,
  Plus,
  Settings2,
  Trash2,
  Loader2,
  Sparkles,
  ChevronRight,
  Pencil,
} from "lucide-react";
import {
  getLearningAreas,
  createLearningArea,
  updateLearningArea,
  deleteLearningArea,
  seedLearningAreas,
  getLearningAreaWithSkills,
  createSkill,
  updateSkill,
  deleteSkill,
} from "@/actions/preschool.action";
import type {
  LearningArea,
  LearningAreaCreate,
  LearningAreaUpdate,
  DevelopmentalSkill,
  DevelopmentalSkillCreate,
} from "@/types";

interface LearningAreasProps {
  initialData?: LearningArea[];
}

export function LearningAreas({ initialData }: LearningAreasProps) {
  const [areas, setAreas] = useState<LearningArea[]>(initialData || []);
  const [loading, setLoading] = useState(!initialData);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingArea, setEditingArea] = useState<LearningArea | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [areaToDelete, setAreaToDelete] = useState<LearningArea | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [expandedArea, setExpandedArea] = useState<string | null>(null);
  const [areaSkills, setAreaSkills] = useState<Record<string, DevelopmentalSkill[]>>({});
  const [loadingSkills, setLoadingSkills] = useState<string | null>(null);
  const [isSkillDialogOpen, setIsSkillDialogOpen] = useState(false);
  const [selectedAreaForSkill, setSelectedAreaForSkill] = useState<LearningArea | null>(null);
  const [editingSkill, setEditingSkill] = useState<DevelopmentalSkill | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    code: "",
    description: "",
    icon: "",
    color: "#3b82f6",
    display_order: 0,
    is_active: true,
  });

  const [skillFormData, setSkillFormData] = useState({
    name: "",
    description: "",
    age_range_months_min: 24,
    age_range_months_max: 60,
  });

  useEffect(() => {
    if (!initialData) {
      loadAreas();
    }
  }, [initialData]);

  const loadAreas = async () => {
    setLoading(true);
    const result = await getLearningAreas(true);
    console.log("Learning areas result:", result);
    if (result.success && result.data) {
      setAreas(result.data);
    } else {
      console.error("Failed to load learning areas:", result.error);
    }
    setLoading(false);
  };

  const loadSkillsForArea = async (areaId: string) => {
    if (areaSkills[areaId]) return; // Already loaded

    setLoadingSkills(areaId);
    const result = await getLearningAreaWithSkills(areaId);
    if (result.success && result.data?.skills) {
      setAreaSkills((prev) => ({ ...prev, [areaId]: result.data!.skills || [] }));
    }
    setLoadingSkills(null);
  };

  const resetForm = () => {
    setFormData({
      name: "",
      code: "",
      description: "",
      icon: "",
      color: "#3b82f6",
      display_order: areas.length,
      is_active: true,
    });
    setEditingArea(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (area: LearningArea) => {
    setEditingArea(area);
    setFormData({
      name: area.name,
      code: area.code,
      description: area.description || "",
      icon: area.icon || "",
      color: area.color || "#3b82f6",
      display_order: area.display_order,
      is_active: area.is_active,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingArea) {
        const updateData: LearningAreaUpdate = {
          name: formData.name,
          code: formData.code,
          description: formData.description || undefined,
          icon: formData.icon || undefined,
          color: formData.color || undefined,
          display_order: formData.display_order,
          is_active: formData.is_active,
        };
        const result = await updateLearningArea(editingArea.id, updateData);
        if (result.success && result.data) {
          setAreas(areas.map((a) => (a.id === editingArea.id ? result.data! : a)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update learning area");
        }
      } else {
        const createData: LearningAreaCreate = {
          name: formData.name,
          code: formData.code,
          description: formData.description || undefined,
          icon: formData.icon || undefined,
          color: formData.color || undefined,
          display_order: formData.display_order,
          is_active: formData.is_active,
        };
        const result = await createLearningArea(createData);
        if (result.success && result.data) {
          setAreas([...areas, result.data]);
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create learning area");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (area: LearningArea) => {
    setAreaToDelete(area);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!areaToDelete) return;

    setIsDeleting(true);
    const result = await deleteLearningArea(areaToDelete.id);
    if (result.success) {
      setAreas(areas.filter((a) => a.id !== areaToDelete.id));
      setDeleteDialogOpen(false);
      setAreaToDelete(null);
    } else {
      setError(result.error || "Failed to delete learning area");
    }
    setIsDeleting(false);
  };

  const handleSeedData = async () => {
    setSeeding(true);
    setError(null);
    const result = await seedLearningAreas(true);
    if (result.success && result.data) {
      // Use the returned data directly (could be new or existing)
      setAreas(result.data);
    } else {
      setError(result.error || "Failed to seed learning areas");
    }
    setSeeding(false);
  };

  const handleAccordionChange = (value: string) => {
    setExpandedArea(value);
    if (value) {
      loadSkillsForArea(value);
    }
  };

  const openSkillDialog = (area: LearningArea) => {
    setSelectedAreaForSkill(area);
    setEditingSkill(null);
    setSkillFormData({
      name: "",
      description: "",
      age_range_months_min: 24,
      age_range_months_max: 60,
    });
    setIsSkillDialogOpen(true);
  };

  const openEditSkillDialog = (skill: DevelopmentalSkill, area: LearningArea) => {
    setSelectedAreaForSkill(area);
    setEditingSkill(skill);
    setSkillFormData({
      name: skill.name,
      description: skill.description || "",
      age_range_months_min: skill.age_range_months_min || 24,
      age_range_months_max: skill.age_range_months_max || 60,
    });
    setIsSkillDialogOpen(true);
  };

  const handleSubmitSkill = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedAreaForSkill) return;

    setSubmitting(true);
    setError(null);

    if (editingSkill) {
      // Update existing skill
      const result = await updateSkill(editingSkill.id, {
        name: skillFormData.name,
        description: skillFormData.description || undefined,
        age_range_months_min: skillFormData.age_range_months_min,
        age_range_months_max: skillFormData.age_range_months_max,
      });
      if (result.success && result.data) {
        setAreaSkills((prev) => ({
          ...prev,
          [selectedAreaForSkill.id]: prev[selectedAreaForSkill.id].map((s) =>
            s.id === editingSkill.id ? result.data! : s
          ),
        }));
        setIsSkillDialogOpen(false);
        setEditingSkill(null);
      } else {
        setError(result.error || "Failed to update skill");
      }
    } else {
      // Create new skill
      const data: DevelopmentalSkillCreate = {
        learning_area_id: selectedAreaForSkill.id,
        name: skillFormData.name,
        description: skillFormData.description || undefined,
        age_range_months_min: skillFormData.age_range_months_min,
        age_range_months_max: skillFormData.age_range_months_max,
      };

      const result = await createSkill(data);
      if (result.success && result.data) {
        setAreaSkills((prev) => ({
          ...prev,
          [selectedAreaForSkill.id]: [...(prev[selectedAreaForSkill.id] || []), result.data!],
        }));
        setIsSkillDialogOpen(false);
      } else {
        setError(result.error || "Failed to create skill");
      }
    }
    setSubmitting(false);
  };

  const handleDeleteSkill = async (skillId: string, areaId: string) => {
    const result = await deleteSkill(skillId);
    if (result.success) {
      setAreaSkills((prev) => ({
        ...prev,
        [areaId]: prev[areaId].filter((s) => s.id !== skillId),
      }));
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
              <BookOpen className="h-5 w-5" />
              Learning Areas
            </CardTitle>
            <CardDescription>
              Configure developmental learning areas and skills for preschool assessment.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            {areas.length === 0 && (
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
                Load Defaults
              </Button>
            )}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline" onClick={openCreateDialog}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Area
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <form onSubmit={handleSubmit}>
                  <DialogHeader>
                    <DialogTitle>
                      {editingArea ? "Edit Learning Area" : "Create Learning Area"}
                    </DialogTitle>
                    <DialogDescription>
                      {editingArea
                        ? "Update the learning area details."
                        : "Add a new learning area for preschool assessment."}
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
                        <Label htmlFor="name">Name</Label>
                        <Input
                          id="name"
                          placeholder="e.g., Language & Literacy"
                          value={formData.name}
                          onChange={(e) =>
                            setFormData({ ...formData, name: e.target.value })
                          }
                          required
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="code">Code</Label>
                        <Input
                          id="code"
                          placeholder="e.g., LL"
                          value={formData.code}
                          onChange={(e) =>
                            setFormData({ ...formData, code: e.target.value.toUpperCase() })
                          }
                          required
                          maxLength={10}
                        />
                      </div>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="description">Description</Label>
                      <Textarea
                        id="description"
                        placeholder="Brief description of this learning area"
                        value={formData.description}
                        onChange={(e) =>
                          setFormData({ ...formData, description: e.target.value })
                        }
                        rows={2}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="grid gap-2">
                        <Label htmlFor="icon">Icon Name</Label>
                        <Input
                          id="icon"
                          placeholder="e.g., book, heart"
                          value={formData.icon}
                          onChange={(e) =>
                            setFormData({ ...formData, icon: e.target.value })
                          }
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="color">Color</Label>
                        <div className="flex gap-2">
                          <Input
                            id="color"
                            type="color"
                            value={formData.color}
                            onChange={(e) =>
                              setFormData({ ...formData, color: e.target.value })
                            }
                            className="w-12 p-1"
                          />
                          <Input
                            value={formData.color}
                            onChange={(e) =>
                              setFormData({ ...formData, color: e.target.value })
                            }
                            placeholder="#3b82f6"
                            className="flex-1"
                          />
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Switch
                          id="is_active"
                          checked={formData.is_active}
                          onCheckedChange={(checked) =>
                            setFormData({ ...formData, is_active: checked })
                          }
                        />
                        <Label htmlFor="is_active" className="text-sm font-normal">
                          Active
                        </Label>
                      </div>
                      <div className="flex items-center gap-2">
                        <Label htmlFor="display_order" className="text-sm">Order:</Label>
                        <Input
                          id="display_order"
                          type="number"
                          value={formData.display_order}
                          onChange={(e) =>
                            setFormData({ ...formData, display_order: parseInt(e.target.value) || 0 })
                          }
                          className="w-16"
                          min={0}
                        />
                      </div>
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
                      {editingArea ? "Update" : "Create"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {areas.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground">
            <BookOpen className="mx-auto mb-2 h-12 w-12 opacity-20" />
            <p>No learning areas configured yet.</p>
            <p className="text-sm">Click &quot;Load Defaults&quot; to add standard preschool areas.</p>
          </div>
        ) : (
          <Accordion
            type="single"
            collapsible
            value={expandedArea || undefined}
            onValueChange={handleAccordionChange}
          >
            {areas
              .sort((a, b) => a.display_order - b.display_order)
              .map((area) => (
                <AccordionItem key={area.id} value={area.id}>
                  <div className="flex items-center">
                    <AccordionTrigger className="hover:no-underline flex-1">
                      <div className="flex flex-1 items-center gap-3 pr-4">
                        <div
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: area.color || "#3b82f6" }}
                        />
                        <span className="font-medium">{area.name}</span>
                        <Badge variant="outline" className="text-xs">
                          {area.code}
                        </Badge>
                        {!area.is_active && (
                          <Badge variant="secondary" className="text-xs">
                            Inactive
                          </Badge>
                        )}
                      </div>
                    </AccordionTrigger>
                    <div className="ml-auto flex items-center gap-1 pr-4">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openEditDialog(area);
                        }}
                      >
                        <Settings2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          openDeleteDialog(area);
                        }}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  <AccordionContent>
                    <div className="space-y-3 pl-6">
                      {area.description && (
                        <p className="text-sm text-muted-foreground">{area.description}</p>
                      )}
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium">Developmental Skills</h4>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => openSkillDialog(area)}
                        >
                          <Plus className="mr-1 h-3 w-3" />
                          Add Skill
                        </Button>
                      </div>
                      {loadingSkills === area.id ? (
                        <div className="flex items-center justify-center py-4">
                          <Loader2 className="h-4 w-4 animate-spin" />
                        </div>
                      ) : areaSkills[area.id]?.length > 0 ? (
                        <div className="space-y-1">
                          {areaSkills[area.id].map((skill) => (
                            <div
                              key={skill.id}
                              className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2 text-sm"
                            >
                              <div className="flex items-center gap-2">
                                <ChevronRight className="h-3 w-3 text-muted-foreground" />
                                <span>{skill.name}</span>
                                {skill.age_range_months_min && skill.age_range_months_max && (
                                  <span className="text-xs text-muted-foreground">
                                    ({skill.age_range_months_min}-{skill.age_range_months_max} months)
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openEditSkillDialog(skill, area)}
                                  className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
                                >
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeleteSkill(skill.id, area.id)}
                                  className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                                >
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="py-2 text-center text-sm text-muted-foreground">
                          No skills defined yet.
                        </p>
                      )}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
          </Accordion>
        )}
      </CardContent>

      {/* Delete Learning Area Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Learning Area</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{areaToDelete?.name}&quot;?
              This will also delete all associated skills. This action cannot be undone.
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

      {/* Add/Edit Skill Dialog */}
      <Dialog open={isSkillDialogOpen} onOpenChange={(open) => {
        setIsSkillDialogOpen(open);
        if (!open) setEditingSkill(null);
      }}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleSubmitSkill}>
            <DialogHeader>
              <DialogTitle>
                {editingSkill ? "Edit Developmental Skill" : "Add Developmental Skill"}
              </DialogTitle>
              <DialogDescription>
                {editingSkill
                  ? `Update skill in ${selectedAreaForSkill?.name}.`
                  : `Add a skill to ${selectedAreaForSkill?.name}.`
                }
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}
              <div className="grid gap-2">
                <Label htmlFor="skill_name">Skill Name</Label>
                <Input
                  id="skill_name"
                  placeholder="e.g., Recognizes letters of the alphabet"
                  value={skillFormData.name}
                  onChange={(e) =>
                    setSkillFormData({ ...skillFormData, name: e.target.value })
                  }
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="skill_description">Description (Optional)</Label>
                <Textarea
                  id="skill_description"
                  placeholder="Additional details about this skill"
                  value={skillFormData.description}
                  onChange={(e) =>
                    setSkillFormData({ ...skillFormData, description: e.target.value })
                  }
                  rows={2}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="age_min">Age Range (months)</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="age_min"
                    type="number"
                    value={skillFormData.age_range_months_min}
                    onChange={(e) =>
                      setSkillFormData({
                        ...skillFormData,
                        age_range_months_min: parseInt(e.target.value) || 0,
                      })
                    }
                    min={0}
                    max={84}
                  />
                  <span>to</span>
                  <Input
                    type="number"
                    value={skillFormData.age_range_months_max}
                    onChange={(e) =>
                      setSkillFormData({
                        ...skillFormData,
                        age_range_months_max: parseInt(e.target.value) || 0,
                      })
                    }
                    min={0}
                    max={84}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setIsSkillDialogOpen(false);
                  setEditingSkill(null);
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={submitting}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingSkill ? "Update Skill" : "Add Skill"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
