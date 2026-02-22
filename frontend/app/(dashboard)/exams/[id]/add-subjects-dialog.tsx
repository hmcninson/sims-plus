"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2, ArrowLeft, ArrowRight } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

import { addExamSubjects } from "@/actions/exams.action";
import { getClasses, getSubjectsForClasses } from "@/actions/academic.action";
import type { Class, ClassSection, Subject } from "@/types";

interface AddSubjectsDialogProps {
  examId: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
}

interface SubjectWithClasses {
  subject: Subject;
  classIds: string[];
}

interface ClassWithSections {
  class: Class;
  sections: ClassSection[];
}

export function AddSubjectsDialog({
  examId,
  variant = "default",
  size = "default",
}: AddSubjectsDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState<1 | 2>(1);

  // Step 1: Classes and Sections
  const [classesWithSections, setClassesWithSections] = useState<ClassWithSections[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<string[]>([]);
  const [selectedSectionIds, setSelectedSectionIds] = useState<string[]>([]);

  // Step 2: Subjects
  const [availableSubjects, setAvailableSubjects] = useState<SubjectWithClasses[]>([]);
  const [selectedSubjectIds, setSelectedSubjectIds] = useState<string[]>([]);

  // Settings
  const [maxScore, setMaxScore] = useState("100");
  const [passMark, setPassMark] = useState("50");

  // Derived: classes that have sections
  const classesWithSectionsMap = new Map(
    classesWithSections
      .filter((c) => c.sections.length > 0)
      .map((c) => [c.class.id, c.sections])
  );

  // Load classes with sections when dialog opens (single API call)
  const handleOpenChange = async (newOpen: boolean) => {
    setOpen(newOpen);
    if (newOpen && classesWithSections.length === 0) {
      setIsLoading(true);
      // Single API call with sections included
      const result = await getClasses(true);
      if (result.success && result.data) {
        const preschoolPatterns = /^(nursery|kg|kindergarten|creche|pre-school|preschool)/i;
        const nonPreschoolClasses = result.data.filter(
          (cls) => cls.level !== "preschool" && !preschoolPatterns.test(cls.name)
        );

        // Map classes with their sections (already included in response)
        const classesWithSectionsData: ClassWithSections[] = nonPreschoolClasses.map((cls) => ({
          class: cls,
          sections: cls.sections || [],
        }));

        setClassesWithSections(classesWithSectionsData);
      }
      setIsLoading(false);
    }
    if (!newOpen) {
      // Reset on close
      setStep(1);
      setSelectedClassIds([]);
      setSelectedSectionIds([]);
      setSelectedSubjectIds([]);
      setAvailableSubjects([]);
    }
  };

  const handleClassToggle = (classId: string) => {
    setSelectedClassIds((prev) => {
      if (prev.includes(classId)) {
        // Deselecting class - also remove its sections
        const classSections = classesWithSectionsMap.get(classId) || [];
        const sectionIdsToRemove = classSections.map((s) => s.id);
        setSelectedSectionIds((prevSections) =>
          prevSections.filter((id) => !sectionIdsToRemove.includes(id))
        );
        return prev.filter((id) => id !== classId);
      } else {
        return [...prev, classId];
      }
    });
  };

  const handleSectionToggle = (sectionId: string) => {
    setSelectedSectionIds((prev) =>
      prev.includes(sectionId)
        ? prev.filter((id) => id !== sectionId)
        : [...prev, sectionId]
    );
  };

  const handleSelectAllClasses = () => {
    const allClasses = classesWithSections.map((c) => c.class);
    if (selectedClassIds.length === allClasses.length) {
      setSelectedClassIds([]);
      setSelectedSectionIds([]);
    } else {
      setSelectedClassIds(allClasses.map((c) => c.id));
    }
  };

  const handleSubjectToggle = (subjectId: string) => {
    setSelectedSubjectIds((prev) =>
      prev.includes(subjectId)
        ? prev.filter((id) => id !== subjectId)
        : [...prev, subjectId]
    );
  };

  const handleSelectAllSubjects = () => {
    if (selectedSubjectIds.length === availableSubjects.length) {
      setSelectedSubjectIds([]);
    } else {
      setSelectedSubjectIds(availableSubjects.map((s) => s.subject.id));
    }
  };

  // Move to step 2: Fetch subjects for selected classes (single bulk request)
  const handleNextStep = async () => {
    if (selectedClassIds.length === 0) {
      toast.error("Please select at least one class");
      return;
    }

    setIsLoading(true);

    // Single API call to get subjects for all selected classes
    const result = await getSubjectsForClasses(selectedClassIds);

    // Build subject map from results
    const subjectMap = new Map<string, SubjectWithClasses>();
    if (result.success && result.data) {
      for (const cs of result.data) {
        if (cs.subject) {
          const existing = subjectMap.get(cs.subject.id);
          if (existing) {
            if (!existing.classIds.includes(cs.class_id)) {
              existing.classIds.push(cs.class_id);
            }
          } else {
            subjectMap.set(cs.subject.id, {
              subject: cs.subject,
              classIds: [cs.class_id],
            });
          }
        }
      }
    }

    const subjects = Array.from(subjectMap.values()).sort((a, b) =>
      a.subject.name.localeCompare(b.subject.name)
    );

    setAvailableSubjects(subjects);
    // Pre-select all subjects by default
    setSelectedSubjectIds(subjects.map((s) => s.subject.id));
    setIsLoading(false);
    setStep(2);
  };

  const handleBackStep = () => {
    setStep(1);
  };

  const handleSubmit = () => {
    if (selectedSubjectIds.length === 0) {
      toast.error("Please select at least one subject");
      return;
    }

    startTransition(async () => {
      const result = await addExamSubjects(examId, {
        class_ids: selectedClassIds,
        section_ids: selectedSectionIds.length > 0 ? selectedSectionIds : undefined,
        subject_ids: selectedSubjectIds,
        max_score: parseFloat(maxScore) || 100,
        pass_mark: parseFloat(passMark) || 50,
      });

      if (result.success) {
        toast.success(
          `Successfully added ${result.data?.length || 0} exam subjects`
        );
        setOpen(false);
        setStep(1);
        setSelectedClassIds([]);
        setSelectedSectionIds([]);
        setSelectedSubjectIds([]);
        setAvailableSubjects([]);
        router.refresh();
      } else {
        toast.error(result.error || "Failed to add subjects");
      }
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant={variant} size={size}>
          <Plus className="mr-2 h-4 w-4" />
          Add Subjects
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>
            {step === 1 ? "Step 1: Select Classes" : "Step 2: Select Subjects"}
          </DialogTitle>
          <DialogDescription>
            {step === 1
              ? "Choose which classes will take this exam."
              : "Choose which subjects to include in this exam."}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : step === 1 ? (
          // Step 1: Class and Section Selection
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Select Classes & Sections</Label>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0"
                  onClick={handleSelectAllClasses}
                >
                  {selectedClassIds.length === classesWithSections.length
                    ? "Deselect All"
                    : "Select All"}
                </Button>
              </div>
              <ScrollArea className="h-[280px] rounded-md border p-4">
                <div className="space-y-3">
                  {classesWithSections.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No classes found. Please configure classes first.
                    </p>
                  ) : (
                    classesWithSections.map(({ class: cls, sections }) => (
                      <div key={cls.id} className="space-y-2">
                        <div className="flex items-center space-x-3">
                          <Checkbox
                            id={`class-${cls.id}`}
                            checked={selectedClassIds.includes(cls.id)}
                            onCheckedChange={() => handleClassToggle(cls.id)}
                          />
                          <label
                            htmlFor={`class-${cls.id}`}
                            className="text-sm font-medium leading-none cursor-pointer"
                          >
                            {cls.name}
                            {sections.length > 0 && (
                              <span className="ml-1 text-xs text-muted-foreground">
                                ({sections.length} sections)
                              </span>
                            )}
                          </label>
                        </div>
                        {/* Show sections if class is selected and has sections */}
                        {selectedClassIds.includes(cls.id) && sections.length > 0 && (
                          <div className="ml-6 pl-4 border-l space-y-2">
                            <p className="text-xs text-muted-foreground">
                              Select specific sections (optional - leave empty for whole class):
                            </p>
                            {sections.map((section) => (
                              <div key={section.id} className="flex items-center space-x-3">
                                <Checkbox
                                  id={`section-${section.id}`}
                                  checked={selectedSectionIds.includes(section.id)}
                                  onCheckedChange={() => handleSectionToggle(section.id)}
                                />
                                <label
                                  htmlFor={`section-${section.id}`}
                                  className="text-sm leading-none cursor-pointer"
                                >
                                  {section.name}
                                </label>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
              <p className="text-xs text-muted-foreground">
                {selectedClassIds.length} classes selected
                {selectedSectionIds.length > 0 && `, ${selectedSectionIds.length} sections`}
              </p>
            </div>
          </div>
        ) : (
          // Step 2: Subject Selection
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Select Subjects</Label>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto p-0"
                  onClick={handleSelectAllSubjects}
                >
                  {selectedSubjectIds.length === availableSubjects.length
                    ? "Deselect All"
                    : "Select All"}
                </Button>
              </div>
              <ScrollArea className="h-[180px] rounded-md border p-4">
                <div className="space-y-3">
                  {availableSubjects.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No subjects found for selected classes.
                    </p>
                  ) : (
                    availableSubjects.map(({ subject, classIds }) => (
                      <div key={subject.id} className="flex items-center space-x-3">
                        <Checkbox
                          id={`subject-${subject.id}`}
                          checked={selectedSubjectIds.includes(subject.id)}
                          onCheckedChange={() => handleSubjectToggle(subject.id)}
                        />
                        <label
                          htmlFor={`subject-${subject.id}`}
                          className="text-sm font-medium leading-none cursor-pointer flex-1"
                        >
                          {subject.name}
                          <span className="ml-2 text-xs text-muted-foreground">
                            ({classIds.length} {classIds.length === 1 ? "class" : "classes"})
                          </span>
                        </label>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
              <p className="text-xs text-muted-foreground">
                {selectedSubjectIds.length} of {availableSubjects.length} subjects selected
              </p>
            </div>

            <Separator />

            {/* Score Settings */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="maxScore">Max Score</Label>
                <Input
                  id="maxScore"
                  type="number"
                  value={maxScore}
                  onChange={(e) => setMaxScore(e.target.value)}
                  min={1}
                  max={1000}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="passMark">Pass Mark</Label>
                <Input
                  id="passMark"
                  type="number"
                  value={passMark}
                  onChange={(e) => setPassMark(e.target.value)}
                  min={0}
                />
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="flex-row justify-between sm:justify-between">
          {step === 2 ? (
            <Button
              type="button"
              variant="outline"
              onClick={handleBackStep}
              disabled={isPending}
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
          ) : (
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
          )}

          {step === 1 ? (
            <Button
              type="button"
              onClick={handleNextStep}
              disabled={selectedClassIds.length === 0}
            >
              Next
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={isPending || selectedSubjectIds.length === 0}
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Adding...
                </>
              ) : (
                <>
                  <Plus className="mr-2 h-4 w-4" />
                  Add {selectedSubjectIds.length} Subjects
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
