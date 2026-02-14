"use client";

import { useState, useCallback, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { MessageSquarePlus, Save, Loader2 } from "lucide-react";
import { SkillRating } from "./SkillRating";
import { cn } from "@/lib/utils";
import type {
  Student,
  DevelopmentalSkill,
  PreschoolRating,
  StudentSkillAssessment,
} from "@/types";

export interface AssessmentData {
  ratingId: string | null;
  notes: string;
  isDirty: boolean;
}

export interface StudentAssessments {
  [skillId: string]: AssessmentData;
}

export interface AllAssessments {
  [studentId: string]: StudentAssessments;
}

interface SkillsAssessmentGridProps {
  students: Student[];
  skills: DevelopmentalSkill[];
  ratings: PreschoolRating[];
  existingAssessments: StudentSkillAssessment[];
  assessments: AllAssessments;
  onAssessmentChange: (
    studentId: string,
    skillId: string,
    data: Partial<AssessmentData>
  ) => void;
  onSave: () => Promise<void>;
  isSaving: boolean;
  disabled?: boolean;
}

export function SkillsAssessmentGrid({
  students,
  skills,
  ratings,
  existingAssessments,
  assessments,
  onAssessmentChange,
  onSave,
  isSaving,
  disabled = false,
}: SkillsAssessmentGridProps) {
  // Ensure arrays are valid
  const safeStudents = Array.isArray(students) ? students : [];
  const safeSkills = Array.isArray(skills) ? skills : [];
  const safeRatings = Array.isArray(ratings) ? ratings : [];

  // Calculate progress stats
  const stats = useMemo(() => {
    let totalCells = safeStudents.length * safeSkills.length;
    let ratedCells = 0;
    let dirtyCells = 0;

    safeStudents.forEach((student) => {
      safeSkills.forEach((skill) => {
        const assessment = assessments[student.id]?.[skill.id];
        if (assessment?.ratingId) {
          ratedCells++;
        }
        if (assessment?.isDirty) {
          dirtyCells++;
        }
      });
    });

    return {
      total: totalCells,
      rated: ratedCells,
      dirty: dirtyCells,
      percentage: totalCells > 0 ? Math.round((ratedCells / totalCells) * 100) : 0,
    };
  }, [safeStudents, safeSkills, assessments]);

  // Get rating by ID for display
  const getRatingById = useCallback(
    (ratingId: string | null) => {
      if (!ratingId) return null;
      return safeRatings.find((r) => r.id === ratingId) || null;
    },
    [safeRatings]
  );

  if (safeStudents.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <p className="text-muted-foreground">No students in this class</p>
      </div>
    );
  }

  if (safeSkills.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-dashed">
        <p className="text-muted-foreground">No skills in this learning area</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Progress bar and save button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="h-2 w-32 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${stats.percentage}%` }}
              />
            </div>
            <span className="text-sm text-muted-foreground">
              {stats.rated}/{stats.total} rated ({stats.percentage}%)
            </span>
          </div>
          {stats.dirty > 0 && (
            <Badge variant="outline" className="text-amber-600">
              {stats.dirty} unsaved
            </Badge>
          )}
        </div>
        <Button
          onClick={onSave}
          disabled={isSaving || stats.dirty === 0 || disabled}
          className="gap-2"
        >
          {isSaving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save Assessments
        </Button>
      </div>

      {/* Rating legend */}
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Legend:</span>
        {safeRatings
          .sort((a, b) => a.numeric_value - b.numeric_value)
          .map((rating) => (
            <span
              key={rating.id}
              className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs"
              style={{
                borderColor: rating.color || "#9ca3af",
                color: rating.color || "#9ca3af",
              }}
            >
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: rating.color || "#9ca3af" }}
              />
              {rating.short_code} = {rating.name}
            </span>
          ))}
      </div>

      {/* Assessment table */}
      <div className="relative w-full overflow-x-auto rounded-md border">
        <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="sticky left-0 z-10 min-w-[180px] bg-background">
                  Student
                </TableHead>
                {safeSkills.map((skill) => (
                  <TableHead
                    key={skill.id}
                    className="w-[130px] min-w-[130px] max-w-[130px] text-center align-bottom p-2 h-16"
                    title={skill.description || skill.name}
                  >
                    <span className="text-xs leading-tight whitespace-normal break-words inline-block max-w-full">
                      {skill.name}
                    </span>
                  </TableHead>
                ))}
                <TableHead className="min-w-[120px] text-center">Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {safeStudents.map((student) => (
                <TableRow key={student.id}>
                  <TableCell className="sticky left-0 z-10 bg-background font-medium">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium">
                        {student.first_name?.[0]}
                        {student.last_name?.[0]}
                      </div>
                      <div>
                        <p className="text-sm">
                          {student.first_name} {student.last_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {student.student_id}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  {safeSkills.map((skill) => {
                    const assessment = assessments[student.id]?.[skill.id];
                    const currentRatingId = assessment?.ratingId || null;

                    return (
                      <TableCell
                        key={skill.id}
                        className={cn(
                          "text-center",
                          assessment?.isDirty && "bg-amber-50 dark:bg-amber-950/20"
                        )}
                      >
                        <SkillRating
                          ratings={safeRatings}
                          selectedRatingId={currentRatingId}
                          onRatingChange={(ratingId) =>
                            onAssessmentChange(student.id, skill.id, {
                              ratingId,
                              isDirty: true,
                            })
                          }
                          disabled={disabled}
                          compact
                        />
                      </TableCell>
                    );
                  })}
                  <TableCell className="text-center">
                    <NotePopover
                      studentId={student.id}
                      studentName={`${student.first_name} ${student.last_name}`}
                      notes={
                        Object.values(assessments[student.id] || {})
                          .map((a) => a.notes)
                          .filter(Boolean)
                          .join("\n") || ""
                      }
                      onNotesChange={(notes) => {
                        // Add notes to the first skill (or create a general notes field)
                        if (safeSkills.length > 0) {
                          onAssessmentChange(student.id, safeSkills[0].id, {
                            notes,
                            isDirty: true,
                          });
                        }
                      }}
                      disabled={disabled}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
      </div>
    </div>
  );
}

// Note popover component
interface NotePopoverProps {
  studentId: string;
  studentName: string;
  notes: string;
  onNotesChange: (notes: string) => void;
  disabled?: boolean;
}

function NotePopover({
  studentId,
  studentName,
  notes,
  onNotesChange,
  disabled,
}: NotePopoverProps) {
  const [localNotes, setLocalNotes] = useState(notes);
  const [isOpen, setIsOpen] = useState(false);

  const handleSave = () => {
    onNotesChange(localNotes);
    setIsOpen(false);
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant={notes ? "secondary" : "ghost"}
          size="sm"
          className={cn("h-7 gap-1", notes && "text-primary")}
          disabled={disabled}
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          {notes ? "Edit" : "Add"}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <div className="space-y-3">
          <div>
            <h4 className="font-medium">Notes for {studentName}</h4>
            <p className="text-xs text-muted-foreground">
              Add observations or comments about this student&apos;s progress.
            </p>
          </div>
          <Textarea
            value={localNotes}
            onChange={(e) => setLocalNotes(e.target.value)}
            placeholder="Enter observations..."
            rows={4}
            disabled={disabled}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={disabled}>
              Save Note
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
