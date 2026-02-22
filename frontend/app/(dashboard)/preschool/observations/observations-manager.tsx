"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import {
  Loader2,
  Plus,
  BookOpen,
  Star,
  Camera,
  Video,
  AlertTriangle,
  Filter,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  Share2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { StudentCombobox } from "@/components/preschool";
import { getStudents } from "@/actions/students.action";
import {
  getStudentObservations,
  createObservation,
  updateObservation,
  deleteObservation,
} from "@/actions/preschool.action";
import type {
  Class,
  LearningArea,
  ProgressObservation,
  ProgressObservationCreate,
  ObservationType,
  Student,
} from "@/types";

interface ObservationsManagerProps {
  classes: Class[];
  learningAreas: LearningArea[];
}

const OBSERVATION_TYPES: { value: ObservationType; label: string; icon: React.ReactNode; color: string }[] = [
  { value: "anecdote", label: "Anecdote", icon: <BookOpen className="h-4 w-4" />, color: "bg-blue-500" },
  { value: "milestone", label: "Milestone", icon: <Star className="h-4 w-4" />, color: "bg-amber-500" },
  { value: "photo", label: "Photo", icon: <Camera className="h-4 w-4" />, color: "bg-green-500" },
  { value: "video", label: "Video", icon: <Video className="h-4 w-4" />, color: "bg-purple-500" },
  { value: "incident", label: "Incident", icon: <AlertTriangle className="h-4 w-4" />, color: "bg-red-500" },
];

export function ObservationsManager({ classes, learningAreas }: ObservationsManagerProps) {
  // Selection state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Data state
  const [students, setStudents] = useState<Student[]>([]);
  const [observations, setObservations] = useState<ProgressObservation[]>([]);

  // Loading state
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingObservations, setIsLoadingObservations] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Dialog state
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedObservation, setSelectedObservation] = useState<ProgressObservation | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    observation_type: "anecdote" as ObservationType,
    learning_area_id: "",
    title: "",
    description: "",
    observation_date: format(new Date(), "yyyy-MM-dd"),
    share_with_parents: false,
    is_highlight: false,
  });

  // Fetch students when class changes
  useEffect(() => {
    async function fetchStudents() {
      if (!selectedClassId) {
        setStudents([]);
        setSelectedStudentId("");
        return;
      }

      setIsLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: selectedClassId,
          page_size: 100,
        });

        if (result.success && result.data) {
          setStudents(
            result.data.items.map((s) => ({
              id: s.id,
              student_id: s.student_id,
              first_name: s.first_name,
              middle_name: s.middle_name,
              last_name: s.last_name,
              gender: s.gender,
              date_of_birth: s.date_of_birth,
              status: s.status,
              class_id: s.class_id,
              section_id: s.section_id,
              photo_url: s.photo_url,
              is_boarder: false,
              created_at: "",
              updated_at: "",
            })) as Student[]
          );
        } else {
          setStudents([]);
        }
      } catch {
        setStudents([]);
      } finally {
        setIsLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [selectedClassId]);

  // Fetch observations when student changes
  const fetchObservations = useCallback(async () => {
    if (!selectedStudentId) {
      setObservations([]);
      return;
    }

    setIsLoadingObservations(true);
    try {
      const result = await getStudentObservations(
        selectedStudentId,
        typeFilter !== "all" ? typeFilter : undefined
      );

      if (result.success && result.data) {
        setObservations(result.data);
      } else {
        setObservations([]);
      }
    } catch {
      setObservations([]);
    } finally {
      setIsLoadingObservations(false);
    }
  }, [selectedStudentId, typeFilter]);

  useEffect(() => {
    fetchObservations();
  }, [fetchObservations]);

  // Open add dialog
  const openAddDialog = () => {
    setFormData({
      observation_type: "anecdote",
      learning_area_id: "",
      title: "",
      description: "",
      observation_date: format(new Date(), "yyyy-MM-dd"),
      share_with_parents: false,
      is_highlight: false,
    });
    setAddDialogOpen(true);
  };

  // Open edit dialog
  const openEditDialog = (observation: ProgressObservation) => {
    setSelectedObservation(observation);
    setFormData({
      observation_type: observation.observation_type,
      learning_area_id: observation.learning_area_id || "",
      title: observation.title,
      description: observation.description || "",
      observation_date: observation.observation_date,
      share_with_parents: observation.share_with_parents,
      is_highlight: observation.is_highlight,
    });
    setEditDialogOpen(true);
  };

  // Handle create
  const handleCreate = async () => {
    if (!selectedStudentId || !formData.title) {
      toast.error("Please fill in required fields");
      return;
    }

    setIsSaving(true);
    try {
      const data: ProgressObservationCreate = {
        student_id: selectedStudentId,
        observation_type: formData.observation_type,
        learning_area_id: formData.learning_area_id || undefined,
        title: formData.title,
        description: formData.description || undefined,
        observation_date: formData.observation_date,
        share_with_parents: formData.share_with_parents,
        is_highlight: formData.is_highlight,
      };

      const result = await createObservation(data);

      if (result.success) {
        toast.success("Observation recorded");
        setAddDialogOpen(false);
        fetchObservations();
      } else {
        toast.error(result.error || "Failed to create observation");
      }
    } catch {
      toast.error("Failed to create observation");
    } finally {
      setIsSaving(false);
    }
  };

  // Handle update
  const handleUpdate = async () => {
    if (!selectedObservation || !formData.title) {
      toast.error("Please fill in required fields");
      return;
    }

    setIsSaving(true);
    try {
      const result = await updateObservation(selectedObservation.id, {
        observation_type: formData.observation_type,
        learning_area_id: formData.learning_area_id || undefined,
        title: formData.title,
        description: formData.description || undefined,
        observation_date: formData.observation_date,
        share_with_parents: formData.share_with_parents,
        is_highlight: formData.is_highlight,
      });

      if (result.success) {
        toast.success("Observation updated");
        setEditDialogOpen(false);
        setSelectedObservation(null);
        fetchObservations();
      } else {
        toast.error(result.error || "Failed to update observation");
      }
    } catch {
      toast.error("Failed to update observation");
    } finally {
      setIsSaving(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!selectedObservation) return;

    setIsSaving(true);
    try {
      const result = await deleteObservation(selectedObservation.id);

      if (result.success) {
        toast.success("Observation deleted");
        setDeleteDialogOpen(false);
        setSelectedObservation(null);
        fetchObservations();
      } else {
        toast.error(result.error || "Failed to delete observation");
      }
    } catch {
      toast.error("Failed to delete observation");
    } finally {
      setIsSaving(false);
    }
  };

  // Get observation type config
  const getTypeConfig = (type: ObservationType) => {
    return OBSERVATION_TYPES.find((t) => t.value === type) || OBSERVATION_TYPES[0];
  };

  // Get selected student
  const selectedStudent = students.find((s) => s.id === selectedStudentId);

  // No classes
  if (classes.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>No Preschool Classes</AlertTitle>
        <AlertDescription>
          There are no preschool classes available. Please create preschool classes first.
        </AlertDescription>
      </Alert>
    );
  }

  // Form fields - rendered inline to prevent re-mounting on state change
  const formFields = (
    <div className="grid gap-4 py-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Type *</Label>
          <Select
            value={formData.observation_type}
            onValueChange={(value) =>
              setFormData((prev) => ({ ...prev, observation_type: value as ObservationType }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OBSERVATION_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  <div className="flex items-center gap-2">
                    {type.icon}
                    {type.label}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Date *</Label>
          <Input
            type="date"
            value={formData.observation_date}
            onChange={(e) => setFormData((prev) => ({ ...prev, observation_date: e.target.value }))}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Learning Area (Optional)</Label>
        <Select
          value={formData.learning_area_id || "_none"}
          onValueChange={(value) => setFormData((prev) => ({ ...prev, learning_area_id: value === "_none" ? "" : value }))}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select learning area..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_none">None</SelectItem>
            {learningAreas.map((area) => (
              <SelectItem key={area.id} value={area.id}>
                {area.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Title *</Label>
        <Input
          placeholder="Brief title for the observation..."
          value={formData.title}
          onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
        />
      </div>

      <div className="space-y-2">
        <Label>Description</Label>
        <Textarea
          placeholder="Detailed observation notes..."
          value={formData.description}
          onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
          rows={4}
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Switch
            id="share"
            checked={formData.share_with_parents}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, share_with_parents: checked }))
            }
          />
          <Label htmlFor="share" className="font-normal">
            Share with parents
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="highlight"
            checked={formData.is_highlight}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, is_highlight: checked }))
            }
          />
          <Label htmlFor="highlight" className="font-normal">
            Mark as highlight
          </Label>
        </div>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Selection Controls */}
      <div className="flex flex-wrap gap-4">
        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Class</Label>
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="Select class..." />
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

        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Student</Label>
          <StudentCombobox
            students={students}
            value={selectedStudentId}
            onValueChange={setSelectedStudentId}
            placeholder="Select student..."
            disabled={!selectedClassId}
            isLoading={isLoadingStudents}
          />
        </div>

        {selectedStudentId && (
          <div className="w-full sm:w-auto">
            <Label className="mb-1.5 block text-sm font-medium">Filter by Type</Label>
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {OBSERVATION_TYPES.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    {type.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {/* Observations List */}
      {selectedStudentId ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-lg">
                Observations for {selectedStudent?.first_name} {selectedStudent?.last_name}
              </CardTitle>
              <CardDescription>
                {observations.length} observation{observations.length !== 1 ? "s" : ""} recorded
              </CardDescription>
            </div>
            <Button onClick={openAddDialog} className="gap-2">
              <Plus className="h-4 w-4" />
              Add Observation
            </Button>
          </CardHeader>
          <CardContent>
            {isLoadingObservations ? (
              <div className="flex h-48 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : observations.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed">
                <BookOpen className="h-10 w-10 text-muted-foreground/50" />
                <p className="mt-4 text-muted-foreground">No observations yet</p>
                <Button variant="outline" className="mt-4" onClick={openAddDialog}>
                  <Plus className="mr-2 h-4 w-4" />
                  Record First Observation
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {observations.map((observation) => {
                  const typeConfig = getTypeConfig(observation.observation_type);
                  const learningArea = learningAreas.find(
                    (a) => a.id === observation.learning_area_id
                  );

                  return (
                    <div
                      key={observation.id}
                      className="flex items-start gap-4 rounded-lg border p-4"
                    >
                      <div
                        className={`flex h-10 w-10 items-center justify-center rounded-full ${typeConfig.color} text-white`}
                      >
                        {typeConfig.icon}
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-medium">{observation.title}</h4>
                            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                              <span>{format(new Date(observation.observation_date), "MMM d, yyyy")}</span>
                              <Badge variant="outline">{typeConfig.label}</Badge>
                              {learningArea && (
                                <Badge variant="secondary">{learningArea.name}</Badge>
                              )}
                              {observation.share_with_parents && (
                                <Badge variant="outline" className="gap-1 text-green-600">
                                  <Share2 className="h-3 w-3" />
                                  Shared
                                </Badge>
                              )}
                              {observation.is_highlight && (
                                <Badge variant="outline" className="gap-1 text-amber-600">
                                  <Star className="h-3 w-3" />
                                  Highlight
                                </Badge>
                              )}
                            </div>
                          </div>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => openEditDialog(observation)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  setSelectedObservation(observation);
                                  setDeleteDialogOpen(true);
                                }}
                                className="text-destructive"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                        {observation.description && (
                          <p className="text-sm text-muted-foreground">
                            {observation.description}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <BookOpen className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">Select a Student</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a class and student to view or record observations
            </p>
          </CardContent>
        </Card>
      )}

      {/* Add Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Observation</DialogTitle>
            <DialogDescription>
              Record an observation for {selectedStudent?.first_name} {selectedStudent?.last_name}
            </DialogDescription>
          </DialogHeader>
          {formFields}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Observation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Observation</DialogTitle>
            <DialogDescription>Update the observation details.</DialogDescription>
          </DialogHeader>
          {formFields}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Observation</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this observation? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
