"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { Loader2, Baby, AlertCircle } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import {
  SkillsAssessmentGrid,
  type AllAssessments,
  type AssessmentData,
} from "@/components/preschool";
import { getStudents } from "@/actions/students.action";
import {
  getSkillsByLearningArea,
  getAssessmentsByTerm,
  bulkUpdateAssessments,
} from "@/actions/preschool.action";
import type {
  Class,
  AcademicYear,
  Term,
  LearningArea,
  PreschoolRatingScale,
  Student,
  DevelopmentalSkill,
  StudentSkillAssessment,
} from "@/types";

interface AssessmentEntryProps {
  classes: Class[];
  academicYears: AcademicYear[];
  currentAcademicYear: AcademicYear | null;
  learningAreas: LearningArea[];
  ratingScale: PreschoolRatingScale | null;
}

// Learning area icons mapping
const LEARNING_AREA_ICONS: Record<string, string> = {
  SED: "🎭", // Social-Emotional Development
  LL: "📚",  // Language & Literacy
  MT: "🔢",  // Mathematical Thinking
  SE: "🔬",  // Scientific Exploration
  "PD-GM": "🏃", // Physical Development - Gross Motor
  "PD-FM": "✋", // Physical Development - Fine Motor
  CA: "🎨",  // Creative Arts
  PH: "🧼",  // Personal Hygiene
};

export function AssessmentEntry({
  classes,
  academicYears,
  currentAcademicYear,
  learningAreas,
  ratingScale,
}: AssessmentEntryProps) {
  // Selection state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedTermId, setSelectedTermId] = useState<string>("");
  const [selectedLearningAreaId, setSelectedLearningAreaId] = useState<string>("");

  // Data state
  const [students, setStudents] = useState<Student[]>([]);
  const [skills, setSkills] = useState<DevelopmentalSkill[]>([]);
  const [existingAssessments, setExistingAssessments] = useState<StudentSkillAssessment[]>([]);
  const [assessments, setAssessments] = useState<AllAssessments>({});

  // Loading state
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingSkills, setIsLoadingSkills] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Get current academic year's terms
  const currentTerms = currentAcademicYear?.terms || [];

  // Set default term if not selected
  useEffect(() => {
    if (!selectedTermId && currentTerms.length > 0) {
      // Find current term or use first one
      const currentTerm = currentTerms.find((t) => t.is_current) || currentTerms[0];
      if (currentTerm) {
        setSelectedTermId(currentTerm.id);
      }
    }
  }, [currentTerms, selectedTermId]);

  // Fetch students when class changes
  useEffect(() => {
    async function fetchStudents() {
      if (!selectedClassId) {
        setStudents([]);
        return;
      }

      setIsLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: selectedClassId,
          page_size: 100, // Get all students
        });

        if (result.success && result.data) {
          // Map StudentListItem to minimal Student fields needed for assessment
          const items = Array.isArray(result.data.items) ? result.data.items : [];
          setStudents(
            items.map((s) => ({
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
          toast.error(result.error || "Failed to fetch students");
          setStudents([]);
        }
      } catch (error) {
        toast.error("Failed to fetch students");
        setStudents([]);
      } finally {
        setIsLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [selectedClassId]);

  // Fetch skills when learning area changes
  useEffect(() => {
    async function fetchSkills() {
      if (!selectedLearningAreaId) {
        setSkills([]);
        return;
      }

      setIsLoadingSkills(true);
      try {
        const result = await getSkillsByLearningArea(selectedLearningAreaId);

        if (result.success && result.data) {
          // Ensure data is an array
          setSkills(Array.isArray(result.data) ? result.data : []);
        } else {
          toast.error(result.error || "Failed to fetch skills");
          setSkills([]);
        }
      } catch (error) {
        toast.error("Failed to fetch skills");
        setSkills([]);
      } finally {
        setIsLoadingSkills(false);
      }
    }

    fetchSkills();
  }, [selectedLearningAreaId]);

  // Fetch existing assessments when term + learning area + students are set
  useEffect(() => {
    async function fetchExistingAssessments() {
      if (!selectedTermId || !selectedLearningAreaId || students.length === 0) {
        return;
      }

      try {
        const result = await getAssessmentsByTerm(selectedTermId, selectedLearningAreaId);

        if (result.success && result.data) {
          // Create a map of student IDs for quick lookup
          const studentIds = new Set(students.map((s) => s.id));

          // Filter assessments for students in this class and store them
          const filtered = result.data.filter((a) => studentIds.has(a.student_id));
          setExistingAssessments(filtered);

          // Pre-populate assessments grid with existing data
          setAssessments((prev) => {
            const updated = { ...prev };
            filtered.forEach((assessment) => {
              if (!updated[assessment.student_id]) {
                updated[assessment.student_id] = {};
              }
              updated[assessment.student_id][assessment.skill_id] = {
                ratingId: assessment.rating_id || null,
                notes: assessment.observation_notes || "",
                isDirty: false,
              };
            });
            return updated;
          });
        }
      } catch (error) {
        // Silently fail - existing assessments are optional
      }
    }

    fetchExistingAssessments();
  }, [selectedTermId, selectedLearningAreaId, students]);

  // Initialize assessments grid when students or skills change
  useEffect(() => {
    const safeStudents = Array.isArray(students) ? students : [];
    const safeSkills = Array.isArray(skills) ? skills : [];

    if (safeStudents.length === 0 || safeSkills.length === 0) {
      return; // Don't clear assessments, just return
    }

    // Initialize empty assessments for all student-skill combinations
    // Preserve existing assessments (especially dirty ones and pre-loaded ones)
    setAssessments((prev) => {
      const newAssessments: AllAssessments = {};
      safeStudents.forEach((student) => {
        newAssessments[student.id] = {};
        safeSkills.forEach((skill) => {
          // Preserve existing assessment if it exists (from previous state or fetched data)
          const existing = prev[student.id]?.[skill.id];
          newAssessments[student.id][skill.id] = existing || {
            ratingId: null,
            notes: "",
            isDirty: false,
          };
        });
      });
      return newAssessments;
    });
  }, [students, skills]);

  // Handle assessment change
  const handleAssessmentChange = useCallback(
    (studentId: string, skillId: string, data: Partial<AssessmentData>) => {
      setAssessments((prev) => ({
        ...prev,
        [studentId]: {
          ...prev[studentId],
          [skillId]: {
            ...prev[studentId]?.[skillId],
            ...data,
          },
        },
      }));
    },
    []
  );

  // Save assessments
  const handleSave = useCallback(async () => {
    if (!selectedTermId || !currentAcademicYear) {
      toast.error("Please select a term");
      return;
    }

    setIsSaving(true);
    try {
      // Collect all dirty assessments
      const assessmentsToSave: Array<{
        studentId: string;
        assessments: Array<{
          skill_id: string;
          rating_id: string | undefined;
          observation_notes?: string;
        }>;
      }> = [];

      Object.entries(assessments).forEach(([studentId, studentAssessments]) => {
        const dirtyAssessments = Object.entries(studentAssessments)
          .filter(([_, data]) => data.isDirty && data.ratingId)
          .map(([skillId, data]) => ({
            skill_id: skillId,
            rating_id: data.ratingId || undefined,
            observation_notes: data.notes || undefined,
          }));

        if (dirtyAssessments.length > 0) {
          assessmentsToSave.push({
            studentId,
            assessments: dirtyAssessments,
          });
        }
      });

      if (assessmentsToSave.length === 0) {
        toast.info("No changes to save");
        setIsSaving(false);
        return;
      }

      // Save each student's assessments
      let totalCreated = 0;
      let totalUpdated = 0;

      for (const { studentId, assessments: studentAssessments } of assessmentsToSave) {
        const payload = {
          student_id: studentId,
          academic_year_id: currentAcademicYear.id,
          term_id: selectedTermId,
          assessments: studentAssessments,
        };

        const result = await bulkUpdateAssessments(payload);

        if (result.success && result.data) {
          totalCreated += result.data.created;
          totalUpdated += result.data.updated;
        }
      }

      // Clear dirty flags
      setAssessments((prev) => {
        const updated = { ...prev };
        Object.keys(updated).forEach((studentId) => {
          Object.keys(updated[studentId]).forEach((skillId) => {
            if (updated[studentId][skillId].isDirty) {
              updated[studentId][skillId] = {
                ...updated[studentId][skillId],
                isDirty: false,
              };
            }
          });
        });
        return updated;
      });

      toast.success(
        `Saved ${totalCreated + totalUpdated} assessments (${totalCreated} new, ${totalUpdated} updated)`
      );
    } catch (error) {
      toast.error("Failed to save assessments");
    } finally {
      setIsSaving(false);
    }
  }, [assessments, selectedTermId, currentAcademicYear]);

  // No preschool classes available
  if (classes.length === 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>No Preschool Classes</AlertTitle>
        <AlertDescription>
          There are no preschool classes (Nursery 1, Nursery 2, KG 1, KG 2) available.
          Please create preschool classes first.
        </AlertDescription>
      </Alert>
    );
  }

  // No rating scale available
  if (!ratingScale || !ratingScale.ratings || ratingScale.ratings.length === 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>No Rating Scale</AlertTitle>
        <AlertDescription>
          No preschool rating scale has been configured. Please set up a rating scale
          in Preschool Settings first.
        </AlertDescription>
      </Alert>
    );
  }

  // No learning areas available
  if (learningAreas.length === 0) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>No Learning Areas</AlertTitle>
        <AlertDescription>
          No learning areas have been configured. Please set up learning areas
          in Preschool Settings first.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Selection Controls */}
      <div className="flex flex-wrap gap-4">
        <div className="w-full sm:w-auto">
          <label className="mb-1.5 block text-sm font-medium">Class</label>
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
          <label className="mb-1.5 block text-sm font-medium">Term</label>
          <Select value={selectedTermId} onValueChange={setSelectedTermId}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="Select term..." />
            </SelectTrigger>
            <SelectContent>
              {currentTerms.map((term) => (
                <SelectItem key={term.id} value={term.id}>
                  {term.name}
                  {term.is_current && " (Current)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Learning Areas Grid */}
      {selectedClassId && selectedTermId && (
        <div>
          <h3 className="mb-3 text-sm font-medium">Learning Areas</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {learningAreas.map((area) => {
              const icon = LEARNING_AREA_ICONS[area.code] || "📋";
              const isSelected = selectedLearningAreaId === area.id;

              return (
                <Card
                  key={area.id}
                  className={cn(
                    "cursor-pointer transition-all hover:shadow-md",
                    isSelected
                      ? "border-2 border-primary bg-primary/5 shadow-md"
                      : "hover:border-primary/50"
                  )}
                  onClick={() => setSelectedLearningAreaId(area.id)}
                >
                  <CardContent className="flex flex-col items-center justify-center p-3 text-center">
                    <span className="text-2xl">{icon}</span>
                    <span
                      className="mt-1 text-xs font-medium"
                      style={{ color: area.color || undefined }}
                    >
                      {area.code}
                    </span>
                    <span className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">
                      {area.name}
                    </span>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Assessment Grid */}
      {selectedClassId && selectedTermId && selectedLearningAreaId && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-lg">
              {learningAreas.find((a) => a.id === selectedLearningAreaId)?.name ||
                "Learning Area"}{" "}
              Skills
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoadingStudents || isLoadingSkills ? (
              <div className="flex h-48 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <SkillsAssessmentGrid
                students={students}
                skills={skills}
                ratings={ratingScale.ratings || []}
                existingAssessments={existingAssessments}
                assessments={assessments}
                onAssessmentChange={handleAssessmentChange}
                onSave={handleSave}
                isSaving={isSaving}
              />
            )}
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!selectedClassId && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Baby className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">Select a Class to Begin</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a preschool class and term to start assessing students
            </p>
          </CardContent>
        </Card>
      )}

      {selectedClassId && selectedTermId && !selectedLearningAreaId && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="text-4xl">📋</div>
            <h3 className="mt-4 text-lg font-medium">Select a Learning Area</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Click on a learning area above to assess students on its developmental skills
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
