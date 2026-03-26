"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  Plus,
  BookOpen,
  Share2,
  Loader2,
  Library,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { LearningStoryCard } from "@/components/preschool/LearningStoryCard";
import { LearningStoryForm } from "@/components/preschool/LearningStoryForm";
import { getStudents } from "@/actions/students.action";
import {
  listLearningStories,
  createLearningStory,
  updateLearningStory,
  deleteLearningStory,
  getLearningAreas,
  getSkillsByLearningArea,
  getStudentObservations,
} from "@/actions/preschool.action";
import type {
  Class,
  Term,
  LearningStory,
  LearningStoryCreate,
  LearningStoryUpdate,
  LearningArea,
  DevelopmentalSkill,
  ProgressObservation,
} from "@/types";

interface StudentItem {
  id: string;
  first_name: string;
  last_name: string;
  student_id: string;
}

interface PortfolioManagerProps {
  classes: Class[];
  terms: Term[];
}

export function PortfolioManager({ classes, terms }: PortfolioManagerProps) {
  // Filter state
  const [selectedClassId, setSelectedClassId] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [selectedTermId, setSelectedTermId] = useState("");
  const [shareFilter, setShareFilter] = useState<"all" | "shared" | "not_shared">("all");

  // Data state
  const [stories, setStories] = useState<LearningStory[]>([]);
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [learningAreas, setLearningAreas] = useState<LearningArea[]>([]);
  const [skills, setSkills] = useState<DevelopmentalSkill[]>([]);
  const [observations, setObservations] = useState<ProgressObservation[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // Sheet state
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editingStory, setEditingStory] = useState<LearningStory | undefined>();
  const [isSaving, setIsSaving] = useState(false);

  // Learning area name lookup
  const areaNames: Record<string, string> = {};
  for (const area of learningAreas) {
    areaNames[area.id] = area.name;
  }

  // Load learning areas on mount
  useEffect(() => {
    async function load() {
      const result = await getLearningAreas();
      if (result.success && result.data) {
        setLearningAreas(result.data);
        // Load all skills
        const allSkills: DevelopmentalSkill[] = [];
        for (const area of result.data) {
          const skillResult = await getSkillsByLearningArea(area.id);
          if (skillResult.success && skillResult.data) {
            allSkills.push(...skillResult.data);
          }
        }
        setSkills(allSkills);
      }
    }
    load();
  }, []);

  // Load students when class changes
  useEffect(() => {
    if (selectedClassId) {
      setLoadingStudents(true);
      getStudents({ class_id: selectedClassId, status: "active" }).then((result) => {
        if (result.success && result.data) {
          setStudents(
            result.data.items.map((s) => ({
              id: s.id,
              first_name: s.first_name,
              last_name: s.last_name,
              student_id: s.student_id,
            }))
          );
        }
        setLoadingStudents(false);
      });
      setSelectedStudentId("");
    } else {
      setStudents([]);
      setSelectedStudentId("");
    }
  }, [selectedClassId]);

  // Load stories based on filters
  const loadStories = useCallback(async () => {
    setLoading(true);
    const params: Record<string, string | boolean | undefined> = {};
    if (selectedClassId) params.class_id = selectedClassId;
    if (selectedStudentId) params.student_id = selectedStudentId;
    if (selectedTermId) params.term_id = selectedTermId;
    if (shareFilter === "shared") params.is_shared = true;
    if (shareFilter === "not_shared") params.is_shared = false;

    const result = await listLearningStories(params as Parameters<typeof listLearningStories>[0]);
    if (result.success && result.data) {
      setStories(result.data);
    } else {
      toast.error(result.error || "Failed to load stories");
    }
    setLoading(false);
  }, [selectedClassId, selectedStudentId, selectedTermId, shareFilter]);

  useEffect(() => {
    loadStories();
  }, [loadStories]);

  // Load observations when editing/creating for a student
  async function loadObservationsForStudent(studentId: string) {
    if (!studentId) {
      setObservations([]);
      return;
    }
    const result = await getStudentObservations(studentId);
    if (result.success && result.data) {
      setObservations(result.data);
    }
  }

  function handleNewStory() {
    setEditingStory(undefined);
    setObservations([]);
    setSheetOpen(true);
  }

  function handleEditStory(story: LearningStory) {
    setEditingStory(story);
    loadObservationsForStudent(story.student_id);
    setSheetOpen(true);
  }

  async function handleDeleteStory(id: string) {
    const result = await deleteLearningStory(id);
    if (result.success) {
      toast.success("Learning story deleted");
      setStories((prev) => prev.filter((s) => s.id !== id));
    } else {
      toast.error(result.error || "Failed to delete story");
    }
  }

  async function handleSubmit(data: LearningStoryCreate | LearningStoryUpdate) {
    setIsSaving(true);
    try {
      if (editingStory) {
        const result = await updateLearningStory(editingStory.id, data as LearningStoryUpdate);
        if (result.success && result.data) {
          toast.success("Learning story updated");
          setStories((prev) =>
            prev.map((s) => (s.id === editingStory.id ? result.data : s))
          );
          setSheetOpen(false);
        } else {
          toast.error(result.error || "Failed to update story");
        }
      } else {
        const result = await createLearningStory(data as LearningStoryCreate);
        if (result.success && result.data) {
          toast.success("Learning story created");
          setStories((prev) => [result.data, ...prev]);
          setSheetOpen(false);
        } else {
          toast.error(result.error || "Failed to create story");
        }
      }
    } finally {
      setIsSaving(false);
    }
  }

  // Stats
  const totalStories = stories.length;
  const currentTermId = terms.find((t) => t.is_current)?.id;
  const storiesThisTerm = currentTermId
    ? stories.filter((s) => s.term_id === currentTermId).length
    : 0;
  const sharedCount = stories.filter((s) => s.is_shared_with_parents).length;

  return (
    <div className="space-y-6">
      {/* Header with New Story button */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-3">
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="All classes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {students.length > 0 && (
            <Select value={selectedStudentId} onValueChange={setSelectedStudentId}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="All students" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Students</SelectItem>
                {students.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.first_name} {s.last_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Select value={selectedTermId} onValueChange={setSelectedTermId}>
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue placeholder="All terms" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Terms</SelectItem>
              {terms.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={shareFilter}
            onValueChange={(v) => setShareFilter(v as typeof shareFilter)}
          >
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue placeholder="Share status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Stories</SelectItem>
              <SelectItem value="shared">Shared</SelectItem>
              <SelectItem value="not_shared">Not Shared</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button onClick={handleNewStory}>
          <Plus className="mr-2 h-4 w-4" />
          New Story
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Stories</CardTitle>
            <Library className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalStories}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">This Term</CardTitle>
            <BookOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{storiesThisTerm}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Shared with Parents</CardTitle>
            <Share2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{sharedCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Story Grid */}
      {loading ? (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <Skeleton className="h-40 w-full" />
              <CardContent className="space-y-3 pt-4">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-4 w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : stories.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <BookOpen className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">No learning stories yet</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Learning stories document meaningful moments in a child&apos;s learning journey.
              Click &quot;New Story&quot; to create your first one.
            </p>
            <Button onClick={handleNewStory} className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Create First Story
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {stories.map((story) => (
            <LearningStoryCard
              key={story.id}
              story={story}
              onEdit={handleEditStory}
              onDelete={handleDeleteStory}
              learningAreaNames={areaNames}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Sheet */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>
              {editingStory ? "Edit Learning Story" : "New Learning Story"}
            </SheetTitle>
            <SheetDescription>
              {editingStory
                ? "Update the details of this learning story."
                : "Document a meaningful learning moment for a child."}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6">
            <LearningStoryForm
              story={editingStory}
              students={students.length > 0 ? students : []}
              learningAreas={learningAreas}
              skills={skills}
              observations={observations}
              onSubmit={handleSubmit}
              onCancel={() => setSheetOpen(false)}
              isSaving={isSaving}
            />
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
