"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Plus,
  FileText,
  Loader2,
  Trash2,
  Save,
  Check,
  ChevronsUpDown,
  Users,
  Search,
  Pencil,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

import { getStudents } from "@/actions/students.action";
import { getClassSubjects } from "@/actions/academic.action";
import { bulkCreateCA, deleteCA, getContinuousAssessments, updateCA } from "@/actions/exams.action";
import type {
  AcademicYear,
  Class,
  ClassSubject,
  StudentListItem,
  AssessmentType,
  CAWithDetails,
  CABulkEntry,
  Subject,
} from "@/types";

const ASSESSMENT_TYPE_CONFIG: Record<AssessmentType, { label: string; color: string }> = {
  class_work: { label: "Class Work", color: "bg-blue-500" },
  homework: { label: "Homework", color: "bg-green-500" },
  test: { label: "Test", color: "bg-amber-500" },
  project: { label: "Project", color: "bg-purple-500" },
  assignment: { label: "Assignment", color: "bg-cyan-500" },
};

// Preschool levels to exclude from CA
const PRESCHOOL_LEVELS = ["creche", "preschool", "nursery_1", "nursery_2", "kg_1", "kg_2"];

interface CAManagementProps {
  academicYears: AcademicYear[];
  classes: Class[];
  subjects: Subject[]; // Not used directly, subjects come from class assignments
}

export function CAManagement({
  academicYears,
  classes,
}: CAManagementProps) {
  // Find current year and term
  const currentYear = academicYears.find((y) => y.is_current);
  const currentTerm = currentYear?.terms?.find((t) => t.is_current);

  // Filter out preschool classes
  const nonPreschoolClasses = classes.filter(
    (c) => !PRESCHOOL_LEVELS.includes(c.level || "")
  );

  // Selection state
  const [selectedYearId, setSelectedYearId] = useState(currentYear?.id || "");
  const [selectedTermId, setSelectedTermId] = useState(currentTerm?.id || "");
  const [selectedClassId, setSelectedClassId] = useState("");
  const [selectedSectionId, setSelectedSectionId] = useState("all");
  const [selectedSubjectId, setSelectedSubjectId] = useState("");

  // Data state
  const [classSubjects, setClassSubjects] = useState<ClassSubject[]>([]);
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [caRecords, setCARecords] = useState<CAWithDetails[]>([]);

  // Loading states
  const [isLoadingSubjects, setIsLoadingSubjects] = useState(false);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingRecords, setIsLoadingRecords] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Dialog state
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedCA, setSelectedCA] = useState<CAWithDetails | null>(null);
  const [editingAssessments, setEditingAssessments] = useState<CAWithDetails[]>([]);
  const [editScores, setEditScores] = useState<Record<string, string>>({});
  const [editFormData, setEditFormData] = useState({
    assessment_type: "class_work" as AssessmentType,
    title: "",
    max_score: "10",
    date: "",
  });
  const [editStudentSearch, setEditStudentSearch] = useState("");
  const [subjectPopoverOpen, setSubjectPopoverOpen] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    assessment_type: "class_work" as AssessmentType,
    title: "",
    max_score: "10",
    date: format(new Date(), "yyyy-MM-dd"),
  });
  const [scores, setScores] = useState<Record<string, string>>({});
  const [studentSearch, setStudentSearch] = useState("");

  // Derived state
  const selectedYear = academicYears.find((y) => y.id === selectedYearId);
  const availableTerms = selectedYear?.terms || [];
  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const availableSections = selectedClass?.sections || [];

  // Auto-select term when year changes
  useEffect(() => {
    if (selectedYearId && availableTerms.length > 0) {
      const currentTermInYear = availableTerms.find((t) => t.is_current);
      if (currentTermInYear) {
        setSelectedTermId(currentTermInYear.id);
      } else if (!selectedTermId || !availableTerms.find(t => t.id === selectedTermId)) {
        setSelectedTermId(availableTerms[0].id);
      }
    }
  }, [selectedYearId, availableTerms]);

  // Load class subjects when class changes
  useEffect(() => {
    const loadClassSubjects = async () => {
      if (!selectedClassId) {
        setClassSubjects([]);
        return;
      }

      setIsLoadingSubjects(true);
      try {
        const result = await getClassSubjects(selectedClassId);
        if (result.success && result.data) {
          setClassSubjects(result.data);
        } else {
          setClassSubjects([]);
        }
      } catch (error) {
        console.error("Failed to load class subjects:", error);
        setClassSubjects([]);
      } finally {
        setIsLoadingSubjects(false);
      }
    };

    loadClassSubjects();
    // Reset dependent selections
    setSelectedSectionId("all");
    setSelectedSubjectId("");
  }, [selectedClassId]);

  // Load students when class or section changes
  useEffect(() => {
    const loadStudents = async () => {
      if (!selectedClassId) {
        setStudents([]);
        return;
      }

      setIsLoadingStudents(true);
      try {
        const filters: { class_id: string; section_id?: string; page_size: number } = {
          class_id: selectedClassId,
          page_size: 100,
        };

        // Only filter by section if a specific one is selected
        if (selectedSectionId && selectedSectionId !== "all") {
          filters.section_id = selectedSectionId;
        }

        const result = await getStudents(filters);
        if (result.success && result.data) {
          setStudents(result.data.items);
        } else {
          setStudents([]);
          console.error("Failed to load students:", result.error);
        }
      } catch (error) {
        console.error("Failed to load students:", error);
        setStudents([]);
      } finally {
        setIsLoadingStudents(false);
      }
    };

    loadStudents();
  }, [selectedClassId, selectedSectionId]);

  // Load CA records when all filters are complete
  const loadCARecords = useCallback(async () => {
    if (!selectedYearId || !selectedTermId || !selectedClassId || !selectedSubjectId) {
      setCARecords([]);
      return;
    }

    setIsLoadingRecords(true);
    try {
      const result = await getContinuousAssessments({
        term_id: selectedTermId,
        class_id: selectedClassId,
        subject_id: selectedSubjectId,
        page_size: 100,
      });
      if (result.success && result.data) {
        setCARecords(result.data);
      } else {
        setCARecords([]);
      }
    } catch (error) {
      console.error("Failed to load CA records:", error);
      setCARecords([]);
    } finally {
      setIsLoadingRecords(false);
    }
  }, [selectedYearId, selectedTermId, selectedClassId, selectedSubjectId]);

  useEffect(() => {
    loadCARecords();
  }, [loadCARecords]);

  // Handlers
  const handleYearChange = (value: string) => {
    setSelectedYearId(value);
    setSelectedTermId("");
  };

  const handleClassChange = (value: string) => {
    setSelectedClassId(value);
  };

  const openAddDialog = () => {
    setFormData({
      assessment_type: "class_work",
      title: "",
      max_score: "10",
      date: format(new Date(), "yyyy-MM-dd"),
    });
    // Initialize all students with empty scores
    const initialScores: Record<string, string> = {};
    for (const student of students) {
      initialScores[student.id] = "";
    }
    setScores(initialScores);
    setStudentSearch("");
    setAddDialogOpen(true);
  };

  // Filter students for dialog search
  const filteredStudents = (students || []).filter((student) => {
    if (!studentSearch) return true;
    const searchLower = studentSearch.toLowerCase();
    return (
      student.first_name.toLowerCase().includes(searchLower) ||
      student.last_name.toLowerCase().includes(searchLower) ||
      student.student_id.toLowerCase().includes(searchLower)
    );
  });

  const openDeleteDialog = (ca: CAWithDetails) => {
    setSelectedCA(ca);
    setDeleteDialogOpen(true);
  };

  const openEditDialog = (assessmentTitle: string) => {
    // Get all CA records for this assessment title
    const assessmentsToEdit = caRecords.filter((ca) => ca.title === assessmentTitle);
    setEditingAssessments(assessmentsToEdit);

    // Initialize edit form data from first assessment
    const firstCA = assessmentsToEdit[0];
    if (firstCA) {
      setEditFormData({
        assessment_type: firstCA.assessment_type as AssessmentType,
        title: firstCA.title,
        max_score: firstCA.max_score.toString(),
        date: firstCA.assessment_date,
      });
    }

    // Initialize edit scores from existing data
    const initialScores: Record<string, string> = {};
    for (const ca of assessmentsToEdit) {
      initialScores[ca.id] = ca.score?.toString() || "";
    }
    setEditScores(initialScores);
    setEditStudentSearch("");
    setEditDialogOpen(true);
  };

  const handleUpdateCA = async () => {
    if (!editFormData.title) {
      toast.error("Please enter a title");
      return;
    }

    const maxScore = parseFloat(editFormData.max_score) || 100;

    // Validate all scores before saving
    const invalidAssessments = editingAssessments.filter((ca) => {
      const score = editScores[ca.id];
      if (!score || score === "") return false;
      const numScore = parseFloat(score);
      return numScore < 0 || numScore > maxScore;
    });

    if (invalidAssessments.length > 0) {
      const invalidStudentNames = invalidAssessments.map((ca) => ca.student_name);
      toast.error(`Invalid scores for: ${invalidStudentNames.join(", ")}`, {
        description: `Scores must be between 0 and ${maxScore}`,
      });
      return;
    }

    setIsSaving(true);
    try {
      let successCount = 0;
      let errorCount = 0;

      // Update each CA record
      for (const ca of editingAssessments) {
        const newScore = editScores[ca.id];
        const originalScore = ca.score?.toString() || "";

        // Check if metadata or score has changed
        const metadataChanged =
          editFormData.title !== ca.title ||
          editFormData.assessment_type !== ca.assessment_type ||
          editFormData.date !== ca.assessment_date ||
          editFormData.max_score !== ca.max_score.toString();
        const scoreChanged = newScore !== originalScore;

        if (metadataChanged || scoreChanged) {
          const result = await updateCA(ca.id, {
            title: editFormData.title,
            assessment_type: editFormData.assessment_type,
            max_score: parseFloat(editFormData.max_score),
            assessment_date: editFormData.date,
            score: newScore ? parseFloat(newScore) : undefined,
          });

          if (result.success) {
            successCount++;
          } else {
            errorCount++;
          }
        }
      }

      if (errorCount > 0) {
        toast.error(`Failed to update ${errorCount} record(s)`);
      }
      if (successCount > 0) {
        toast.success(`Updated ${successCount} record(s)`);
      } else if (errorCount === 0) {
        toast.info("No changes to save");
      }

      setEditDialogOpen(false);
      loadCARecords();
    } catch (error) {
      toast.error("Failed to update assessment");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateCA = async () => {
    if (!formData.title) {
      toast.error("Please enter a title");
      return;
    }

    const maxScore = parseFloat(formData.max_score) || 100;

    // Prepare entries - only include students with scores
    const entries: CABulkEntry[] = Object.entries(scores)
      .filter(([_, score]) => score !== "")
      .map(([studentId, score]) => ({
        student_id: studentId,
        score: parseFloat(score),
      }));

    if (entries.length === 0) {
      toast.error("Please enter at least one score");
      return;
    }

    // Validate scores don't exceed max
    const invalidEntries = entries.filter((e) => e.score !== undefined && (e.score < 0 || e.score > maxScore));
    if (invalidEntries.length > 0) {
      const invalidStudentNames = invalidEntries.map((e) => {
        const student = students.find((s) => s.id === e.student_id);
        return student ? `${student.first_name} ${student.last_name}` : "Unknown";
      });
      toast.error(`Invalid scores for: ${invalidStudentNames.join(", ")}`, {
        description: `Scores must be between 0 and ${maxScore}`,
      });
      return;
    }

    setIsSaving(true);
    try {
      // Map to backend expected format
      const scores = entries.map((entry) => ({
        student_id: entry.student_id,
        score: entry.score,
      }));

      const result = await bulkCreateCA({
        term_id: selectedTermId,
        class_id: selectedClassId,
        subject_id: selectedSubjectId,
        assessment_type: formData.assessment_type,
        title: formData.title,
        max_score: parseFloat(formData.max_score),
        assessment_date: formData.date,
        scores,
      } as any);

      if (result.success) {
        toast.success("Assessment scores saved", {
          description: `${entries.length} scores recorded for ${formData.title}`,
        });
        setAddDialogOpen(false);
        loadCARecords();
      } else {
        toast.error("Failed to save assessment", {
          description: result.error,
        });
      }
    } catch (error) {
      toast.error("Failed to save assessment");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCA = async () => {
    if (!selectedCA) return;

    setIsSaving(true);
    try {
      const result = await deleteCA(selectedCA.id);

      if (result.success) {
        toast.success("Assessment deleted");
        setDeleteDialogOpen(false);
        setSelectedCA(null);
        loadCARecords();
      } else {
        toast.error("Failed to delete assessment", {
          description: result.error,
        });
      }
    } catch (error) {
      toast.error("Failed to delete assessment");
    } finally {
      setIsSaving(false);
    }
  };

  // Computed values
  const uniqueAssessments = [...new Set((caRecords || []).map((ca) => ca.title))];
  const isFiltersComplete = selectedYearId && selectedTermId && selectedClassId && selectedSubjectId;
  const canAddAssessment = isFiltersComplete && (students || []).length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Continuous Assessment</h1>
          <p className="text-muted-foreground">
            Track class work, homework, tests, and other assessments.
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Select Class and Subject</CardTitle>
          <CardDescription>
            Choose the term, class, and subject to manage continuous assessments.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
            {/* Academic Year */}
            <div className="space-y-2">
              <Label>Academic Year</Label>
              <Select value={selectedYearId} onValueChange={handleYearChange}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select year" />
                </SelectTrigger>
                <SelectContent>
                  {academicYears.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      {year.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Term */}
            <div className="space-y-2">
              <Label>Term</Label>
              <Select
                value={selectedTermId}
                onValueChange={setSelectedTermId}
                disabled={!selectedYearId || availableTerms.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={
                      !selectedYearId
                        ? "Select year first"
                        : availableTerms.length === 0
                        ? "No terms available"
                        : "Select term"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableTerms.map((term) => (
                    <SelectItem key={term.id} value={term.id}>
                      {term.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Class */}
            <div className="space-y-2">
              <Label>Class</Label>
              <Select value={selectedClassId} onValueChange={handleClassChange}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select class" />
                </SelectTrigger>
                <SelectContent>
                  {nonPreschoolClasses.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Section */}
            <div className="space-y-2">
              <Label>Section</Label>
              <Select
                value={selectedSectionId}
                onValueChange={setSelectedSectionId}
                disabled={!selectedClassId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={!selectedClassId ? "Select class first" : "All Sections"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sections</SelectItem>
                  {availableSections.map((section) => (
                    <SelectItem key={section.id} value={section.id}>
                      {section.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Subject */}
            <div className="space-y-2">
              <Label>Subject</Label>
              <Popover open={subjectPopoverOpen} onOpenChange={setSubjectPopoverOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={subjectPopoverOpen}
                    className={cn(
                      "w-full justify-between font-normal",
                      !selectedSubjectId && "text-muted-foreground"
                    )}
                    disabled={!selectedClassId || isLoadingSubjects}
                  >
                    {isLoadingSubjects ? (
                      <span className="flex items-center">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Loading...
                      </span>
                    ) : selectedSubjectId ? (
                      classSubjects.find((cs) => cs.subject_id === selectedSubjectId)?.subject?.name
                    ) : classSubjects.length === 0 ? (
                      "No subjects assigned"
                    ) : (
                      "Select subject..."
                    )}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[300px] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search subjects..." />
                    <CommandList>
                      <CommandEmpty>No subject found.</CommandEmpty>
                      <CommandGroup>
                        {classSubjects.map((cs) => (
                          <CommandItem
                            key={cs.subject_id}
                            value={`${cs.subject?.code} ${cs.subject?.name}`}
                            onSelect={() => {
                              setSelectedSubjectId(cs.subject_id);
                              setSubjectPopoverOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                selectedSubjectId === cs.subject_id ? "opacity-100" : "opacity-0"
                              )}
                            />
                            <span className="font-medium">{cs.subject?.code}</span>
                            <span className="ml-2 text-muted-foreground">{cs.subject?.name}</span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>
          </div>

          {/* Status info */}
          {selectedClassId && (
            <div className="mt-4 flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <Users className="h-4 w-4" />
                {isLoadingStudents ? (
                  <span>Loading students...</span>
                ) : (
                  <span>{students.length} student(s)</span>
                )}
              </div>
              {classSubjects.length === 0 && !isLoadingSubjects && (
                <span className="text-amber-600">
                  No subjects assigned to this class.{" "}
                  <a href={`/classes/${selectedClassId}/subjects`} className="underline">
                    Assign subjects
                  </a>
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Assessment Records */}
      {isFiltersComplete && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Assessment Records</CardTitle>
              <CardDescription>
                {isLoadingRecords ? (
                  "Loading..."
                ) : (
                  <>
                    {uniqueAssessments.length} assessment(s) recorded for{" "}
                    {classSubjects.find((cs) => cs.subject_id === selectedSubjectId)?.subject?.name ||
                      "this subject"}
                  </>
                )}
              </CardDescription>
            </div>
            <Button onClick={openAddDialog} disabled={!canAddAssessment || isLoadingStudents}>
              {isLoadingStudents ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add Assessment
            </Button>
          </CardHeader>
          <CardContent>
            {isLoadingRecords ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : uniqueAssessments.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
                <h3 className="mt-4 text-lg font-semibold">No assessments recorded</h3>
                <p className="text-muted-foreground">
                  {students.length === 0
                    ? "No students enrolled in this class/section."
                    : "Add class work, homework, tests, or other assessments."}
                </p>
                {canAddAssessment && (
                  <Button onClick={openAddDialog} className="mt-4">
                    <Plus className="mr-2 h-4 w-4" />
                    Add Assessment
                  </Button>
                )}
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Assessment</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead>Max Score</TableHead>
                      <TableHead>Entries</TableHead>
                      <TableHead className="w-[70px]"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {uniqueAssessments.map((title) => {
                      const assessments = caRecords.filter((ca) => ca.title === title);
                      const firstCA = assessments[0];
                      if (!firstCA) return null;

                      return (
                        <TableRow key={title}>
                          <TableCell className="font-medium">{title}</TableCell>
                          <TableCell>
                            <Badge
                              className={`${
                                ASSESSMENT_TYPE_CONFIG[firstCA.assessment_type]?.color || "bg-gray-500"
                              } text-white`}
                            >
                              {ASSESSMENT_TYPE_CONFIG[firstCA.assessment_type]?.label ||
                                firstCA.assessment_type}
                            </Badge>
                          </TableCell>
                          <TableCell suppressHydrationWarning>{format(new Date(firstCA.assessment_date), "MMM d, yyyy")}</TableCell>
                          <TableCell>{firstCA.max_score}</TableCell>
                          <TableCell>{assessments.length} students</TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => openEditDialog(title)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-destructive hover:text-destructive"
                                onClick={() => openDeleteDialog(firstCA)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Add Assessment Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Add Continuous Assessment</DialogTitle>
            <DialogDescription>
              Enter scores for a class work, homework, test, or other assessment.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-hidden flex flex-col gap-4 py-4">
            {/* Assessment Details */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Assessment Type</Label>
                <Select
                  value={formData.assessment_type}
                  onValueChange={(value) =>
                    setFormData({ ...formData, assessment_type: value as AssessmentType })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ASSESSMENT_TYPE_CONFIG).map(([key, config]) => (
                      <SelectItem key={key} value={key}>
                        {config.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Title *</Label>
                <Input
                  placeholder="e.g., Week 3 Class Test"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Date</Label>
                <Input
                  type="date"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Score</Label>
                <Input
                  type="number"
                  min={1}
                  value={formData.max_score}
                  onChange={(e) => setFormData({ ...formData, max_score: e.target.value })}
                />
              </div>
            </div>

            {/* Student Scores */}
            <div className="flex-1 overflow-hidden border rounded-md flex flex-col">
              {/* Search integrated into table */}
              <div className="border-b bg-muted/50 px-3 py-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search students by name or ID..."
                    value={studentSearch}
                    onChange={(e) => setStudentSearch(e.target.value)}
                    className="pl-8 h-9 bg-background"
                  />
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">#</TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead className="w-[100px]">Score (/{formData.max_score})</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredStudents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
                        {studentSearch ? "No students match your search" : "No students found"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredStudents.map((student, index) => (
                      <TableRow key={student.id}>
                        <TableCell className="text-muted-foreground">{index + 1}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarFallback>
                                {student.first_name[0]}
                                {student.last_name[0]}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <p className="font-medium">
                                {student.first_name} {student.last_name}
                              </p>
                              <p className="text-sm text-muted-foreground">{student.student_id}</p>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Input
                            type="number"
                            min={0}
                            max={parseFloat(formData.max_score)}
                            step={0.5}
                            value={scores[student.id] || ""}
                            onChange={(e) => {
                              const value = e.target.value;
                              const maxScore = parseFloat(formData.max_score) || 100;
                              // Allow empty value or validate against max
                              if (value === "" || parseFloat(value) <= maxScore) {
                                setScores({ ...scores, [student.id]: value });
                              } else {
                                // Clamp to max score
                                setScores({ ...scores, [student.id]: maxScore.toString() });
                              }
                            }}
                            className="w-20"
                            placeholder="-"
                          />
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateCA} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Save className="mr-2 h-4 w-4" />
              Save Assessment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Assessment</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedCA?.title}"? This will remove all scores for
              this assessment and cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteCA}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit Assessment Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Edit Assessment</DialogTitle>
            <DialogDescription>
              Update assessment details and student scores.
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-hidden flex flex-col gap-4 py-4">
            {/* Assessment Details */}
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>Type</Label>
                <Select
                  value={editFormData.assessment_type}
                  onValueChange={(value) =>
                    setEditFormData({ ...editFormData, assessment_type: value as AssessmentType })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ASSESSMENT_TYPE_CONFIG).map(([key, config]) => (
                      <SelectItem key={key} value={key}>
                        {config.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Title *</Label>
                <Input
                  placeholder="e.g., Week 3 Class Test"
                  value={editFormData.title}
                  onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Date</Label>
                <Input
                  type="date"
                  value={editFormData.date}
                  onChange={(e) => setEditFormData({ ...editFormData, date: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>Max Score</Label>
                <Input
                  type="number"
                  min="1"
                  value={editFormData.max_score}
                  onChange={(e) => setEditFormData({ ...editFormData, max_score: e.target.value })}
                />
              </div>
            </div>

            {/* Student Scores */}
            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-medium">
                  Student Scores ({editingAssessments.length} students)
                </Label>
              </div>

              <div className="flex-1 overflow-hidden flex flex-col rounded-md border">
                {/* Fixed Search Header */}
                <div className="flex items-center border-b bg-muted/50 px-3 py-2">
                  <Search className="h-4 w-4 text-muted-foreground mr-2" />
                  <Input
                    placeholder="Search students..."
                    value={editStudentSearch}
                    onChange={(e) => setEditStudentSearch(e.target.value)}
                    className="border-0 bg-transparent h-8 focus-visible:ring-0 focus-visible:ring-offset-0"
                  />
                </div>

                {/* Scrollable Table */}
                <div className="flex-1 overflow-auto">
                  <Table>
                    <TableHeader className="sticky top-0 bg-background z-10">
                      <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead>ID</TableHead>
                        <TableHead className="w-[120px]">Score</TableHead>
                      </TableRow>
                    </TableHeader>
                  <TableBody>
                    {editingAssessments
                      .filter((ca) => {
                        if (!editStudentSearch) return true;
                        const searchLower = editStudentSearch.toLowerCase();
                        return (
                          ca.student_name.toLowerCase().includes(searchLower) ||
                          ca.student_id_number.toLowerCase().includes(searchLower)
                        );
                      })
                      .map((ca) => (
                        <TableRow key={ca.id}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Avatar className="h-8 w-8">
                                <AvatarFallback className="text-xs">
                                  {ca.student_name
                                    .split(" ")
                                    .map((n) => n[0])
                                    .join("")
                                    .toUpperCase()
                                    .slice(0, 2)}
                                </AvatarFallback>
                              </Avatar>
                              <span className="font-medium">{ca.student_name}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-muted-foreground">
                            {ca.student_id_number}
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              min="0"
                              max={parseFloat(editFormData.max_score) || 100}
                              step="0.5"
                              placeholder="—"
                              className="w-20 h-8"
                              value={editScores[ca.id] || ""}
                              onChange={(e) => {
                                const value = e.target.value;
                                const maxScore = parseFloat(editFormData.max_score) || 100;
                                // Allow empty value or validate against max
                                if (value === "" || parseFloat(value) <= maxScore) {
                                  setEditScores({
                                    ...editScores,
                                    [ca.id]: value,
                                  });
                                } else {
                                  // Clamp to max score
                                  setEditScores({
                                    ...editScores,
                                    [ca.id]: maxScore.toString(),
                                  });
                                }
                              }}
                            />
                          </TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                  </Table>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateCA} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
