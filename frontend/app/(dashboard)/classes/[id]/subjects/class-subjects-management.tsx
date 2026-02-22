"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  BookOpen,
  Plus,
  Trash2,
  Loader2,
  Check,
  Search,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

import {
  getClassSubjects,
  assignSubjectToClass,
  removeSubjectFromClass,
} from "@/actions/academic.action";
import type { Class, Subject, ClassSubject, SubjectCategory } from "@/types";

const CATEGORY_CONFIG: Record<SubjectCategory, { label: string; color: string }> = {
  core: { label: "Core", color: "bg-blue-500" },
  elective: { label: "Elective", color: "bg-green-500" },
  vocational: { label: "Vocational", color: "bg-amber-500" },
  extra: { label: "Extra", color: "bg-purple-500" },
};

interface ClassSubjectsManagementProps {
  classData: Class;
  allSubjects: Subject[];
  initialClassSubjects: ClassSubject[];
}

export function ClassSubjectsManagement({
  classData,
  allSubjects,
  initialClassSubjects,
}: ClassSubjectsManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [classSubjects, setClassSubjects] = useState<ClassSubject[]>(initialClassSubjects);
  const [searchQuery, setSearchQuery] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [selectedSubjectId, setSelectedSubjectId] = useState<string | null>(null);

  // Form state for adding subjects
  const [selectedSubjects, setSelectedSubjects] = useState<Set<string>>(new Set());
  const [subjectSettings, setSubjectSettings] = useState<
    Record<string, { is_compulsory: boolean; periods_per_week: number }>
  >({});

  // Get IDs of already assigned subjects
  const assignedSubjectIds = new Set(classSubjects.map((cs) => cs.subject_id));

  // Available subjects to add (not already assigned)
  const availableSubjects = allSubjects.filter(
    (s) => !assignedSubjectIds.has(s.id) && s.is_active
  );

  // Filter available subjects by search
  const filteredAvailableSubjects = availableSubjects.filter(
    (s) =>
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Enriched class subjects with subject details
  const enrichedClassSubjects = classSubjects.map((cs) => {
    const subject = allSubjects.find((s) => s.id === cs.subject_id);
    return {
      ...cs,
      subject_name: subject?.name || "Unknown",
      subject_code: subject?.code || "???",
      subject_category: subject?.category || "core",
    };
  });

  const refreshClassSubjects = () => {
    startTransition(async () => {
      const result = await getClassSubjects(classData.id);
      if (result.success && result.data) {
        setClassSubjects(result.data);
      }
    });
  };

  const toggleSubjectSelection = (subjectId: string) => {
    const newSelected = new Set(selectedSubjects);
    if (newSelected.has(subjectId)) {
      newSelected.delete(subjectId);
      const newSettings = { ...subjectSettings };
      delete newSettings[subjectId];
      setSubjectSettings(newSettings);
    } else {
      newSelected.add(subjectId);
      setSubjectSettings({
        ...subjectSettings,
        [subjectId]: { is_compulsory: true, periods_per_week: 5 },
      });
    }
    setSelectedSubjects(newSelected);
  };

  const handleAddSubjects = async () => {
    if (selectedSubjects.size === 0) {
      toast.error("Please select at least one subject");
      return;
    }

    startTransition(async () => {
      let successCount = 0;
      let failCount = 0;

      for (const subjectId of selectedSubjects) {
        const settings = subjectSettings[subjectId] || {
          is_compulsory: true,
          periods_per_week: 5,
        };

        const result = await assignSubjectToClass({
          class_id: classData.id,
          subject_id: subjectId,
          is_compulsory: settings.is_compulsory,
          periods_per_week: settings.periods_per_week,
        });

        if (result.success) {
          successCount++;
        } else {
          failCount++;
        }
      }

      if (successCount > 0) {
        toast.success(`Added ${successCount} subject${successCount > 1 ? "s" : ""} to ${classData.name}`);
      }
      if (failCount > 0) {
        toast.error(`Failed to add ${failCount} subject${failCount > 1 ? "s" : ""}`);
      }

      setAddDialogOpen(false);
      setSelectedSubjects(new Set());
      setSubjectSettings({});
      setSearchQuery("");
      refreshClassSubjects();
    });
  };

  const openRemoveDialog = (subjectId: string) => {
    setSelectedSubjectId(subjectId);
    setRemoveDialogOpen(true);
  };

  const handleRemoveSubject = async () => {
    if (!selectedSubjectId) return;

    startTransition(async () => {
      const result = await removeSubjectFromClass(classData.id, selectedSubjectId);

      if (result.success) {
        const subjectName =
          enrichedClassSubjects.find((cs) => cs.subject_id === selectedSubjectId)
            ?.subject_name || "Subject";
        toast.success(`${subjectName} removed from ${classData.name}`);
        setRemoveDialogOpen(false);
        setSelectedSubjectId(null);
        refreshClassSubjects();
      } else {
        toast.error("Failed to remove subject", {
          description: result.error,
        });
      }
    });
  };

  // Stats
  const stats = {
    total: classSubjects.length,
    compulsory: classSubjects.filter((cs) => cs.is_compulsory).length,
    optional: classSubjects.filter((cs) => !cs.is_compulsory).length,
  };

  // Check if this is a preschool class (includes specific grade levels)
  const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];
  const isPreschool = classData.level ? PRESCHOOL_LEVELS.includes(classData.level) : false;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/classes">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {classData.name} - {isPreschool ? "Learning Areas" : "Subjects"}
          </h1>
          <p className="text-muted-foreground">
            {isPreschool
              ? "Preschool classes use Learning Areas for developmental assessment."
              : "Manage which subjects are taught in this class."
            }
          </p>
        </div>
        {!isPreschool && (
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Subjects
          </Button>
        )}
      </div>

      {/* Preschool Notice */}
      {isPreschool && (
        <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-blue-700 dark:text-blue-300">
              <Sparkles className="h-5 w-5" />
              Preschool Assessment
            </CardTitle>
            <CardDescription>
              Preschool classes use <strong>Learning Areas</strong> and <strong>Developmental Skills</strong> instead of traditional subjects.
              These are configured in the Preschool Settings.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/settings/preschool">
              <Button variant="outline" size="sm">
                <Sparkles className="mr-2 h-4 w-4" />
                Go to Preschool Settings
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards - Hidden for preschool */}
      {!isPreschool && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Total Subjects</CardDescription>
              <CardTitle className="text-3xl">{stats.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Compulsory</CardDescription>
              <CardTitle className="text-3xl text-blue-600">{stats.compulsory}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Optional/Elective</CardDescription>
              <CardTitle className="text-3xl text-green-600">{stats.optional}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Subject List - Hidden for preschool */}
      {!isPreschool && (
        <Card>
          <CardHeader>
            <CardTitle>Assigned Subjects</CardTitle>
            <CardDescription>
              Subjects currently assigned to {classData.name}. Students in this class
              will be examined on these subjects.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {enrichedClassSubjects.length === 0 ? (
              <div className="text-center py-12">
                <BookOpen className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-semibold">No subjects assigned</h3>
                <p className="text-muted-foreground">
                  Add subjects to this class to enable examinations and grading.
              </p>
              <Button onClick={() => setAddDialogOpen(true)} className="mt-4">
                <Plus className="mr-2 h-4 w-4" />
                Add Subjects
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Subject Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Category</TableHead>
                    <TableHead className="hidden md:table-cell">Type</TableHead>
                    <TableHead className="hidden md:table-cell">Periods/Week</TableHead>
                    <TableHead className="w-[70px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {enrichedClassSubjects.map((cs) => (
                    <TableRow key={cs.id}>
                      <TableCell className="font-mono font-medium">
                        {cs.subject_code}
                      </TableCell>
                      <TableCell className="font-medium">{cs.subject_name}</TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <Badge
                          className={`${
                            CATEGORY_CONFIG[cs.subject_category as SubjectCategory]?.color ||
                            "bg-gray-500"
                          } text-white`}
                        >
                          {CATEGORY_CONFIG[cs.subject_category as SubjectCategory]?.label ||
                            cs.subject_category}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        <Badge variant={cs.is_compulsory ? "default" : "secondary"}>
                          {cs.is_compulsory ? "Compulsory" : "Optional"}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">{cs.periods_per_week || "-"}</TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => openRemoveDialog(cs.subject_id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      )}

      {/* Add Subjects Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Add Subjects to {classData.name}</DialogTitle>
            <DialogDescription>
              Select subjects to add to this class. Configure each subject as compulsory
              or optional.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-hidden flex flex-col gap-4 py-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search subjects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* Subject List */}
            <div className="flex-1 overflow-y-auto border rounded-md">
              {filteredAvailableSubjects.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  {availableSubjects.length === 0
                    ? "All subjects have been assigned to this class."
                    : "No subjects match your search."}
                </div>
              ) : (
                <div className="divide-y">
                  {filteredAvailableSubjects.map((subject) => {
                    const isSelected = selectedSubjects.has(subject.id);
                    const settings = subjectSettings[subject.id];

                    return (
                      <div
                        key={subject.id}
                        className={`p-4 cursor-pointer transition-colors ${
                          isSelected ? "bg-muted/50" : "hover:bg-muted/30"
                        }`}
                        onClick={() => toggleSubjectSelection(subject.id)}
                      >
                        <div className="flex items-start gap-4">
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => toggleSubjectSelection(subject.id)}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm text-muted-foreground">
                                {subject.code}
                              </span>
                              <span className="font-medium">{subject.name}</span>
                              <Badge
                                className={`${
                                  CATEGORY_CONFIG[subject.category]?.color || "bg-gray-500"
                                } text-white text-xs`}
                              >
                                {CATEGORY_CONFIG[subject.category]?.label || subject.category}
                              </Badge>
                            </div>
                            {subject.description && (
                              <p className="mt-1 text-sm text-muted-foreground truncate">
                                {subject.description}
                              </p>
                            )}

                            {/* Settings when selected */}
                            {isSelected && settings && (
                              <div
                                className="mt-3 flex items-center gap-6 pt-3 border-t"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <div className="flex items-center gap-2">
                                  <Switch
                                    id={`compulsory-${subject.id}`}
                                    checked={settings.is_compulsory}
                                    onCheckedChange={(checked) =>
                                      setSubjectSettings({
                                        ...subjectSettings,
                                        [subject.id]: {
                                          ...settings,
                                          is_compulsory: checked,
                                        },
                                      })
                                    }
                                  />
                                  <Label
                                    htmlFor={`compulsory-${subject.id}`}
                                    className="text-sm"
                                  >
                                    Compulsory
                                  </Label>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Label className="text-sm">Periods/Week:</Label>
                                  <Input
                                    type="number"
                                    min={1}
                                    max={20}
                                    value={settings.periods_per_week}
                                    onChange={(e) =>
                                      setSubjectSettings({
                                        ...subjectSettings,
                                        [subject.id]: {
                                          ...settings,
                                          periods_per_week: parseInt(e.target.value) || 1,
                                        },
                                      })
                                    }
                                    className="w-16 h-8"
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Selection summary */}
            {selectedSubjects.size > 0 && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Check className="h-4 w-4 text-green-600" />
                <span>
                  {selectedSubjects.size} subject{selectedSubjects.size > 1 ? "s" : ""}{" "}
                  selected
                </span>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setAddDialogOpen(false);
                setSelectedSubjects(new Set());
                setSubjectSettings({});
                setSearchQuery("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddSubjects}
              disabled={isPending || selectedSubjects.size === 0}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Add {selectedSubjects.size > 0 ? selectedSubjects.size : ""} Subject
              {selectedSubjects.size !== 1 ? "s" : ""}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Remove Confirmation Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Subject</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{" "}
              {enrichedClassSubjects.find((cs) => cs.subject_id === selectedSubjectId)
                ?.subject_name || "this subject"}{" "}
              from {classData.name}? Students will no longer be examined on this
              subject.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveSubject}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
